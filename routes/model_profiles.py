"""Device model profile library, drift analysis, and registry routes."""

from functools import wraps
import json
import os
from pathlib import Path
import secrets

from flask import Blueprint, Response, current_app, jsonify, render_template, request, session

from services import model_profiles


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


def _actor():
    return (session.get("social_user") or {}).get("username") or "unknown"


def _inventory_records(app_module):
    if hasattr(app_module, "inventory_records"):
        return app_module.inventory_records()
    with app_module.device_inventory_lock:
        return [dict(item) for item in app_module.device_inventory.values()]


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


def _device(app_module, identifier):
    device = app_module.find_inventory_device(identifier) or {}
    if not device:
        raise ValueError("Device was not found in inventory")
    if not device.get("ip"):
        raise ValueError("Device model profiles require a saved IP device")
    return device


def _persist_device(app_module, identifier, device):
    with app_module.device_inventory_lock:
        item_key = _find_inventory_key(app_module, identifier)
        if item_key is None:
            return None
        app_module.device_inventory[item_key] = dict(device)
        return dict(app_module.device_inventory[item_key])


def _apply_and_persist(app_module, identifier, device, alert=True):
    before = (device.get("model_port_drift") or {}).get("digest")
    result = model_profiles.apply_device_profile(_database_path(), device)
    updated = result["device"]
    drift = result["drift"]
    if (
        alert
        and drift["severity"] in {"high", "critical"}
        and drift["digest"] != before
        and drift["digest"] != device.get("model_drift_alert_digest")
    ):
        alert_device = dict(updated)
        alert_device["name"] = (
            alert_device.get("display_name")
            or alert_device.get("name")
            or alert_device.get("ip")
        )
        alert_device["model_drift_summary"] = (
            f"{len(drift['unexpected'])} unexpected, "
            f"{len(drift['missing_expected'])} missing expected, "
            f"{len(drift['deprecated'])} deprecated service(s)"
        )
        try:
            app_module.create_new_device_alert(
                alert_device,
                "model-profile-drift",
                next(iter(alert_device.get("interfaces") or []), None),
            )
        except Exception:
            current_app.logger.exception("Unable to create model drift alert")
        updated["model_drift_alert_digest"] = drift["digest"]
    persisted = _persist_device(app_module, identifier, updated) or updated
    return result, persisted


def _profile_from_form(existing=None):
    existing = existing or {}
    return {
        "manufacturer": request.form.get("manufacturer") or existing.get("manufacturer"),
        "model": request.form.get("model") if "model" in request.form else existing.get("model"),
        "family": request.form.get("family") if "family" in request.form else existing.get("family"),
        "scope": request.form.get("scope") or existing.get("scope") or "exact",
        "hardware_revision": request.form.get("hardwareRevision") if "hardwareRevision" in request.form else existing.get("hardware_revision"),
        "firmware_min": request.form.get("firmwareMin") if "firmwareMin" in request.form else existing.get("firmware_min"),
        "firmware_max": request.form.get("firmwareMax") if "firmwareMax" in request.form else existing.get("firmware_max"),
        "aliases": request.form.get("aliases") if "aliases" in request.form else existing.get("aliases"),
        "manufacturer_aliases": request.form.get("manufacturerAliases") if "manufacturerAliases" in request.form else existing.get("manufacturer_aliases"),
        "notes": request.form.get("notes") if "notes" in request.form else existing.get("notes"),
        "risk_notes": request.form.get("riskNotes") if "riskNotes" in request.form else existing.get("risk_notes"),
        "actor": _actor(),
    }


def _port_rule_from_form(profile_id):
    return {
        "profile_id": profile_id,
        "port": request.form.get("port"),
        "protocol": request.form.get("protocol") or "tcp",
        "service": request.form.get("service"),
        "description": request.form.get("description"),
        "classification": request.form.get("classification") or "expected",
        "exposure": request.form.get("exposure") or "unknown",
        "authentication_expected": request.form.get("authenticationExpected"),
        "encryption_expected": request.form.get("encryptionExpected"),
        "risk": request.form.get("risk") or "info",
        "remediation": request.form.get("remediation"),
        "hardware_revision": request.form.get("hardwareRevision"),
        "firmware_min": request.form.get("firmwareMin"),
        "firmware_max": request.form.get("firmwareMax"),
        "source_name": request.form.get("sourceName"),
        "source_url": request.form.get("sourceUrl"),
        "source_reliability": request.form.get("sourceReliability") or 50,
        "confidence": request.form.get("confidence") or "confirmed",
        "actor": _actor(),
        "allow_replace": request.form.get("replace") == "on",
    }


def create_model_profiles_blueprint(context_provider):
    blueprint = Blueprint("model_profiles", __name__)

    @blueprint.get("/models")
    def model_library_page():
        return render_template(
            "model_profiles.html",
            title="Device Model Library",
            **context_provider(),
        )

    @blueprint.get("/models/<int:profile_id>")
    def model_profile_page(profile_id):
        try:
            profile = model_profiles.profile_detail(_database_path(), profile_id)
        except ValueError:
            profile = None
        return render_template(
            "model_profile_detail.html",
            title=(
                f"Model {profile['manufacturer']} {profile['model'] or profile['family']}"
                if profile
                else "Model Profile Not Found"
            ),
            profile_id=profile_id,
            profile=profile,
            **context_provider(),
        ), (200 if profile else 404)

    @blueprint.get("/api/model-profiles")
    @_login_required
    def list_model_profiles():
        profiles = model_profiles.list_profiles(
            _database_path(),
            query=request.args.get("q") or "",
            scope=request.args.get("scope") or "",
        )
        return jsonify({"status": "success", "profiles": profiles})

    @blueprint.post("/api/model-profiles")
    @_write_required()
    def create_model_profile():
        try:
            profile = model_profiles.upsert_profile(
                _database_path(), **_profile_from_form()
            )
        except ValueError as exc:
            return _error(exc)
        import app as app_module
        app_module.record_social_audit(
            "model-profile.create",
            detail=f"profile={profile['id']}; manufacturer={profile['manufacturer']}; model={profile['model']}",
        )
        return jsonify({"status": "success", "profile": profile})

    @blueprint.get("/api/model-profiles/<int:profile_id>")
    @_login_required
    def get_model_profile(profile_id):
        try:
            profile = model_profiles.profile_detail(_database_path(), profile_id)
        except ValueError as exc:
            return _error(exc, 404)
        return jsonify(
            {
                "status": "success",
                "profile": profile,
                "history": model_profiles.revision_history(_database_path(), profile_id),
            }
        )

    @blueprint.post("/api/model-profiles/<int:profile_id>")
    @_write_required()
    def update_model_profile(profile_id):
        try:
            existing = model_profiles.profile_detail(_database_path(), profile_id)
            profile = model_profiles.upsert_profile(
                _database_path(), **_profile_from_form(existing)
            )
        except ValueError as exc:
            return _error(exc, 404)
        return jsonify({"status": "success", "profile": profile})

    @blueprint.post("/api/model-profiles/<int:profile_id>/ports")
    @_write_required()
    def add_model_port_rule(profile_id):
        try:
            result = model_profiles.add_port_rule(
                _database_path(), **_port_rule_from_form(profile_id)
            )
            profile = model_profiles.profile_detail(_database_path(), profile_id)
        except ValueError as exc:
            return _error(exc)
        return jsonify(
            {
                "status": "conflict" if result.get("status") == "conflict" else "success",
                "result": result,
                "profile": profile,
            }
        ), (409 if result.get("status") == "conflict" else 200)

    @blueprint.post("/api/model-profiles/<int:profile_id>/ports/<int:rule_id>/delete")
    @_write_required(admin=True)
    def delete_model_port_rule(profile_id, rule_id):
        if not model_profiles.delete_port_rule(
            _database_path(), profile_id, rule_id, actor=_actor()
        ):
            return _error("Model port rule was not found", 404)
        return jsonify(
            {
                "status": "success",
                "profile": model_profiles.profile_detail(_database_path(), profile_id),
            }
        )

    @blueprint.get("/api/model-profiles/<int:profile_id>/fleet")
    @_login_required
    def model_profile_fleet(profile_id):
        import app as app_module
        try:
            fleet = model_profiles.fleet_summary(
                _database_path(), _inventory_records(app_module), profile_id
            )
        except ValueError as exc:
            return _error(exc, 404)
        return jsonify({"status": "success", "fleet": fleet})

    @blueprint.get("/api/model-profiles/<int:profile_id>/history")
    @_login_required
    def model_profile_history(profile_id):
        return jsonify(
            {
                "status": "success",
                "history": model_profiles.revision_history(_database_path(), profile_id),
            }
        )

    @blueprint.post("/api/model-profiles/<int:profile_id>/rollback/<int:revision>")
    @_write_required(admin=True)
    def rollback_model_profile(profile_id, revision):
        try:
            profile = model_profiles.rollback(
                _database_path(),
                profile_id,
                revision,
                actor=_actor(),
                note=request.form.get("note"),
            )
        except ValueError as exc:
            return _error(exc, 404)
        return jsonify({"status": "success", "profile": profile})

    @blueprint.get("/api/model-profile-conflicts")
    @_login_required
    def list_model_profile_conflicts():
        return jsonify(
            {
                "status": "success",
                "conflicts": model_profiles.conflicts(
                    _database_path(),
                    profile_id=request.args.get("profileId"),
                    status=request.args.get("status") or "open",
                ),
            }
        )

    @blueprint.post("/api/model-profile-conflicts/<int:conflict_id>/resolve")
    @_write_required(admin=True)
    def resolve_model_profile_conflict(conflict_id):
        try:
            profile = model_profiles.resolve_conflict(
                _database_path(),
                conflict_id,
                request.form.get("choice"),
                actor=_actor(),
                note=request.form.get("note"),
            )
        except ValueError as exc:
            return _error(exc, 404)
        return jsonify({"status": "success", "profile": profile})

    @blueprint.get("/api/model-profiles/<int:profile_id>/contribution.json")
    @_login_required
    def export_model_contribution(profile_id):
        import app as app_module
        try:
            payload = model_profiles.contribution_payload(
                _database_path(), profile_id, _inventory_records(app_module)
            )
        except ValueError as exc:
            return _error(exc, 404)
        return Response(
            json.dumps(payload, indent=2),
            mimetype="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=model-profile-{profile_id}-contribution.json"
            },
        )

    @blueprint.get("/api/model-registry/export.json")
    @_login_required
    def export_model_registry():
        signing_key = os.environ.get("MOBILE_ROUTER_MODEL_REGISTRY_SIGNING_KEY")
        payload = model_profiles.export_registry(
            _database_path(),
            publisher=os.environ.get("MOBILE_ROUTER_MODEL_REGISTRY_PUBLISHER") or _actor(),
            version=request.args.get("version") or "",
            signing_key=signing_key,
        )
        return Response(
            json.dumps(payload, indent=2),
            mimetype="application/json",
            headers={
                "Content-Disposition": "attachment; filename=device-model-registry.json"
            },
        )

    @blueprint.post("/api/model-registry/preview")
    @_write_required(admin=True)
    def preview_model_registry():
        try:
            payload = json.loads(request.form.get("registryJson") or "{}")
            verification = model_profiles.verify_registry(
                payload,
                require_signature=request.form.get("requireSignature") == "on",
            )
        except (json.JSONDecodeError, ValueError) as exc:
            return _error(exc)
        return jsonify(
            {
                "status": "success",
                "verification": verification,
                "profiles": [
                    {
                        "manufacturer": item.get("manufacturer"),
                        "model": item.get("model"),
                        "family": item.get("family"),
                        "scope": item.get("scope"),
                        "port_count": len(item.get("ports") or []),
                    }
                    for item in payload.get("profiles") or []
                ],
            }
        )

    @blueprint.post("/api/model-registry/import")
    @_write_required(admin=True)
    def import_model_registry():
        artifact = request.files.get("registryFile")
        try:
            if artifact and artifact.filename:
                payload = json.load(artifact.stream)
            else:
                payload = json.loads(request.form.get("registryJson") or "{}")
            result = model_profiles.import_registry(
                _database_path(),
                payload,
                actor=_actor(),
                source_url=request.form.get("sourceUrl"),
                require_signature=request.form.get("requireSignature") == "on",
            )
        except (json.JSONDecodeError, UnicodeError, ValueError) as exc:
            return _error(exc)
        return jsonify({"status": "success", "result": result})

    @blueprint.post("/api/model-registry/sync")
    @_write_required(admin=True)
    def sync_model_registries():
        urls = model_profiles.configured_registry_urls()
        if not urls:
            return _error(
                "No model registries are configured in MOBILE_ROUTER_MODEL_REGISTRY_URLS"
            )
        results = model_profiles.sync_registries(
            _database_path(),
            urls=urls,
            require_signature=request.form.get("allowUnsigned") != "on",
        )
        return jsonify({"status": "success", "results": results})

    @blueprint.get("/api/model-registry/history")
    @_login_required
    def model_registry_history():
        return jsonify(
            {
                "status": "success",
                "imports": model_profiles.registry_import_history(_database_path()),
            }
        )

    @blueprint.get("/clients/<path:identifier>/model-profile")
    @_login_required
    def client_model_profile(identifier):
        import app as app_module
        try:
            device = _device(app_module, identifier)
            result, persisted = _apply_and_persist(
                app_module, identifier, device, alert=False
            )
            model_profiles.record_observations(_database_path(), persisted)
        except ValueError as exc:
            return _error(exc, 404)
        return jsonify(
            {
                "status": "success",
                "result": result,
                "device": persisted,
            }
        )

    @blueprint.post("/clients/<path:identifier>/model-profile/apply")
    @_write_required()
    def apply_client_model_profile(identifier):
        import app as app_module
        try:
            device = _device(app_module, identifier)
            result, persisted = _apply_and_persist(
                app_module, identifier, device, alert=True
            )
            observations = model_profiles.record_observations(
                _database_path(), persisted
            )
        except ValueError as exc:
            return _error(exc, 404)
        app_module.append_client_timeline_event(
            device["ip"],
            "Model profile assessed",
            (
                f"Matched {len(result['profiles'])} profile layer(s); "
                f"drift severity {result['drift']['severity']} "
                f"({result['drift']['score']}/100)."
            ),
            "model-profile",
        )
        app_module.save_runtime_state("model-profile-apply")
        return jsonify(
            {
                "status": "success",
                "result": result,
                "device": persisted,
                "observations": observations,
            }
        )

    @blueprint.post("/clients/<path:identifier>/model-profile/assign")
    @_write_required()
    def assign_client_model_profile(identifier):
        import app as app_module
        try:
            device = _device(app_module, identifier)
            profile_id = int(request.form.get("profileId"))
            model_profiles.profile_detail(_database_path(), profile_id)
        except (TypeError, ValueError) as exc:
            return _error(exc)
        device["model_profile_manual_id"] = profile_id
        result, persisted = _apply_and_persist(
            app_module, identifier, device, alert=False
        )
        app_module.save_runtime_state("model-profile-assignment")
        return jsonify({"status": "success", "result": result, "device": persisted})

    @blueprint.post("/clients/<path:identifier>/model-profile/override")
    @_write_required()
    def override_client_port(identifier):
        import app as app_module
        try:
            device = _device(app_module, identifier)
            updated = model_profiles.set_device_override(
                device,
                port=request.form.get("port"),
                protocol=request.form.get("protocol") or "tcp",
                service=request.form.get("service"),
                classification=request.form.get("classification") or "local-configuration",
                description=request.form.get("description"),
                risk=request.form.get("risk") or "info",
                remediation=request.form.get("remediation"),
            )
            result, persisted = _apply_and_persist(
                app_module, identifier, updated, alert=False
            )
        except ValueError as exc:
            return _error(exc)
        app_module.save_runtime_state("model-profile-device-override")
        return jsonify({"status": "success", "result": result, "device": persisted})

    @blueprint.post("/clients/<path:identifier>/model-profile/investigate")
    @_write_required()
    def investigate_client_port(identifier):
        import app as app_module
        from services import device_identification

        try:
            device = _device(app_module, identifier)
            safe_probes = None
            if request.form.get("activeProbe") == "on":
                base = app_module.fingerprint_client_services(identifier)
                safe_probes = device_identification.supplement_service_probes(
                    device,
                    device["ip"],
                    base_fingerprints=base,
                )
            peers = [
                item
                for item in _inventory_records(app_module)
                if item.get("model") == device.get("model")
                and item.get("id") != device.get("id")
            ]
            investigation = model_profiles.investigate_port(
                _database_path(),
                device,
                request.form.get("port"),
                request.form.get("protocol") or "tcp",
                safe_probes=safe_probes,
                peers=peers,
            )
        except ValueError as exc:
            return _error(exc)
        return jsonify({"status": "success", "investigation": investigation})

    return blueprint
