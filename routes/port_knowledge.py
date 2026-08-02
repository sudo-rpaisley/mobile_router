"""Authenticated routes for reusable model-specific port knowledge."""

from functools import wraps
import json
from pathlib import Path
import secrets

from flask import Blueprint, Response, current_app, jsonify, request, session

from services import port_knowledge


def _error(message, status=400):
    return jsonify({"status": "error", "message": str(message)}), status


def _database_path():
    return Path(current_app.instance_path) / "device_port_knowledge.sqlite3"


def _login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("social_user"):
            return _error("Login required", 401)
        return view(*args, **kwargs)

    return wrapped


def _write_required(admin=False):
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


def _find_inventory_key(app_module, identifier):
    normalized = app_module.normalize_mac(identifier)
    for key, item in app_module.device_inventory.items():
        values = {
            str(key),
            str(item.get("id") or ""),
            str(item.get("ip") or ""),
            str(item.get("mac") or ""),
            str(item.get("address") or ""),
        }
        if str(identifier) in values or (normalized and normalized in values):
            return key
    return None


def _persist_device(app_module, identifier, device):
    with app_module.device_inventory_lock:
        key = _find_inventory_key(app_module, identifier)
        if key is None:
            return None
        app_module.device_inventory[key] = dict(device)
        return dict(app_module.device_inventory[key])


def _device_payload(app_module, identifier):
    device = app_module.find_inventory_device(identifier) or {}
    if not device:
        raise ValueError("Device was not found in inventory")
    if not device.get("ip"):
        raise ValueError("Port knowledge requires a saved IP device")
    return device


def _knowledge_payload(path, device):
    ident = port_knowledge.identity(device)
    approved = port_knowledge.mappings(
        path,
        manufacturer=ident["manufacturer"],
        model=ident["model"],
    )
    learned = port_knowledge.candidates(
        path,
        manufacturer=ident["manufacturer"],
        model=ident["model"],
    )
    mapping_keys = {
        (int(item["port"]), item["protocol"]): item
        for item in approved
    }
    needs_application = False
    for detail in device.get("open_port_details", []):
        try:
            key = (
                int(detail.get("port")),
                str(detail.get("protocol") or "tcp").casefold(),
            )
        except (TypeError, ValueError):
            continue
        mapping = mapping_keys.get(key)
        if mapping and detail.get("knowledge_mapping_id") != mapping["id"]:
            needs_application = True
            break
    application_token = "|".join(
        [
            str(device.get("last_port_scan") or ""),
            *[
                f"{item['id']}:{item['updated_at']}"
                for item in approved
            ],
        ]
    )
    return {
        "identity": ident,
        "mappings": approved,
        "candidates": learned,
        "open_ports": device.get("open_port_details", []),
        "needs_application": needs_application,
        "application_token": application_token,
        "configured_registry_count": len(port_knowledge.configured_urls()),
    }


def create_port_knowledge_blueprint(context_provider):
    del context_provider
    blueprint = Blueprint("port_knowledge", __name__)

    @blueprint.get("/clients/<path:identifier>/port-knowledge")
    @_login_required
    def client_port_knowledge(identifier):
        import app as app_module

        try:
            device = _device_payload(app_module, identifier)
        except ValueError as exc:
            return _error(exc, 404)
        return jsonify(
            {
                "status": "success",
                "knowledge": _knowledge_payload(_database_path(), device),
            }
        )

    @blueprint.post("/clients/<path:identifier>/port-knowledge/learn")
    @_write_required()
    def learn_client_ports(identifier):
        import app as app_module
        from services import device_identification

        try:
            device = _device_payload(app_module, identifier)
            safe_probes = None
            if request.form.get("activeProbe") == "on":
                base = app_module.fingerprint_client_services(identifier)
                safe_probes = device_identification.supplement_service_probes(
                    device,
                    device["ip"],
                    base_fingerprints=base,
                )
            result = port_knowledge.process(
                _database_path(),
                device,
                safe_probes=safe_probes,
            )
        except ValueError as exc:
            return _error(exc)
        except Exception as exc:
            current_app.logger.exception("Port knowledge learning failed")
            return _error(f"Port knowledge learning failed: {exc}", 500)

        updated = _persist_device(app_module, identifier, result["device"])
        user = (session.get("social_user") or {}).get("username") or "unknown"
        app_module.append_client_timeline_event(
            device["ip"],
            "Model port knowledge updated",
            (
                f"Applied {len(result['applied'])} mapping(s), recorded "
                f"{result['learning']['observed']} candidate observation(s), and "
                f"promoted {len(result['learning']['promoted'])} repeated mapping(s)."
            ),
            "port-knowledge",
        )
        app_module.record_social_audit(
            "port-knowledge.learn",
            profile_id=str(identifier),
            detail=f"operator={user}; active_probe={bool(safe_probes)}",
        )
        app_module.save_runtime_state("port-knowledge-learn")
        return jsonify(
            {
                "status": "success",
                "result": result,
                "device": updated or result["device"],
                "knowledge": _knowledge_payload(_database_path(), updated or result["device"]),
            }
        )

    @blueprint.post("/clients/<path:identifier>/port-knowledge/mappings")
    @_write_required()
    def add_client_mapping(identifier):
        import app as app_module

        user = (session.get("social_user") or {}).get("username") or "unknown"
        try:
            device = _device_payload(app_module, identifier)
            ident = port_knowledge.identity(
                device,
                manufacturer=request.form.get("manufacturer"),
                model=request.form.get("model"),
            )
            mapping = port_knowledge.add_mapping(
                _database_path(),
                manufacturer=ident["manufacturer"],
                model=ident["model"],
                port=request.form.get("port"),
                protocol=request.form.get("protocol") or "tcp",
                service=request.form.get("service"),
                description=request.form.get("description"),
                source_name=request.form.get("sourceName") or "Manual research",
                source_url=request.form.get("sourceUrl"),
                confidence="confirmed",
                verified_by=user,
            )
            device["manufacturer"] = ident["manufacturer"] or device.get("manufacturer")
            device["model"] = ident["model"]
            applied = port_knowledge.apply(_database_path(), device)
        except ValueError as exc:
            return _error(exc)

        updated = _persist_device(app_module, identifier, applied["device"])
        app_module.append_client_timeline_event(
            device["ip"],
            "Port mapping confirmed",
            (
                f"{mapping['port']}/{mapping['protocol']} mapped to "
                f"{mapping['service']} for {mapping['model']}."
            ),
            "port-knowledge",
        )
        app_module.record_social_audit(
            "port-knowledge.mapping.add",
            profile_id=str(identifier),
            detail=(
                f"model={mapping['model']}; port={mapping['port']}/"
                f"{mapping['protocol']}; service={mapping['service']}"
            ),
        )
        app_module.save_runtime_state("port-knowledge-mapping-add")
        return jsonify(
            {
                "status": "success",
                "mapping": mapping,
                "device": updated or applied["device"],
                "knowledge": _knowledge_payload(_database_path(), updated or applied["device"]),
            }
        )

    @blueprint.post("/clients/<path:identifier>/port-knowledge/candidates/<int:candidate_id>/approve")
    @_write_required()
    def approve_client_candidate(identifier, candidate_id):
        import app as app_module

        user = (session.get("social_user") or {}).get("username") or "unknown"
        try:
            device = _device_payload(app_module, identifier)
            mapping = port_knowledge.approve(
                _database_path(),
                candidate_id,
                verified_by=user,
                source_url=request.form.get("sourceUrl"),
            )
            applied = port_knowledge.apply(_database_path(), device)
        except ValueError as exc:
            return _error(exc, 404)

        updated = _persist_device(app_module, identifier, applied["device"])
        app_module.record_social_audit(
            "port-knowledge.candidate.approve",
            profile_id=str(identifier),
            detail=f"candidate={candidate_id}; mapping={mapping['id']}",
        )
        app_module.save_runtime_state("port-knowledge-candidate-approve")
        return jsonify(
            {
                "status": "success",
                "mapping": mapping,
                "device": updated or applied["device"],
                "knowledge": _knowledge_payload(_database_path(), updated or applied["device"]),
            }
        )

    @blueprint.post("/clients/<path:identifier>/port-knowledge/mappings/<int:mapping_id>/delete")
    @_write_required(admin=True)
    def delete_client_mapping(identifier, mapping_id):
        import app as app_module

        if not port_knowledge.delete(_database_path(), mapping_id):
            return _error("Port mapping was not found", 404)
        device = _device_payload(app_module, identifier)
        applied = port_knowledge.apply(_database_path(), device)
        updated = _persist_device(app_module, identifier, applied["device"])
        app_module.record_social_audit(
            "port-knowledge.mapping.delete",
            profile_id=str(identifier),
            detail=f"mapping={mapping_id}",
        )
        app_module.save_runtime_state("port-knowledge-mapping-delete")
        return jsonify(
            {
                "status": "success",
                "knowledge": _knowledge_payload(
                    _database_path(), updated or applied["device"]
                ),
            }
        )

    @blueprint.post("/port-knowledge/import")
    @_write_required(admin=True)
    def import_port_registry():
        user = (session.get("social_user") or {}).get("username") or "unknown"
        artifact = request.files.get("registryFile")
        try:
            if artifact and artifact.filename:
                payload = json.load(artifact.stream)
            else:
                payload = json.loads(request.form.get("registryJson") or "{}")
            result = port_knowledge.import_registry(
                _database_path(),
                payload,
                source_name=request.form.get("sourceName") or "Imported registry",
                source_url=request.form.get("sourceUrl"),
                verified_by=user,
            )
        except (json.JSONDecodeError, UnicodeError, ValueError) as exc:
            return _error(exc)
        import app as app_module
        app_module.record_social_audit(
            "port-knowledge.registry.import",
            detail=f"imported={result['imported']}; errors={len(result['errors'])}",
        )
        return jsonify({"status": "success", "result": result})

    @blueprint.post("/port-knowledge/sync")
    @_write_required(admin=True)
    def sync_port_registries():
        urls = port_knowledge.configured_urls()
        if not urls:
            return _error(
                "No online registries are configured in MOBILE_ROUTER_PORT_REGISTRY_URLS"
            )
        results = port_knowledge.sync(
            _database_path(),
            urls=urls,
        )
        import app as app_module
        app_module.record_social_audit(
            "port-knowledge.registry.sync",
            detail=f"sources={len(urls)}; success={len([item for item in results if item.get('status') == 'success'])}",
        )
        return jsonify({"status": "success", "results": results})

    @blueprint.get("/port-knowledge/export.json")
    @_login_required
    def export_port_registry():
        payload = port_knowledge.export_registry(_database_path())
        return Response(
            json.dumps(payload, indent=2),
            mimetype="application/json",
            headers={
                "Content-Disposition": "attachment; filename=device-port-knowledge.json"
            },
        )

    return blueprint
