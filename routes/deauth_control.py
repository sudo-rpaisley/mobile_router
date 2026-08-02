"""Administrator-only routes for bounded deauthentication lab control."""

from functools import wraps
import secrets

from flask import Blueprint, current_app, jsonify, request, session

from services import deauth_control as deauth_control_service


def _admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = session.get("social_user") or {}
        if not user:
            return jsonify({"status": "error", "message": "Administrator login required"}), 401
        if user.get("role") != "admin":
            return jsonify({"status": "error", "message": "Administrator role required"}), 403
        if request.method != "GET":
            expected = session.get("social_csrf_token") or ""
            supplied = (
                request.form.get("csrf_token")
                or request.headers.get("X-CSRF-Token")
                or ""
            )
            if not expected or not secrets.compare_digest(str(expected), str(supplied)):
                return jsonify({"status": "error", "message": "Invalid CSRF token"}), 400
        return view(*args, **kwargs)

    return wrapped


def _error(message, status=400):
    return jsonify({"status": "error", "message": str(message)}), status


def create_deauth_control_blueprint(context_provider):
    del context_provider
    blueprint = Blueprint("deauth_control", __name__)

    @blueprint.route("/deauth/start", methods=["POST"])
    @_admin_required
    def start_deauth():
        data = request.form
        selected_interface = (data.get("selectedInterface") or "").strip()
        if not selected_interface:
            return _error("Choose a wireless interface")

        try:
            ap_mac, target_mac = deauth_control_service.validate_start_request(
                data,
                _normalize_mac,
            )
            operator = (session.get("social_user") or {}).get("username") or "unknown"

            def send_frame():
                from scripts.wifi.deauth import send_deauth_frame

                send_deauth_frame(ap_mac, target_mac, selected_interface)

            job = deauth_control_service.start_deauth(
                ap_mac=ap_mac,
                target_mac=target_mac,
                interface=selected_interface,
                operator=operator,
                send_frame=send_frame,
            )
        except ValueError as exc:
            return _error(exc)
        except Exception as exc:
            current_app.logger.exception("Unable to start bounded deauth lab")
            return _error(f"Deauth start error: {exc}", 500)

        current_app.logger.warning(
            "Bounded deauth lab started by %s for AP %s target %s on %s; hard deadline %.3f",
            operator,
            ap_mac,
            target_mac,
            selected_interface,
            job["hard_deadline"],
        )
        return jsonify(
            {
                "status": "success",
                "message": "Bounded deauth lab run started",
                "job": job,
            }
        )

    @blueprint.route("/deauth/heartbeat", methods=["POST"])
    @_admin_required
    def heartbeat_deauth():
        job_id = (request.form.get("jobId") or "").strip()
        if not job_id:
            return _error("Missing bounded deauth job ID")
        try:
            job = deauth_control_service.heartbeat_deauth(job_id)
        except ValueError as exc:
            return _error(exc, 409)
        return jsonify({"status": "success", "job": job})

    @blueprint.route("/deauth/stop", methods=["POST"])
    @_admin_required
    def stop_deauth():
        job_id = (request.form.get("jobId") or "").strip() or None
        try:
            job = deauth_control_service.stop_deauth(job_id, "manual_stop")
        except ValueError as exc:
            return _error(exc, 409)
        current_app.logger.warning(
            "Bounded deauth lab stop requested by %s",
            (session.get("social_user") or {}).get("username") or "unknown",
        )
        return jsonify({"status": "success", "job": job})

    @blueprint.route("/deauth/emergency-stop", methods=["POST"])
    @_admin_required
    def emergency_stop_deauth():
        job = deauth_control_service.emergency_stop_deauth("web_emergency_stop")
        current_app.logger.error(
            "Bounded deauth emergency stop requested by %s",
            (session.get("social_user") or {}).get("username") or "unknown",
        )
        return jsonify({"status": "success", "job": job})

    @blueprint.route("/deauth/status")
    @_admin_required
    def deauth_status():
        return jsonify(
            {
                "status": "success",
                "job": deauth_control_service.deauth_status(),
                "local_emergency_stop": (
                    "python -m scripts.wifi.deauth_emergency_stop"
                ),
            }
        )

    return blueprint


def _normalize_mac(value):
    from app_support.identifiers import normalize_mac

    return normalize_mac(value)
