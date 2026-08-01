"""Client identity, timeline, health, metadata, and relationship helpers."""

from app_support.context import context_refresher


_CONTEXT_PROVIDER = None


def configure_client_intelligence_context(provider):
    global _CONTEXT_PROVIDER
    _CONTEXT_PROVIDER = provider


_refresh_context = context_refresher(globals(), lambda: _CONTEXT_PROVIDER)


@_refresh_context
def _dhcp_lease_display_name(ip):
    """Look for a client hostname in common local DHCP lease files."""
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
                return _clean_detected_client_name(parts[3], ip)
        block_match = re.search(rf'lease\s+{re.escape(ip)}\s+\{{(.*?)\}}', content, re.S)
        if block_match:
            host_match = re.search(r'client-hostname\s+"([^"]+)"', block_match.group(1))
            if host_match:
                return _clean_detected_client_name(host_match.group(1), ip)
    return ''


@_refresh_context
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


@_refresh_context
def enrich_ip_client_display_name(identifier, device=None):
    """Detect and persist a better display name for an IP client when possible."""
    device = dict(device or find_inventory_device(identifier) or {})
    ip = device.get('ip') or (identifier if identifier and not MAC_RE.match(str(identifier)) else None)
    if not ip:
        return device
    existing = display_name_for_inventory_device(device, ip)
    if existing and existing not in {ip, device.get('mac'), device.get('id')}:
        device['display_name'] = existing
        return device
    detected = _clean_detected_client_name(device.get('hostname') or device.get('name'), ip)
    source = 'inventory'
    if not detected:
        detected = _dhcp_lease_display_name(ip)
        source = 'dhcp-lease'
    if not detected:
        detected = _reverse_dns_display_name(ip)
        source = 'reverse-dns'
    if not detected:
        device['display_name'] = existing or ip
        return device
    updates = {'detected_display_name': detected, 'display_name': detected, 'hostname': device.get('hostname') or detected, 'display_name_source': source}
    with device_inventory_lock:
        key = device.get('id') or f'ip:{ip}'
        existing_record = device_inventory.get(key)
        if existing_record is None:
            for candidate_key, item in device_inventory.items():
                if item.get('ip') == ip or item.get('mac') == device.get('mac'):
                    key = candidate_key
                    existing_record = item
                    break
        existing_record = dict(existing_record or {'id': key, 'ip': ip, 'manufacturer': device.get('manufacturer') or 'Unknown', 'first_seen': time.time(), 'sources': [], 'interfaces': []})
        existing_record.update({k: v for k, v in updates.items() if v})
        existing_record['last_seen'] = time.time()
        device_inventory[key] = existing_record
        device = dict(existing_record)
    append_client_timeline_event(ip, 'Display name detected', f'Detected "{detected}" from {source}.', source)
    return device


@_refresh_context
def client_timeline(identifier, inventory_device=None):
    """Return explicit and inferred timeline entries for a client."""
    keys = {str(identifier or '').strip()}
    for field in ('ip', 'mac', 'id'):
        value = (inventory_device or {}).get(field)
        if value:
            keys.add(str(value))
    events = []
    with client_timelines_lock:
        for key in keys:
            events.extend(dict(item) for item in client_timelines.get(key, []))
    if inventory_device:
        if inventory_device.get('first_seen'):
            events.append({'timestamp': inventory_device['first_seen'], 'type': 'First discovered', 'message': 'Device first entered inventory.', 'source': ', '.join(inventory_device.get('sources', []))})
        if inventory_device.get('last_seen'):
            events.append({'timestamp': inventory_device['last_seen'], 'type': 'Last seen', 'message': 'Device was refreshed by discovery or scan activity.', 'source': ', '.join(inventory_device.get('sources', []))})
        if inventory_device.get('last_port_scan'):
            events.append({'timestamp': inventory_device['last_port_scan'], 'type': 'Port scan', 'message': f"{len(inventory_device.get('open_ports', []))} open port(s) saved to this profile.", 'source': 'port-scan'})
    unique = {(round(item.get('timestamp', 0), 3), item.get('type'), item.get('message')): item for item in events}
    ordered = sorted(unique.values(), key=lambda item: item.get('timestamp', 0), reverse=True)[:12]
    for item in ordered:
        item['time_label'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(item.get('timestamp', time.time())))
    return ordered


@_refresh_context
def client_health_summary(device, ip=None):
    """Build a simple client health/risk summary from inventory evidence."""
    device = device or {}
    flags = []
    score = 100
    open_ports = device.get('open_port_details') or []
    if not device.get('manufacturer') or device.get('manufacturer') == 'Unknown':
        flags.append('Unknown manufacturer')
        score -= 10
    risky_ports = {21: 'FTP', 23: 'Telnet', 445: 'SMB', 3389: 'RDP', 5900: 'VNC'}
    exposed = [item for item in open_ports if item.get('port') in risky_ports]
    if exposed:
        flags.append(f"{len(exposed)} sensitive service(s) exposed")
        score -= 25
    if len(open_ports) >= 8:
        flags.append('Large open-port surface')
        score -= 15
    if not device.get('hostname') and not device.get('name'):
        flags.append('No hostname learned')
        score -= 5
    if not open_ports:
        flags.append('No service baseline yet')
        score -= 5
    score = max(0, min(100, score))
    if score >= 85:
        level = 'Good'
        badge = 'success'
    elif score >= 60:
        level = 'Review'
        badge = 'warning'
    else:
        level = 'Attention'
        badge = 'danger'
    return {'score': score, 'level': level, 'badge': badge, 'flags': flags or ['No notable client concerns from saved data'], 'open_port_count': len(open_ports), 'identity': device.get('hostname') or device.get('name') or ip or 'Unknown client'}


@_refresh_context
def _ttl_os_hint(history):
    """Infer a coarse OS/device family hint from observed ping TTL values."""
    ttl_values = []
    for item in history or []:
        for match in re.findall(r'ttl[= ](\d+)', item.get('output') or '', flags=re.I):
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
    return {'hint': hint, 'confidence': 'low', 'evidence': [f'Observed TTL {ttl} in reachability history']}


@_refresh_context
def client_intelligence_profile(identifier, active_probe=False):
    """Build a richer client intelligence snapshot from saved and optional safe probes."""
    device = enrich_ip_client_display_name(identifier, find_inventory_device(identifier) or {})
    host = device.get('ip') or identifier
    observed_names = [item.get('name') for item in device.get('observed_names', []) if item.get('name')]
    detected_names = [device.get('hostname'), device.get('name'), device.get('display_name'), device.get('detected_display_name'), *observed_names]
    reverse_name = _reverse_dns_display_name(host) if host else ''
    if reverse_name:
        detected_names.append(reverse_name)
    dhcp_name = _dhcp_lease_display_name(host) if host else ''
    if dhcp_name:
        detected_names.append(dhcp_name)
    reachability = client_reachability_history(host, limit=10)
    fingerprints = fingerprint_client_services(identifier) if active_probe else []
    open_ports = device.get('open_port_details') or []
    web_ports = [item for item in open_ports if item.get('web_url') or str(item.get('service') or '').lower() in {'http', 'https'}]
    sensitive = [item for item in open_ports if item.get('port') in {21, 23, 445, 3389, 5900}]
    stability = {
        'first_seen': device.get('first_seen'),
        'last_seen': device.get('last_seen'),
        'sources': device.get('sources', []),
        'interfaces': device.get('interfaces', []),
        'seen_count_hint': len(device.get('sources', [])) + len(device.get('interfaces', [])),
    }
    recommendations = []
    if device.get('likely_randomized_mac'):
        recommendations.append('MAC appears locally administered/private; correlate by hostname, services, and SSID-scoped labels instead of OUI alone.')
    if not device.get('manufacturer') or device.get('manufacturer') == 'Unknown':
        recommendations.append('Manufacturer is unknown; refresh the OUI database or collect mDNS/DHCP/UPnP identity metadata.')
    if sensitive:
        recommendations.append('Sensitive remote-access or file-sharing ports are present; verify they are expected for this device.')
    if not open_ports:
        recommendations.append('No saved port/service baseline yet; run common ports once and reuse the saved profile before any larger scan.')
    if web_ports:
        recommendations.append('Web services are present; inspect titles, headers, favicon hashes, TLS certificates, and preview thumbnails for app identification.')
    if not recommendations:
        recommendations.append('Saved identity and service data is sufficient for a lightweight baseline; monitor for drift over time.')
    return {
        'host': host,
        'manufacturer': device.get('manufacturer') or 'Unknown',
        'mac': device.get('mac'),
        'names': sorted({name for name in detected_names if name and name != host})[:12],
        'dns': {'reverse': reverse_name, 'forward': _forward_dns_records(detected_names)},
        'dhcp': {'hostname': dhcp_name},
        'os_hint': _ttl_os_hint(reachability),
        'services': {'open_port_count': len(open_ports), 'web_port_count': len(web_ports), 'sensitive_port_count': len(sensitive), 'fingerprints': fingerprints},
        'stability': stability,
        'relationships': client_relationship_map(identifier),
        'recommendations': recommendations[:8],
    }


@_refresh_context
def update_client_metadata(identifier, data):
    """Persist user-maintained client tags, ownership, notes, and expected ports."""
    target = str(identifier or '').strip()
    if not target:
        raise ValueError('Missing client identifier')
    raw_tags = data.get('tags') or ''
    tags = sorted({tag.strip() for tag in raw_tags.split(',') if tag.strip()})[:12]
    expected_ports = []
    raw_expected_ports = data.get('expectedPorts') or ''
    for raw_port in raw_expected_ports.split(','):
        raw_port = raw_port.strip()
        if not raw_port:
            continue
        port = parse_int(raw_port, 'Expected ports must be integers')
        if not 1 <= port <= 65535:
            raise ValueError('Expected ports must be between 1 and 65535')
        expected_ports.append(port)
    updates = {
        'client_tags': tags,
        'client_owner': (data.get('owner') or '').strip()[:80],
        'client_location': (data.get('location') or '').strip()[:80],
        'client_notes': (data.get('notes') or '').strip()[:500],
        'expected_open_ports': sorted(set(expected_ports)),
    }
    with device_inventory_lock:
        key = f'ip:{target}'
        existing = device_inventory.get(key)
        if existing is None:
            for candidate_key, item in device_inventory.items():
                if item.get('ip') == target or item.get('mac') == target or item.get('id') == target:
                    key = candidate_key
                    existing = item
                    break
        existing = dict(existing or {'id': key, 'ip': target, 'manufacturer': 'Unknown', 'first_seen': time.time(), 'sources': [], 'interfaces': []})
        key = existing.get('id') or inventory_key(existing) or key
        existing.update({k: v for k, v in updates.items() if v not in (None, '')})
        existing['last_seen'] = time.time()
        device_inventory[key] = existing
    append_client_timeline_event(target, 'Profile updated', 'Client tags, ownership, notes, or expected ports were updated.', 'client-metadata')
    return dict(existing)


@_refresh_context
def save_client_baseline(identifier):
    """Save current observed identity/service details as the expected baseline."""
    device = find_inventory_device(identifier) or {}
    target = device.get('ip') or identifier
    baseline = {
        'saved_at': time.time(),
        'hostname': device.get('hostname') or device.get('name'),
        'manufacturer': device.get('manufacturer'),
        'open_ports': sorted(device.get('open_ports', [])),
        'mac': device.get('mac'),
        'sources': list(device.get('sources', [])),
    }
    updated = update_client_metadata(target, {'expectedPorts': ','.join(str(port) for port in baseline['open_ports'])})
    with device_inventory_lock:
        key = updated.get('id')
        device_inventory[key]['client_baseline'] = baseline
        updated = dict(device_inventory[key])
    append_client_timeline_event(target, 'Baseline saved', f"Saved {len(baseline['open_ports'])} expected open port(s).", 'client-baseline')
    return updated


@_refresh_context
def client_profile_export(identifier):
    """Build an exportable IP client profile."""
    device = find_inventory_device(identifier) or {}
    host = device.get('ip') or identifier
    related_evidence = [
        item for item in evidence_records()
        if str(item.get('device') or '') in {str(host), str(device.get('mac') or ''), str(device.get('id') or '')}
    ]
    return {
        'exported_at': time.time(),
        'host': host,
        'device': device,
        'health': client_health_summary(device, host),
        'baseline': client_baseline_diff(device),
        'reachability_history': client_reachability_history(host, limit=25),
        'timeline': client_timeline(host, device),
        'evidence': related_evidence,
    }


@_refresh_context
def client_relationship_map(identifier):
    """Build a lightweight client relationship map for profile rendering/export."""
    device = find_inventory_device(identifier) or {}
    host = device.get('ip') or identifier
    nodes = [{'id': f'client:{host}', 'label': host, 'type': 'client'}]
    links = []
    for iface in device.get('interfaces', []):
        nodes.append({'id': f'interface:{iface}', 'label': iface, 'type': 'interface'})
        links.append({'source': f'client:{host}', 'target': f'interface:{iface}', 'label': 'seen on'})
    for source in device.get('sources', []):
        nodes.append({'id': f'source:{source}', 'label': source, 'type': 'source'})
        links.append({'source': f'client:{host}', 'target': f'source:{source}', 'label': 'discovered by'})
    for port in device.get('open_port_details', [])[:12]:
        node_id = f"service:{host}:{port.get('port')}"
        nodes.append({'id': node_id, 'label': f"{port.get('port')}/tcp {port.get('service') or 'Unknown'}", 'type': 'service'})
        links.append({'source': f'client:{host}', 'target': node_id, 'label': 'exposes'})
    for item in client_profile_export(identifier).get('evidence', [])[:8]:
        node_id = f"evidence:{item.get('id')}"
        nodes.append({'id': node_id, 'label': item.get('title') or 'Evidence', 'type': 'evidence'})
        links.append({'source': f'client:{host}', 'target': node_id, 'label': 'has evidence'})
    unique_nodes = {node['id']: node for node in nodes}
    return {'nodes': list(unique_nodes.values()), 'links': links}


__all__ = [
    '_dhcp_lease_display_name',
    'display_name_for_inventory_device',
    'enrich_ip_client_display_name',
    'client_timeline',
    'client_health_summary',
    '_ttl_os_hint',
    'client_intelligence_profile',
    'update_client_metadata',
    'save_client_baseline',
    'client_profile_export',
    'client_relationship_map'
]
