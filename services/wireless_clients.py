"""Wireless-network client cache, labels, and display helpers."""

import time


HIDDEN_SSID_LABEL = '<Hidden SSID>'


def cache_key(network, normalize_mac):
    """Build a stable cache key for SSID/interface/BSSID scoped clients."""
    return (
        (network.get('interface') or '').strip(),
        (network.get('ssid') or HIDDEN_SSID_LABEL).strip(),
        normalize_mac(network.get('bssid')) or 'any-bssid',
    )


def client_label_key(interface, ssid, bssid, identity, normalize_mac):
    """Build a stable key for a custom client label scoped to one Wi-Fi network."""
    return (
        (interface or '').strip(),
        (ssid or HIDDEN_SSID_LABEL).strip(),
        normalize_mac(bssid) or 'any-bssid',
        (identity or '').strip(),
    )


def client_display_label(network, client, labels, normalize_mac):
    """Resolve the best display label for a client on a specific Wi-Fi network."""
    identity = client.get('mac') or client.get('ip')
    label = labels.get(
        client_label_key(
            network.get('interface'),
            network.get('ssid'),
            network.get('bssid'),
            identity,
            normalize_mac,
        )
    )
    if label:
        return label
    return (
        client.get('display_name')
        or client.get('hostname')
        or client.get('name')
        or client.get('ip')
        or client.get('mac')
        or 'Client'
    )


def sort_clients(clients):
    """Sort network clients by role, saved service profile, known state, then label."""
    return sorted(
        clients,
        key=lambda item: (
            item.get('sort_bucket', 9),
            0 if item.get('network_known_state') == 'New' else 1,
            (item.get('display_name') or item.get('ip') or item.get('mac') or '').lower(),
        ),
    )


def _known_manufacturer(*values):
    for value in values:
        if value and value != 'Unknown' and value != 'Unknown manufacturer':
            return value
    return None


def merge_network_clients(network, cache, labels, normalize_mac, inventory_records, lookup_manufacturer=None):
    """Persist and merge wireless clients plus inventory devices for a network view."""
    key = cache_key(network, normalize_mac)
    now = time.time()
    existing_cache = [
        dict(client) for client in cache.get(key, [])
        if client.get('source') != 'inventory'
    ]
    known_identities = {
        client.get('mac') or client.get('ip')
        for client in existing_cache
        if client.get('mac') or client.get('ip')
    }
    cached = {
        client.get('mac') or client.get('ip'): {**dict(client), 'currently_visible': False}
        for client in existing_cache
        if client.get('mac') or client.get('ip')
    }
    for raw_client in network.get('clients') or []:
        client = dict(raw_client)
        mac = normalize_mac(client.get('mac'))
        if mac:
            client['mac'] = mac
        client['source'] = client.get('source') or 'wireless-client-observation'
        looked_up_manufacturer = lookup_manufacturer(mac) if lookup_manufacturer and mac else None
        client['manufacturer'] = _known_manufacturer(client.get('manufacturer'), looked_up_manufacturer, 'Unknown')
        identity = client.get('mac') or client.get('ip')
        if not identity:
            continue
        previous = cached.get(identity, {})
        client['network_first_seen'] = previous.get('network_first_seen') or now
        client['network_last_seen'] = now
        client['currently_visible'] = True
        cached[identity] = {**previous, **client}

    interface_name = network.get('interface')
    inventory_devices = []
    for device in inventory_records():
        if interface_name and interface_name not in set(device.get('interfaces') or []):
            continue
        if device.get('is_control_traffic') or not (device.get('ip') or device.get('mac')):
            continue

        possible_identities = [value for value in (device.get('mac'), device.get('ip')) if value]
        matched_identity = next((identity for identity in possible_identities if identity in cached), None)
        if not matched_identity:
            # Inventory is interface-scoped, not SSID/BSSID-scoped. Never inject a
            # device into a Wi-Fi network page unless that exact identity was
            # already observed or cached for this specific network key.
            continue

        inventory_devices.append(device)
        previous = cached.get(matched_identity, {})
        resolved_manufacturer = _known_manufacturer(
            device.get('manufacturer'),
            previous.get('manufacturer'),
            lookup_manufacturer(device.get('mac')) if lookup_manufacturer and device.get('mac') else None,
            'Unknown',
        )
        cached[matched_identity] = {
            **previous,
            'mac': device.get('mac') or previous.get('mac'),
            'ip': device.get('ip') or previous.get('ip'),
            'display_name': device.get('display_name'),
            'manufacturer': resolved_manufacturer,
            'sources': device.get('sources', []),
            'discovery_methods': device.get('discovery_methods') or device.get('sources', []),
            'network_role': device.get('network_role'),
            'network_scope': device.get('network_scope'),
            'scan_note': device.get('scan_note'),
            'open_port_details': device.get('open_port_details', []),
            'client_tags': device.get('client_tags', []),
            'client_notes': device.get('client_notes'),
            'observed_names': device.get('observed_names', []),
            'likely_randomized_mac': device.get('likely_randomized_mac'),
            'device_role_guess': device.get('device_role_guess'),
            'network_first_seen': previous.get('network_first_seen') or device.get('first_seen') or now,
            'network_last_seen': max(
                previous.get('network_last_seen') or 0,
                device.get('last_seen') or now,
            ),
            'source': previous.get('source') or 'wireless-client-observation',
        }

    for identity, client in list(cached.items()):
        first_seen = client.get('network_first_seen') or now
        client['network_first_seen'] = first_seen
        client['network_last_seen'] = client.get('network_last_seen') or now
        client['network_known_state'] = (
            'Known' if identity in known_identities or (now - first_seen) > 86400 else 'New'
        )
        client['has_open_ports'] = bool(client.get('open_port_details'))
        client['sort_bucket'] = (
            0
            if 'gateway' in str(client.get('network_role') or '').lower()
            else (1 if client.get('has_open_ports') else 2)
        )
        client['custom_label'] = labels.get(
            client_label_key(
                network.get('interface'),
                network.get('ssid'),
                network.get('bssid'),
                identity,
                normalize_mac,
            )
        )
        client['display_name'] = client_display_label(network, client, labels, normalize_mac)

    disappeared_clients = sort_clients([
        client
        for client in cached.values()
        if not client.get('currently_visible') and client.get('source') != 'inventory'
    ])
    clients = sort_clients([client for client in cached.values() if client not in disappeared_clients])
    cache[key] = clients + disappeared_clients
    network['clients'] = clients
    network['disappeared_clients'] = disappeared_clients
    network['interface_devices'] = inventory_devices
    network['client_count'] = len(clients)
    network['inventory_device_count'] = len(inventory_devices)
    return network
