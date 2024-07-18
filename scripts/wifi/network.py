from access_point import AccessPoint
import time

class Network:
    def __init__(self, ssid):
        self.ssid = ssid if ssid else "<Hidden SSID>"
        self.access_points = []
        self.client_last_seen = {}

    def add_access_point(self, bssid, channel, signal):
        if not any(ap.bssid == bssid for ap in self.access_points):
            self.access_points.append(AccessPoint(bssid, channel, signal))

    def add_client(self, bssid, client_mac, signal):
        for ap in self.access_points:
            if ap.bssid == bssid:
                ap.add_client(client_mac, signal)
                self.client_last_seen[client_mac] = time.time()
            else:
                ap.remove_client(client_mac)

    def show_all_clients(self):
        clients = []
        for ap in self.access_points:
            clients.extend(ap.clients)
        return clients

    def frequent_clients(self, threshold=3600):  # threshold in seconds
        current_time = time.time()
        return {mac: last_seen for mac, last_seen in self.client_last_seen.items() if current_time - last_seen <= threshold}

    def __str__(self):
        aps_str = '\n  '.join(str(ap) for ap in self.access_points)
        return f'SSID: {self.ssid}\n  {aps_str}'

    def summary(self):
        aps_summary = '\n  '.join(ap.summary() for ap in self.access_points)
        return f'SSID: {self.ssid}\n  {aps_summary}'
