import psutil
import bluetooth

class NetworkInterface:
    def __init__(self, name, interface_type):
        self.name = name
        self.interface_type = interface_type
        self.addresses = []

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
    else:
        return 'Unknown'

def get_network_interfaces():
    interfaces = psutil.net_if_addrs()
    network_objects = []

    for name, addresses in interfaces.items():
        interface_type = get_interface_type(name)
        network_interface = NetworkInterface(name, interface_type)
        for address in addresses:
            network_interface.add_address(
                family=address.family,
                address=address.address,
                netmask=address.netmask,
                broadcast=address.broadcast,
                ptp=address.ptp
            )
        network_objects.append(network_interface)
    
    # Print the __str__ representation of each NetworkInterface object
    for network_object in network_objects:
        print(network_object)
    
    return network_objects

def get_bluetooth_devices():
    try:
        bluetooth_devices = bluetooth.discover_devices(duration=8, lookup_names=True, flush_cache=True, lookup_class=False)
        bluetooth_objects = [BluetoothDevice(address=addr, name=name) for addr, name in bluetooth_devices]
        return bluetooth_objects
    except Exception as e:
        print(f"Error discovering Bluetooth devices: {e}")
        return []
    
