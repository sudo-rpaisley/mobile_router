"""Client timelines, health, intelligence snapshots, exports, and relationships."""

import time

from app_support.client_intelligence_dependencies import (
    client_intelligence_dependencies,
)


def client_timeline(identifier, inventory_device=None):
    """Return explicit and inferred timeline entries for a client."""
    deps = client_intelligence_dependencies()
    keys = {str(identifier or '').strip()}
    for field in ('ip', 'mac', 'id'):
        value = (inventory_device or {}).get(field)
        if value:
            keys.add(str(value))
    events = []
    with deps.client_timelines_lock:
        for key in keys:
            events.extend(dict(item) for item in deps.client_timelines.get(key, []))
    if inventory_device:
        if inventory_device.get('first_seen'):
            events.append({
                'timestamp': inventory_device['first_seen'],
                'type': 'First discovered',
                'message': 'Device first entered inventory.',
                'source': ', '.join(inventory_device.get('sources', [])),
            })
        if inventory_device.get('last_seen'):
            events.append({
                'timestamp': inventory_device['last_seen'],
                'type': 'Last seen',
                'message': 'Device was refreshed by discovery or scan activity.',
                'source': ', '.join(inventory_device.get('sources', [])),
            })
        if inventory_device.get('last_port_scan'):
            events.append({
                'timestamp': inventory_device['last_port_scan'],
                'type': 'Port scan',
                'message': (
                    f"{len(inventory_device.get('open_ports', []))} "
                    'open port(s) saved to this profile.'
                ),
                'source': 'port-scan',
            })
    unique = {
        (
            round(item.get('timestamp', 0), 3),
            item.get('type'),
            item.get('message'),
        ): item
        for item in events
    }
    ordered = sorted(
        unique.values(),
        key=lambda item: item.get('timestamp', 0),
        reverse=True,
    )[:12]
    for item in ordered:
        item['time_label'] = time.strftime(
            '%Y-%m-%d %H:%M:%S',
            time.localtime(item.get('timestamp', time.time())),
        )
    return ordered


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
    level, badge = (
        ('Good', 'success') if score >= 85
        else ('Review', 'warning') if score >= 60
        else ('Attention', 'danger')
    )
    return {
        'score': score,
        'level': level,
        'badge': badge,
        'flags': flags or ['No notable client concerns from saved data'],
        'open_port_count': len(open_ports),
        'identity': (
            device.get('hostname')
            or device.get('name')
            or ip
            or 'Unknown client'
        ),
    }


def client_intelligence_profile(identifier, active_probe=False):
    """Build a richer client intelligence snapshot from saved and safe probes."""
    deps = client_intelligence_dependencies()
    device = deps.enrich_ip_client_display_name(
        identifier,
        deps.find_inventory_device(identifier) or {},
    )
    host = device.get('ip') or identifier
    observed_names = [
        item.get('name')
        for item in device.get('observed_names', [])
        if item.get('name')
    ]
    detected_names = [
        device.get('hostname'), device.get('name'), device.get('display_name'),
        device.get('detected_display_name'), *observed_names,
    ]
    reverse_name = deps._reverse_dns_display_name(host) if host else ''
    if reverse_name:
        detected_names.append(reverse_name)
    dhcp_name = deps._dhcp_lease_display_name(host) if host else ''
    if dhcp_name:
        detected_names.append(dhcp_name)
    reachability = deps.client_reachability_history(host, limit=10)
    fingerprints = deps.fingerprint_client_services(identifier) if active_probe else []
    open_ports = device.get('open_port_details') or []
    web_ports = [
        item for item in open_ports
        if item.get('web_url')
        or str(item.get('service') or '').lower() in {'http', 'https'}
    ]
    sensitive = [
        item for item in open_ports
        if item.get('port') in {21, 23, 445, 3389, 5900}
    ]
    recommendations = []
    if device.get('likely_randomized_mac'):
        recommendations.append(
            'MAC appears locally administered/private; correlate by hostname, '
            'services, and SSID-scoped labels instead of OUI alone.'
        )
    if not device.get('manufacturer') or device.get('manufacturer') == 'Unknown':
        recommendations.append(
            'Manufacturer is unknown; refresh the OUI database or collect '
            'mDNS/DHCP/UPnP identity metadata.'
        )
    if sensitive:
        recommendations.append(
            'Sensitive remote-access or file-sharing ports are present; verify '
            'they are expected for this device.'
        )
    if not open_ports:
        recommendations.append(
            'No saved port/service baseline yet; run common ports once and reuse '
            'the saved profile before any larger scan.'
        )
    if web_ports:
        recommendations.append(
            'Web services are present; inspect titles, headers, favicon hashes, '
            'TLS certificates, and preview thumbnails for app identification.'
        )
    if not recommendations:
        recommendations.append(
            'Saved identity and service data is sufficient for a lightweight '
            'baseline; monitor for drift over time.'
        )
    return {
        'host': host,
        'manufacturer': device.get('manufacturer') or 'Unknown',
        'mac': device.get('mac'),
        'names': sorted({
            name for name in detected_names if name and name != host
        })[:12],
        'dns': {
            'reverse': reverse_name,
            'forward': deps._forward_dns_records(detected_names),
        },
        'dhcp': {'hostname': dhcp_name},
        'os_hint': deps._ttl_os_hint(reachability),
        'services': {
            'open_port_count': len(open_ports),
            'web_port_count': len(web_ports),
            'sensitive_port_count': len(sensitive),
            'fingerprints': fingerprints,
        },
        'stability': {
            'first_seen': device.get('first_seen'),
            'last_seen': device.get('last_seen'),
            'sources': device.get('sources', []),
            'interfaces': device.get('interfaces', []),
            'seen_count_hint': (
                len(device.get('sources', []))
                + len(device.get('interfaces', []))
            ),
        },
        'relationships': deps.client_relationship_map(identifier),
        'recommendations': recommendations[:8],
    }


def client_profile_export(identifier):
    """Build an exportable IP client profile."""
    deps = client_intelligence_dependencies()
    device = deps.find_inventory_device(identifier) or {}
    host = device.get('ip') or identifier
    identities = {
        str(host), str(device.get('mac') or ''), str(device.get('id') or '')
    }
    related_evidence = [
        item for item in deps.evidence_records()
        if str(item.get('device') or '') in identities
    ]
    return {
        'exported_at': time.time(),
        'host': host,
        'device': device,
        'health': deps.client_health_summary(device, host),
        'baseline': deps.client_baseline_diff(device),
        'reachability_history': deps.client_reachability_history(host, limit=25),
        'timeline': deps.client_timeline(host, device),
        'evidence': related_evidence,
    }


def client_relationship_map(identifier):
    """Build a lightweight client relationship map for rendering/export."""
    deps = client_intelligence_dependencies()
    device = deps.find_inventory_device(identifier) or {}
    host = device.get('ip') or identifier
    nodes = [{'id': f'client:{host}', 'label': host, 'type': 'client'}]
    links = []
    for iface in device.get('interfaces', []):
        node_id = f'interface:{iface}'
        nodes.append({'id': node_id, 'label': iface, 'type': 'interface'})
        links.append({'source': f'client:{host}', 'target': node_id, 'label': 'seen on'})
    for source in device.get('sources', []):
        node_id = f'source:{source}'
        nodes.append({'id': node_id, 'label': source, 'type': 'source'})
        links.append({'source': f'client:{host}', 'target': node_id, 'label': 'discovered by'})
    for port in device.get('open_port_details', [])[:12]:
        node_id = f"service:{host}:{port.get('port')}"
        nodes.append({
            'id': node_id,
            'label': f"{port.get('port')}/tcp {port.get('service') or 'Unknown'}",
            'type': 'service',
        })
        links.append({'source': f'client:{host}', 'target': node_id, 'label': 'exposes'})
    for item in deps.client_profile_export(identifier).get('evidence', [])[:8]:
        node_id = f"evidence:{item.get('id')}"
        nodes.append({
            'id': node_id,
            'label': item.get('title') or 'Evidence',
            'type': 'evidence',
        })
        links.append({'source': f'client:{host}', 'target': node_id, 'label': 'has evidence'})
    return {
        'nodes': list({node['id']: node for node in nodes}.values()),
        'links': links,
    }
