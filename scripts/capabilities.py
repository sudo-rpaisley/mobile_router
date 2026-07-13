import importlib.util
import platform
import shutil
import sys
from typing import Dict, List

CORE_COMMANDS = ["ip", "ifconfig", "ipconfig", "arp", "ping", "traceroute", "tracepath", "tracert"]
OPTIONAL_COMMANDS = ["iw", "aireplay-ng", "rfkill", "hciconfig"]
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


def build_capabilities() -> Dict[str, object]:
    commands = command_status(CORE_COMMANDS + OPTIONAL_COMMANDS)
    packages = package_status(OPTIONAL_PACKAGES)
    system = platform.system()

    features = {
        "Core web UI": True,
        "Minecraft status lab": True,
        "Minecraft mob toggles": True,
        "Interface inventory": bool(commands.get("ip", {}).get("available") or commands.get("ifconfig", {}).get("available") or commands.get("ipconfig", {}).get("available")),
        "Passive ARP scan": bool(commands.get("arp", {}).get("available") or system == "Linux"),
        "Active ping scan": bool(commands.get("ping", {}).get("available")),
        "Traceroute": bool(commands.get("traceroute", {}).get("available") or commands.get("tracepath", {}).get("available") or commands.get("tracert", {}).get("available")),
        "Bluetooth scan": packages["bleak"],
        "Wi-Fi packet scan": packages["scapy"] and system == "Linux",
        "Windows Wi-Fi connect": packages["pywifi"] and system == "Windows",
        "Aireplay deauth": bool(commands.get("aireplay-ng", {}).get("available")),
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
    }
