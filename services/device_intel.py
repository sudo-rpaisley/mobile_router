"""Device identity, role, and service intelligence helpers."""

import hashlib
import socket
import ssl
from urllib.parse import urljoin
from urllib.request import Request
from urllib.error import HTTPError, URLError


def is_locally_administered_mac(mac):
    """Return True when a MAC has the local/private address bit set."""
    if not mac:
        return False
    try:
        first_octet = int(str(mac).replace('-', ':').split(':')[0], 16)
    except (ValueError, IndexError):
        return False
    return bool(first_octet & 0b00000010)


def merge_observed_names(existing, device, source, now):
    """Merge host/name/display labels into a source-attributed observed-name history."""
    names = {
        (item.get('name'), item.get('source')): dict(item)
        for item in existing.get('observed_names', [])
        if item.get('name')
    }
    for field in ('display_name', 'hostname', 'name'):
        value = str(device.get(field) or '').strip().strip('.')
        if not value:
            continue
        key = (value, source)
        previous = names.get(key, {})
        names[key] = {
            'name': value[:120],
            'source': source,
            'field': field,
            'first_seen': previous.get('first_seen') or now,
            'last_seen': now,
        }
    return sorted(names.values(), key=lambda item: item.get('last_seen') or 0, reverse=True)[:12]


def infer_device_role(device):
    """Infer a likely device role from vendor, names, services, ports, and metadata."""
    text_parts = [
        device.get('manufacturer'),
        device.get('hostname'),
        device.get('name'),
        device.get('display_name'),
        device.get('device_type'),
        device.get('network_role'),
    ]
    for item in device.get('open_port_details') or []:
        text_parts.extend([item.get('service'), item.get('description'), item.get('http_title'), item.get('http_server')])
    for item in device.get('service_metadata_list') or []:
        text_parts.extend(str(value) for value in item.values() if isinstance(value, (str, int)))
    metadata = device.get('service_metadata') or {}
    if isinstance(metadata, dict):
        text_parts.extend(str(value) for value in metadata.values() if isinstance(value, (str, int)))
    value = ' '.join(str(part or '') for part in text_parts).lower()
    port_set = {int(item.get('port')) for item in device.get('open_port_details') or [] if item.get('port')}

    rules = [
        ('Gateway/router', 'high', ['gateway', 'router', 'openwrt', 'internetgatewaydevice'], {53, 67, 80, 443}),
        ('Printer', 'high', ['printer', '_ipp', 'laserjet', 'cups'], {631, 9100, 515}),
        ('NAS/file server', 'high', ['nas', 'synology', 'qnap', 'samba', 'smb'], {139, 445, 2049}),
        ('Camera/NVR', 'medium', ['camera', 'nvr', 'rtsp', 'hikvision', 'dahua'], {554, 8000, 8080}),
        ('Media/TV device', 'medium', ['airplay', 'chromecast', 'roku', 'tv', 'spotify', 'dlna'], {7000, 8008, 8009}),
        ('Home automation/IoT', 'medium', ['home assistant', 'esphome', 'tasmota', 'iot', 'esp32'], {8123, 6053, 1883}),
        ('Remote admin host', 'medium', ['ssh', 'rdp', 'vnc'], {22, 3389, 5900}),
        ('Web appliance', 'medium', ['http', 'nginx', 'apache', 'lighttpd'], {80, 443, 8080, 8443}),
    ]
    evidence = []
    for role, confidence, terms, ports in rules:
        matched_terms = [term for term in terms if term in value]
        matched_ports = sorted(port_set & ports)
        if matched_terms or matched_ports:
            if matched_terms:
                evidence.append(f"Matched terms: {', '.join(matched_terms[:3])}")
            if matched_ports:
                evidence.append(f"Matched ports: {', '.join(str(port) for port in matched_ports[:4])}")
            return {'role': role, 'confidence': confidence, 'evidence': evidence[:4]}
    if device.get('is_control_traffic'):
        return {'role': device.get('network_role') or 'Control traffic', 'confidence': 'high', 'evidence': ['Classified as control traffic']}
    return {'role': device.get('network_role') or device.get('device_type') or 'Client', 'confidence': 'low', 'evidence': ['No strong role fingerprint yet']}


def favicon_metadata(url, urlopen, timeout=3):
    """Fetch and hash a site's favicon for lightweight web-app fingerprinting."""
    try:
        favicon_url = urljoin(url, '/favicon.ico')
        req = Request(favicon_url, headers={'User-Agent': 'MobileRouterLab/1.0'})
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read(131072)
        if not data:
            return None
        digest = hashlib.sha256(data).hexdigest()
        hints = {
            # These are intentionally conservative generic hints. More known hashes
            # can be added later from locally collected, non-sensitive samples.
        }
        return {
            'url': favicon_url,
            'sha256': digest,
            'size': len(data),
            'app_hint': hints.get(digest),
        }
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return None


def tls_certificate_metadata(host, port, timeout=3):
    """Collect basic TLS certificate identity for HTTPS-like services."""
    try:
        context = ssl._create_unverified_context()
        with socket.create_connection((host, int(port)), timeout=timeout) as raw_sock:
            with context.wrap_socket(raw_sock, server_hostname=host) as tls_sock:
                cert = tls_sock.getpeercert()
                cipher = tls_sock.cipher()
    except (OSError, ssl.SSLError, ValueError):
        return None
    subject = dict(part[0] for part in cert.get('subject', []) if part)
    issuer = dict(part[0] for part in cert.get('issuer', []) if part)
    sans = [value for key, value in cert.get('subjectAltName', []) if key.lower() == 'dns']
    return {
        'subject_common_name': subject.get('commonName'),
        'issuer_common_name': issuer.get('commonName'),
        'dns_names': sans[:12],
        'not_before': cert.get('notBefore'),
        'not_after': cert.get('notAfter'),
        'cipher': cipher[0] if cipher else None,
    }
