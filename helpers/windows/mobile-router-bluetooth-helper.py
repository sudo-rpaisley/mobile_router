#!/usr/bin/env python3
"""Bundled Windows Bluetooth helper for Mobile Router.

This helper implements the Mobile Router JSON helper protocol so Windows users
can use the bundled file without setting PATH or environment variables. It does
not open system-wide Windows Bluetooth pairing or rename the PC. Instead, it
starts a Mobile Router-owned Bluetooth LE advertisement with an app-specific
service UUID so phones can discover/connect to this app without pairing with the
whole laptop.
"""

import json
import os
import subprocess
import sys
import tempfile

PROTOCOL_VERSION = 1
MAX_REQUEST_BYTES = 1024 * 1024
MOBILE_ROUTER_BLE_SERVICE_UUID = "7b6cdbd8-0f54-4f7d-9f65-4b875f6d3f7a"
ADVERTISING_STATE_PATH = os.path.join(tempfile.gettempdir(), "mobile-router-bluetooth-advertising.json")
STOP_SIGNAL_PATH = os.path.join(tempfile.gettempdir(), "mobile-router-bluetooth-advertising.stop")
APP_SCOPED_PAIRING_NOTE = (
    "Mobile Router advertises its own Bluetooth LE service for app-scoped phone "
    "connections. It does not open Windows Bluetooth settings, rename the PC, or "
    "pair the phone with the whole laptop."
)


def response(**payload):
    json.dump({"protocol_version": PROTOCOL_VERSION, **payload}, sys.stdout)


def read_request():
    raw = sys.stdin.read(MAX_REQUEST_BYTES + 1)
    if len(raw.encode("utf-8")) > MAX_REQUEST_BYTES:
        raise ValueError("Helper request is too large")
    request = json.loads(raw or "{}")
    if request.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("Helper protocol version does not match")
    return request


def validate_display_name(value):
    name = str(value or "Mobile Router").strip() or "Mobile Router"
    if any(ord(character) < 32 or ord(character) == 127 for character in name):
        raise ValueError("Bluetooth display name cannot contain control characters")
    if len(name.encode("utf-8")) > 248:
        raise ValueError("Bluetooth display name must be no more than 248 UTF-8 bytes")
    return name


def _powershell_executable():
    for command in ("powershell", "pwsh"):
        try:
            result = subprocess.run(
                [command, "-NoProfile", "-Command", "$PSVersionTable.PSVersion.Major"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            return command
    return None


def _load_state():
    try:
        with open(ADVERTISING_STATE_PATH, "r", encoding="utf-8") as state_file:
            state = json.load(state_file)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(state, dict):
        return None
    return state


def _write_state(state):
    with open(ADVERTISING_STATE_PATH, "w", encoding="utf-8") as state_file:
        json.dump(state, state_file)


def _remove_file(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except OSError:
        pass


def _clear_state_files():
    _remove_file(ADVERTISING_STATE_PATH)
    _remove_file(STOP_SIGNAL_PATH)


def _process_running(pid):
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    return True


def _powershell_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def _advertising_script(display_name, service_uuid, stop_path):
    name_literal = _powershell_literal(display_name)
    uuid_literal = _powershell_literal(service_uuid)
    stop_literal = _powershell_literal(stop_path)
    return f"""
$ErrorActionPreference = 'Stop'
$name = {name_literal}
$serviceUuid = [Guid]{uuid_literal}
$stopPath = {stop_literal}
[Windows.Devices.Bluetooth.Advertisement.BluetoothLEAdvertisementPublisher, Windows.Devices.Bluetooth, ContentType = WindowsRuntime] | Out-Null
$publisher = [Windows.Devices.Bluetooth.Advertisement.BluetoothLEAdvertisementPublisher]::new()
$publisher.Advertisement.LocalName = $name
$publisher.Advertisement.ServiceUuids.Add($serviceUuid)
$publisher.Start()
try {{
    while (-not (Test-Path -LiteralPath $stopPath)) {{ Start-Sleep -Milliseconds 500 }}
}}
finally {{
    $publisher.Stop()
    if (Test-Path -LiteralPath $stopPath) {{ Remove-Item -LiteralPath $stopPath -Force }}
}}
""".strip()


def stop_app_scoped_advertising():
    state = _load_state()
    if not state:
        _clear_state_files()
        return {"stopped": False, "message": "No Mobile Router app-scoped Bluetooth advertisement was running."}
    try:
        with open(STOP_SIGNAL_PATH, "w", encoding="utf-8") as stop_file:
            stop_file.write("stop")
    except OSError:
        pass
    pid = state.get("pid")
    _remove_file(ADVERTISING_STATE_PATH)
    if not _process_running(pid):
        _remove_file(STOP_SIGNAL_PATH)
    return {
        "stopped": True,
        "display_name": state.get("display_name"),
        "service_uuid": state.get("service_uuid"),
        "message": "Mobile Router app-scoped Bluetooth advertising is off.",
    }


def start_app_scoped_advertising(display_name):
    name = validate_display_name(display_name)
    existing_state = _load_state()
    if existing_state and _process_running(existing_state.get("pid")):
        return {
            "enabled": True,
            "display_name": existing_state.get("display_name", name),
            "service_uuid": existing_state.get("service_uuid", MOBILE_ROUTER_BLE_SERVICE_UUID),
            "message": "Mobile Router app-scoped Bluetooth advertising is already running.",
        }
    _clear_state_files()
    powershell = _powershell_executable()
    if not powershell:
        return {"enabled": False, "message": "PowerShell is required for app-scoped Bluetooth LE advertising on Windows."}
    service_uuid = MOBILE_ROUTER_BLE_SERVICE_UUID
    script = _advertising_script(name, service_uuid, STOP_SIGNAL_PATH)
    try:
        process = subprocess.Popen(
            [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            text=True,
        )
    except OSError as exc:
        return {"enabled": False, "message": f"Unable to start app-scoped Bluetooth advertising: {exc}"}
    _write_state({"pid": process.pid, "display_name": name, "service_uuid": service_uuid})
    return {
        "enabled": True,
        "display_name": name,
        "service_uuid": service_uuid,
        "message": (
            f'Mobile Router is advertising "{name}" as an app-scoped Bluetooth LE service. '
            "Connect from a Mobile Router companion/client app instead of Windows Bluetooth settings."
        ),
    }


def handle_set_advertising(request):
    enabled = request.get("enabled") is True
    result = start_app_scoped_advertising(request.get("display_name")) if enabled else stop_app_scoped_advertising()
    status = "success" if result.get("enabled") is True or result.get("stopped") is True or not enabled else "error"
    return response(
        status=status,
        enabled=result.get("enabled") is True,
        app_scoped_pairing=True,
        display_name=result.get("display_name"),
        service_uuid=result.get("service_uuid", MOBILE_ROUTER_BLE_SERVICE_UUID),
        message=result["message"],
    )


def main():
    try:
        request = read_request()
        action = request.get("action")
        if action == "capabilities":
            return response(
                status="success",
                capabilities={
                    "advertising": True,
                    "app_scoped_pairing": True,
                    "pbap": False,
                    "map": False,
                    "service_uuid": MOBILE_ROUTER_BLE_SERVICE_UUID,
                    "note": APP_SCOPED_PAIRING_NOTE,
                },
            )
        if action == "set_advertising":
            return handle_set_advertising(request)
        return response(status="error", message=f"Unsupported helper action: {action}")
    except Exception as exc:
        return response(status="error", message=str(exc))


if __name__ == "__main__":
    main()
