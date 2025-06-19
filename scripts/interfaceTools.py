import subprocess
import socket
from bleak import BleakScanner
import threading
import time
import os
import ipaddress
import re
import shutil

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
        self.update_thread = threading.Thread(target=self.update_state_periodically, daemon=True)
        self.update_thread.start()
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
            17: 'AF_PACKET (MAC)',
            24: 'AF_PPPOX (PPPoX)',
            29: 'AF_CAN (Controller Area Network)',
            31: 'AF_BLUETOOTH (Bluetooth)',
            36: 'AF_IEEE802154 (IEEE 802.15.4)',
            38: 'AF_ALG (Linux crypto API)'
        }
        return family_names.get(family, f'Unknown ({family})')

    def get_mac_address(self):
        for addr in self.addresses:
            if addr['family'] == 'AF_PACKET (MAC)':
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
        """Get the operational state of the interface."""
        state_file = f"/sys/class/net/{self.name}/operstate"
        try:
            with open(state_file) as f:
                state = f.read().strip()
            return 'UP' if state == 'up' else 'DOWN'
        except FileNotFoundError:
            return 'UNKNOWN'

    def update_state(self):
        """Update the state of the interface."""
        new_state = self.get_state()
        if new_state != self.state:
            self.state = new_state

    def update_state_periodically(self, interval=5):
        """Periodically update the state of the interface."""
        while True:
            self.update_state()
            time.sleep(interval)

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
    def __init__(self, address, name):
        self.address = address
        self.name = name

    def __str__(self):
        return (f"Bluetooth Device: {self.name}\n"
                f"  Address: {self.address}\n")

def get_interface_type(name):
    if name.startswith('wlan') or name.startswith('wifi') or name.startswith('wlo'):
        return 'Wireless'
    elif name.startswith('eth') or name.startswith('en'):
        return 'Wired'
    elif name.startswith('lo'):
        return 'Loopback'
    elif name.startswith('br'):
        return 'Bridge'
    elif name.startswith('bond'):
        return 'Bond'
    elif name.startswith('sta'):
        return 'Station'
    else:
        return 'Unknown'


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


def get_network_interfaces():
    base_path = "/sys/class/net"
    interface_names = [
        name
        for name in os.listdir(base_path)
        if os.path.isdir(os.path.join(base_path, name))
    ]
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

        # MAC address
        try:
            with open(f"/sys/class/net/{name}/address") as f:
                mac = f.read().strip()
            network_interface.add_address(socket.AF_PACKET, mac, None, None, None)
        except FileNotFoundError:
            pass

        # IPv4 addresses
        for info in _parse_ip_addrs(name, "inet"):
            network_interface.add_address(
                socket.AF_INET,
                info["address"],
                info["netmask"],
                info["broadcast"],
                None,
            )

        # IPv6 addresses
        for info in _parse_ip_addrs(name, "inet6"):
            network_interface.add_address(
                socket.AF_INET6,
                info["address"],
                info["netmask"],
                info["broadcast"],
                None,
            )

        # Determine manufacturer based on MAC address
        network_interface.manufacturer = lookup_manufacturer(network_interface.get_mac_address())
        network_objects.append(network_interface)
    
    return network_objects


async def get_bluetooth_devices():
    try:
        devices = await BleakScanner.discover()
        bluetooth_objects = [BluetoothDevice(address=device.address, name=device.name) for device in devices]
        return bluetooth_objects
    except Exception as e:
        print(f"Error discovering Bluetooth devices: {e}")
        return []

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

