"""Client display-name discovery and coarse operating-system hints."""

import os
import re
import time

from app_support.client_intelligence_dependencies import (
    client_intelligence_dependencies,
)


def _dhcp_lease_display_name(ip):
    """Look for a client hostname in common local DHCP lease files."""
    deps = client_intelligence_dependencies()
    lease_paths = [
        '/var/lib/misc/dnsmasq.leases',
        '/tmp/dhcp.leases',
        '/var/lib/dhcp/dhcpd.leases',
        '/var/lib/dhcp/dhclient.leases',
    ]
    for path in lease_paths:
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding='utf-8', errors='ignore') as handle:
                content = handle.read()
        except OSError:
            continue
        for line in content.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[2] == ip:
                return deps._clean_detected_client_name(parts[3], ip)
        block_match = re.search(
            rf'lease\s+{re.escape(ip)}\s+\{{(.*?)\}}',
            content,
            re.S,
        )
        if block_match:
            host_match = re.search(
                r'client-hostname\s+"([^"]+)"',
                block_match.group(1),
            )
            if host_match:
                return deps._clean_detected_client_name(host_match.group(1), ip)
    return ''


def display_name_for_inventory_device(device, fallback=None):
    """Choose the best human-readable name for an inventory device."""
    device = device or {}
    return (
        device.get('preferred_name')
        or device.get('detected_display_name')
        or device.get('name')
        or device.get('hostname')
        or device.get('friendly_name')
        or device.get('ssid')
        or device.get('ip')
        or device.get('mac')
        or fallback
        or 'Unknown device'
    )


def enrich_ip_client_display_name(identifier, device=None):
    """Detect and persist a better display name for an IP client when possible."""
    deps = client_intelligence_dependencies()
    device = dict(device or deps.find_inventory_device(identifier) or {})
    ip = device.get('ip') or (
        identifier
        if identifier and not deps.MAC_RE.match(str(identifier))
        else None
    )
    if not ip:
        return device
    existing = display_name_for_inventory_device(device, ip)
    if existing and existing not in {ip, device.get('mac'), device.get('id')}:
        device['display_name'] = existing
        return device
    detected = deps._clean_detected_client_name(
        device.get('hostname') or device.get('name'),
        ip,
    )
    source = 'inventory'
    if not detected:
        detected = _dhcp_lease_display_name(ip)
        source = 'dhcp-lease'
    if not detected:
        detected = deps._reverse_dns_display_name(ip)
        source = 'reverse-dns'
    if not detected:
        device['display_name'] = existing or ip
        return device
    updates = {
        'detected_display_name': detected,
        'display_name': detected,
        'hostname': device.get('hostname') or detected,
        'display_name_source': source,
    }
    with deps.device_inventory_lock:
        key = device.get('id') or f'ip:{ip}'
        existing_record = deps.device_inventory.get(key)
        if existing_record is None:
            for candidate_key, item in deps.device_inventory.items():
                if item.get('ip') == ip or item.get('mac') == device.get('mac'):
                    key = candidate_key
                    existing_record = item
                    break
        existing_record = dict(existing_record or {
            'id': key,
            'ip': ip,
            'manufacturer': device.get('manufacturer') or 'Unknown',
            'first_seen': time.time(),
            'sources': [],
            'interfaces': [],
        })
        existing_record.update({
            key: value for key, value in updates.items() if value
        })
        existing_record['last_seen'] = time.time()
        deps.device_inventory[key] = existing_record
        device = dict(existing_record)
    deps.append_client_timeline_event(
        ip,
        'Display name detected',
        f'Detected "{detected}" from {source}.',
        source,
    )
    return device


def _ttl_os_hint(history):
    """Infer a coarse OS/device family hint from observed ping TTL values."""
    ttl_values = []
    for item in history or []:
        for match in re.findall(
            r'ttl[= ](\d+)',
            item.get('output') or '',
            flags=re.I,
        ):
            try:
                ttl_values.append(int(match))
            except ValueError:
                continue
    if not ttl_values:
        return {'hint': 'Unknown', 'confidence': 'low', 'evidence': []}
    ttl = max(ttl_values)
    if ttl <= 64:
        hint = 'Linux/Unix, Android, or embedded IoT family'
    elif ttl <= 128:
        hint = 'Windows-family host or appliance'
    else:
        hint = 'Network appliance or BSD-derived stack'
    return {
        'hint': hint,
        'confidence': 'low',
        'evidence': [f'Observed TTL {ttl} in reachability history'],
    }
