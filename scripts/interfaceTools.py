import os
import re
import threading
import time
import asyncio
from bleak import BleakScanner

class NetworkInterface:
    def __init__(self, name, interface_type):
        self.name = name
        self.interface_type = interface_type
        self.state = self.get_state()
        self.addresses = self.get_addresses()
        self.update_thread = threading.Thread(target=self.update_state_periodically, daemon=True)
        self.update_thread.start()

    def get_state(self):
        """Get the state of the interface using system commands."""
        try:
            with open(f'/sys/class/net/{self.name}/operstate') as f:
                state = f.read().strip()
                return 'UP' if state == 'up' else 'DOWN'
        except FileNotFoundError:
            return 'UNKNOWN'
        except NotADirectoryError:
            return 'UNKNOWN'

    def get_addresses(self):
        """Get the IP addresses of the interface using system commands."""
        addresses = []
        try:
            result = os.popen(f'ip addr show {self.name}').read()
            inet_lines = re.findall(r'inet [^\s]+', result)
            inet6_lines = re.findall(r'inet6 [^\s]+', result)

            for line in inet_lines:
                address = line.split()[1]
                addresses.append({'family': 'AF_INET (IPv4)', 'address': address})
            
            for line in inet6_lines:
                address = line.split()[1]
                addresses.append({'family': 'AF_INET6 (IPv6)', 'address': address})
        except Exception as e:
            print(f"Error getting addresses for {self.name}: {e}")

        return addresses

    def get_mac_address(self):
        """Get the MAC address of the interface."""
        for addr in self.addresses:
            if addr['family'] == 'AF_PACKET (MAC)':
                return addr['address']
        return None

    def update_state(self):
        new_state = self.get_state()
        if new_state != self.state:
            self.state = new_state
            print(f"{self.name} state changed to {self.state}")

    def update_state_periodically(self, interval=5):
        while True:
            self.update_state()
            time.sleep(interval)

    def __str__(self):
        addresses_str = "\n".join(
            [f"  Family: {addr['family']}\n"
             f"  Address: {addr['address']}\n"
             for addr in self.addresses]
        )
        return (f"Interface: {self.name}\n"
                f"  Type: {self.interface_type}\n"
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



def get_network_interfaces():
    interfaces = os.listdir('/sys/class/net/')
    network_objects = []

    for name in interfaces:
        if os.path.isdir(f'/sys/class/net/{name}'):
            interface_type = get_interface_type(name)
            network_interface = NetworkInterface(name, interface_type)
            network_objects.append(network_interface)
    
    for network_object in network_objects:
        print(network_object)
    
    return network_objects


async def get_bluetooth_devices():
    try:
        devices = await BleakScanner.discover()
        bluetooth_objects = [BluetoothDevice(address=device.address, name=device.name) for device in devices]
        return bluetooth_objects
    except Exception as e:
        print(f"Error discovering Bluetooth devices: {e}")
        return []


def main():
    # Get and print network interfaces
    network_interfaces = get_network_interfaces()

    # Discover and print Bluetooth devices
    loop = asyncio.get_event_loop()
    bluetooth_devices = loop.run_until_complete(get_bluetooth_devices())
    for device in bluetooth_devices:
        print(device)


if __name__ == "__main__":
    main()

