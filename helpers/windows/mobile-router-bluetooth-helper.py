#!/usr/bin/env python3
"""Bundled Windows Bluetooth helper for Mobile Router.

This helper implements the Mobile Router JSON helper protocol so Windows users
can use the bundled file without setting PATH or environment variables. Windows
restricts programmatic classic Bluetooth discoverability, so the advertising
action opens the Bluetooth settings page and tells the operator what to do next.
"""

import json
import os
import platform
import subprocess
import sys
import tempfile

PROTOCOL_VERSION = 1
MAX_REQUEST_BYTES = 1024 * 1024
BLUETOOTH_LOCAL_NAME_REGISTRY_PATH = r"HKLM:\SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters"
BLUETOOTH_LOCAL_NAME_VALUE = "LocalName"
ORIGINAL_NAME_STATE_PATH = os.path.join(tempfile.gettempdir(), "mobile-router-bluetooth-original-name.json")


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


def open_bluetooth_settings():
    if platform.system() != "Windows":
        return False
    try:
        os.startfile("ms-settings:bluetooth")
        return True
    except OSError:
        try:
            subprocess.Popen(["cmd", "/c", "start", "", "ms-settings:bluetooth"])
            return True
        except OSError:
            return False


def windows_bluetooth_display_name():
    return (
        os.environ.get("COMPUTERNAME")
        or os.environ.get("HOSTNAME")
        or platform.node()
        or "this Windows PC"
    )


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


def _run_powershell(script):
    powershell = _powershell_executable()
    if not powershell:
        return {"ok": False, "message": "PowerShell is not available."}
    try:
        result = subprocess.run(
            [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "message": str(exc)}
    output = (result.stdout or result.stderr or "").strip()
    return {"ok": result.returncode == 0, "message": output}


def _read_saved_original_name():
    try:
        with open(ORIGINAL_NAME_STATE_PATH, "r", encoding="utf-8") as state_file:
            state = json.load(state_file)
    except (OSError, json.JSONDecodeError):
        return None
    original_name = state.get("original_name")
    return str(original_name) if original_name else None


def _save_original_name(name):
    if _read_saved_original_name() is not None:
        return
    try:
        with open(ORIGINAL_NAME_STATE_PATH, "w", encoding="utf-8") as state_file:
            json.dump({"original_name": name}, state_file)
    except OSError:
        pass


def _clear_saved_original_name():
    try:
        os.remove(ORIGINAL_NAME_STATE_PATH)
    except FileNotFoundError:
        pass
    except OSError:
        pass


def _powershell_string(value):
    return "'" + str(value).replace("'", "''") + "'"


def set_windows_bluetooth_local_name(display_name):
    current_name = windows_bluetooth_display_name()
    _save_original_name(current_name)
    name_literal = _powershell_string(display_name)
    path_literal = _powershell_string(BLUETOOTH_LOCAL_NAME_REGISTRY_PATH)
    value_literal = _powershell_string(BLUETOOTH_LOCAL_NAME_VALUE)
    script = (
        f"$path = {path_literal}; "
        f"$name = {name_literal}; "
        f"$valueName = {value_literal}; "
        "if (-not (Test-Path $path)) { throw 'Bluetooth local-name registry path was not found.' }; "
        "New-ItemProperty -Path $path -Name $valueName -Value $name -PropertyType String -Force | Out-Null; "
        "Restart-Service bthserv -Force -ErrorAction SilentlyContinue; "
        "Write-Output $name"
    )
    result = _run_powershell(script)
    if result["ok"]:
        return {"applied": True, "visible_name": display_name, "message": result["message"]}
    return {"applied": False, "visible_name": current_name, "message": result["message"]}


def restore_windows_bluetooth_local_name():
    original_name = _read_saved_original_name()
    if not original_name:
        return {"restored": False, "message": "No temporary Bluetooth name override was saved."}
    result = set_windows_bluetooth_local_name(original_name)
    if result["applied"]:
        _clear_saved_original_name()
        return {"restored": True, "visible_name": original_name, "message": result["message"]}
    return {"restored": False, "visible_name": result["visible_name"], "message": result["message"]}


def handle_set_advertising(request):
    enabled = request.get("enabled") is True
    configured_name = str(request.get("display_name") or "Mobile Router").strip()
    visible_name = windows_bluetooth_display_name()
    rename_result = {"applied": False, "visible_name": visible_name, "message": ""}
    if enabled:
        rename_result = set_windows_bluetooth_local_name(configured_name)
        visible_name = rename_result["visible_name"]
        opened = open_bluetooth_settings()
        if not opened:
            if rename_result["applied"]:
                restore_windows_bluetooth_local_name()
            return response(
                status="error",
                message="Open Windows Bluetooth settings manually, enable Bluetooth, and pair the phone with this PC.",
            )
        return response(
            status="success",
            enabled=True,
            display_name=configured_name,
            visible_name=visible_name,
            name_override_applied=rename_result["applied"],
            message=(
                "Windows Bluetooth settings opened. Enable Bluetooth and pair the phone "
                f'with "{visible_name}" from the phone. '
                + (
                    "Mobile Router temporarily changed the Windows Bluetooth local name; "
                    "turn advertising off to restore the previous name."
                    if rename_result["applied"]
                    else f'Windows kept the PC Bluetooth name because the temporary name override failed: {rename_result["message"]}'
                )
            ),
        )
    restore_result = restore_windows_bluetooth_local_name()
    return response(
        status="success",
        enabled=False,
        name_override_restored=restore_result["restored"],
        visible_name=restore_result.get("visible_name", windows_bluetooth_display_name()),
        message=(
            "Windows Bluetooth advertising is off. "
            + (
                f'Restored the previous Bluetooth local name "{restore_result["visible_name"]}".'
                if restore_result["restored"]
                else restore_result["message"]
            )
        ),
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
                    "pbap": False,
                    "map": False,
                    "note": "Bundled helper opens Windows Bluetooth settings for pairing; PBAP/MAP sync requires a full native helper.",
                },
            )
        if action == "set_advertising":
            return handle_set_advertising(request)
        return response(status="error", message=f"Unsupported helper action: {action}")
    except Exception as exc:
        return response(status="error", message=str(exc))


if __name__ == "__main__":
    main()
