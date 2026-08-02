"""Authenticated routes for explainable passive and active device identification."""

from functools import wraps
from pathlib import Path
import secrets

from flask import Blueprint, current_app, jsonify, request, session

from services import device_identification, port_knowledge


IDENTIFICATION_STAGES = {"passive", "safe", "deep"}


def _error(message, status=400):
    return jsonify({"status": "error", "message": str(message)}), status


def _authenticated(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = session.get("social_user") or {}
        if not user:
            return _error("Login required", 401)
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


def _passive_summary(device):
    summary = {}
    for key in (
        "discovery_methods",
        "sources",
        "interfaces",
        "protocol_counts",
        "destination_ports",
        "traffic_profile",
        "passive_analytics",
        "service_metadata",
    ):
        value = (device or {}).get(key)
        if value not in (None, "", [], {}):
            summary[key] = value
    return summary


def _persist_assessment(app_module, identifier, assessment, stage):
    now = assessment.get("assessed_at")
    updated = None
    with app_module.device_inventory_lock:
        normalized = app_module.normalize_mac(identifier)
        for key, item in app_module.device_inventory.items():
            matches = {
                str(key),
                str(item.get("id") or ""),
                str(item.get("ip") or ""),
                str(item.get("mac") or ""),
                str(item.get("address") or ""),
            }
            if str(identifier) in matches or (normalized and normalized in matches):
                item["identity_assessment"] = assessment
                item["identity_signature"] = assessment.get("identity_signature")
                item["identity_signature_tokens"] = assessment.get("signature_tokens", [])
                item["identity_identification_stage"] = stage
                item["identity_assessed_at"] = now
                if assessment.get("manufacturer"):
                    item["manufacturer"] = assessment["manufacturer"]
                if assessment.get("model"):
                    item["model"] = assessment["model"]
                    item["model_source"] = assessment.get("model_source")
                updated = dict(item)
                break
    return updated


def _persist_device(app_module, identifier, device):
    with app_module.device_inventory_lock:
        normalized = app_module.normalize_mac(identifier)
        for key, item in app_module.device_inventory.items():
            matches = {
                str(key),
                str(item.get("id") or ""),
                str(item.get("ip") or ""),
                str(item.get("mac") or ""),
                str(item.get("address") or ""),
            }
            if str(identifier) in matches or (normalized and normalized in matches):
                app_module.device_inventory[key] = dict(device)
                return dict(app_module.device_inventory[key])
    return None


def create_device_identification_blueprint(context_provider):
    del context_provider
    blueprint = Blueprint("device_identification", __name__)

    @blueprint.post("/clients/<path:identifier>/identify")
    @_authenticated
    def identify_client(identifier):
        import app as app_module

        stage = str(request.form.get("stage") or "safe").strip().lower()
        if stage not in IDENTIFICATION_STAGES:
            return _error("Choose passive, safe, or deep identification")
        user = session.get("social_user") or {}
        authorized = request.form.get("authorized") == "on"
        if stage == "deep":
            if user.get("role") != "admin":
                return _error("Administrator role required for deep identification", 403)
            if not authorized:
                return _error("Confirm authorization before running deep identification")

        device = app_module.find_inventory_device(identifier) or {}
        if not device:
            return _error("Device was not found in inventory", 404)
        device = app_module.enrich_ip_client_display_name(identifier, device)
        host = device.get("ip") or identifier
        if not device.get("ip"):
            return _error("Device identification requires a saved IP address")

        reverse_name = app_module._reverse_dns_display_name(host)
        dhcp_name = app_module._dhcp_lease_display_name(host)
        reachability = app_module.client_reachability_history(host, limit=10)
        os_hint = app_module._ttl_os_hint(reachability)
        safe_probes = {}
        deep_probe = {}

        try:
            if stage in {"safe", "deep"}:
                base = app_module.fingerprint_client_services(identifier)
                safe_probes = device_identification.supplement_service_probes(
                    device,
                    host,
                    base_fingerprints=base,
                )
            if stage == "deep":
                ports = [
                    item.get("port")
                    for item in device.get("open_port_details", [])
                    if item.get("port")
                ]
                deep_probe = device_identification.deep_device_probe(
                    host,
                    ports,
                    authorized=True,
                    snmp_community=request.form.get("snmpCommunity"),
                )
            assessment = device_identification.identify_device(
                device,
                reverse_name=reverse_name,
                dhcp_name=dhcp_name,
                os_hint=os_hint,
                safe_probes=safe_probes,
                deep_probe=deep_probe,
                passive_summary=_passive_summary(device),
            )
            model_identity = port_knowledge.extract_identity(
                device,
                safe_probes=safe_probes,
                assessment=assessment,
            )
            assessment["manufacturer"] = model_identity["manufacturer"]
            assessment["model"] = model_identity["model"]
            assessment["model_source"] = model_identity["source"]
        except ValueError as exc:
            return _error(exc)
        except Exception as exc:
            current_app.logger.exception("Device identification failed for %s", identifier)
            return _error(f"Device identification failed: {exc}", 500)

        updated = _persist_assessment(app_module, identifier, assessment, stage)
        knowledge_result = port_knowledge.process(
            Path(current_app.instance_path) / "device_port_knowledge.sqlite3",
            updated or device,
            safe_probes=safe_probes,
        )
        updated = _persist_device(
            app_module,
            identifier,
            knowledge_result["device"],
        ) or knowledge_result["device"]
        app_module.append_client_timeline_event(
            host,
            "Device identified",
            (
                f"Likely {assessment['likely_device']} with "
                f"{assessment['confidence']} confidence ({assessment['score']}/100). "
                f"Model-port knowledge applied {len(knowledge_result['applied'])} mapping(s)."
            ),
            f"device-identification:{stage}",
        )
        app_module.record_social_audit(
            "device.identify",
            profile_id=str(identifier),
            detail=(
                f"stage={stage}; likely={assessment['likely_device']}; "
                f"model={assessment.get('model') or 'unknown'}; "
                f"confidence={assessment['confidence']}; score={assessment['score']}"
            ),
        )
        app_module.save_runtime_state(f"device-identification:{stage}")
        return jsonify(
            {
                "status": "success",
                "stage": stage,
                "identification": assessment,
                "safe_probes": safe_probes,
                "deep_probe": deep_probe,
                "port_knowledge": knowledge_result,
                "device": updated,
            }
        )

    @blueprint.get("/clients/<path:identifier>/identify")
    def saved_identification(identifier):
        import app as app_module

        if not session.get("social_user"):
            return _error("Login required", 401)
        device = app_module.find_inventory_device(identifier) or {}
        if not device:
            return _error("Device was not found in inventory", 404)
        return jsonify(
            {
                "status": "success",
                "identification": device.get("identity_assessment"),
                "stage": device.get("identity_identification_stage"),
            }
        )

    return blueprint
