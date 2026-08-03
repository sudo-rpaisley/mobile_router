"""Edit saved service records and optionally publish them to model profiles."""

from functools import wraps
from pathlib import Path
import secrets

from flask import Blueprint, current_app, jsonify, redirect, request, session, url_for

from services import model_profiles, service_records


def _error(message, status=400):
    return jsonify({"status": "error", "message": str(message)}), status


def _write_required(view):
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
            return _error("Invalid or expired form token", 400)
        return view(*args, **kwargs)

    return wrapped


def _find_inventory_key(app_module, identifier):
    normalized = app_module.normalize_mac(identifier)
    for item_key, item in app_module.device_inventory.items():
        values = {
            str(item_key),
            str(item.get("id") or ""),
            str(item.get("ip") or ""),
            str(item.get("mac") or ""),
            str(item.get("address") or ""),
        }
        if str(identifier) in values or (normalized and normalized in values):
            return item_key
    return None


def _persist_device(app_module, identifier, device):
    with app_module.device_inventory_lock:
        item_key = _find_inventory_key(app_module, identifier)
        if item_key is None:
            return None
        app_module.device_inventory[item_key] = dict(device)
        return dict(app_module.device_inventory[item_key])


def _model_database_path():
    return Path(current_app.instance_path) / "device_port_knowledge.sqlite3"


def create_service_records_blueprint(context_provider):
    del context_provider
    blueprint = Blueprint("service_records", __name__)

    @blueprint.before_app_request
    def apply_service_record_overrides():
        """Reapply manual values after a later scan refreshes detected services."""
        if request.method != "GET" or request.endpoint not in {
            "client_detail",
            "client_service_detail",
        }:
            return None
        identifier = (request.view_args or {}).get("identifier")
        if not identifier:
            return None
        import app as app_module

        device = app_module.find_inventory_device(identifier) or {}
        if not device or not device.get("service_record_overrides"):
            return None
        updated = service_records.apply_overrides(device)
        _persist_device(app_module, identifier, updated)
        return None

    @blueprint.post("/clients/<identifier>/services/<int:port>")
    @_write_required
    def update_service_record(identifier, port):
        import app as app_module

        device = app_module.find_inventory_device(identifier) or {}
        if not device:
            return _error("Device was not found in inventory", 404)
        protocol = request.form.get("protocol") or "tcp"
        clear = request.form.get("clearOverride") == "on"
        actor = (session.get("social_user") or {}).get("username") or "unknown"
        try:
            updated = service_records.update_override(
                device,
                port=port,
                protocol=protocol,
                service=request.form.get("service"),
                description=request.form.get("description"),
                notes=request.form.get("notes"),
                source_name=request.form.get("sourceName"),
                source_url=request.form.get("sourceUrl"),
                updated_by=actor,
                clear=clear,
            )
        except ValueError as exc:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return _error(exc)
            return redirect(url_for(
                "client_service_detail",
                identifier=identifier,
                port=port,
                error=str(exc),
            ))

        persisted = _persist_device(app_module, identifier, updated) or updated
        host = persisted.get("ip") or identifier
        action = "Saved service override removed" if clear else "Saved service record edited"
        app_module.append_client_timeline_event(
            host,
            action,
            f"Updated {port}/{protocol} from the saved-service editor.",
            "saved-service-editor",
        )
        app_module.record_social_audit(
            "service-record.clear" if clear else "service-record.update",
            profile_id=str(identifier),
            detail=f"port={port}; protocol={protocol}",
        )

        model_result = None
        model_status = ""
        if not clear and request.form.get("applyToModel") == "on":
            profile_id = persisted.get("model_profile_id") or persisted.get(
                "model_profile_manual_id"
            )
            if not profile_id:
                model_status = "no-profile"
            else:
                try:
                    model_result = model_profiles.add_port_rule(
                        _model_database_path(),
                        profile_id=profile_id,
                        port=port,
                        protocol=protocol,
                        service=request.form.get("service"),
                        description=request.form.get("description"),
                        classification=request.form.get("classification") or "investigate",
                        exposure=request.form.get("exposure") or "unknown",
                        authentication_expected=request.form.get("authenticationExpected") == "on",
                        encryption_expected=request.form.get("encryptionExpected") == "on",
                        risk=request.form.get("risk") or "info",
                        remediation=request.form.get("remediation"),
                        source_name=request.form.get("sourceName"),
                        source_url=request.form.get("sourceUrl"),
                        source_reliability=request.form.get("sourceReliability") or 50,
                        confidence="user-confirmed",
                        actor=actor,
                        allow_replace=request.form.get("replaceModelRule") == "on",
                    )
                    model_status = (
                        "conflict"
                        if isinstance(model_result, dict)
                        and model_result.get("status") == "conflict"
                        else "saved"
                    )
                except ValueError as exc:
                    model_status = f"error:{exc}"

        app_module.save_runtime_state("saved-service-record")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({
                "status": "success",
                "message": action,
                "device": persisted,
                "model_status": model_status,
                "model_result": model_result,
            })
        return redirect(url_for(
            "client_service_detail",
            identifier=identifier,
            port=port,
            saved="1",
            cleared="1" if clear else "",
            model=model_status,
        ))

    return blueprint
