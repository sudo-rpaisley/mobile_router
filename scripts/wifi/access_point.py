from client import Client

class AccessPoint:
    def __init__(self, bssid, channel, signal):
        self.bssid = bssid
        self.channel = channel
        self.signal = signal
        self.clients = []

    def add_client(self, mac, signal):
        existing_client = next((client for client in self.clients if client.mac == mac), None)
        if existing_client:
            existing_client.signal = signal
        else:
            self.clients.append(Client(mac, signal))

    def remove_client(self, mac):
        self.clients = [client for client in self.clients if client.mac != mac]

    def __str__(self):
        clients_str = '\n    '.join(str(client) for client in self.clients)
        return f'BSSID: {self.bssid}, Channel: {self.channel}, Signal: {self.signal} dBm\n    {clients_str}'

    def summary(self):
        return f'BSSID: {self.bssid}, Channel: {self.channel}, Signal: {self.signal} dBm, Clients: {len(self.clients)}'
