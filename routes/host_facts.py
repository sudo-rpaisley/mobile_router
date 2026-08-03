"""Host facts and capabilities workspace routes."""

from functools import wraps
from pathlib import Path
import secrets
import time

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from services import host_facts


def _error(message, status=400):
    return jsonify({"status": "error", "message": str(message)}), status


def _login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("social_user"):
            return _error("Login required", 401)
        return view(*args, **kwargs)

    return wrapped


def _write_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("social_user"):
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


def _credential_path():
    return Path(current_app.instance_path) / "host_credential_references.json"


def _decorate_for_page(device):
    decorated = dict(device or {})
    facts = []
    for raw in decorated.get("host_facts") or []:
        item = dict(raw)
        item["first_seen_label"] = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(float(
                item.get("first_seen")
                or item.get("observed_at")
                or time.time()
            )),
        )
        item["last_seen_label"] = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(float(
                item.get("last_seen")
                or item.get("observed_at")
                or time.time()
            )),
        )
        facts.append(item)
    decorated["host_facts"] = facts
    runs = []
    for raw in decorated.get("host_fact_runs") or []:
        item = dict(raw)
        item["time_label"] = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(float(item.get("timestamp") or time.time())),
        )
        runs.append(item)
    decorated["host_fact_runs"] = runs
    baseline = dict(decorated.get("host_fact_baseline") or {})
    if baseline.get("saved_at"):
        baseline["saved_at_label"] = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(float(baseline["saved_at"])),
        )
    decorated["host_fact_baseline"] = baseline
    return decorated


def create_host_facts_blueprint(context_provider):
    blueprint = Blueprint("host_facts", __name__)

    @blueprint.get("/clients/<path:identifier>/host-facts")
    @_login_required
    def host_facts_page(identifier):
        import app as app_module

        device = app_module.find_inventory_device(identifier) or {}
        if not device:
            return render_template(
                "host_facts.html",
                title="Host not found",
                identifier=identifier,
                device=None,
                facts=[],
                credential_profiles=[],
                capabilities=host_facts.capabilities(),
                error="Device was not found in inventory.",
                **context_provider(),
            ), 404
        decorated = _decorate_for_page(device)
        facts = decorated.get("host_facts") or []
        summary = {
            "total": len(facts),
            "changed": len([
                item for item in facts if item.get("changed_since_baseline")
            ]),
            "high_confidence": len([
                item
                for item in facts
                if item.get("confidence") in {"high", "very-high"}
            ]),
            "sensitive": len([
                item
                for item in facts
                if item.get("sensitivity") == "sensitive"
            ]),
        }
        return render_template(
            "host_facts.html",
            title=(
                "Host Facts · "
                f"{device.get('display_name') or device.get('name') or device.get('ip') or identifier}"
            ),
            identifier=identifier,
            device=decorated,
            facts=facts,
            summary=summary,
            credential_profiles=host_facts.load_credential_references(
                _credential_path()
            ),
            capabilities=host_facts.capabilities(),
            error=request.args.get("error"),
            message=request.args.get("message"),
            **context_provider(),
        )

    @blueprint.post("/clients/<path:identifier>/host-facts/collect")
    @_write_required
    def collect_host_facts(identifier):
        import app as app_module

        device = app_module.find_inventory_device(identifier) or {}
        if not device:
            return _error("Device was not found in inventory", 404)
        user = session.get("social_user") or {}
        actor = user.get("username") or "unknown"
        mode = str(request.form.get("mode") or "passive").strip().casefold()
        host = device.get("ip") or identifier
        try:
            if mode == "passive":
                relationship_map = app_module.client_relationship_map(identifier)
                passive_provider = getattr(
                    app_module,
                    "passive_observation_summary",
                    None,
                )
                passive_summary = (
                    passive_provider() if callable(passive_provider) else {}
                )
                observed = host_facts.passive_facts(
                    device,
                    relationships=relationship_map,
                    passive_summary=passive_summary,
                )
            elif mode == "safe":
                if request.form.get("authorized") != "on":
                    raise ValueError(
                        "Confirm authorization before safe protocol negotiation"
                    )
                fingerprints = app_module.fingerprint_client_services(identifier)
                observed = host_facts.safe_facts(
                    device,
                    host,
                    base_fingerprints=fingerprints,
                )
            elif mode == "deep":
                if user.get("role") != "admin":
                    return _error(
                        "Administrator role required for deep identification",
                        403,
                    )
                if request.form.get("authorized") != "on":
                    raise ValueError(
                        "Confirm authorization before deep identification"
                    )
                profiles = host_facts.load_credential_references(
                    _credential_path()
                )
                profile = host_facts.credential_reference(
                    profiles,
                    request.form.get("credentialProfile"),
                )
                snmp_community = ""
                if profile and profile.get("kind") == "snmp-v2c":
                    snmp_community = host_facts.resolve_secret(profile)
                    if not snmp_community:
                        raise ValueError(
                            f"Environment variable {profile.get('secret_env')} is not set"
                        )
                observed = host_facts.deep_facts(
                    device,
                    host,
                    authorized=True,
                    snmp_community=snmp_community or None,
                )
            else:
                raise ValueError("Unsupported host-facts collection mode")
        except ValueError as exc:
            return redirect(url_for(
                "host_facts.host_facts_page",
                identifier=identifier,
                error=str(exc),
            ))
        updated = host_facts.apply_fact_run(
            device,
            observed,
            mode=mode,
            actor=actor,
        )
        _persist_device(app_module, identifier, updated)
        app_module.append_client_timeline_event(
            host,
            "Host facts collected",
            f"Collected {len(observed)} {mode} host fact(s).",
            "host-facts",
        )
        app_module.record_social_audit(
            "host-facts.collect",
            profile_id=str(identifier),
            detail=f"mode={mode}; facts={len(observed)}",
        )
        app_module.save_runtime_state(f"host-facts:{mode}")
        return redirect(url_for(
            "host_facts.host_facts_page",
            identifier=identifier,
            message=f"Collected {len(observed)} {mode} host fact(s).",
        ))

    @blueprint.post("/clients/<path:identifier>/host-facts/baseline")
    @_write_required
    def baseline_host_facts(identifier):
        import app as app_module

        device = app_module.find_inventory_device(identifier) or {}
        if not device:
            return _error("Device was not found in inventory", 404)
        actor = (session.get("social_user") or {}).get("username") or "unknown"
        updated = host_facts.save_baseline(device, actor=actor)
        _persist_device(app_module, identifier, updated)
        app_module.append_client_timeline_event(
            device.get("ip") or identifier,
            "Host facts baseline saved",
            (
                f"Saved {len(updated.get('host_facts') or [])} fact(s) "
                "as the comparison baseline."
            ),
            "host-facts",
        )
        app_module.record_social_audit(
            "host-facts.baseline",
            profile_id=str(identifier),
            detail=f"facts={len(updated.get('host_facts') or [])}",
        )
        app_module.save_runtime_state("host-facts-baseline")
        return redirect(url_for(
            "host_facts.host_facts_page",
            identifier=identifier,
            message="Host facts baseline saved.",
        ))

    @blueprint.post(
        "/clients/<path:identifier>/host-facts/credential-references"
    )
    @_write_required
    def create_credential_reference(identifier):
        user = session.get("social_user") or {}
        if user.get("role") != "admin":
            return _error("Administrator role required", 403)
        try:
            profile = host_facts.save_credential_reference(
                _credential_path(),
                name=request.form.get("name"),
                kind=request.form.get("kind"),
                secret_env=request.form.get("secretEnv"),
                username=request.form.get("username"),
                notes=request.form.get("notes"),
                actor=user.get("username") or "unknown",
            )
        except ValueError as exc:
            return redirect(url_for(
                "host_facts.host_facts_page",
                identifier=identifier,
                error=str(exc),
            ))
        return redirect(url_for(
            "host_facts.host_facts_page",
            identifier=identifier,
            message=f"Credential reference {profile['name']} saved.",
        ))

    @blueprint.get("/clients/<path:identifier>/host-facts.json")
    @_login_required
    def export_host_facts(identifier):
        import app as app_module

        device = app_module.find_inventory_device(identifier) or {}
        if not device:
            return _error("Device was not found in inventory", 404)
        return jsonify({
            "schema": "mobile-router-host-facts-v1",
            "exported_at": time.time(),
            "identifier": identifier,
            "device": {
                "ip": device.get("ip"),
                "mac": device.get("mac"),
                "manufacturer": device.get("manufacturer"),
                "model": device.get("model"),
                "firmware": (
                    device.get("firmware")
                    or device.get("firmware_version")
                ),
            },
            "facts": device.get("host_facts") or [],
            "baseline": device.get("host_fact_baseline"),
            "runs": device.get("host_fact_runs") or [],
        })

    return blueprint
