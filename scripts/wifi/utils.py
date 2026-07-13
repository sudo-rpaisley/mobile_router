import platform
import subprocess
import time
from .network import Network

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


def _add_network(ssid, bssid=None, channel=None, signal=None, security=None):
    network_key = ssid or "<Hidden SSID>"
    if network_key not in networks:
        networks[network_key] = Network(network_key)
        networks[network_key].security = security or "Unknown"
    elif security and getattr(networks[network_key], "security", "Unknown") == "Unknown":
        networks[network_key].security = security

    if bssid:
        networks[network_key].add_access_point(bssid, channel, signal)


def _run_command(command, timeout=20):
    return subprocess.run(command, capture_output=True, check=False, text=True, timeout=timeout)


def _scan_linux_with_nmcli(interface_name):
    command = [
        "nmcli",
        "-t",
        "--escape",
        "no",
        "-f",
        "SSID,BSSID,CHAN,SIGNAL,SECURITY",
        "device",
        "wifi",
        "list",
    ]
    if interface_name:
        command.extend(["ifname", interface_name])
    command.extend(["--rescan", "yes"])

    result = _run_command(command)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "nmcli wireless scan failed")

    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split(":")]
        if len(parts) < 10:
            continue
        security = parts[-1] or "Open"
        signal = parts[-2]
        channel = parts[-3]
        bssid = ":".join(parts[-9:-3])
        ssid = ":".join(parts[:-9])
        _add_network(ssid, bssid, channel, _parse_signal(signal), security)


def _scan_linux_with_scapy(interface_name, timeout):
    from scapy.all import sniff
    from scapy.layers.dot11 import Dot11, Dot11Beacon, Dot11ProbeResp, Dot11Elt, Dot11ProbeReq, Dot11AssoReq, Dot11Addr2, Dot11Addr3

    if not interface_name:
        raise RuntimeError("A wireless interface is required for packet scanning")

    def sniff_networks(packet):
        if packet.haslayer(Dot11Beacon) or packet.haslayer(Dot11ProbeResp):
            ssid = packet[Dot11Elt].info.decode(errors="replace")
            bssid = packet[Dot11].addr3
            channel = None
            if packet.haslayer(Dot11Elt) and packet.getlayer(Dot11Elt, ID=3):
                channel_info = packet.getlayer(Dot11Elt, ID=3).info
                channel = channel_info[0] if channel_info else None
            dbm_signal = getattr(packet, "dBm_AntSignal", None)
            _add_network(ssid, bssid, channel, dbm_signal)

        if packet.haslayer(Dot11AssoReq) or packet.haslayer(Dot11ProbeReq):
            client_mac = packet[Dot11Addr2].addr2
            bssid = packet[Dot11Addr3].addr3
            dbm_signal = getattr(packet, "dBm_AntSignal", None)

            for network in networks.values():
                network.add_client(bssid, client_mac, dbm_signal)

    sniff(iface=interface_name, prn=sniff_networks, timeout=timeout)


def _parse_signal(signal):
    try:
        return int(signal)
    except (TypeError, ValueError):
        return signal or None


def scan_networks(interface_name=None, timeout=12):
    """Scan nearby wireless networks for the requested interface."""
    global networks
    networks = {}

    system = platform.system()
    if system == "Linux":
        try:
            _scan_linux_with_nmcli(interface_name)
        except (FileNotFoundError, RuntimeError, subprocess.TimeoutExpired):
            _scan_linux_with_scapy(interface_name, timeout)
    elif system == "Windows":
        import pywifi

        wifi = pywifi.PyWiFi()
        ifaces = wifi.interfaces()
        if not ifaces:
            raise RuntimeError("No wireless interfaces found")

        iface = ifaces[0]
        if interface_name:
            iface = next((candidate for candidate in ifaces if candidate.name() == interface_name), iface)

        iface.scan()
        time.sleep(5)  # Wait for the scan to complete
        scan_results = iface.scan_results()

        for network in scan_results:
            _add_network(network.ssid, network.bssid, network.freq, network.signal)
    else:
        raise RuntimeError("Wireless scanning is only supported on Linux and Windows")

    track_client_devices()
    detect_rogue_aps()
    send_alerts()
    display_all_networks()


def get_frequent_clients(threshold=3600):
    frequent_clients = {}
    for network in networks.values():
        frequent_clients.update(network.frequent_clients(threshold))
    return frequent_clients


def get_networks_summary():
    """Return a sorted summary of scanned networks grouped by SSID."""
    results = []
    for network in networks.values():
        access_points = network.access_points
        strongest_ap = max(access_points, key=lambda ap: ap.signal if isinstance(ap.signal, int) else -999, default=None)
        results.append({
            'ssid': network.ssid,
            'bssid': strongest_ap.bssid if strongest_ap else None,
            'channel': strongest_ap.channel if strongest_ap else None,
            'freq': strongest_ap.channel if strongest_ap else None,
            'signal': strongest_ap.signal if strongest_ap else None,
            'security': getattr(network, 'security', 'Unknown'),
            'access_points': len(access_points),
        })
    return sorted(results, key=lambda item: item['signal'] if isinstance(item['signal'], int) else -999, reverse=True)


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
            if i.name() == interface_name:
                iface = i
                break
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

MODE_LABELS = {
    'managed': 'Managed',
    'monitor': 'Monitor',
    'ap': 'Access Point',
    'ibss': 'Ad-hoc',
    'mesh point': 'Mesh Point',
    'p2p-client': 'P2P Client',
    'p2p-go': 'P2P Group Owner',
}


def _normalize_mode(mode):
    return (mode or '').strip().lower().replace('__', ' ')


def _parse_supported_modes(output):
    modes = []
    in_modes = False
    for line in output.splitlines():
        stripped = line.strip()
        if stripped == 'Supported interface modes:':
            in_modes = True
            continue
        if in_modes and stripped.startswith('* '):
            modes.append(_normalize_mode(stripped[2:]))
            continue
        if in_modes and stripped and not stripped.startswith('* '):
            break
    return modes


def _parse_current_mode(output):
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith('type '):
            return _normalize_mode(stripped.removeprefix('type '))
    return None


def _get_interface_phy(interface_name):
    phy_name_path = f'/sys/class/net/{interface_name}/phy80211/name'
    try:
        with open(phy_name_path) as phy_name_file:
            return phy_name_file.read().strip()
    except FileNotFoundError:
        return None


def get_adapter_modes(interface_name):
    """Return supported wireless modes and the interface's current mode."""
    if platform.system() != 'Linux':
        return {'current_mode': None, 'supported_modes': []}

    phy_name = _get_interface_phy(interface_name)
    if not phy_name:
        return {'current_mode': None, 'supported_modes': []}

    phy_result = _run_command(['iw', 'phy', phy_name, 'info'])
    if phy_result.returncode != 0:
        raise RuntimeError(phy_result.stderr.strip() or f'Unable to read modes for {interface_name}')

    dev_result = _run_command(['iw', 'dev', interface_name, 'info'])
    if dev_result.returncode != 0:
        raise RuntimeError(dev_result.stderr.strip() or f'Unable to read current mode for {interface_name}')

    supported_modes = _parse_supported_modes(phy_result.stdout)
    current_mode = _parse_current_mode(dev_result.stdout)
    return {
        'current_mode': current_mode,
        'supported_modes': [
            {'value': mode, 'label': MODE_LABELS.get(mode, mode.title())}
            for mode in supported_modes
        ],
    }


def set_adapter_mode(interface_name, mode):
    """Set a wireless adapter mode and return the refreshed mode state."""
    requested_mode = _normalize_mode(mode)
    mode_state = get_adapter_modes(interface_name)
    supported_values = {item['value'] for item in mode_state['supported_modes']}

    if requested_mode not in supported_values:
        raise ValueError(f'{MODE_LABELS.get(requested_mode, requested_mode)} mode is not supported by {interface_name}')

    if mode_state['current_mode'] == requested_mode:
        return mode_state

    commands = [
        ['ip', 'link', 'set', interface_name, 'down'],
        ['iw', 'dev', interface_name, 'set', 'type', requested_mode],
        ['ip', 'link', 'set', interface_name, 'up'],
    ]
    for command in commands:
        result = _run_command(command)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f'Failed to run {" ".join(command)}')

    return get_adapter_modes(interface_name)
