import os
import platform
import shutil
import subprocess
from pathlib import Path


DATA_FEATURES = {"contacts", "call_history", "messages"}
IMPLEMENTED_SYNC_FEATURES = {"contacts", "call_history"}
HELPER_SYNC_FEATURES = {"contacts", "call_history", "messages"}
CONTROL_FEATURES = {"call_controls", "media_controls", "tethering"}

PHONE_PROFILE_SUPPORT = {
    "android": {
        "label": "Android",
        "features": {
            "contacts": "PBAP",
            "call_history": "PBAP",
            "messages": "MAP",
            "call_controls": "HFP",
            "media_controls": "AVRCP",
            "tethering": "PAN",
        },
        "note": "Availability still depends on the Android manufacturer, Bluetooth settings, and permissions approved during pairing.",
    },
    "iphone": {
        "label": "iPhone",
        "features": {
            "contacts": "PBAP 1.2",
            "call_history": "PBAP 1.2",
            "messages": "MAP 1.4",
            "call_controls": "HFP 1.8",
            "media_controls": "AVRCP 1.6",
            "tethering": "PAN",
        },
        "note": "Apple documents these profiles, but the exact data and actions exposed can vary by accessory and user permission.",
    },
}


def _is_openwrt(release_path=None):
    path = Path(release_path) if release_path else Path("/etc/openwrt_release")
    return path.exists()


def detect_host_environment(system=None, openwrt=None):
    detected_system = system or platform.system()
    detected_openwrt = _is_openwrt() if openwrt is None else bool(openwrt)
    if detected_system == "Linux" and detected_openwrt:
        return {
            "id": "openwrt",
            "label": "OpenWrt",
            "system": "Linux",
            "limited": True,
        }
    if detected_system == "Linux":
        return {
            "id": "linux",
            "label": "Linux",
            "system": "Linux",
            "limited": False,
        }
    if detected_system == "Windows":
        return {
            "id": "windows",
            "label": "Windows",
            "system": "Windows",
            "limited": False,
        }
    if detected_system == "Darwin":
        return {
            "id": "macos",
            "label": "macOS",
            "system": "Darwin",
            "limited": False,
        }
    return {
        "id": "unknown",
        "label": detected_system or "Unknown",
        "system": detected_system or "Unknown",
        "limited": False,
    }


def _command_details(command_lookup=None):
    lookup = command_lookup or shutil.which
    commands = ("bluetoothctl", "busctl", "obexctl", "powershell", "pwsh")
    details = {}
    for command in commands:
        path = lookup(command)
        details[command] = {"available": path is not None, "path": path}
    return details


def _helper_status(environment):
    configured_helper = os.environ.get("MOBILE_ROUTER_BLUETOOTH_HELPER")
    if not configured_helper:
        return {"available": False, "path": None}
    helper_path = Path(configured_helper)
    return {"available": helper_path.is_file(), "path": str(helper_path)}


def _bluez_obex_status(commands, runner=None):
    busctl = commands.get("busctl", {}).get("path")
    if not busctl:
        return {"available": False, "scope": None}
    run = runner or subprocess.run
    for scope in ("--user", "--system"):
        try:
            result = run(
                [busctl, scope, "tree", "org.bluez.obex"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            return {"available": True, "scope": scope}
    return {"available": False, "scope": None}


def _backend_for_environment(environment, commands, helper, bluez_obex):
    environment_id = environment["id"]
    if environment_id in {"linux", "openwrt"}:
        has_bluez_control = (
            commands["bluetoothctl"]["available"]
            or commands["busctl"]["available"]
        )
        has_obex = commands["obexctl"]["available"] or commands["busctl"]["available"]
        prerequisites_ready = has_bluez_control and has_obex
        missing = []
        if not has_bluez_control:
            missing.append("BlueZ controller access (bluetoothctl or D-Bus/busctl)")
        if not has_obex:
            missing.append("BlueZ OBEX client tools (obexctl/obexd)")
        built_in_connector = bluez_obex["available"]
        connector_ready = prerequisites_ready and (
            built_in_connector or helper["available"]
        )
        if (
            commands["busctl"]["available"]
            and not bluez_obex["available"]
            and not helper["available"]
        ):
            missing.append("running BlueZ OBEX D-Bus service (obexd)")
        if not commands["busctl"]["available"] and not helper["available"]:
            missing.append("busctl or a Mobile Router BlueZ OBEX connector")
        return {
            "id": "bluez-obex",
            "label": "BlueZ OBEX",
            "transport": "RFCOMM + OBEX",
            "prerequisites_ready": prerequisites_ready,
            "connector_ready": connector_ready,
            "missing": missing,
            "sync_features": sorted(IMPLEMENTED_SYNC_FEATURES),
            "note": (
                "Uses the same BlueZ D-Bus transport on desktop Linux and OpenWrt. "
                "OpenWrt installations can omit control/audio components that are not selected."
            ),
        }
    if environment_id == "windows":
        return {
            "id": "windows-rfcomm",
            "label": "Windows RFCOMM helper",
            "transport": "WinRT RFCOMM + portable OBEX",
            "prerequisites_ready": True,
            "connector_ready": helper["available"],
            "missing": [] if helper["available"] else ["Packaged Mobile Router Windows Bluetooth helper"],
            "sync_features": sorted(HELPER_SYNC_FEATURES) if helper["available"] else [],
            "note": "Windows includes RFCOMM, HFP, AVRCP, and PAN support, but PBAP/MAP require the Mobile Router protocol helper.",
        }
    if environment_id == "macos":
        return {
            "id": "macos-iobluetooth",
            "label": "macOS IOBluetooth helper",
            "transport": "IOBluetooth RFCOMM/OBEX",
            "prerequisites_ready": True,
            "connector_ready": helper["available"],
            "missing": [] if helper["available"] else ["Packaged Mobile Router macOS Bluetooth helper"],
            "sync_features": sorted(HELPER_SYNC_FEATURES) if helper["available"] else [],
            "note": "The helper isolates macOS IOBluetooth APIs from the portable Python data layer.",
        }
    return {
        "id": "unsupported",
        "label": "No host backend",
        "transport": "Unavailable",
        "prerequisites_ready": False,
        "connector_ready": False,
        "missing": [f'No Bluetooth phone backend is defined for {environment["label"]}'],
        "sync_features": [],
        "note": "The configuration page remains available, but phone data transfer is disabled.",
    }


def _feature_runtime_status(settings, backend):
    selected_features = settings.get("enabled_features", {})
    statuses = {}
    for feature_key, enabled in selected_features.items():
        if not enabled:
            statuses[feature_key] = {
                "selected": False,
                "status": "disabled",
                "label": "Not selected",
            }
        elif feature_key in set(backend.get("sync_features", [])) and backend["connector_ready"]:
            statuses[feature_key] = {
                "selected": True,
                "status": "ready",
                "label": "Connector available",
            }
        elif feature_key in DATA_FEATURES:
            statuses[feature_key] = {
                "selected": True,
                "status": "transport_required",
                "label": "Transport required",
            }
        elif feature_key in CONTROL_FEATURES:
            statuses[feature_key] = {
                "selected": True,
                "status": "host_integration_required",
                "label": "Host integration required",
            }
    return statuses


def build_bluetooth_phone_runtime(
    settings,
    system=None,
    openwrt=None,
    command_lookup=None,
    bluez_obex_lookup=None,
):
    environment = detect_host_environment(system=system, openwrt=openwrt)
    commands = _command_details(command_lookup=command_lookup)
    helper = _helper_status(environment)
    obex_lookup = bluez_obex_lookup or _bluez_obex_status
    bluez_obex = (
        obex_lookup(commands)
        if environment["id"] in {"linux", "openwrt"}
        else {"available": False, "scope": None}
    )
    backend = _backend_for_environment(environment, commands, helper, bluez_obex)
    return {
        "host": environment,
        "backend": backend,
        "commands": commands,
        "helper": helper,
        "bluez_obex": bluez_obex,
        "features": _feature_runtime_status(settings, backend),
        "phones": PHONE_PROFILE_SUPPORT,
    }
