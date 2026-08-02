"""Combined active, passive, neighbor, and service discovery."""

import os

from app_support.passive_monitoring_dependencies import (
    passive_monitoring_dependencies,
)


def comprehensive_network_device_scan(
    selected_interface,
    include_passive=True,
    include_services=True,
    sweep_cidr=None,
):
    """Combine active, passive, neighbor, service, and optional sweep results."""
    deps = passive_monitoring_dependencies()
    if not selected_interface:
        raise ValueError('Missing interface')
    groups = []
    errors = []
    try:
        groups.append((
            'active-arp',
            deps.classify_scan_results(
                deps.active_scan(selected_interface),
                selected_interface,
            ),
        ))
    except Exception as exc:
        errors.append(f'active scan: {exc}')
    if include_passive:
        try:
            groups.append((
                'passive-observation',
                deps.classify_scan_results(
                    deps.passive_scan(selected_interface),
                    selected_interface,
                ),
            ))
        except Exception as exc:
            errors.append(f'passive scan: {exc}')
    if os.name != 'nt':
        neigh = deps._run_text_command(
            ['ip', 'neigh', 'show', 'dev', selected_interface],
            timeout=5,
        )
        groups.append((
            'neighbor-table',
            deps.parse_neighbor_table(neigh.get('output')),
        ))
        arp = deps._run_text_command(['arp', '-an'], timeout=5)
        groups.append((
            'arp-cache',
            deps.parse_neighbor_table(arp.get('output')),
        ))
    if sweep_cidr:
        try:
            sweep = deps.run_ping_sweep(sweep_cidr, count=1, timeout=1)
            groups.append((
                'ping-sweep',
                [
                    {
                        'ip': item.get('host'),
                        'discovery_methods': ['ping-sweep'],
                        'reachable': item.get('reachable'),
                    }
                    for item in sweep.get('results', [])
                    if item.get('reachable')
                ],
            ))
        except Exception as exc:
            errors.append(f'ping sweep: {exc}')
    if include_services:
        mdns = deps.discover_mdns_services(selected_interface)
        groups.append((
            'mdns',
            [
                {
                    'ip': service.get('ip'),
                    'hostname': service.get('hostname'),
                    'name': service.get('name'),
                    'device_type': service.get('role'),
                    'service_metadata': service,
                    'discovery_methods': ['mdns'],
                }
                for service in mdns.get('services', [])
            ],
        ))
        upnp = deps.discover_upnp_devices(timeout=2)
        groups.append((
            'upnp-ssdp',
            [
                {
                    'ip': device.get('ip'),
                    'name': device.get('friendly_name'),
                    'manufacturer': device.get('manufacturer'),
                    'device_type': device.get('role'),
                    'service_metadata': device,
                    'discovery_methods': ['upnp-ssdp'],
                }
                for device in upnp.get('devices', [])
            ],
        ))
        lldp = deps.discover_lldp_neighbors(selected_interface)
        groups.append((
            'lldp-cdp',
            [
                {
                    'ip': neighbor.get('management_address'),
                    'name': neighbor.get('name'),
                    'device_type': neighbor.get('role'),
                    'service_metadata': neighbor,
                    'discovery_methods': ['lldp-cdp'],
                }
                for neighbor in lldp.get('neighbors', [])
            ],
        ))
    merged = deps.merge_discovered_devices(groups)
    enriched = deps.record_inventory_devices(
        merged,
        'comprehensive-network-scan',
        selected_interface,
    )
    return {
        'devices': enriched,
        'methods': [method for method, _devices in groups],
        'errors': errors,
        'summary': {
            'total_devices': len(enriched),
            'host_like': len([
                item for item in enriched
                if not item.get('is_control_traffic')
            ]),
            'with_services': len([
                item for item in enriched
                if item.get('service_metadata')
                or item.get('service_metadata_list')
            ]),
        },
    }
