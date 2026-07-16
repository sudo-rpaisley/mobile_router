import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path

from scripts.bluetooth_phone_connector import (
    BluetoothPhoneConnectorError,
    BluetoothPhoneHelperClient,
)


BLUETOOTH_PHONE_FEATURES = (
    {
        "key": "contacts",
        "label": "Contacts",
        "profile": "PBAP",
        "description": "Synchronise the phone book and supported contact details.",
    },
    {
        "key": "call_history",
        "label": "Call history",
        "profile": "PBAP",
        "description": "Synchronise incoming, outgoing, missed, and combined recent calls.",
    },
    {
        "key": "messages",
        "label": "Messages",
        "profile": "MAP",
        "description": "Synchronise supported SMS/MMS messages and message notifications.",
    },
    {
        "key": "call_controls",
        "label": "Call controls",
        "profile": "HFP",
        "description": "Show caller information and enable supported dial, answer, and end-call controls.",
    },
    {
        "key": "media_controls",
        "label": "Media controls",
        "profile": "AVRCP",
        "description": "Show media metadata and enable supported playback controls.",
    },
    {
        "key": "tethering",
        "label": "Bluetooth tethering",
        "profile": "PAN",
        "description": "Allow Mobile Router to use an authorised phone network connection.",
    },
)

FEATURE_KEYS = {feature["key"] for feature in BLUETOOTH_PHONE_FEATURES}
DEFAULT_DISPLAY_NAME = "Mobile Router"
DEFAULT_SETTINGS = {
    "display_name": DEFAULT_DISPLAY_NAME,
    "advertise_enabled": False,
    "enabled_features": {key: False for key in FEATURE_KEYS},
}
BLUEZ_ADAPTER_PATH_RE = re.compile(r"(/org/bluez/hci\d+)(?:\s|$)")


class BluetoothPhoneSettingsError(ValueError):
    """Raised when Bluetooth phone settings cannot be validated or loaded."""


class BluetoothDisplayNameUnavailable(RuntimeError):
    """Raised when the host Bluetooth display name cannot be changed safely."""


class BluetoothPairingModeUnavailable(RuntimeError):
    """Raised when the host adapter cannot be made pairable/discoverable safely."""


def bluetooth_phone_config_path():
    configured_path = os.environ.get("MOBILE_ROUTER_BLUETOOTH_PHONE_CONFIG")
    if configured_path:
        return Path(configured_path)
    return Path(__file__).resolve().parents[1] / "config" / "bluetooth_phone.json"


def _settings_copy():
    return {
        "display_name": DEFAULT_SETTINGS["display_name"],
        "advertise_enabled": DEFAULT_SETTINGS["advertise_enabled"],
        "enabled_features": dict(DEFAULT_SETTINGS["enabled_features"]),
    }


def validate_display_name(value):
    name = str(value or "").strip()
    if not name:
        raise BluetoothPhoneSettingsError("A Bluetooth display name is required")
    if any(ord(character) < 32 or ord(character) == 127 for character in name):
        raise BluetoothPhoneSettingsError("The Bluetooth display name cannot contain control characters")
    if len(name.encode("utf-8")) > 248:
        raise BluetoothPhoneSettingsError("The Bluetooth display name must be no more than 248 UTF-8 bytes")
    return name


def normalise_feature_selection(selected_features):
    selected = set(selected_features or [])
    unknown = selected - FEATURE_KEYS
    if unknown:
        raise BluetoothPhoneSettingsError(
            f"Unsupported Bluetooth phone feature: {sorted(unknown)[0]}"
        )
    return {key: key in selected for key in FEATURE_KEYS}


def build_settings(display_name, selected_features, advertise_enabled=False):
    return {
        "display_name": validate_display_name(display_name),
        "advertise_enabled": advertise_enabled is True,
        "enabled_features": normalise_feature_selection(selected_features),
    }


def load_bluetooth_phone_settings(path=None):
    config_path = Path(path) if path else bluetooth_phone_config_path()
    settings = _settings_copy()
    if not config_path.exists():
        return settings

    try:
        with config_path.open("r", encoding="utf-8") as config_file:
            saved_settings = json.load(config_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise BluetoothPhoneSettingsError(
            f"Unable to read Bluetooth phone settings: {exc}"
        ) from exc

    if not isinstance(saved_settings, dict):
        raise BluetoothPhoneSettingsError("Bluetooth phone settings must contain a JSON object")

    settings["display_name"] = validate_display_name(
        saved_settings.get("display_name", DEFAULT_DISPLAY_NAME)
    )
    settings["advertise_enabled"] = saved_settings.get("advertise_enabled") is True
    saved_features = saved_settings.get("enabled_features", {})
    if not isinstance(saved_features, dict):
        raise BluetoothPhoneSettingsError("enabled_features must contain a JSON object")
    settings["enabled_features"] = {
        key: saved_features.get(key) is True for key in FEATURE_KEYS
    }
    return settings


def save_bluetooth_phone_settings(settings, path=None):
    normalised_settings = build_settings(
        settings.get("display_name"),
        [
            key
            for key, enabled in settings.get("enabled_features", {}).items()
            if enabled is True
        ],
        settings.get("advertise_enabled") is True,
    )
    config_path = Path(path) if path else bluetooth_phone_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = config_path.with_suffix(f"{config_path.suffix}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as config_file:
            json.dump(normalised_settings, config_file, indent=2, sort_keys=True)
            config_file.write("\n")
        temporary_path.replace(config_path)
    except OSError as exc:
        raise BluetoothPhoneSettingsError(
            f"Unable to save Bluetooth phone settings: {exc}"
        ) from exc
    return normalised_settings


def bluetooth_phone_feature_options(settings):
    enabled_features = settings.get("enabled_features", {})
    return [
        {**feature, "enabled": enabled_features.get(feature["key"]) is True}
        for feature in BLUETOOTH_PHONE_FEATURES
    ]


def _bluez_dbus_available(busctl_path):
    try:
        result = subprocess.run(
            [busctl_path, "tree", "org.bluez"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0



def _configured_bluetooth_helper():
    configured_helper = os.environ.get("MOBILE_ROUTER_BLUETOOTH_HELPER")
    if configured_helper:
        helper_path = Path(configured_helper)
        return str(helper_path) if helper_path.is_file() else None
    return (
        shutil.which("mobile-router-bluetooth-helper")
        or shutil.which("bluetooth-phone-helper")
    )

def bluetooth_pairing_mode_capability(system=None):
    system = system or platform.system()
    helper = _configured_bluetooth_helper()
    if system == "Linux":
        bluetoothctl = shutil.which("bluetoothctl")
        if bluetoothctl:
            return {
                "available": True,
                "tool": "bluetoothctl",
                "path": bluetoothctl,
                "message": "Mobile Router can make the adapter powered, pairable, and discoverable for phones.",
            }
        if helper:
            return {
                "available": True,
                "tool": "native-helper",
                "path": helper,
                "message": "Mobile Router can ask the configured Bluetooth helper to advertise this adapter for phones.",
            }
        return {
            "available": False,
            "tool": None,
            "path": None,
            "message": "Pairing mode requires BlueZ bluetoothctl or a Mobile Router Bluetooth helper on this host.",
        }
    if system in {"Windows", "Darwin"}:
        if helper:
            return {
                "available": True,
                "tool": "native-helper",
                "path": helper,
                "message": "Mobile Router can ask the configured native Bluetooth helper to advertise this adapter for phones.",
            }
        platform_name = "Windows" if system == "Windows" else "macOS"
        return {
            "available": False,
            "tool": None,
            "path": None,
            "message": (
                f"{platform_name} Bluetooth advertising needs the Mobile Router native "
                "Bluetooth helper installed, or MOBILE_ROUTER_BLUETOOTH_HELPER set "
                "to the helper executable."
            ),
        }
    return {
        "available": False,
        "tool": None,
        "path": None,
        "message": (
            "Automatic pairing mode is not supported on this host without a "
            "native Mobile Router Bluetooth helper."
        ),
    }


def _run_bluetoothctl_pairing_commands(commands, capability, timeout):
    for command in commands:
        try:
            result = subprocess.run(
                [capability["path"], *command],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"Unable to update Bluetooth advertising: {exc}") from exc
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "Bluetooth advertising command failed").strip()
            raise RuntimeError(message)


def _run_helper_advertising(capability, enabled, display_name=None, timeout=15):
    try:
        result = BluetoothPhoneHelperClient(
            capability["path"],
            timeout=timeout,
        ).set_advertising(enabled, display_name=display_name)
    except BluetoothPhoneConnectorError as exc:
        raise RuntimeError(f"Bluetooth helper advertising request failed: {exc}") from exc
    return {
        "enabled": result["enabled"],
        "tool": capability["tool"],
        "message": result["message"],
    }


def enable_bluetooth_pairing_mode(display_name, timeout=15):
    name = validate_display_name(display_name)
    capability = bluetooth_pairing_mode_capability()
    if not capability["available"]:
        raise BluetoothPairingModeUnavailable(capability["message"])
    if capability["tool"] == "native-helper":
        result = _run_helper_advertising(capability, True, display_name=name, timeout=timeout)
        return {**result, "display_name": name}

    _run_bluetoothctl_pairing_commands(
        [
            ["power", "on"],
            ["system-alias", name],
            ["agent", "NoInputNoOutput"],
            ["default-agent"],
            ["pairable", "on"],
            ["discoverable", "on"],
        ],
        capability,
        timeout,
    )
    return {
        "enabled": True,
        "display_name": name,
        "tool": capability["tool"],
        "message": f'Bluetooth advertising is on for "{name}". Phones can now pair with it.',
    }


def disable_bluetooth_pairing_mode(timeout=15):
    capability = bluetooth_pairing_mode_capability()
    if not capability["available"]:
        raise BluetoothPairingModeUnavailable(capability["message"])
    if capability["tool"] == "native-helper":
        return _run_helper_advertising(capability, False, timeout=timeout)
    _run_bluetoothctl_pairing_commands(
        [["discoverable", "off"], ["pairable", "off"]],
        capability,
        timeout,
    )
    return {
        "enabled": False,
        "tool": capability["tool"],
        "message": "Bluetooth advertising is off.",
    }

def bluetooth_display_name_capability(system=None):
    system = system or platform.system()
    if system == "Linux":
        bluetoothctl = shutil.which("bluetoothctl")
        if bluetoothctl:
            return {
                "available": True,
                "tool": "bluetoothctl",
                "path": bluetoothctl,
                "message": "The selected name can be applied to the BlueZ controller alias.",
            }
        busctl = shutil.which("busctl")
        if busctl and _bluez_dbus_available(busctl):
            return {
                "available": True,
                "tool": "busctl",
                "path": busctl,
                "message": "The selected name can be applied through the BlueZ D-Bus service.",
            }
        return {
            "available": False,
            "tool": None,
            "path": None,
            "message": "The name will be saved for Mobile Router, but applying it to the adapter requires BlueZ bluetoothctl or D-Bus access.",
        }
    if system == "Windows":
        return {
            "available": False,
            "tool": None,
            "path": None,
            "message": "The name will be saved for the Mobile Router service. Windows uses the computer name as its system Bluetooth name.",
        }
    return {
        "available": False,
        "tool": None,
        "path": None,
        "message": "The name will be saved for the Mobile Router service; this platform does not expose a supported adapter rename action.",
    }


def _find_bluez_adapter_path(busctl_path, timeout=10):
    result = subprocess.run(
        [busctl_path, "tree", "org.bluez"],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            (result.stderr or result.stdout or "BlueZ D-Bus tree lookup failed").strip()
        )
    for line in result.stdout.splitlines():
        match = BLUEZ_ADAPTER_PATH_RE.search(line)
        if match:
            return match.group(1)
    raise RuntimeError("No BlueZ Bluetooth controller was found")


def apply_bluetooth_display_name(display_name, timeout=10):
    name = validate_display_name(display_name)
    capability = bluetooth_display_name_capability()
    if not capability["available"]:
        raise BluetoothDisplayNameUnavailable(capability["message"])

    if capability["tool"] == "bluetoothctl":
        command = [capability["path"], "system-alias", name]
    else:
        adapter_path = _find_bluez_adapter_path(capability["path"], timeout=timeout)
        command = [
            capability["path"],
            "set-property",
            "org.bluez",
            adapter_path,
            "org.bluez.Adapter1",
            "Alias",
            "s",
            name,
        ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Unable to update the Bluetooth display name: {exc}") from exc
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "Bluetooth adapter rename failed").strip()
        raise RuntimeError(message)
    return {
        "applied": True,
        "display_name": name,
        "tool": capability["tool"],
        "message": f'Bluetooth display name updated to "{name}".',
    }
