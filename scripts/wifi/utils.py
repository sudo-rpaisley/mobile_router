import importlib.util
import platform
import re
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
        networks[network_key].add_access_point(_normalize_mac(bssid), channel, signal)


def _normalize_mac(mac):
    return (mac or '').strip().lower()


def _is_usable_device_mac(mac):
    normalized = _normalize_mac(mac)
    if not normalized or normalized == 'ff:ff:ff:ff:ff:ff':
        return False
    first_octet = normalized.split(':', 1)[0]
    try:
        return not bool(int(first_octet, 16) & 1)
    except ValueError:
        return False


def _find_network_by_bssid(bssid):
    normalized_bssid = _normalize_mac(bssid)
    if not normalized_bssid:
        return None, None
    for network in networks.values():
        for ap in network.access_points:
            if _normalize_mac(ap.bssid) == normalized_bssid:
                return network, ap
    return None, None


def _record_observed_device(bssid, device_mac, signal=None):
    """Attach an observed wireless device to the network/AP where it was seen."""
    normalized_bssid = _normalize_mac(bssid)
    normalized_device = _normalize_mac(device_mac)
    if not _is_usable_device_mac(normalized_device) or normalized_device == normalized_bssid:
        return False

    network, ap = _find_network_by_bssid(normalized_bssid)
    if not network or not ap:
        return False

    network.add_client(ap.bssid, normalized_device, signal)
    return True


def _known_bssid_from_addresses(*addresses):
    for address in addresses:
        network, ap = _find_network_by_bssid(address)
        if network and ap:
            return ap.bssid
    return None


def _device_from_addresses(bssid, *addresses):
    normalized_bssid = _normalize_mac(bssid)
    for address in addresses:
        normalized = _normalize_mac(address)
        if normalized != normalized_bssid and _is_usable_device_mac(normalized):
            return normalized
    return None

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



def _network_count():
    return sum(len(network.access_points) for network in networks.values())


def _scan_linux_with_iw(interface_name):
    if not interface_name:
        raise RuntimeError('A wireless interface is required for iw scanning')

    result = _run_command(['iw', 'dev', interface_name, 'scan'], timeout=30)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or 'iw wireless scan failed')

    current_bssid = None
    current_ssid = None
    current_channel = None
    current_signal = None
    current_security = 'Open'

    def flush_bss():
        if current_bssid:
            _add_network(current_ssid, current_bssid, current_channel, current_signal, current_security)

    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith('BSS '):
            flush_bss()
            current_bssid = stripped.split()[1].split('(')[0]
            current_ssid = None
            current_channel = None
            current_signal = None
            current_security = 'Open'
        elif stripped.startswith('SSID:'):
            current_ssid = stripped.split(':', 1)[1].strip()
        elif stripped.startswith('freq:') and current_channel is None:
            current_channel = _parse_signal(stripped.split(':', 1)[1].strip())
        elif stripped.startswith('signal:'):
            signal_value = stripped.split(':', 1)[1].strip().split()[0]
            try:
                current_signal = int(float(signal_value))
            except (TypeError, ValueError):
                current_signal = _parse_signal(signal_value)
        elif stripped.startswith('DS Parameter set:') and 'channel' in stripped:
            current_channel = _parse_signal(stripped.rsplit(' ', 1)[-1])
        elif stripped.startswith('capability:') and 'Privacy' in stripped:
            current_security = 'Secured'
        elif stripped.startswith('RSN:'):
            current_security = 'WPA2/WPA3'
        elif stripped.startswith('WPA:'):
            current_security = 'WPA'

    flush_bss()

def _scan_linux_with_scapy(interface_name, timeout):
    from scapy.all import sniff
    from scapy.layers.dot11 import Dot11, Dot11Beacon, Dot11ProbeResp, Dot11Elt

    if not interface_name:
        raise RuntimeError("A wireless interface is required for packet scanning")

    def sniff_networks(packet):
        if not packet.haslayer(Dot11):
            return

        dot11 = packet[Dot11]
        addr1 = getattr(dot11, 'addr1', None)
        addr2 = getattr(dot11, 'addr2', None)
        addr3 = getattr(dot11, 'addr3', None)
        dbm_signal = getattr(packet, "dBm_AntSignal", None)

        if packet.haslayer(Dot11Beacon) or packet.haslayer(Dot11ProbeResp):
            ssid = packet[Dot11Elt].info.decode(errors="replace") if packet.haslayer(Dot11Elt) else None
            bssid = addr3 or addr2
            channel = None
            if packet.haslayer(Dot11Elt) and packet.getlayer(Dot11Elt, ID=3):
                channel_info = packet.getlayer(Dot11Elt, ID=3).info
                channel = channel_info[0] if channel_info else None
            _add_network(ssid, bssid, channel, dbm_signal)
            return

        bssid = _known_bssid_from_addresses(addr3, addr1, addr2)
        if not bssid:
            return

        device_mac = _device_from_addresses(bssid, addr2, addr1, addr3)
        _record_observed_device(bssid, device_mac, dbm_signal)

    sniff(iface=interface_name, prn=sniff_networks, timeout=timeout)


def _parse_signal(signal):
    try:
        return int(signal)
    except (TypeError, ValueError):
        return signal or None


def _parse_percent_signal(signal):
    value = (signal or '').strip().removesuffix('%')
    return _parse_signal(value)


def _scan_windows_with_netsh(interface_name=None):
    command = ['netsh', 'wlan', 'show', 'networks', 'mode=bssid']
    if interface_name:
        command.append(f'interface={interface_name}')

    result = _run_command(command)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or 'netsh wireless scan failed')

    current_ssid = None
    current_security = None
    current_bssid = None
    current_signal = None
    current_channel = None

    def flush_bssid():
        if current_bssid:
            _add_network(current_ssid, current_bssid, current_channel, current_signal, current_security)

    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped or ':' not in stripped:
            continue

        key, value = [part.strip() for part in stripped.split(':', 1)]
        key_lower = key.lower()

        if key_lower.startswith('ssid ') and value:
            flush_bssid()
            current_ssid = value
            current_security = None
            current_bssid = None
            current_signal = None
            current_channel = None
        elif key_lower == 'authentication':
            current_security = value or 'Open'
        elif key_lower.startswith('bssid '):
            flush_bssid()
            current_bssid = value
            current_signal = None
            current_channel = None
        elif key_lower == 'signal':
            current_signal = _parse_percent_signal(value)
        elif key_lower == 'channel':
            current_channel = _parse_signal(value)

    flush_bssid()


def _scan_windows_with_pywifi(interface_name):
    if importlib.util.find_spec('pywifi') is None:
        raise RuntimeError('Windows Wi-Fi scan requires netsh or the optional pywifi package')

    import pywifi

    wifi = pywifi.PyWiFi()
    ifaces = wifi.interfaces()
    if not ifaces:
        raise RuntimeError('No wireless interfaces found')

    iface = ifaces[0]
    if interface_name:
        iface = next((candidate for candidate in ifaces if candidate.name() == interface_name), iface)

    iface.scan()
    time.sleep(5)  # Wait for the scan to complete
    scan_results = iface.scan_results()

    for network in scan_results:
        _add_network(network.ssid, network.bssid, network.freq, network.signal)

def scan_networks(interface_name=None, timeout=12):
    """Scan nearby wireless networks for the requested interface."""
    global networks
    networks = {}

    system = platform.system()
    if system == "Linux":
        scan_errors = []
        try:
            _scan_linux_with_nmcli(interface_name)
        except (FileNotFoundError, RuntimeError, subprocess.TimeoutExpired) as exc:
            scan_errors.append(str(exc))

        try:
            _scan_linux_with_iw(interface_name)
        except (FileNotFoundError, RuntimeError, subprocess.TimeoutExpired) as exc:
            scan_errors.append(str(exc))

        sniff_timeout = timeout if _network_count() == 0 else min(timeout, 5)
        try:
            _scan_linux_with_scapy(interface_name, sniff_timeout)
        except (FileNotFoundError, RuntimeError, subprocess.TimeoutExpired, ModuleNotFoundError) as exc:
            scan_errors.append(str(exc))
            if _network_count() == 0:
                raise RuntimeError('; '.join(error for error in scan_errors if error) or 'No wireless scan backend succeeded')
    elif system == "Windows":
        scan_errors = []
        try:
            _scan_windows_with_netsh(interface_name)
        except (FileNotFoundError, RuntimeError, subprocess.TimeoutExpired) as exc:
            scan_errors.append(str(exc))

        if _network_count() <= 1:
            try:
                _scan_windows_with_pywifi(interface_name)
            except (FileNotFoundError, RuntimeError, subprocess.TimeoutExpired, ModuleNotFoundError) as exc:
                scan_errors.append(str(exc))

        if _network_count() == 0 and scan_errors:
            raise RuntimeError('; '.join(error for error in scan_errors if error) or 'No wireless scan backend succeeded')
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
        radio = _ap_radio_details(strongest_ap.channel, strongest_ap.signal) if strongest_ap else {}
        results.append({
            'ssid': network.ssid,
            'bssid': strongest_ap.bssid if strongest_ap else None,
            'bssid_manufacturer': _mac_manufacturer(strongest_ap.bssid) if strongest_ap else 'Unknown',
            'channel': radio.get('channel') if strongest_ap else None,
            'freq': radio.get('frequency') if strongest_ap else None,
            'frequency': radio.get('frequency') if strongest_ap else None,
            'band': radio.get('band') if strongest_ap else 'Unknown band',
            'signal': strongest_ap.signal if strongest_ap else None,
            'security': getattr(network, 'security', 'Unknown'),
            'access_points': len(access_points),
        })
    return sorted(results, key=lambda item: item['signal'] if isinstance(item['signal'], int) else -999, reverse=True)


def _mac_manufacturer(mac):
    try:
        from scripts.interfaceTools import lookup_manufacturer
    except ImportError:
        return 'Unknown'
    return lookup_manufacturer(mac)


def _mac_bytes(mac):
    normalized = _normalize_mac(mac)
    parts = normalized.split(':')
    if len(parts) != 6:
        return None
    try:
        return [int(part, 16) for part in parts]
    except ValueError:
        return None


def _ap_identity_reasons(left_bssid, right_bssid):
    left = _mac_bytes(left_bssid)
    right = _mac_bytes(right_bssid)
    if not left or not right:
        return []

    reasons = []
    if left[:5] == right[:5]:
        reasons.append('BSSIDs share the first five octets and differ only by radio/BSSID index')
    if left[1:5] == right[1:5] and abs(left[5] - right[5]) <= 16:
        reasons.append('BSSIDs share the same device-specific suffix with nearby radio indexes')
    if left[:3] == right[:3] and abs(left[5] - right[5]) <= 16:
        reasons.append('BSSIDs share an OUI and nearby last-octet values')
    return reasons


def _group_access_points(access_points):
    """Infer likely physical AP groupings from BSSID patterns for one SSID."""
    if not access_points:
        return [], []

    parents = list(range(len(access_points)))
    group_reasons = {}

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left, right, reasons):
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[right_root] = left_root
        root = find(left_root)
        group_reasons.setdefault(root, set()).update(reasons)

    for left_index, left_ap in enumerate(access_points):
        for right_index in range(left_index + 1, len(access_points)):
            right_ap = access_points[right_index]
            reasons = _ap_identity_reasons(left_ap.get('bssid'), right_ap.get('bssid'))
            if reasons:
                union(left_index, right_index, reasons)

    grouped = {}
    for index, ap in enumerate(access_points):
        root = find(index)
        grouped.setdefault(root, []).append(ap)

    ap_groups = []
    for group_number, (root, members) in enumerate(grouped.items(), start=1):
        reasons = sorted(group_reasons.get(root, []))
        strong_reason = any('first five octets' in reason or 'device-specific suffix' in reason for reason in reasons)
        confidence = 'High' if len(members) > 1 and strong_reason else 'Medium'
        label = f'AP group {group_number}' if len(members) > 1 else 'Unique AP'
        for member in members:
            member['physical_ap_group'] = label
            member['identity_confidence'] = confidence if len(members) > 1 else 'Low'
            member['identity_reasons'] = reasons
        ap_groups.append({
            'label': label,
            'bssids': [member.get('bssid') for member in members],
            'bands': sorted({member.get('band') for member in members if member.get('band') and member.get('band') != 'Unknown band'}),
            'channels': [member.get('channel') for member in members if member.get('channel')],
            'confidence': confidence if len(members) > 1 else 'Low',
            'reasons': reasons,
            'likely_same_physical_ap': len(members) > 1,
        })

    return access_points, ap_groups


def _coerce_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _channel_from_frequency(frequency):
    freq = _coerce_int(frequency)
    if freq is None:
        return None
    if freq == 2484:
        return 14
    if 2412 <= freq <= 2472:
        return int((freq - 2407) / 5)
    if 5000 <= freq <= 5900:
        return int((freq - 5000) / 5)
    if 5955 <= freq <= 7115:
        return int((freq - 5950) / 5)
    return None


def _frequency_from_channel(channel):
    channel_number = _coerce_int(channel)
    if channel_number is None:
        return None
    if channel_number == 14:
        return 2484
    if 1 <= channel_number <= 13:
        return 2407 + (channel_number * 5)
    if 32 <= channel_number <= 177:
        return 5000 + (channel_number * 5)
    return None


def _frequency_band(channel=None, frequency=None):
    freq = _coerce_int(frequency)
    if freq:
        if 2400 <= freq < 2500:
            return '2.4 GHz'
        if 4900 <= freq < 5925:
            return '5 GHz'
        if 5925 <= freq <= 7125:
            return '6 GHz'

    channel_number = _coerce_int(channel)
    if channel_number is None:
        return 'Unknown band'
    if 1 <= channel_number <= 14:
        return '2.4 GHz'
    if 32 <= channel_number <= 177:
        return '5 GHz'
    if 1 <= channel_number <= 233:
        return '6 GHz'
    return 'Unknown band'


def _signal_quality(signal):
    value = _coerce_int(signal)
    if value is None:
        return 'Unknown signal'
    if value >= 0:
        if value >= 70:
            return 'Strong'
        if value >= 40:
            return 'Usable'
        return 'Weak'
    if value >= -55:
        return 'Excellent'
    if value >= -67:
        return 'Good'
    if value >= -75:
        return 'Fair'
    return 'Weak'


def _channel_notes(channel=None, frequency=None):
    notes = []
    channel_number = _coerce_int(channel) or _channel_from_frequency(frequency)
    band = _frequency_band(channel_number, frequency)

    if band == '2.4 GHz':
        if channel_number in {1, 6, 11}:
            notes.append('Preferred non-overlapping 2.4 GHz channel')
        elif channel_number:
            notes.append('Overlaps with nearby 2.4 GHz channels')
    elif band == '5 GHz' and channel_number in range(52, 145):
        notes.append('DFS channel; may be affected by radar events')
    elif band == '6 GHz':
        notes.append('6 GHz requires Wi-Fi 6E/7 client support')

    return notes


def _ap_radio_details(channel=None, signal=None):
    channel_number = _coerce_int(channel)
    frequency = channel_number if channel_number and channel_number > 1000 else _frequency_from_channel(channel_number)
    display_channel = _channel_from_frequency(channel_number) if channel_number and channel_number > 1000 else channel_number

    return {
        'channel': display_channel if display_channel is not None else channel,
        'frequency': frequency,
        'band': _frequency_band(display_channel, frequency),
        'signal_quality': _signal_quality(signal),
        'notes': _channel_notes(display_channel, frequency),
    }


def _format_signal(signal):
    if signal in (None, ''):
        return 'Unknown signal'
    try:
        value = int(signal)
    except (TypeError, ValueError):
        return str(signal)
    return f'{value}%' if value >= 0 else f'{value} dBm'


def get_network_detail(ssid=None, bssid=None, interface_name=None):
    """Return detailed information for a scanned SSID/BSSID, including AP clients."""
    requested_ssid = (ssid or '').strip()
    requested_bssid = (bssid or '').strip().lower()
    matched = None

    for network in networks.values():
        ssid_matches = requested_ssid and network.ssid == requested_ssid
        bssid_matches = requested_bssid and any((ap.bssid or '').lower() == requested_bssid for ap in network.access_points)
        if ssid_matches or bssid_matches:
            matched = network
            break

    access_points = []
    clients = []
    discovered = matched is not None

    if matched:
        for ap in matched.access_points:
            ap_clients = [
                {
                    'mac': client.mac,
                    'signal': client.signal,
                    'signal_label': _format_signal(client.signal),
                    'bssid': ap.bssid,
                    'manufacturer': _mac_manufacturer(client.mac),
                }
                for client in ap.clients
            ]
            radio = _ap_radio_details(ap.channel, ap.signal)
            access_points.append({
                'bssid': ap.bssid,
                'manufacturer': _mac_manufacturer(ap.bssid),
                'channel': radio['channel'],
                'raw_channel': ap.channel,
                'frequency': radio['frequency'],
                'band': radio['band'],
                'signal': ap.signal,
                'signal_label': _format_signal(ap.signal),
                'signal_quality': radio['signal_quality'],
                'notes': radio['notes'],
                'clients': ap_clients,
            })
            clients.extend(ap_clients)
        access_points, ap_groups = _group_access_points(access_points)
        strongest_ap = max(matched.access_points, key=lambda ap: ap.signal if isinstance(ap.signal, int) else -999, default=None)
        detail_ssid = matched.ssid
        security = getattr(matched, 'security', 'Unknown')
        primary_bssid = strongest_ap.bssid if strongest_ap else (bssid or None)
        channel = strongest_ap.channel if strongest_ap else None
        signal = strongest_ap.signal if strongest_ap else None
    else:
        detail_ssid = requested_ssid or '<Hidden SSID>'
        security = 'Unknown'
        primary_bssid = bssid or None
        channel = None
        signal = None
        ap_groups = []

    return {
        'ssid': detail_ssid,
        'bssid': primary_bssid,
        'security': security,
        'channel': channel,
        'signal': signal,
        'signal_label': _format_signal(signal),
        'interface': interface_name,
        'gateway': get_default_gateway(interface_name),
        'bands': sorted({ap['band'] for ap in access_points if ap.get('band') and ap.get('band') != 'Unknown band'}),
        'ap_groups': ap_groups,
        'access_points': access_points,
        'clients': clients,
        'discovered': discovered,
    }


def _parse_linux_default_gateway(output):
    for line in output.splitlines():
        parts = line.split()
        if parts and parts[0] == 'default' and 'via' in parts:
            return parts[parts.index('via') + 1]
    return None


def _parse_windows_default_gateway(output):
    for line in output.splitlines():
        if 'Default Gateway' not in line:
            continue
        _, _, value = line.partition(':')
        gateway = value.strip()
        if gateway:
            return gateway
    for line in output.splitlines():
        match = re.match(r'\s*0\.0\.0\.0\s+0\.0\.0\.0\s+(\S+)\s+', line)
        if match:
            return match.group(1)
    return None


def _lookup_arp_mac(ip_address):
    if not ip_address:
        return None

    commands = []
    if platform.system() == 'Windows':
        commands.append(['arp', '-a', ip_address])
    else:
        commands.extend([
            ['ip', 'neigh', 'show', ip_address],
            ['arp', '-n', ip_address],
        ])

    for command in commands:
        try:
            result = _run_command(command, timeout=5)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
        output = result.stdout or ''
        mac_match = re.search(r'([0-9a-fA-F]{2}(?:[:-][0-9a-fA-F]{2}){5})', output)
        if mac_match:
            return mac_match.group(1).replace('-', ':').lower()
    return None


def get_default_gateway(interface_name=None):
    """Return the default gateway IP/MAC when the host OS exposes it."""
    system = platform.system()
    commands = []
    parser = None

    if system == 'Linux':
        if interface_name:
            commands.append(['ip', 'route', 'show', 'default', 'dev', interface_name])
        commands.append(['ip', 'route', 'show', 'default'])
        parser = _parse_linux_default_gateway
    elif system == 'Windows':
        if interface_name:
            commands.append(['netsh', 'interface', 'ip', 'show', 'config', f'name={interface_name}'])
        commands.append(['route', 'print', '-4', '0.0.0.0'])
        parser = _parse_windows_default_gateway
    else:
        return {'ip': None, 'mac': None, 'manufacturer': 'Unknown'}

    for command in commands:
        try:
            result = _run_command(command, timeout=5)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
        if result.returncode != 0:
            continue
        gateway_ip = parser(result.stdout or '')
        if gateway_ip:
            gateway_mac = _lookup_arp_mac(gateway_ip)
            return {'ip': gateway_ip, 'mac': gateway_mac, 'manufacturer': _mac_manufacturer(gateway_mac)}

    return {'ip': None, 'mac': None, 'manufacturer': 'Unknown'}


def connect_to_network(ssid, password=None, interface_name=None):
    """Attempt to connect to a wireless network using pywifi."""
    if importlib.util.find_spec('pywifi') is None:
        raise RuntimeError('Connecting to Wi-Fi networks requires the optional pywifi package')

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
