import importlib.util
import os
import platform
import shutil
import subprocess
import sys
from typing import Dict, List

from services.oui import oui_database_status

CORE_COMMANDS = ["ip", "ifconfig", "ipconfig", "arp", "ping", "traceroute", "tracepath", "tracert"]
OPTIONAL_COMMANDS = ["iw", "nmcli", "netsh", "aireplay-ng", "rfkill", "hciconfig", "bluetoothctl", "busctl", "powershell", "pwsh", "wkhtmltoimage", "chromium", "chromium-browser", "google-chrome"]
REQUIRED_PACKAGE_SPECS = {
    "blinker": "blinker==1.8.2",
    "click": "click==8.1.7",
    "Flask": "Flask==3.0.3",
    "Flask-SocketIO": "Flask-SocketIO==5.3.6",
    "itsdangerous": "itsdangerous==2.2.0",
    "Jinja2": "Jinja2==3.1.4",
    "MarkupSafe": "MarkupSafe==2.1.5",
    "Werkzeug": "Werkzeug==3.0.3",
}
REQUIRED_PACKAGE_IMPORTS = {
    "Flask": "flask",
    "Flask-SocketIO": "flask_socketio",
    "Jinja2": "jinja2",
    "MarkupSafe": "markupsafe",
}
REQUIRED_PACKAGES = list(REQUIRED_PACKAGE_SPECS)
OPTIONAL_PACKAGES = ["bleak", "scapy", "pywifi"]
OPTIONAL_PACKAGE_SPECS = {
    "bleak": "bleak==0.22.3",
    "scapy": "scapy==2.5.0",
    "pywifi": "pywifi==1.1.12",
}

CENTRAL_CAPABILITY_REGISTRY = [
    {
        "id": "core-web-ui",
        "name": "Core web UI",
        "category": "Core",
        "description": "Dashboard, navigation, theme controls, reports, jobs, and inventory views.",
        "feature": "Core web UI",
        "commands": [],
        "packages": ["Flask", "Flask-SocketIO", "Jinja2"],
    },
    {
        "id": "interface-inventory",
        "name": "Interface inventory",
        "category": "Discovery",
        "description": "List local network adapters, addresses, status, and manufacturer metadata.",
        "feature": "Interface inventory",
        "commands": ["ip", "ifconfig", "ipconfig"],
        "packages": [],
    },
    {
        "id": "oui-vendor-lookup",
        "name": "OUI vendor lookup",
        "category": "Discovery",
        "description": "Resolve MAC/BSSID prefixes to vendors using the bundled database with built-in fallbacks.",
        "feature": "OUI vendor lookup",
        "commands": [],
        "packages": [],
    },
    {
        "id": "passive-arp-scan",
        "name": "Passive ARP scan",
        "category": "Discovery",
        "description": "Read ARP cache entries to discover local devices without probing.",
        "feature": "Passive ARP scan",
        "commands": ["arp"],
        "packages": [],
    },
    {
        "id": "active-ping-scan",
        "name": "Active ping scan",
        "category": "Discovery",
        "description": "Probe local subnets and merge ARP results for live host discovery.",
        "feature": "Active ping scan",
        "commands": ["ping"],
        "packages": [],
    },
    {
        "id": "port-scan",
        "name": "Port scan",
        "category": "Services",
        "description": "Concurrent TCP port scans with live jobs, cancellation, and service hints.",
        "feature": "Port scan",
        "commands": [],
        "packages": [],
    },
    {
        "id": "traceroute",
        "name": "Traceroute",
        "category": "Services",
        "description": "Trace network paths using platform traceroute tools.",
        "feature": "Traceroute",
        "commands": ["traceroute", "tracepath", "tracert"],
        "packages": [],
    },
    {
        "id": "wifi-network-scan",
        "name": "Wi-Fi network scan",
        "category": "Wireless",
        "description": "Discover SSIDs/BSSIDs, channels, bands, security, and signal strength.",
        "feature": "Wi-Fi network scan",
        "commands": ["nmcli", "iw", "netsh"],
        "packages": ["scapy", "pywifi"],
    },
    {
        "id": "linux-monitor-packet-scan",
        "name": "Linux monitor packet scan",
        "category": "Wireless",
        "description": "Use Scapy and monitor-mode adapters for deeper wireless packet visibility.",
        "feature": "Linux monitor packet scan",
        "commands": [],
        "packages": ["scapy"],
    },
    {
        "id": "bluetooth-scan",
        "name": "Bluetooth scan",
        "category": "Bluetooth",
        "description": "Discover Bluetooth devices through Bleak or platform tools.",
        "feature": "Bluetooth scan",
        "commands": ["bluetoothctl", "powershell", "pwsh"],
        "packages": ["bleak"],
    },
    {
        "id": "bluetooth-actions",
        "name": "Bluetooth actions",
        "category": "Bluetooth",
        "description": "Run local Bluetooth info/connect/pair/trust/block/remove actions when BlueZ tooling is available.",
        "feature": "Bluetooth actions",
        "commands": ["bluetoothctl", "busctl"],
        "packages": [],
    },
    {
        "id": "reports",
        "name": "Reports",
        "category": "Operations",
        "description": "Export inventory, alerts, jobs, capabilities, and interfaces as JSON, CSV, Markdown, or HTML.",
        "feature": "Reports",
        "commands": [],
        "packages": [],
    },
    {
        "id": "new-device-alerts",
        "name": "New device alerts",
        "category": "Operations",
        "description": "Raise unread alerts when newly observed non-control devices enter inventory.",
        "feature": "New device alerts",
        "commands": [],
        "packages": [],
    },
]


def command_status(commands: List[str]) -> Dict[str, Dict[str, object]]:
    return {
        command: {
            "available": shutil.which(command) is not None,
            "path": shutil.which(command),
        }
        for command in commands
    }


def package_import_name(package: str) -> str:
    return REQUIRED_PACKAGE_IMPORTS.get(package, package)


def package_status(packages: List[str]) -> Dict[str, bool]:
    return {package: importlib.util.find_spec(package_import_name(package)) is not None for package in packages}


def _available(commands, *names):
    return any(commands.get(name, {}).get("available") for name in names)


def _display_command_names(system):
    if system == "Windows":
        return ["ipconfig", "arp", "ping", "tracert", "netsh", "powershell", "pwsh"]
    if system == "Linux":
        return ["ip", "ifconfig", "arp", "ping", "traceroute", "tracepath", "nmcli", "iw", "bluetoothctl", "busctl", "rfkill", "hciconfig", "aireplay-ng"]
    return ["ifconfig", "ping", "traceroute", "arp"]


def _display_feature_names(system):
    common = [
        "Core web UI",
        "Minecraft status lab",
        "Minecraft mob toggles",
        "Interface inventory",
        "OUI vendor lookup",
        "Passive ARP scan",
        "Active ping scan",
        "Traceroute",
        "Port scan",
        "Reports",
        "New device alerts",
        "Bluetooth scan",
        "Bluetooth actions",
        "Wi-Fi network scan",
    ]
    if system == "Windows":
        return common + ["Windows Wi-Fi connect"]
    if system == "Linux":
        return common + ["Linux monitor packet scan", "Aireplay deauth"]
    return common


def _display_package_names(system):
    # Show every optional Python integration so each one always has a download
    # control, even when it primarily helps another platform.
    return OPTIONAL_PACKAGES


def _busctl_bluez_available(busctl):
    try:
        result = subprocess.run(
            [busctl, "tree", "org.bluez"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _bluetooth_actions_available(commands):
    if commands.get("bluetoothctl", {}).get("available"):
        return True
    busctl = commands.get("busctl", {})
    return bool(busctl.get("available") and _busctl_bluez_available(busctl.get("path")))


def _browser_screenshot_available(commands):
    return any(commands.get(name, {}).get("available") for name in ("wkhtmltoimage", "chromium", "chromium-browser", "google-chrome"))


def _host_dependencies(system, commands):
    if system != "Linux":
        return []

    bluetooth_actions_available = _bluetooth_actions_available(commands)
    return [
        {
            "id": "bluez",
            "name": "BlueZ Bluetooth actions",
            "available": bluetooth_actions_available,
            "details": "Required for Bluetooth device action buttons such as info, connect, disconnect, pair, trust, block, and remove.",
            "install_hint": "Install the distro BlueZ package, then start/enable the bluetooth service. Debian/Ubuntu: sudo apt install bluez && sudo systemctl enable --now bluetooth. Alpine/OpenWrt-style systems may use bluez, bluez-utils, or bluez-daemon packages.",
            "install_action": False,
        },
        {
            "id": "browser-screenshot",
            "name": "Browser screenshot tooling",
            "available": _browser_screenshot_available(commands),
            "details": "Enables HTTP service preview thumbnails for long-hover web-port cards and saved service pages.",
            "install_hint": "Install one of: chromium, chromium-browser, google-chrome, or wkhtmltoimage. Debian/Ubuntu: sudo apt install chromium (or wkhtmltopdf for wkhtmltoimage).",
            "install_action": True,
        },
    ]


def _privilege_prefix():
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return []
    sudo = shutil.which("sudo")
    return [sudo, "-n"] if sudo else []


def browser_screenshot_install_plan():
    """Return package-manager commands to install browser screenshot tooling."""
    prefix = _privilege_prefix()
    if shutil.which("apt-get"):
        return [prefix + ["apt-get", "update"], prefix + ["apt-get", "install", "-y", "chromium"]]
    if shutil.which("apk"):
        return [prefix + ["apk", "add", "--no-cache", "chromium"]]
    if shutil.which("dnf"):
        return [prefix + ["dnf", "install", "-y", "chromium"]]
    if shutil.which("yum"):
        return [prefix + ["yum", "install", "-y", "chromium"]]
    if shutil.which("pacman"):
        return [prefix + ["pacman", "-Sy", "--noconfirm", "chromium"]]
    raise RuntimeError("No supported package manager found. Install chromium, chromium-browser, google-chrome, or wkhtmltoimage manually.")


def install_host_dependency(dependency_id):
    """Install an approved host dependency using the local package manager."""
    if dependency_id != "browser-screenshot":
        raise ValueError(f"Unsupported host dependency: {dependency_id}")
    if _browser_screenshot_available(command_status(["wkhtmltoimage", "chromium", "chromium-browser", "google-chrome"])):
        return {"dependency": dependency_id, "installed": True, "message": "Browser screenshot tooling is already available.", "commands": []}
    commands = browser_screenshot_install_plan()
    outputs = []
    for command in commands:
        if not command or command[0] is None:
            raise RuntimeError("Unable to build an install command for this host.")
        result = subprocess.run(command, capture_output=True, text=True, timeout=600, check=False)
        outputs.append({"command": " ".join(command), "returncode": result.returncode, "stdout": result.stdout[-2000:], "stderr": result.stderr[-2000:]})
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "Host dependency install failed"
            raise RuntimeError(message)
    installed = _browser_screenshot_available(command_status(["wkhtmltoimage", "chromium", "chromium-browser", "google-chrome"]))
    return {"dependency": dependency_id, "installed": installed, "message": "Browser screenshot tooling installed." if installed else "Install command completed but tooling was not found on PATH.", "commands": outputs}


def _install_python_package(package, specs):
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", specs[package]],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or f"pip failed installing {package}"
        raise RuntimeError(message)
    return {
        "package": package,
        "installed": importlib.util.find_spec(package_import_name(package)) is not None,
        "output": result.stdout.strip(),
    }


def install_optional_package(package):
    """Install an approved optional package into the current Python environment."""
    if package not in OPTIONAL_PACKAGE_SPECS:
        raise ValueError(f"Unsupported optional package: {package}")
    return _install_python_package(package, OPTIONAL_PACKAGE_SPECS)


def install_required_package(package):
    """Install an approved required package into the current Python environment."""
    if package not in REQUIRED_PACKAGE_SPECS:
        raise ValueError(f"Unsupported required package: {package}")
    return _install_python_package(package, REQUIRED_PACKAGE_SPECS)


def ensure_required_packages_installed():
    """Auto-download any missing required Python package pins."""
    results = []
    for package, installed in package_status(REQUIRED_PACKAGES).items():
        if not installed:
            results.append(install_required_package(package))
    return results


def build_capability_registry(features, commands, required_packages, packages):
    """Resolve the central capability registry against current runtime status."""
    registry = []
    for capability in CENTRAL_CAPABILITY_REGISTRY:
        command_requirements = {name: commands.get(name, {"available": False, "path": None}) for name in capability.get("commands", [])}
        package_requirements = {}
        for name in capability.get("packages", []):
            package_requirements[name] = required_packages.get(name, packages.get(name, False))
        registry.append({
            **capability,
            "available": bool(features.get(capability.get("feature"), False)),
            "commands_status": command_requirements,
            "packages_status": package_requirements,
        })
    return registry

def build_capabilities() -> Dict[str, object]:
    required_install_results = ensure_required_packages_installed()
    commands = command_status(CORE_COMMANDS + OPTIONAL_COMMANDS)
    required_packages = package_status(REQUIRED_PACKAGES)
    packages = package_status(OPTIONAL_PACKAGES)
    system = platform.system()

    has_windows_shell = _available(commands, "powershell", "pwsh")
    has_bluetooth_scan = bool(
        packages["bleak"]
        or (system == "Windows" and has_windows_shell)
        or (system == "Linux" and commands.get("bluetoothctl", {}).get("available"))
    )
    has_bluetooth_actions = _bluetooth_actions_available(commands)
    has_wifi_network_scan = bool(
        (system == "Windows" and (commands.get("netsh", {}).get("available") or packages["pywifi"]))
        or (system == "Linux" and (_available(commands, "nmcli", "iw") or packages["scapy"]))
    )

    oui_status = oui_database_status()

    features = {
        "Core web UI": True,
        "Minecraft status lab": True,
        "Minecraft mob toggles": True,
        "Interface inventory": bool(commands.get("ip", {}).get("available") or commands.get("ifconfig", {}).get("available") or commands.get("ipconfig", {}).get("available") or system == "Windows"),
        "OUI vendor lookup": bool(oui_status.get("loaded")),
        "Passive ARP scan": bool(commands.get("arp", {}).get("available") or system == "Linux"),
        "Active ping scan": bool(commands.get("ping", {}).get("available")),
        "Traceroute": bool(commands.get("traceroute", {}).get("available") or commands.get("tracepath", {}).get("available") or commands.get("tracert", {}).get("available")),
        "Port scan": True,
        "Reports": True,
        "New device alerts": True,
        "Bluetooth scan": has_bluetooth_scan,
        "Bluetooth actions": has_bluetooth_actions,
        "Wi-Fi network scan": has_wifi_network_scan,
        "Linux monitor packet scan": bool(packages["scapy"] and system == "Linux"),
        "Windows Wi-Fi connect": bool(packages["pywifi"] and system == "Windows"),
        "Aireplay deauth": bool(commands.get("aireplay-ng", {}).get("available")),
    }

    feature_notes = {
        "Bluetooth scan": "Uses Bleak for BLE plus Windows PowerShell or Linux bluetoothctl fallbacks.",
        "Bluetooth actions": "Requires the host BlueZ tools: bluetoothctl, or busctl with a running BlueZ D-Bus service.",
        "Wi-Fi network scan": "Uses nmcli/iw/Scapy on Linux or netsh/pywifi on Windows.",
        "Linux monitor packet scan": "Requires Linux and Scapy; monitor-mode support depends on the adapter/driver.",
        "Windows Wi-Fi connect": "Requires the optional pywifi package for connection management.",
        "Aireplay deauth": "Requires the external aireplay-ng command from aircrack-ng.",
        "Reports": "Exports the current in-memory runtime state; restart-persistent storage is not required.",
        "New device alerts": "Alerts are generated for newly recorded non-control inventory devices.",
        "OUI vendor lookup": "Uses oui/oui_db.csv when available and a built-in fallback set for common lab, router, and virtual-device prefixes.",
    }

    display_command_names = _display_command_names(system)
    display_feature_names = _display_feature_names(system)
    display_package_names = _display_package_names(system)
    display_commands = {name: commands[name] for name in display_command_names if name in commands}
    display_features = {name: features[name] for name in display_feature_names if name in features}
    display_packages = {name: packages[name] for name in display_package_names if name in packages}
    display_host_dependencies = _host_dependencies(system, commands)
    registry = build_capability_registry(features, commands, required_packages, packages)

    return {
        "platform": {
            "system": system,
            "release": platform.release(),
            "machine": platform.machine(),
            "python_version": sys.version.split()[0],
        },
        "commands": commands,
        "display_commands": display_commands,
        "required_packages": required_packages,
        "required_package_specs": REQUIRED_PACKAGE_SPECS,
        "required_install_results": required_install_results,
        "packages": packages,
        "display_packages": display_packages,
        "optional_package_specs": OPTIONAL_PACKAGE_SPECS,
        "display_host_dependencies": display_host_dependencies,
        "features": features,
        "display_features": display_features,
        "feature_notes": feature_notes,
        "registry": registry,
        "display_registry": registry,
        "oui_database": oui_status,
    }
