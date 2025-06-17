import platform
import time
from network import Network

# Global dictionary to store networks
networks = {}

# Add the BSSIDs of authorized access points here
authorized_aps = {
    "d6:21:f9:d9:c9:49",  # Replace with actual authorized BSSIDs
    "e2:21:f9:d9:c9:48",
    "72:8e:29:d0:4a:73",
    "0c:8e:29:d0:4a:72",
    "e8:8f:6f:9:fb:8c",
    "d6:92:5e:1a:60:3b",
    "d6:92:5e:61:15:d8",
    "d4:92:5e:61:15:d0",
    "da:21:f9:d9:c9:49"
}

tracked_clients = {}  # Format: {"client_mac": {"last_seen": timestamp, "signal": signal}}
alerts = []

def display_all_networks():
    for network in networks.values():
        print(network)
        clients = network.show_all_clients()
        if clients:
            print("Clients:")
            for client in clients:
                print(f"  {client}")

def track_client_devices():
    global tracked_clients
    current_time = time.time()
    for network in networks.values():
        for ap in network.access_points:
            for client in ap.clients:
                tracked_clients[client.mac] = {"last_seen": current_time, "signal": client.signal}

    # Remove clients that have not been seen for a while (e.g., 5 minutes)
    timeout = 300
    tracked_clients = {mac: info for mac, info in tracked_clients.items() if current_time - info["last_seen"] < timeout}

def detect_rogue_aps():
    global alerts
    for network in networks.values():
        for ap in network.access_points:
            if ap.bssid not in authorized_aps:
                alert = f"Rogue AP detected: BSSID {ap.bssid}, SSID {network.ssid}"
                alerts.append(alert)

def send_alerts():
    for alert in alerts:
        print(alert)
    alerts.clear()

def scan_networks():
    global networks
    if platform.system() == "Linux":
        from scapy.all import sniff
        from scapy.layers.dot11 import Dot11, Dot11Beacon, Dot11ProbeResp, Dot11Elt, Dot11ProbeReq, Dot11AssoReq, Dot11Addr2, Dot11Addr3

        def sniff_networks(packet):
            if packet.haslayer(Dot11Beacon) or packet.haslayer(Dot11ProbeResp):
                ssid = packet[Dot11Elt].info.decode()
                bssid = packet[Dot11].addr3
                channel = int(ord(packet[Dot11Elt:3].info))
                dbm_signal = packet.dBm_AntSignal

                if ssid not in networks:
                    networks[ssid] = Network(ssid)
                networks[ssid].add_access_point(bssid, channel, dbm_signal)
            
            if packet.haslayer(Dot11AssoReq) or packet.haslayer(Dot11ProbeReq):
                client_mac = packet[Dot11Addr2].addr2
                bssid = packet[Dot11Addr3].addr3
                dbm_signal = packet.dBm_AntSignal

                for network in networks.values():
                    network.add_client(bssid, client_mac, dbm_signal)

        print("Starting network scan on Linux...")
        sniff(iface="wlan0", prn=sniff_networks, timeout=60)
        print("Network scan completed.")
        track_client_devices()
        detect_rogue_aps()
        send_alerts()
        display_all_networks()

    elif platform.system() == "Windows":
        import pywifi
        from pywifi import const

        wifi = pywifi.PyWiFi()
        iface = wifi.interfaces()[0]

        iface.scan()
        time.sleep(5)  # Wait for the scan to complete
        scan_results = iface.scan_results()

        networks = {}
        for network in scan_results:
            ssid = network.ssid
            bssid = network.bssid
            signal = network.signal
            channel = network.freq

            if ssid not in networks:
                networks[ssid] = Network(ssid)
            networks[ssid].add_access_point(bssid, channel, signal)

        print("Network scan completed.")
        track_client_devices()
        detect_rogue_aps()
        send_alerts()
        display_all_networks()

    else:
        print("Unsupported platform. This script only supports Linux and Windows.")

def get_frequent_clients(threshold=3600):
    frequent_clients = {}
    for network in networks.values():
        frequent_clients.update(network.frequent_clients(threshold))
    return frequent_clients
def get_networks_summary():
    """Return a list summary of scanned networks."""
    results = []
    for network in networks.values():
        for ap in network.access_points:
            results.append({
                'ssid': network.ssid,
                'bssid': ap.bssid,
                'freq': ap.channel,
                'signal': ap.signal
            })
    return results


def connect_to_network(ssid, password=None, interface_name=None):
    """Attempt to connect to a wireless network using pywifi."""
    import pywifi
    from pywifi import const

    wifi = pywifi.PyWiFi()
    ifaces = wifi.interfaces()
    if not ifaces:
        raise RuntimeError("No wireless interfaces found")

    iface = None
    if interface_name:
        for i in ifaces:
            try:
                if i.name() == interface_name:
                    iface = i
                    break
            except Exception:
                continue
    if iface is None:
        iface = ifaces[0]

    iface.disconnect()
    time.sleep(1)

    profile = pywifi.Profile()
    profile.ssid = ssid
    profile.auth = const.AUTH_ALG_OPEN
    if password:
        profile.akm.append(const.AKM_TYPE_WPA2PSK)
        profile.cipher = const.CIPHER_TYPE_CCMP
        profile.key = password
    else:
        profile.akm.append(const.AKM_TYPE_NONE)
        profile.cipher = const.CIPHER_TYPE_NONE

    iface.remove_all_network_profiles()
    tmp_profile = iface.add_network_profile(profile)
    iface.connect(tmp_profile)
    time.sleep(5)
    if iface.status() == const.IFACE_CONNECTED:
        return True
    iface.disconnect()
    return False

