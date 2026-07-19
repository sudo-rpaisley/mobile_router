"""Inventory persistence and import/export helpers.

The Flask app owns the in-memory dictionaries and callback functions; this
module keeps inventory merge/export logic isolated from route handlers.
"""

import time


def find_device(identifier, inventory, lock, normalize_mac):
    """Find an inventory item by normalized MAC, IP, or inventory id."""
    normalized = normalize_mac(identifier) if identifier else None
    with lock:
        if normalized:
            for key in (f'mac:{normalized}', normalized):
                if key in inventory:
                    return dict(inventory[key])
            for item in inventory.values():
                if normalize_mac(item.get('mac') or item.get('address')) == normalized:
                    return dict(item)
        for item in inventory.values():
            if item.get('ip') == identifier or item.get('id') == identifier:
                return dict(item)
    return None


def merge_devices(
    devices,
    source,
    interface,
    inventory,
    lock,
    normalize_mac,
    inventory_key,
    lookup_manufacturer,
    create_new_device_alert,
    create_grouped_device_alert,
):
    """Merge discovered devices into inventory with source, interface, and OUI metadata."""
    now = time.time()
    changed_devices = []
    new_devices = []
    with lock:
        for raw_device in devices or []:
            device = dict(raw_device)
            mac = normalize_mac(device.get('mac') or device.get('address') or device.get('bssid'))
            if mac:
                device['mac'] = mac
            key = inventory_key(device)
            if not key:
                continue
            existing = inventory.get(key, {})
            first_seen = existing.get('first_seen', now)
            sources = sorted(set(existing.get('sources', [])) | {source})
            interfaces_seen = sorted(set(existing.get('interfaces', [])) | ({interface} if interface else set()))
            manufacturer = (
                device.get('manufacturer')
                or (lookup_manufacturer(mac) if mac else None)
                or existing.get('manufacturer')
                or 'Unknown'
            )
            merged = {
                **existing,
                **{k: v for k, v in device.items() if v not in (None, '')},
                'id': key,
                'mac': mac or existing.get('mac'),
                'manufacturer': manufacturer,
                'first_seen': first_seen,
                'last_seen': now,
                'sources': sources,
                'interfaces': interfaces_seen,
            }
            is_new_device = not existing
            inventory[key] = merged
            if is_new_device and not merged.get('is_control_traffic'):
                new_devices.append(dict(merged))
            changed_devices.append(dict(merged))
    if source == 'passive-scan' or len(new_devices) <= 1:
        for device in new_devices:
            create_new_device_alert(device, source, interface)
    else:
        create_grouped_device_alert(new_devices, source, interface)
    return changed_devices


def record_open_ports(
    host,
    port_details,
    source,
    inventory,
    lock,
    enrich_port_web_url,
    append_client_timeline_event,
    is_client_watched,
    create_client_watch_alert,
):
    """Attach open-port/service findings to an IP device profile."""
    host = (host or '').strip()
    if not host:
        return None
    details = sorted(
        [enrich_port_web_url(host, item) for item in (port_details or []) if item.get('port')],
        key=lambda item: item['port'],
    )
    now = time.time()
    added_ports = []
    changed_ports = []
    with lock:
        key = f'ip:{host}'
        existing_key = key if key in inventory else None
        if existing_key is None:
            for candidate_key, item in inventory.items():
                if item.get('ip') == host:
                    existing_key = candidate_key
                    break
        if existing_key is None:
            existing_key = key
            inventory[existing_key] = {
                'id': key,
                'ip': host,
                'manufacturer': 'Unknown',
                'first_seen': now,
                'interfaces': [],
                'sources': [],
            }
        device = inventory[existing_key]
        existing_details = {
            item.get('port'): dict(item)
            for item in device.get('open_port_details', [])
            if item.get('port')
        }
        for detail in details:
            previous = existing_details.get(detail['port'])
            if previous is None:
                added_ports.append(detail)
            elif (
                previous.get('service') != detail.get('service')
                or previous.get('description') != detail.get('description')
            ):
                changed_ports.append({'previous': previous, 'current': detail})
            existing_details[detail['port']] = detail
        device['open_port_details'] = [existing_details[port] for port in sorted(existing_details)]
        device['open_ports'] = sorted(existing_details)
        device['last_port_scan'] = now
        device['last_seen'] = now
        device['sources'] = sorted(set(device.get('sources', [])) | {source})
        inventory[existing_key] = device
        updated = dict(device)
    if added_ports:
        added_summary = ', '.join(
            f"{item['port']}/tcp {item.get('service') or 'Unknown'}"
            for item in added_ports
        )
        append_client_timeline_event(
            host,
            'New open ports',
            f'Added {added_summary} from {source}.',
            source,
        )
        if is_client_watched(host):
            added_numbers = ', '.join(str(item['port']) for item in added_ports)
            create_client_watch_alert(
                host,
                'New open port discovered',
                f'{len(added_ports)} new port(s): {added_numbers}',
            )
    for change in changed_ports:
        current = change['current']
        append_client_timeline_event(
            host,
            'Service changed',
            f"{current['port']}/tcp is now {current.get('service') or 'Unknown'} from {source}.",
            source,
        )
    return updated


def export_payload(records, exported_at=None):
    """Build a portable inventory export including saved port/service details."""
    devices = []
    for device in records or []:
        devices.append({
            'id': device.get('id'),
            'display_name': device.get('display_name'),
            'ip': device.get('ip'),
            'mac': device.get('mac'),
            'bssid': device.get('bssid'),
            'manufacturer': device.get('manufacturer'),
            'hostname': device.get('hostname'),
            'name': device.get('name'),
            'device_type': device.get('device_type'),
            'sources': device.get('sources', []),
            'interfaces': device.get('interfaces', []),
            'first_seen': device.get('first_seen'),
            'last_seen': device.get('last_seen'),
            'client_tags': device.get('client_tags', []),
            'client_notes': device.get('client_notes'),
            'expected_open_ports': device.get('expected_open_ports', []),
            'open_ports': device.get('open_ports', []),
            'open_port_details': device.get('open_port_details', []),
            'last_port_scan': device.get('last_port_scan'),
        })
    return {'exported_at': exported_at or time.time(), 'schema': 'mobile-router-inventory-v1', 'devices': devices}


def import_payload(
    payload,
    source,
    record_inventory_devices,
    find_inventory_device,
    inventory_key,
    inventory,
    lock,
    record_device_open_ports,
):
    """Import devices and saved port/service profiles from a portable JSON export."""
    if not isinstance(payload, dict):
        raise ValueError('Inventory import must be a JSON object')
    devices = payload.get('devices')
    if not isinstance(devices, list):
        raise ValueError('Inventory import must contain a devices list')
    imported_devices = 0
    imported_port_profiles = 0
    for raw in devices[:1000]:
        if not isinstance(raw, dict):
            continue
        device = {
            key: raw.get(key)
            for key in ('ip', 'mac', 'bssid', 'hostname', 'name', 'device_type', 'manufacturer')
            if raw.get(key)
        }
        device['sources'] = sorted(set(raw.get('sources') or []) | {source})
        interfaces = raw.get('interfaces') or []
        interface = interfaces[0] if interfaces else None
        enriched = record_inventory_devices([device], source, interface)
        identifier = raw.get('ip') or raw.get('mac') or raw.get('bssid')
        if not identifier:
            continue
        imported_devices += len(enriched)
        updates = {}
        for field in ('client_tags', 'client_notes', 'expected_open_ports', 'last_port_scan'):
            if raw.get(field) not in (None, ''):
                updates[field] = raw.get(field)
        if updates:
            target = find_inventory_device(identifier) or {}
            key = target.get('id') or inventory_key({
                **device,
                'ip': raw.get('ip'),
                'mac': raw.get('mac'),
                'bssid': raw.get('bssid'),
            })
            with lock:
                if key in inventory:
                    inventory[key].update(updates)
        port_details = raw.get('open_port_details') or []
        if raw.get('ip') and port_details:
            record_device_open_ports(raw.get('ip'), port_details, source=source)
            imported_port_profiles += 1
    return {'imported_devices': imported_devices, 'imported_port_profiles': imported_port_profiles}


def manufacturer_summary(records):
    """Summarize inventory by manufacturer/OUI."""
    vendors = {}
    unknown = 0
    for item in records or []:
        vendor = item.get('manufacturer') or 'Unknown'
        vendors.setdefault(vendor, {'manufacturer': vendor, 'count': 0, 'devices': []})
        vendors[vendor]['count'] += 1
        vendors[vendor]['devices'].append(item)
        if vendor == 'Unknown':
            unknown += 1
    top_vendors = sorted(vendors.values(), key=lambda item: (-item['count'], item['manufacturer']))
    return {
        'total_devices': len(records or []),
        'known_manufacturers': len([vendor for vendor in vendors if vendor != 'Unknown']),
        'unknown_manufacturers': unknown,
        'top_vendors': top_vendors,
    }
