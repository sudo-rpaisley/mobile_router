import importlib.util
import platform
import shutil
import subprocess
import sys
from typing import Dict, List

CORE_COMMANDS = ["ip", "ifconfig", "ipconfig", "arp", "ping", "traceroute", "tracepath", "tracert"]
OPTIONAL_COMMANDS = ["iw", "nmcli", "netsh", "aireplay-ng", "rfkill", "hciconfig", "bluetoothctl", "powershell", "pwsh"]
OPTIONAL_PACKAGES = ["bleak", "scapy", "pywifi"]
OPTIONAL_PACKAGE_SPECS = {
    "bleak": "bleak==0.22.2",
    "scapy": "scapy==2.5.0",
    "pywifi": "pywifi==1.1.12",
}


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


def _display_command_names(system):
    if system == "Windows":
        return ["ipconfig", "arp", "ping", "tracert", "netsh", "powershell", "pwsh"]
    if system == "Linux":
        return ["ip", "ifconfig", "arp", "ping", "traceroute", "tracepath", "nmcli", "iw", "bluetoothctl", "rfkill", "hciconfig", "aireplay-ng"]
    return ["ifconfig", "ping", "traceroute", "arp"]


def _display_feature_names(system):
    common = [
        "Core web UI",
        "Minecraft status lab",
        "Minecraft mob toggles",
        "Interface inventory",
        "Passive ARP scan",
        "Active ping scan",
        "Traceroute",
        "Bluetooth scan",
        "Wi-Fi network scan",
    ]
    if system == "Windows":
        return common + ["Windows Wi-Fi connect"]
    if system == "Linux":
        return common + ["Linux monitor packet scan", "Aireplay deauth"]
    return common


def _display_package_names(system):
    if system == "Windows":
        return ["bleak", "pywifi"]
    if system == "Linux":
        return ["bleak", "scapy"]
    return ["bleak"]


def install_optional_package(package):
    """Install an approved optional package into the current Python environment."""
    if package not in OPTIONAL_PACKAGE_SPECS:
        raise ValueError(f"Unsupported optional package: {package}")

    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", OPTIONAL_PACKAGE_SPECS[package]],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or f"pip failed installing {package}"
        raise RuntimeError(message)
    return {
        "package": package,
        "installed": importlib.util.find_spec(package) is not None,
        "output": result.stdout.strip(),
    }


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

    display_command_names = _display_command_names(system)
    display_feature_names = _display_feature_names(system)
    display_package_names = _display_package_names(system)
    display_commands = {name: commands[name] for name in display_command_names if name in commands}
    display_features = {name: features[name] for name in display_feature_names if name in features}
    display_packages = {name: packages[name] for name in display_package_names if name in packages}

    return {
        "platform": {
            "system": system,
            "release": platform.release(),
            "machine": platform.machine(),
            "python_version": sys.version.split()[0],
        },
        "commands": commands,
        "display_commands": display_commands,
        "packages": packages,
        "display_packages": display_packages,
        "optional_package_specs": OPTIONAL_PACKAGE_SPECS,
        "features": features,
        "display_features": display_features,
        "feature_notes": feature_notes,
    }
