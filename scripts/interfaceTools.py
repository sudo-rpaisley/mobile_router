import subprocess
import socket
import platform
import importlib
import importlib.util
import os
import ipaddress
import re
import shutil
import json

AF_PACKET_FAMILY = getattr(socket, "AF_PACKET", 17)
_WINDOWS_INTERFACE_METADATA = {}

# Load a small local OUI database mapping prefixes to manufacturer names
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
GRANDPARENT_DIR = os.path.dirname(PARENT_DIR)

# Try locating the OUI database inside the project directory or one of the
# parent directories. This allows keeping the file outside the repository if
# desired.
OUI_DB_PATH = None
for candidate in [
    os.path.join(BASE_DIR, 'oui', 'oui_db.csv'),
    os.path.join(PARENT_DIR, 'oui', 'oui_db.csv'),
    os.path.join(GRANDPARENT_DIR, 'oui', 'oui_db.csv'),
]:
    if os.path.exists(candidate):
        OUI_DB_PATH = candidate
        break

def _load_oui_db():
    """Load the OUI database from the detected path if available."""
    db = {}
    if OUI_DB_PATH and os.path.exists(OUI_DB_PATH):
        with open(OUI_DB_PATH) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                prefix, name = line.split(',', 1)
                db[prefix.lower()] = name.strip()
    return db

OUI_DB = _load_oui_db()


def _normalize_interface_state(status, interface_type=None):
    """Normalize platform-specific adapter status strings for display."""
    normalized = str(status or '').strip().casefold()
    normalized_type = str(interface_type or '').strip().casefold()

    if normalized in {'up', 'connected', 'running', 'ok'}:
        return 'UP'
    if normalized_type == 'bluetooth' and normalized == 'disconnected':
        return 'UP'
    if normalized in {'down', 'disconnected', 'disabled', 'error', 'degraded', 'not present', 'notpresent', 'unknown'}:
        return 'DOWN'
    return 'UNKNOWN'

def lookup_manufacturer(mac):
    """Return the vendor for the given MAC address using the local OUI database."""
    if not mac:
        return 'Unknown'

    normalized = ':'.join(mac.lower().split(':')[:3])

    return OUI_DB.get(normalized, 'Unknown')

class NetworkInterface:
    def __init__(self, name, interface_type):
        self.name = name
        self.interface_type = interface_type
        self.state = self.get_state()  # Initialize the state when the object is created
        self.addresses = []
        self.manufacturer = 'Unknown'
        self.extra_info = {}

    def add_address(self, family, address, netmask, broadcast, ptp):
        self.addresses.append({
            'family': self.family_name(family),
            'address': address,
            'netmask': netmask,
            'broadcast': broadcast,
            'ptp': ptp
        })

    def family_name(self, family):
        family_names = {
            1: 'AF_UNIX (Unix domain sockets)',
            2: 'AF_INET (IPv4)',
            10: 'AF_INET6 (IPv6)',
            16: 'AF_APPLETALK (AppleTalk)',
            AF_PACKET_FAMILY: 'AF_PACKET (MAC)',
            getattr(socket, 'AF_LINK', 18): 'AF_LINK (MAC)',
            24: 'AF_PPPOX (PPPoX)',
            29: 'AF_CAN (Controller Area Network)',
            31: 'AF_BLUETOOTH (Bluetooth)',
            36: 'AF_IEEE802154 (IEEE 802.15.4)',
            38: 'AF_ALG (Linux crypto API)'
        }
        return family_names.get(family, f'Unknown ({family})')

    def get_mac_address(self):
        for addr in self.addresses:
            if addr['family'] in {'AF_PACKET (MAC)', 'AF_LINK (MAC)'}:
                return addr['address']
        return None

    def get_ipv4(self):
        for addr in self.addresses:
            if addr['family'] == 'AF_INET (IPv4)':
                return addr['address']
        return None

    def get_ipv6(self):
        for addr in self.addresses:
            if addr['family'] == 'AF_INET6 (IPv6)':
                return addr['address']
        return None

    def get_state(self):
        """Get the operational state of the interface when the OS exposes it."""
        metadata_status = _WINDOWS_INTERFACE_METADATA.get(self.name, {}).get("Status")
        if metadata_status:
            return _normalize_interface_state(metadata_status, self.interface_type)

        state_file = f"/sys/class/net/{self.name}/operstate"
        if os.path.exists(state_file):
            try:
                with open(state_file) as f:
                    state = f.read().strip()
                return _normalize_interface_state(state, self.interface_type)
            except OSError:
                return 'UNKNOWN'
        return 'UNKNOWN'

    def update_state(self):
        """Update the state of the interface."""
        new_state = self.get_state()
        if new_state != self.state:
            self.state = new_state

    def to_dict(self):
        return {
            'name': self.name,
            'interface_type': self.interface_type,
            'state': self.state,
            'addresses': self.addresses,
            'manufacturer': self.manufacturer,
            'extra_info': self.extra_info,
        }

    def __eq__(self, other):
        if not isinstance(other, NetworkInterface):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __str__(self):
        addresses_str = "\n".join(
            [f"  Family: {addr['family']}\n"
             f"  Address: {addr['address']}\n"
             f"  Netmask: {addr['netmask']}\n"
             f"  Broadcast: {addr['broadcast']}\n"
             f"  PTP: {addr['ptp']}\n"
             for addr in self.addresses]
        )
        return (f"Interface: {self.name}\n"
                f"  Type: {self.interface_type}\n"
                f"  Manufacturer: {self.manufacturer}\n"
                f"  State: {self.state}\n"
                f"{addresses_str}\n")


class BluetoothDevice:
    def __init__(self, address, name, **metadata):
        self.address = address
        self.name = name
        self.metadata = {key: value for key, value in metadata.items() if value not in (None, '')}

    def to_dict(self):
        return {
            'address': self.address,
            'name': self.name,
            **self.metadata,
        }

    def __str__(self):
        metadata = "\n".join(f"  {key}: {value}" for key, value in self.metadata.items())
        return (f"Bluetooth Device: {self.name}\n"
                f"  Address: {self.address}\n"
                f"{metadata}\n")

def _powershell_json(command):
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        return []
    try:
        output = subprocess.check_output(
            [powershell, "-NoProfile", "-NonInteractive", "-Command", command],
            encoding="utf-8",
            errors="ignore",
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if not output.strip():
        return []
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, dict):
        return [payload]
    return payload if isinstance(payload, list) else []


def _get_windows_bluetooth_pnp_metadata():
    devices = _powershell_json(
        "Get-PnpDevice -Class Bluetooth -PresentOnly:$false | "
        "Select-Object FriendlyName,Name,Status,Class,InstanceId | "
        "ConvertTo-Json -Compress"
    )
    metadata = {}
    for device in devices:
        if not isinstance(device, dict):
            continue
        name = device.get("FriendlyName") or device.get("Name")
        if not name:
            continue
        metadata[name] = {
            "Name": name,
            "InterfaceDescription": name,
            "Status": device.get("Status") or "DOWN",
            "MediaType": "Bluetooth",
            "PhysicalMediaType": "Bluetooth",
            "PnpInstanceId": device.get("InstanceId"),
        }
    return metadata


def _get_windows_adapter_metadata():
    """Return Windows adapter information indexed by friendly name."""

    adapters = _powershell_json(
        "Get-NetAdapter -IncludeHidden | "
        "Select-Object Name,InterfaceDescription,Status,"
        "MediaType,PhysicalMediaType | "
        "ConvertTo-Json -Compress"
    )
    metadata = {
        adapter["Name"]: adapter
        for adapter in adapters
        if isinstance(adapter, dict) and adapter.get("Name")
    }

    for name, bluetooth_metadata in _get_windows_bluetooth_pnp_metadata().items():
        metadata.setdefault(name, bluetooth_metadata)

    return metadata

def get_interface_type(name):
    normalized_name = name.casefold()

    metadata = _WINDOWS_INTERFACE_METADATA.get(name, {})
    description = str(
        metadata.get("InterfaceDescription") or ""
    ).casefold()

    combined = f"{normalized_name} {description}"

    if "bluetooth" in combined:
        return "Bluetooth"

    vpn_markers = (
        "vpn",
        "openvpn",
        "nordvpn",
        "wireguard",
        "tap-",
        "wintun",
        "tailscale",
        "zerotier",
    )
    if any(marker in combined for marker in vpn_markers):
        return "VPN"

    virtual_markers = (
        "vmware",
        "vmnet",
        "virtualbox",
        "hyper-v",
        "vethernet",
        "virtual ethernet",
        "docker",
        "wsl",
    )
    if any(marker in combined for marker in virtual_markers):
        return "Virtual"

    wireless_markers = (
        "wi-fi",
        "wifi",
        "wireless",
        "802.11",
    )
    if (
        normalized_name.startswith(("wlan", "wlo"))
        or any(marker in combined for marker in wireless_markers)
    ):
        return "Wireless"

    if (
        normalized_name == "lo"
        or normalized_name.startswith("loopback")
    ):
        return "Loopback"

    if normalized_name.startswith("br"):
        return "Bridge"

    if normalized_name.startswith("bond"):
        return "Bond"

    if normalized_name.startswith("sta"):
        return "Station"

    if (
        normalized_name.startswith(("eth", "en"))
        or "ethernet" in combined
        or normalized_name.startswith("local area connection")
    ):
        return "Wired"

    return "Unknown"


def _parse_ip_addrs(name, family):
    """Return a list of address dictionaries for the given interface."""
    try:
        output = subprocess.check_output([
            "ip", "-o", "-f", family, "addr", "show", name
        ], encoding="utf-8")
    except Exception:
        return []

    results = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        addr = parts[3]
        broadcast = None
        if "brd" in parts:
            idx = parts.index("brd")
            if idx + 1 < len(parts):
                broadcast = parts[idx + 1]

        if "/" in addr:
            ip, prefix = addr.split("/", 1)
            try:
                if family == "inet":
                    netmask = str(ipaddress.IPv4Network("0.0.0.0/" + prefix).netmask)
                else:
                    netmask = str(ipaddress.IPv6Network("::/" + prefix).netmask)
            except Exception:
                netmask = None
        else:
            ip = addr
            netmask = None

        results.append({
            "address": ip,
            "netmask": netmask,
            "broadcast": broadcast,
        })
    return results


def get_bridge_ports(name):
    """Return a list of interfaces attached to a bridge."""
    path = f"/sys/class/net/{name}/brif"
    try:
        return os.listdir(path)
    except Exception:
        return []


def get_bond_slaves(name):
    """Return the slave interfaces for a bonding device."""
    path = f"/sys/class/net/{name}/bonding/slaves"
    try:
        with open(path) as f:
            return f.read().strip().split()
    except Exception:
        return []


def get_station_info(name):
    """Return connection info for a station interface."""
    try:
        output = subprocess.check_output(["iw", name, "link"], encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _list_interface_names():
    """Return user-facing network-interface names."""

    base_path = "/sys/class/net"
    if os.path.isdir(base_path):
        return [
            name
            for name in os.listdir(base_path)
            if os.path.isdir(os.path.join(base_path, name))
        ]

    if platform.system() == "Windows":
        metadata = _get_windows_adapter_metadata()

        _WINDOWS_INTERFACE_METADATA.clear()
        _WINDOWS_INTERFACE_METADATA.update(metadata)

        if metadata:
            return list(metadata)

    try:
        return [name for _, name in socket.if_nameindex()]
    except OSError:
        return []


def _parse_unix_ifconfig(name):
    """Parse IPv4, IPv6, and MAC details from ifconfig on macOS/BSD/minimal Linux."""
    ifconfig_tool = shutil.which("ifconfig")
    if not ifconfig_tool:
        return {"mac": None, "ipv4": [], "ipv6": []}

    try:
        output = subprocess.check_output([ifconfig_tool, name], encoding="utf-8", errors="ignore")
    except Exception:
        return {"mac": None, "ipv4": [], "ipv6": []}

    mac = None
    ipv4 = []
    ipv6 = []
    for line in output.splitlines():
        stripped = line.strip()
        mac_match = re.search(r"(?:ether|HWaddr)\s+([0-9A-Fa-f:]{17})", stripped)
        if mac_match:
            mac = mac_match.group(1).lower()

        inet_match = re.search(r"inet (?:addr:)?(\d+(?:\.\d+){3})", stripped)
        if inet_match and not stripped.startswith("inet6"):
            netmask_match = re.search(r"(?:netmask |Mask:)(0x[0-9A-Fa-f]+|\d+(?:\.\d+){3})", stripped)
            broadcast_match = re.search(r"(?:broadcast |Bcast:)(\d+(?:\.\d+){3})", stripped)
            netmask = netmask_match.group(1) if netmask_match else None
            if netmask and netmask.startswith("0x"):
                try:
                    netmask = str(ipaddress.IPv4Address(int(netmask, 16)))
                except ValueError:
                    netmask = None
            ipv4.append({"address": inet_match.group(1), "netmask": netmask, "broadcast": broadcast_match.group(1) if broadcast_match else None})

        inet6_match = re.search(r"inet6 (?:addr: )?([0-9A-Fa-f:]+)", stripped)
        if inet6_match:
            ipv6.append({"address": inet6_match.group(1), "netmask": None, "broadcast": None})

    return {"mac": mac, "ipv4": ipv4, "ipv6": ipv6}


def _parse_windows_ipconfig(name):
    """Parse IPv4, IPv6 and MAC details from ipconfig /all."""

    empty_result = {
        "mac": None,
        "ipv4": [],
        "ipv6": [],
    }

    try:
        output = subprocess.check_output(
            ["ipconfig", "/all"],
            encoding="utf-8",
            errors="ignore",
        )
    except (OSError, subprocess.SubprocessError):
        return empty_result

    # Find adapter headings such as:
    # Ethernet adapter Ethernet:
    # Wireless LAN adapter WiFi:
    adapter_pattern = re.compile(
        r"^[^\r\n]*?\badapter\s+(.+?):\s*$",
        re.IGNORECASE | re.MULTILINE,
    )

    matches = list(adapter_pattern.finditer(output))

    for index, match in enumerate(matches):
        adapter_name = match.group(1).strip()

        if adapter_name.casefold() != name.casefold():
            continue

        section_start = match.end()
        section_end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(output)
        )
        section = output[section_start:section_end]

        mac = None
        ipv4 = []
        ipv6 = []

        for line in section.splitlines():
            if "Physical Address" in line:
                value = line.split(":", 1)[-1].strip()
                value = value.replace("-", ":").lower()

                if re.fullmatch(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", value):
                    mac = value

            elif "IPv4 Address" in line:
                value = line.split(":", 1)[-1]
                value = value.split("(")[0].strip()

                ipv4.append({
                    "address": value,
                    "netmask": None,
                    "broadcast": None,
                })

            elif "Subnet Mask" in line and ipv4:
                value = line.split(":", 1)[-1].strip()
                ipv4[-1]["netmask"] = value

            elif "IPv6 Address" in line:
                value = line.split(":", 1)[-1]
                value = value.split("(")[0].strip()

                ipv6.append({
                    "address": value,
                    "netmask": None,
                    "broadcast": None,
                })

        return {
            "mac": mac,
            "ipv4": ipv4,
            "ipv6": ipv6,
        }

    return empty_result


def _get_interface_details(name):
    if platform.system() == "Windows":
        return _parse_windows_ipconfig(name)

    details = _parse_unix_ifconfig(name)
    linux_mac_path = f"/sys/class/net/{name}/address"
    if os.path.exists(linux_mac_path):
        try:
            with open(linux_mac_path) as f:
                details["mac"] = f.read().strip()
        except OSError:
            pass

    ip_tool = shutil.which("ip")
    if ip_tool:
        details["ipv4"] = _parse_ip_addrs(name, "inet")
        details["ipv6"] = _parse_ip_addrs(name, "inet6")

    return details


def get_network_interfaces():
    interface_names = _list_interface_names()
    network_objects = []

    for name in interface_names:
        interface_type = get_interface_type(name)
        network_interface = NetworkInterface(name, interface_type)

        if interface_type == 'Bridge':
            network_interface.extra_info['ports'] = get_bridge_ports(name)
        elif interface_type == 'Bond':
            network_interface.extra_info['slaves'] = get_bond_slaves(name)
        elif interface_type == 'Station':
            network_interface.extra_info['link'] = get_station_info(name)

        details = _get_interface_details(name)
        if details["mac"]:
            network_interface.add_address(AF_PACKET_FAMILY, details["mac"], None, None, None)

        for info in details["ipv4"]:
            network_interface.add_address(socket.AF_INET, info["address"], info["netmask"], info["broadcast"], None)

        for info in details["ipv6"]:
            network_interface.add_address(socket.AF_INET6, info["address"], info["netmask"], info["broadcast"], None)

        network_interface.manufacturer = lookup_manufacturer(network_interface.get_mac_address())
        network_objects.append(network_interface)

    return network_objects


def _dedupe_bluetooth_devices(devices):
    seen = set()
    unique = []
    for device in devices:
        key = (device.address or device.name or '').casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(device)
    return unique


def _parse_windows_bluetooth_devices(output):
    if not output.strip():
        return []

    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return []

    if isinstance(payload, dict):
        payload = [payload]

    devices = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = item.get('FriendlyName') or item.get('Name')
        instance_id = item.get('InstanceId') or ''
        address_match = re.search(r'([0-9A-Fa-f]{12})', instance_id)
        address = None
        if address_match:
            raw = address_match.group(1).lower()
            address = ':'.join(raw[index:index + 2] for index in range(0, 12, 2))
        if name or address:
            devices.append(BluetoothDevice(
                address or instance_id,
                name or 'Unknown',
                status=item.get('Status'),
                instance_id=instance_id,
                device_class=item.get('Class'),
                pnp_manufacturer=item.get('Manufacturer'),
                service=item.get('Service'),
            ))
    return devices


def _get_windows_bluetooth_devices():
    powershell = shutil.which('powershell') or shutil.which('pwsh')
    if not powershell:
        return []

    try:
        output = subprocess.check_output(
            [
                powershell,
                '-NoProfile',
                '-NonInteractive',
                '-Command',
                (
                    "Get-PnpDevice -Class Bluetooth | "
                    "Where-Object { $_.FriendlyName -or $_.Name } | "
                    "Select-Object FriendlyName,Name,InstanceId,Status,Class,Manufacturer,Service | "
                    "ConvertTo-Json -Compress"
                ),
            ],
            encoding='utf-8',
            errors='ignore',
        )
    except (OSError, subprocess.SubprocessError):
        return []

    return _parse_windows_bluetooth_devices(output)


def _parse_bluetoothctl_devices(output):
    devices = []
    for line in output.splitlines():
        match = re.match(r'Device\s+([0-9A-Fa-f:]{17})\s+(.+)', line.strip())
        if match:
            devices.append(BluetoothDevice(match.group(1).lower(), match.group(2).strip()))
    return devices


def _get_linux_bluetooth_devices(timeout=8):
    bluetoothctl = shutil.which('bluetoothctl')
    if not bluetoothctl:
        return []

    try:
        subprocess.run([bluetoothctl, '--timeout', str(timeout), 'scan', 'on'], capture_output=True, text=True, timeout=timeout + 3)
        output = subprocess.check_output([bluetoothctl, 'devices'], encoding='utf-8', errors='ignore')
    except (OSError, subprocess.SubprocessError):
        return []

    return _parse_bluetoothctl_devices(output)


async def get_bluetooth_devices(timeout=10):
    bluetooth_objects = []

    if importlib.util.find_spec("bleak") is not None:
        bleak_module = importlib.import_module("bleak")
        try:
            devices = await bleak_module.BleakScanner.discover(timeout=timeout)
            for device in devices:
                bluetooth_objects.append(BluetoothDevice(
                    address=device.address,
                    name=device.name,
                    details=getattr(device, 'details', None),
                    rssi=getattr(device, 'rssi', None),
                ))
        except Exception as e:
            print(f"Error discovering BLE devices: {e}")
    else:
        print("Bluetooth BLE scan unavailable: bleak is not installed")

    if platform.system() == "Windows":
        bluetooth_objects.extend(_get_windows_bluetooth_devices())
    elif platform.system() == "Linux":
        bluetooth_objects.extend(_get_linux_bluetooth_devices(timeout=timeout))

    return _dedupe_bluetooth_devices(bluetooth_objects)

def spoof_mac(interface, new_mac):
    """Change the MAC address of a network interface.

    This attempts to use the ``ip`` command if available and falls back to
    ``ifconfig``. A simple MAC address validation is performed before
    executing the commands.
    """

    mac_re = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
    if not mac_re.match(new_mac):
        print(f"Invalid MAC address: {new_mac}")
        return False

    ip_tool = shutil.which("ip")
    if ip_tool:
        cmds = [
            [ip_tool, "link", "set", interface, "down"],
            [ip_tool, "link", "set", interface, "address", new_mac],
            [ip_tool, "link", "set", interface, "up"],
        ]
    else:
        ifconfig_tool = shutil.which("ifconfig")
        if not ifconfig_tool:
            print("Neither 'ip' nor 'ifconfig' command found")
            return False
        cmds = [
            [ifconfig_tool, interface, "down"],
            [ifconfig_tool, interface, "hw", "ether", new_mac],
            [ifconfig_tool, interface, "up"],
        ]

    for cmd in cmds:
        try:
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError as e:
            print(f"Failed to run {' '.join(cmd)}: {e}")
            return False
        except FileNotFoundError as e:
            print(str(e))
            return False

    return True

