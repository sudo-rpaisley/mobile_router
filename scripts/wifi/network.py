from .access_point import AccessPoint
import time

class Network:
    def __init__(self, ssid):
        self.ssid = ssid if ssid else "<Hidden SSID>"
        self.access_points = []
        self.client_last_seen = {}

    def add_access_point(self, bssid, channel, signal, wps=False, wps_status=None, channel_width=None, width_source='inferred'):
        existing = next((ap for ap in self.access_points if ap.bssid == bssid), None)
        if existing:
            existing.channel = channel if channel is not None else existing.channel
            existing.signal = signal if signal is not None else existing.signal
            existing.wps = existing.wps or wps is True
            existing.wps_status = wps_status or existing.wps_status
            existing.channel_width = channel_width or existing.channel_width
            existing.width_source = width_source or existing.width_source
            return
        self.access_points.append(AccessPoint(bssid, channel, signal, wps, wps_status, channel_width, width_source))

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
