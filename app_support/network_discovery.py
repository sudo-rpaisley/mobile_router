"""Pure parsers and merge helpers for network discovery."""

import re
import uuid

from app_support.identifiers import normalize_mac

def classify_service_role(service_type, text=''):
    value = f"{service_type or ''} {text or ''}".lower()
    if any(term in value for term in ['printer', 'ipp', 'pdl-datastream']):
        return 'Printer'
    if any(term in value for term in ['airplay', 'media', 'spotify', 'raop', 'dlna', 'mediarenderer']):
        return 'Media device'
    if any(term in value for term in ['router', 'gateway', 'internetgatewaydevice', 'wanipconnection']):
        return 'Gateway/router'
    if any(term in value for term in ['workstation', 'smb', 'ssh', 'http']):
        return 'Host service'
    return 'Service endpoint'

def _parse_mdns_output(output):
    services = []
    for line in (output or '').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = [part.strip() for part in line.split(';')]
        if len(parts) >= 9 and parts[0] == '=':
            txt = ';'.join(parts[9:]) if len(parts) > 9 else ''
            services.append({
                'interface': parts[1],
                'protocol': parts[2],
                'name': parts[3],
                'service_type': parts[4],
                'domain': parts[5],
                'hostname': parts[6],
                'ip': parts[7],
                'port': parts[8],
                'txt': txt,
                'role': classify_service_role(parts[4], txt),
            })
    return services

def _parse_ssdp_response(response):
    headers = {}
    for line in response.split('\r\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            headers[key.strip().lower()] = value.strip()
    location = headers.get('location') or ''
    host = ''
    try:
        from urllib.parse import urlparse
        host = urlparse(location).hostname or ''
    except Exception:
        host = ''
    service_type = headers.get('st') or headers.get('nt') or ''
    return {
        'ip': host,
        'friendly_name': headers.get('server') or headers.get('usn') or 'UPnP device',
        'manufacturer': headers.get('manufacturer') or headers.get('server') or 'Unknown',
        'model': headers.get('modelname') or headers.get('server') or '',
        'service_type': service_type,
        'control_url': location,
        'usn': headers.get('usn'),
        'role': classify_service_role(service_type, headers.get('server')),
        'headers': headers,
    }

def _parse_lldpctl_keyvalue(output):
    neighbors = []
    current = {}
    for line in (output or '').splitlines():
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"')
        if key.endswith('.chassis.name'):
            if current:
                neighbors.append(current)
            current = {'name': value, 'protocol': 'LLDP/CDP'}
        elif key.endswith('.port.ifname') or key.endswith('.port.descr'):
            current['port_id'] = value
        elif key.endswith('.mgmt-ip'):
            current['management_address'] = value
        elif '.vlan.' in key and key.endswith('.vid'):
            current.setdefault('vlans', []).append(value)
        elif key.endswith('.chassis.descr'):
            current['description'] = value
    if current:
        neighbors.append(current)
    for neighbor in neighbors:
        neighbor['role'] = 'Switch/router neighbor'
    return neighbors

def parse_neighbor_table(output):
    """Parse Linux ip neigh/ARP-like output into device dictionaries."""
    devices = []
    for line in (output or '').splitlines():
        tokens = line.split()
        if not tokens:
            continue
        ip = tokens[0].strip('()')
        mac = None
        iface = None
        arp_match = re.search(r'\(([^)]+)\)\s+at\s+([0-9a-fA-F:.-]+).*\s+on\s+(\S+)', line)
        if arp_match:
            ip, mac, iface = arp_match.groups()
        if 'lladdr' in tokens:
            mac = tokens[tokens.index('lladdr') + 1]
        if 'dev' in tokens:
            iface = tokens[tokens.index('dev') + 1]
        if mac or ip:
            devices.append({'ip': ip, 'mac': mac, 'interface': iface, 'discovery_methods': ['neighbor-table'], 'scan_note': 'Observed in local ARP/neighbor table.'})
    return devices

def merge_discovered_devices(groups):
    """Merge device records from multiple discovery methods by MAC, IP, or name."""
    merged = {}
    for method, devices in groups:
        for raw in devices or []:
            device = dict(raw)
            mac = normalize_mac(device.get('mac') or device.get('address') or device.get('bssid'))
            if mac:
                device['mac'] = mac
            key = mac or device.get('ip') or device.get('hostname') or device.get('name') or uuid.uuid4().hex
            current = merged.setdefault(key, {})
            methods = set(current.get('discovery_methods') or []) | set(device.get('discovery_methods') or []) | {method}
            service_metadata = list(current.get('service_metadata_list') or [])
            if device.get('service_metadata'):
                service_metadata.append(device.get('service_metadata'))
            current.update({k: v for k, v in device.items() if v not in (None, '', [])})
            current['discovery_methods'] = sorted(methods)
            if service_metadata:
                current['service_metadata_list'] = service_metadata[-10:]
    return list(merged.values())

def passive_device_identity(device):
    """Return a stable identity key for passive observation analytics."""
    mac = normalize_mac((device or {}).get('mac') or (device or {}).get('address'))
    if mac:
        return mac
    ip = str((device or {}).get('ip') or '').strip()
    if ip:
        return f'ip:{ip}'
    name = str((device or {}).get('hostname') or (device or {}).get('name') or '').strip()
    if name:
        return f'name:{name.lower()}'
    return None
