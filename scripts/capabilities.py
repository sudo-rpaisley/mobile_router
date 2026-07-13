import importlib.util
import platform
import shutil
import sys
from typing import Dict, List

CORE_COMMANDS = ["ip", "ifconfig", "ipconfig", "arp", "ping", "traceroute", "tracepath", "tracert"]
OPTIONAL_COMMANDS = ["iw", "nmcli", "netsh", "aireplay-ng", "rfkill", "hciconfig", "bluetoothctl", "powershell", "pwsh"]
OPTIONAL_PACKAGES = ["bleak", "scapy", "pywifi"]


def command_status(commands: List[str]) -> Dict[str, Dict[str, object]]:
    return {
        command: {
            "available": shutil.which(command) is not None,
            "path": shutil.which(command),
        }
        for command in commands
    }


def package_status(packages: List[str]) -> Dict[str, bool]:
    return {package: importlib.util.find_spec(package) is not None for package in packages}


def _available(commands, *names):
    return any(commands.get(name, {}).get("available") for name in names)


def build_capabilities() -> Dict[str, object]:
    commands = command_status(CORE_COMMANDS + OPTIONAL_COMMANDS)
    packages = package_status(OPTIONAL_PACKAGES)
    system = platform.system()

    has_windows_shell = _available(commands, "powershell", "pwsh")
    has_bluetooth_scan = bool(
        packages["bleak"]
        or (system == "Windows" and has_windows_shell)
        or (system == "Linux" and commands.get("bluetoothctl", {}).get("available"))
    )
    has_wifi_network_scan = bool(
        (system == "Windows" and (commands.get("netsh", {}).get("available") or packages["pywifi"]))
        or (system == "Linux" and (_available(commands, "nmcli", "iw") or packages["scapy"]))
    )

    features = {
        "Core web UI": True,
        "Minecraft status lab": True,
        "Minecraft mob toggles": True,
        "Interface inventory": bool(commands.get("ip", {}).get("available") or commands.get("ifconfig", {}).get("available") or commands.get("ipconfig", {}).get("available") or system == "Windows"),
        "Passive ARP scan": bool(commands.get("arp", {}).get("available") or system == "Linux"),
        "Active ping scan": bool(commands.get("ping", {}).get("available")),
        "Traceroute": bool(commands.get("traceroute", {}).get("available") or commands.get("tracepath", {}).get("available") or commands.get("tracert", {}).get("available")),
        "Bluetooth scan": has_bluetooth_scan,
        "Wi-Fi network scan": has_wifi_network_scan,
        "Linux monitor packet scan": bool(packages["scapy"] and system == "Linux"),
        "Windows Wi-Fi connect": bool(packages["pywifi"] and system == "Windows"),
        "Aireplay deauth": bool(commands.get("aireplay-ng", {}).get("available")),
    }

    feature_notes = {
        "Bluetooth scan": "Uses Bleak for BLE plus Windows PowerShell or Linux bluetoothctl fallbacks.",
        "Wi-Fi network scan": "Uses nmcli/iw/Scapy on Linux or netsh/pywifi on Windows.",
        "Linux monitor packet scan": "Requires Linux and Scapy; monitor-mode support depends on the adapter/driver.",
        "Windows Wi-Fi connect": "Requires the optional pywifi package for connection management.",
        "Aireplay deauth": "Requires the external aireplay-ng command from aircrack-ng.",
    }

    return {
        "platform": {
            "system": system,
            "release": platform.release(),
            "machine": platform.machine(),
            "python_version": sys.version.split()[0],
        },
        "commands": commands,
        "packages": packages,
        "features": features,
        "feature_notes": feature_notes,
    }
