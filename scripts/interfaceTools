import psutil
import bluetooth

class NetworkInterface:
    def __init__(self, name, family, address, netmask, broadcast, ptp, interface_type):
        self.name = name
        self.family = family
        self.address = address
        self.netmask = netmask
        self.broadcast = broadcast
        self.ptp = ptp
        self.interface_type = interface_type

    def __str__(self):
        return (f"Interface: {self.name}\n"
                f"  Type: {self.interface_type}\n"
                f"  Family: {self.family}\n"
                f"  Address: {self.address}\n"
                f"  Netmask: {self.netmask}\n"
                f"  Broadcast: {self.broadcast}\n"
                f"  PTP: {self.ptp}\n")

class BluetoothDevice:
    def __init__(self, address, name):
        self.address = address
        self.name = name

    def __str__(self):
        return (f"Bluetooth Device: {self.name}\n"
                f"  Address: {self.address}\n")

def get_interface_type(name):
    if name.startswith('wlan') or name.startswith('wifi'):
        return 'Wireless'
    elif name.startswith('eth') or name.startswith('en'):
        return 'Wired'
    else:
        return 'Unknown'

def get_network_interfaces():
    interfaces = psutil.net_if_addrs()
    network_objects = []

    for name, addresses in interfaces.items():
        interface_type = get_interface_type(name)
        for address in addresses:
            network_interface = NetworkInterface(
                name=name,
                family=address.family,
                address=address.address,
                netmask=address.netmask,
                broadcast=address.broadcast,
                ptp=address.ptp,
                interface_type=interface_type
            )
            network_objects.append(network_interface)

    return network_objects

def get_bluetooth_devices():
    try:
        bluetooth_devices = bluetooth.discover_devices(duration=8, lookup_names=True, flush_cache=True, lookup_class=False)
        bluetooth_objects = [BluetoothDevice(address=addr, name=name) for addr, name in bluetooth_devices]
        return bluetooth_objects
    except Exception as e:
        print(f"Error discovering Bluetooth devices: {e}")
        return []