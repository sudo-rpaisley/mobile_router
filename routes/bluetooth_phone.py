import io
import json
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, render_template, request, send_file

from scripts.bluetooth_phone import (
    BluetoothPairingModeUnavailable,
    BluetoothPhoneSettingsError,
    bluetooth_pairing_mode_capability,
    bluetooth_phone_feature_options,
    build_settings,
    disable_bluetooth_pairing_mode,
    load_bluetooth_phone_settings,
    enable_bluetooth_pairing_mode,
    save_bluetooth_phone_settings,
)
from scripts.bluetooth_phone_runtime import build_bluetooth_phone_runtime
from scripts.bluetooth_phone_bluez import BluezObexConnector
from scripts.bluetooth_phone_connector import (
    BluetoothPhoneConnectorError,
    BluetoothPhoneHelperClient,
)


def create_bluetooth_phone_blueprint(context_provider):
    blueprint = Blueprint("bluetooth_phone", __name__)

    def render_settings_page(settings, notice=None, notice_style="info", status_code=200):
        context = context_provider()
        return (
            render_template(
                "bluetooth_phone.html",
                title="Phone Integration",
                settings=settings,
                feature_options=bluetooth_phone_feature_options(settings),
                pairing_capability=bluetooth_pairing_mode_capability(),
                notice=notice,
                notice_style=notice_style,
                **context,
            ),
            status_code,
        )

    @blueprint.route("/bluetooth-phone", methods=["GET", "POST"])
    def bluetooth_phone_page():
        config_path = current_app.config.get("BLUETOOTH_PHONE_CONFIG")
        if request.method == "GET":
            try:
                settings = load_bluetooth_phone_settings(config_path)
            except BluetoothPhoneSettingsError as exc:
                current_app.logger.warning("Unable to load Bluetooth phone settings: %s", exc)
                settings = build_settings("Mobile Router", [])
                return render_settings_page(settings, str(exc), "danger", 500)
            return render_settings_page(settings)

        try:
            settings = build_settings(
                request.form.get("display_name"),
                request.form.getlist("features"),
                request.form.get("advertise_enabled") == "true",
            )
            settings = save_bluetooth_phone_settings(settings, config_path)
        except BluetoothPhoneSettingsError as exc:
            current_app.logger.info("Bluetooth phone settings validation failed: %s", exc)
            fallback_name = request.form.get("display_name") or "Mobile Router"
            try:
                submitted_settings = build_settings(
                    fallback_name,
                    [feature for feature in request.form.getlist("features") if feature],
                    request.form.get("advertise_enabled") == "true",
                )
            except BluetoothPhoneSettingsError:
                submitted_settings = build_settings("Mobile Router", [])
            return render_settings_page(submitted_settings, str(exc), "danger", 400)

        notice = "Bluetooth phone settings saved."
        notice_style = "success"
        try:
            if settings["advertise_enabled"]:
                result = enable_bluetooth_pairing_mode(settings["display_name"])
                notice = f"Bluetooth phone settings saved. {result['message']}"
            else:
                result = disable_bluetooth_pairing_mode()
                notice = f"Bluetooth phone settings saved. {result['message']}"
        except BluetoothPairingModeUnavailable as exc:
            notice = f"Bluetooth phone settings saved. {exc}"
            notice_style = "info"
        except Exception as exc:
            current_app.logger.warning("Unable to update Bluetooth advertising: %s", exc)
            notice = f"Bluetooth phone settings saved, but Bluetooth advertising could not be updated: {exc}"
            notice_style = "warning"

        current_app.logger.info(
            "Bluetooth phone settings saved with %s selected feature(s)",
            sum(settings["enabled_features"].values()),
        )
        return render_settings_page(settings, notice, notice_style)


    @blueprint.route("/bluetooth-phone/pairing-mode", methods=["POST"])
    def bluetooth_phone_pairing_mode():
        config_path = current_app.config.get("BLUETOOTH_PHONE_CONFIG")
        try:
            settings = load_bluetooth_phone_settings(config_path)
        except BluetoothPhoneSettingsError as exc:
            current_app.logger.warning("Unable to load Bluetooth phone settings: %s", exc)
            settings = build_settings("Mobile Router", [])
            return render_settings_page(settings, str(exc), "danger", 500)

        try:
            result = enable_bluetooth_pairing_mode(settings["display_name"])
        except BluetoothPairingModeUnavailable as exc:
            return render_settings_page(settings, str(exc), "info", 400)
        except Exception as exc:
            current_app.logger.warning("Unable to enable Bluetooth pairing mode: %s", exc)
            return render_settings_page(
                settings,
                f"Bluetooth pairing mode could not be enabled: {exc}",
                "warning",
                500,
            )
        return render_settings_page(settings, result["message"], "success")

    @blueprint.route("/bluetooth-phone/status")
    def bluetooth_phone_status():
        config_path = current_app.config.get("BLUETOOTH_PHONE_CONFIG")
        try:
            settings = load_bluetooth_phone_settings(config_path)
        except BluetoothPhoneSettingsError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 500
        return jsonify(
            {
                "status": "success",
                "runtime": build_bluetooth_phone_runtime(settings),
            }
        )

    @blueprint.route("/bluetooth-phone/sync", methods=["POST"])
    def bluetooth_phone_sync():
        config_path = current_app.config.get("BLUETOOTH_PHONE_CONFIG")
        try:
            settings = load_bluetooth_phone_settings(config_path)
        except BluetoothPhoneSettingsError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 500

        if request.form.get("confirm_phone_access") != "true":
            return jsonify(
                {
                    "status": "error",
                    "message": "Confirm that you are authorised to access this phone.",
                }
            ), 400

        runtime = build_bluetooth_phone_runtime(settings)
        if not runtime["backend"]["connector_ready"]:
            return jsonify(
                {
                    "status": "error",
                    "message": "The Bluetooth phone connector requirements are not available on this host.",
                }
            ), 503

        host_id = runtime["host"]["id"]
        has_bluez_obex = runtime.get("bluez_obex", {}).get("available") is True
        helper = runtime.get("helper", {})
        try:
            if host_id in {"linux", "openwrt"} and has_bluez_obex:
                connector = BluezObexConnector(
                    bus_scope=runtime["bluez_obex"].get("scope")
                )
            elif helper.get("available"):
                connector = BluetoothPhoneHelperClient(helper["path"])
            else:
                return jsonify(
                    {
                        "status": "error",
                        "message": "No usable native Bluetooth phone connector was found.",
                    }
                ), 503
            data = connector.synchronise(
                request.form.get("device_id"),
                settings["enabled_features"],
            )
        except BluetoothPhoneConnectorError as exc:
            current_app.logger.info("Bluetooth phone synchronisation failed: %s", exc)
            return jsonify({"status": "error", "message": str(exc)}), 502

        exported_at = datetime.now(timezone.utc)
        export = {
            "format": "mobile-router-phone-export",
            "version": 1,
            "exported_at": exported_at.isoformat(),
            "device_id": request.form.get("device_id"),
            "features": sorted(data),
            "data": data,
        }
        payload = json.dumps(export, indent=2, ensure_ascii=False).encode("utf-8")
        response = send_file(
            io.BytesIO(payload),
            mimetype="application/json",
            as_attachment=True,
            download_name=f"mobile-router-phone-{exported_at.strftime('%Y%m%d-%H%M%S')}.json",
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    return blueprint
