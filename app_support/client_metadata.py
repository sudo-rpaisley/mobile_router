"""Client-maintained metadata and baseline persistence."""

import time

from app_support.client_intelligence_dependencies import (
    client_intelligence_dependencies,
)


def update_client_metadata(identifier, data):
    """Persist user-maintained client tags, ownership, notes, and expected ports."""
    deps = client_intelligence_dependencies()
    target = str(identifier or '').strip()
    if not target:
        raise ValueError('Missing client identifier')
    raw_tags = data.get('tags') or ''
    tags = sorted({
        tag.strip() for tag in raw_tags.split(',') if tag.strip()
    })[:12]
    expected_ports = []
    for raw_port in (data.get('expectedPorts') or '').split(','):
        raw_port = raw_port.strip()
        if not raw_port:
            continue
        port = deps.parse_int(raw_port, 'Expected ports must be integers')
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
    with deps.device_inventory_lock:
        key = f'ip:{target}'
        existing = deps.device_inventory.get(key)
        if existing is None:
            for candidate_key, item in deps.device_inventory.items():
                if (
                    item.get('ip') == target
                    or item.get('mac') == target
                    or item.get('id') == target
                ):
                    key = candidate_key
                    existing = item
                    break
        existing = dict(existing or {
            'id': key,
            'ip': target,
            'manufacturer': 'Unknown',
            'first_seen': time.time(),
            'sources': [],
            'interfaces': [],
        })
        key = existing.get('id') or deps.inventory_key(existing) or key
        existing.update({
            field: value
            for field, value in updates.items()
            if value not in (None, '')
        })
        existing['last_seen'] = time.time()
        deps.device_inventory[key] = existing
    deps.append_client_timeline_event(
        target,
        'Profile updated',
        'Client tags, ownership, notes, or expected ports were updated.',
        'client-metadata',
    )
    return dict(existing)


def save_client_baseline(identifier):
    """Save current observed identity/service details as the expected baseline."""
    deps = client_intelligence_dependencies()
    device = deps.find_inventory_device(identifier) or {}
    target = device.get('ip') or identifier
    baseline = {
        'saved_at': time.time(),
        'hostname': device.get('hostname') or device.get('name'),
        'manufacturer': device.get('manufacturer'),
        'open_ports': sorted(device.get('open_ports', [])),
        'mac': device.get('mac'),
        'sources': list(device.get('sources', [])),
    }
    updated = deps.update_client_metadata(
        target,
        {
            'expectedPorts': ','.join(
                str(port) for port in baseline['open_ports']
            )
        },
    )
    with deps.device_inventory_lock:
        key = updated.get('id')
        deps.device_inventory[key]['client_baseline'] = baseline
        updated = dict(deps.device_inventory[key])
    deps.append_client_timeline_event(
        target,
        'Baseline saved',
        f"Saved {len(baseline['open_ports'])} expected open port(s).",
        'client-baseline',
    )
    return updated
