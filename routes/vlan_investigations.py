"""VLAN inventory, routed investigation, segmentation, and probe routes."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps
import ipaddress
import json
from pathlib import Path
import secrets
import socket
import time

from flask import Blueprint, Response, current_app, jsonify, render_template, request, session

from services import vlan_investigations as vlan_service


def _database_path():
    return Path(current_app.instance_path) / "vlan_investigations.sqlite3"


def _error(message, status=400):
    return jsonify({"status": "error", "message": str(message)}), status


def _login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("social_user"):
            return _error("Login required", 401)
        return view(*args, **kwargs)

    return wrapped


def _write_required(admin=True):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = session.get("social_user") or {}
            if not user:
                return _error("Login required", 401)
            if admin and user.get("role") != "admin":
                return _error("Administrator role required", 403)
            expected = str(session.get("social_csrf_token") or "")
            supplied = str(
                request.form.get("csrf_token")
                or request.headers.get("X-CSRF-Token")
                or ""
            )
            if not expected or not secrets.compare_digest(expected, supplied):
                return _error("Invalid CSRF token", 400)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def _actor():
    return (session.get("social_user") or {}).get("username") or "unknown"


def _inventory_records(app_module):
    return app_module.inventory_records() if hasattr(app_module, "inventory_records") else []


def _persist_vlan_assignments(app_module):
    changed = 0
    with app_module.device_inventory_lock:
        for key, original in list(app_module.device_inventory.items()):
            decorated = vlan_service.decorate_device(_database_path(), original)
            vlan_fields = {
                name: decorated.get(name)
                for name in (
                    "vlan_id", "vlan_tag", "vlan_name", "vlan_subnet", "vlan_gateway",
                    "vlan_interface", "vlan_label", "vlan_assignment_source", "vlan_confidence",
                )
                if decorated.get(name) not in (None, "")
            }
            if any(original.get(name) != value for name, value in vlan_fields.items()):
                updated = dict(original)
                updated.update(vlan_fields)
                app_module.device_inventory[key] = updated
                changed += 1
    if changed:
        app_module.save_runtime_state("vlan-assignments")
    return changed


def _record_devices(app_module, vlan, devices, source):
    normalized = []
    for record in devices or []:
        if not isinstance(record, dict):
            continue
        item = dict(record)
        if not item.get("ip") and not item.get("mac"):
            continue
        item.update(
            vlan_id=vlan["id"],
            vlan_tag=vlan.get("tag"),
            vlan_name=vlan["name"],
            vlan_subnet=vlan["subnet"],
            vlan_gateway=vlan.get("gateway"),
            vlan_interface=vlan.get("interface_name"),
            vlan_label=vlan["label"],
            vlan_assignment_source=source,
            vlan_confidence="high",
        )
        normalized.append(item)
    if normalized:
        app_module.record_inventory_devices(
            normalized,
            source,
            vlan.get("interface_name") or None,
        )
        _persist_vlan_assignments(app_module)
    return normalized


def _scan_host(app_module, host):
    try:
        result = app_module.run_ping_check(str(host), count=1, timeout=1)
    except Exception as exc:  # Individual hosts must not abort the bounded investigation.
        return {
            "host": str(host),
            "reachable": False,
            "packet_loss_percent": 100.0,
            "latency": {},
            "output": str(exc),
            "checked_at": time.time(),
        }
    return result


def _reverse_name(address):
    try:
        return socket.gethostbyaddr(str(address))[0]
    except (OSError, socket.herror, socket.gaierror):
        return ""


def _routed_investigation(app_module, vlan, ports):
    network = vlan_service.bounded_investigation_network(vlan["subnet"])
    hosts = list(network.hosts())
    started = time.time()
    results = []
    workers = min(32, max(1, len(hosts)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="vlan-ping") as executor:
        futures = {executor.submit(_scan_host, app_module, host): str(host) for host in hosts}
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: ipaddress.ip_address(item["host"]))

    reachable = [item for item in results if item.get("reachable")]
    for item in reachable:
        item["hostname"] = _reverse_name(item["host"])
        item["services"] = vlan_service.safe_tcp_check(
            item["host"], ports, timeout=0.35, source_ip=vlan.get("source_ip") or None
        ) if ports else []

    route = app_module.build_route_diagnostics(
        vlan.get("gateway") or (str(hosts[0]) if hosts else None)
    )
    devices = [
        {
            "ip": item["host"],
            "hostname": item.get("hostname"),
            "name": item.get("hostname"),
            "open_ports": [probe["port"] for probe in item.get("services", []) if probe.get("open")],
            "open_port_details": [
                {
                    "port": probe["port"],
                    "service": "Detected TCP service",
                    "description": "Port accepted a bounded VLAN investigation connection",
                }
                for probe in item.get("services", []) if probe.get("open")
            ],
        }
        for item in reachable
    ]
    recorded = _record_devices(app_module, vlan, devices, "vlan-routed-investigation")
    summary = {
        "total_hosts": len(results),
        "reachable_hosts": len(reachable),
        "unreachable_hosts": len(results) - len(reachable),
        "selected_ports": ports,
        "recorded_devices": len(recorded),
        "visibility": "routed",
        "duration_seconds": round(time.time() - started, 2),
    }
    return route, results, summary


def _import_pfsense(app_module, payload):
    parsed = vlan_service.parse_pfsense_payload(payload)
    saved = []
    existing = vlan_service.list_vlans(_database_path())
    for candidate in parsed["vlans"]:
        match = next(
            (
                item for item in existing
                if item["subnet"] == candidate["subnet"]
                or (
                    candidate.get("tag") is not None
                    and item.get("tag") is not None
                    and int(item["tag"]) == int(candidate["tag"])
                )
            ),
            None,
        )
        saved_item = vlan_service.save_vlan(
            _database_path(), candidate, vlan_id=match["id"] if match else None
        )
        saved.append(saved_item)
        existing = vlan_service.list_vlans(_database_path())

    devices = []
    for record in parsed["devices"]:
        vlan = None
        raw_tag = record.get("vlan_tag")
        if raw_tag not in (None, ""):
            vlan = next(
                (item for item in saved if item.get("tag") is not None and str(item["tag"]) == str(raw_tag)),
                None,
            )
        if vlan is None and record.get("ip"):
            vlan = vlan_service.vlan_for_ip(_database_path(), record["ip"])
        if vlan:
            devices.extend(_record_devices(app_module, vlan, [record], "pfsense-import"))
        else:
            devices.append(record)
    if devices:
        app_module.record_inventory_devices(devices, "pfsense-import")
        _persist_vlan_assignments(app_module)
    return {"vlans": saved, "devices": devices}


def create_vlan_investigations_blueprint(context_provider):
    blueprint = Blueprint("vlan_investigations", __name__)

    @blueprint.get("/vlans")
    @_login_required
    def vlan_index():
        import app as app_module

        _persist_vlan_assignments(app_module)
        vlans = vlan_service.list_vlans(_database_path())
        devices = vlan_service.decorate_devices(_database_path(), _inventory_records(app_module))
        counts = {item["id"]: 0 for item in vlans}
        for device in devices:
            if device.get("vlan_id") in counts:
                counts[device["vlan_id"]] += 1
        return render_template(
            "vlans.html",
            title="VLAN Investigations",
            vlans=vlans,
            device_counts=counts,
            integrations=vlan_service.list_integrations(_database_path()),
            probes=vlan_service.list_remote_probes(_database_path()),
            csrf_token=session.get("social_csrf_token"),
            **context_provider(),
        )

    @blueprint.post("/vlans")
    @_write_required(admin=True)
    def create_vlan():
        import app as app_module

        try:
            vlan = vlan_service.save_vlan(_database_path(), request.form)
            changed = _persist_vlan_assignments(app_module)
        except ValueError as exc:
            return _error(exc)
        app_module.record_social_audit(
            "vlan.create", detail=f"{vlan['label']} ({vlan['subnet']})"
        )
        return jsonify({"status": "success", "vlan": vlan, "assigned_devices": changed})

    @blueprint.get("/vlans/<vlan_id>")
    @_login_required
    def vlan_detail(vlan_id):
        import app as app_module

        vlan = vlan_service.get_vlan(_database_path(), vlan_id)
        if not vlan:
            return render_template(
                "vlan_detail.html", title="VLAN not found", vlan=None, **context_provider()
            ), 404
        devices = [
            item for item in vlan_service.decorate_devices(_database_path(), _inventory_records(app_module))
            if item.get("vlan_id") == vlan_id
        ]
        return render_template(
            "vlan_detail.html",
            title=vlan["label"],
            vlan=vlan,
            devices=devices,
            investigations=vlan_service.list_investigations(_database_path(), vlan_id),
            matrix=vlan_service.segmentation_matrix(_database_path()),
            all_vlans=vlan_service.list_vlans(_database_path()),
            integrations=vlan_service.list_integrations(_database_path()),
            probes=vlan_service.list_remote_probes(_database_path(), vlan_id=vlan_id),
            csrf_token=session.get("social_csrf_token"),
            **context_provider(),
        )

    @blueprint.post("/vlans/<vlan_id>/update")
    @_write_required(admin=True)
    def update_vlan(vlan_id):
        import app as app_module

        try:
            vlan = vlan_service.save_vlan(_database_path(), request.form, vlan_id=vlan_id)
            changed = _persist_vlan_assignments(app_module)
        except ValueError as exc:
            return _error(exc)
        app_module.record_social_audit("vlan.update", detail=vlan["label"])
        return jsonify({"status": "success", "vlan": vlan, "assigned_devices": changed})

    @blueprint.post("/vlans/<vlan_id>/delete")
    @_write_required(admin=True)
    def delete_vlan(vlan_id):
        import app as app_module

        vlan = vlan_service.get_vlan(_database_path(), vlan_id)
        if not vlan_service.delete_vlan(_database_path(), vlan_id):
            return _error("VLAN definition was not found", 404)
        app_module.record_social_audit(
            "vlan.delete", detail=(vlan or {}).get("label") or vlan_id
        )
        return jsonify({"status": "success", "message": "VLAN definition deleted"})

    @blueprint.post("/vlans/<vlan_id>/investigate")
    @_write_required(admin=True)
    def investigate_vlan(vlan_id):
        import app as app_module

        vlan = vlan_service.get_vlan(_database_path(), vlan_id)
        if not vlan:
            return _error("VLAN definition was not found", 404)
        if request.form.get("authorised") != "on":
            return _error("Confirm that this routed VLAN investigation is authorised")
        try:
            ports = vlan_service.parse_ports(request.form.get("ports"))
            route, hosts, summary = _routed_investigation(app_module, vlan, ports)
            investigation = vlan_service.save_investigation(
                _database_path(), vlan_id, "routed", "complete", route, hosts, summary
            )
        except ValueError as exc:
            return _error(exc)
        app_module.record_social_audit(
            "vlan.investigate",
            detail=f"{vlan['label']}: {summary['reachable_hosts']}/{summary['total_hosts']} reachable",
        )
        return jsonify({"status": "success", "investigation": investigation})

    @blueprint.post("/vlans/segmentation-rules")
    @_write_required(admin=True)
    def create_segmentation_rule():
        import app as app_module

        try:
            rule = vlan_service.save_segmentation_rule(_database_path(), request.form)
        except ValueError as exc:
            return _error(exc)
        app_module.record_social_audit("vlan.segmentation.create", detail=rule["id"])
        return jsonify({"status": "success", "rule": rule})

    @blueprint.post("/vlans/segmentation-rules/<rule_id>/test")
    @_write_required(admin=True)
    def test_segmentation_rule(rule_id):
        import app as app_module

        if request.form.get("authorised") != "on":
            return _error("Confirm that this segmentation test is authorised")
        rule = vlan_service.get_segmentation_rule(_database_path(), rule_id)
        if not rule:
            return _error("Segmentation rule was not found", 404)
        if rule.get("source_probe_id"):
            return _error("This rule is assigned to a remote probe and cannot be run from the main host", 409)
        source_vlan = vlan_service.get_vlan(_database_path(), rule["source_vlan_id"])
        started = time.monotonic()
        detail = ""
        try:
            if rule["protocol"] == "tcp":
                result = vlan_service.safe_tcp_check(
                    rule["destination"], [rule["port"]], timeout=1.0,
                    source_ip=(source_vlan or {}).get("source_ip") or None,
                )[0]
                observed = "allow" if result["open"] else "block"
                latency_ms = result["latency_ms"]
                detail = result["detail"]
            elif rule["protocol"] == "icmp":
                ping = app_module.run_ping_check(rule["destination"], count=1, timeout=2)
                observed = "allow" if ping.get("reachable") else "block"
                latency_ms = (ping.get("latency") or {}).get("avg_ms")
                detail = ping.get("output") or "ICMP check completed"
            else:
                observed = "error"
                latency_ms = round((time.monotonic() - started) * 1000, 2)
                detail = "UDP policy cannot be proven reliably from the main host; use a remote probe or protocol-specific check"
        except Exception as exc:
            observed = "error"
            latency_ms = round((time.monotonic() - started) * 1000, 2)
            detail = str(exc)
        source = (
            f"main-host via source {source_vlan.get('source_ip')}"
            if source_vlan and source_vlan.get("source_ip")
            else "main-host routed perspective"
        )
        result = vlan_service.record_segmentation_result(
            _database_path(), rule_id, observed, source, detail, latency_ms
        )
        app_module.record_social_audit(
            "vlan.segmentation.test", detail=f"{rule_id}:{observed}"
        )
        return jsonify({"status": "success", "result": result})

    @blueprint.post("/vlans/pfsense/integrations")
    @_write_required(admin=True)
    def create_pfsense_integration():
        import app as app_module

        try:
            integration = vlan_service.save_integration(_database_path(), request.form)
        except ValueError as exc:
            return _error(exc)
        app_module.record_social_audit(
            "vlan.pfsense.configure", detail=integration["name"]
        )
        return jsonify({"status": "success", "integration": integration})

    @blueprint.post("/vlans/pfsense/import")
    @_write_required(admin=True)
    def import_pfsense_json():
        import app as app_module

        artifact = request.files.get("pfsense_file")
        try:
            if artifact and artifact.filename:
                data = artifact.stream.read(vlan_service.MAX_IMPORT_BYTES + 1)
                if len(data) > vlan_service.MAX_IMPORT_BYTES:
                    raise ValueError("pfSense import exceeded the 2 MiB safety limit")
                payload = json.loads(data.decode("utf-8"))
            else:
                payload = request.get_json(silent=True) or json.loads(
                    request.form.get("pfsense_json") or "{}"
                )
            result = _import_pfsense(app_module, payload)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            return _error(exc)
        app_module.record_social_audit(
            "vlan.pfsense.import",
            detail=f"{len(result['vlans'])} VLANs, {len(result['devices'])} devices",
        )
        return jsonify({"status": "success", **result})

    @blueprint.post("/vlans/pfsense/integrations/<integration_id>/sync")
    @_write_required(admin=True)
    def sync_pfsense_integration(integration_id):
        import app as app_module

        integration = vlan_service.get_integration(_database_path(), integration_id)
        if not integration:
            return _error("pfSense integration was not found", 404)
        try:
            payload = vlan_service.fetch_integration_payload(integration)
            result = _import_pfsense(app_module, payload)
            vlan_service.update_integration_status(
                _database_path(), integration_id,
                f"Imported {len(result['vlans'])} VLANs and {len(result['devices'])} devices",
            )
        except Exception as exc:
            vlan_service.update_integration_status(
                _database_path(), integration_id, f"Sync failed: {exc}"
            )
            return _error(exc, 502)
        app_module.record_social_audit("vlan.pfsense.sync", detail=integration["name"])
        return jsonify({"status": "success", **result})

    @blueprint.post("/vlans/probes")
    @_write_required(admin=True)
    def create_remote_probe():
        import app as app_module

        try:
            probe = vlan_service.save_remote_probe(_database_path(), request.form)
        except ValueError as exc:
            return _error(exc)
        app_module.record_social_audit("vlan.probe.create", detail=probe["name"])
        return jsonify({"status": "success", "probe": probe})

    @blueprint.get("/vlans/probes/<probe_id>/config.json")
    @_login_required
    def remote_probe_config(probe_id):
        probe = vlan_service.get_remote_probe(_database_path(), probe_id)
        if not probe:
            return _error("Remote probe was not found", 404)
        vlan = vlan_service.get_vlan(_database_path(), probe["vlan_id"])
        return jsonify(
            {
                "schema": "mobile-router-vlan-probe-v1",
                "probe_id": probe["id"],
                "name": probe["name"],
                "vlan": {"id": vlan["id"], "label": vlan["label"], "subnet": vlan["subnet"]},
                "server_ingest_path": f"/api/v1/vlan-probes/{probe['id']}/observations",
                "secret_environment_variable": probe["secret_env"],
                "agent_script": "scripts/vlan_probe_agent.py",
            }
        )

    @blueprint.post("/api/v1/vlan-probes/<probe_id>/observations")
    def ingest_remote_probe(probe_id):
        import app as app_module

        body = request.get_data(cache=False)
        try:
            probe, payload = vlan_service.verify_probe_submission(
                _database_path(), probe_id, body,
                request.headers.get("X-Probe-Timestamp"),
                request.headers.get("X-Probe-Nonce"),
                request.headers.get("X-Probe-Signature"),
            )
            vlan = vlan_service.get_vlan(_database_path(), probe["vlan_id"])
            devices = _record_devices(
                app_module, vlan, payload.get("devices") or [], "vlan-remote-probe"
            )
            segmentation_results = []
            for observation in payload.get("segmentation_results") or []:
                segmentation_results.append(
                    vlan_service.record_segmentation_result(
                        _database_path(), observation.get("rule_id"),
                        observation.get("observed"), f"remote-probe:{probe['name']}",
                        observation.get("detail") or "", observation.get("latency_ms"),
                    )
                )
            investigation = vlan_service.save_investigation(
                _database_path(), vlan["id"], "remote-agent", "complete",
                payload.get("route") or {}, payload.get("hosts") or [],
                {
                    "recorded_devices": len(devices),
                    "segmentation_results": len(segmentation_results),
                    "visibility": "local-layer-2",
                    "probe": probe["name"],
                },
            )
        except ValueError as exc:
            return _error(exc, 401)
        return jsonify(
            {
                "status": "success",
                "recorded_devices": len(devices),
                "segmentation_results": len(segmentation_results),
                "investigation_id": investigation["id"],
            }
        )

    @blueprint.get("/vlans/export.json")
    @_login_required
    def vlan_export():
        return jsonify(
            {
                "schema": "mobile-router-vlan-investigations-v1",
                "exported_at": time.time(),
                "vlans": vlan_service.list_vlans(_database_path()),
                "segmentation_rules": vlan_service.list_segmentation_rules(_database_path()),
                "integrations": [
                    {
                        key: value for key, value in item.items()
                        if key not in {"token_configured"}
                    }
                    for item in vlan_service.list_integrations(_database_path())
                ],
                "remote_probes": [
                    {
                        key: value for key, value in item.items()
                        if key not in {"secret_configured"}
                    }
                    for item in vlan_service.list_remote_probes(_database_path())
                ],
            }
        )

    return blueprint
