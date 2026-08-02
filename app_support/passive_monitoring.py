"""Passive observation analytics, monitor workers, and combined scans."""

import os
import threading
import time

from app_support.context import ContextProvider, DependencyProxy, dependency_proxy


_REQUIRED_DEPENDENCIES = frozenset({
    '_run_text_command',
    'active_scan',
    'classify_scan_results',
    'discover_lldp_neighbors',
    'discover_mdns_services',
    'discover_upnp_devices',
    'lookup_manufacturer',
    'merge_discovered_devices',
    'normalize_mac',
    'packet_passive_scan',
    'parse_int',
    'parse_neighbor_table',
    'passive_analytics_lock',
    'passive_device_identity',
    'passive_monitor_jobs',
    'passive_monitor_lock',
    'passive_observation_analytics',
    'passive_scan',
    'record_inventory_devices',
    'run_ping_sweep',
    'save_runtime_state',
})
_DEPENDENCIES: DependencyProxy | None = None


def configure_passive_monitoring_context(provider: ContextProvider) -> None:
    """Configure the explicit application dependencies used by this module."""
    global _DEPENDENCIES
    _DEPENDENCIES = dependency_proxy(
        provider,
        _REQUIRED_DEPENDENCIES,
        label='passive monitoring',
    )


def _dependencies() -> DependencyProxy:
    if _DEPENDENCIES is None:
        raise RuntimeError('Passive monitoring dependencies are not configured')
    return _DEPENDENCIES


def record_passive_observation_analytics(
    interface,
    devices,
    source='passive-scan',
):
    """Track passive-only observation counts, churn, and quiet devices per interface."""
    deps = _dependencies()
    iface = str(interface or 'unknown').strip() or 'unknown'
    now = time.time()
    seen_identities = []
    with deps.passive_analytics_lock:
        analytics = deps.passive_observation_analytics.setdefault(iface, {
            'interface': iface,
            'started_at': now,
            'last_update': None,
            'total_samples': 0,
            'devices': {},
            'history': [],
            'last_seen_identities': [],
        })
        known_before = set((analytics.get('devices') or {}).keys())
        devices_map = analytics.setdefault('devices', {})
        for device in devices or []:
            identity = deps.passive_device_identity(device)
            if not identity:
                continue
            seen_identities.append(identity)
            record = devices_map.setdefault(identity, {
                'identity': identity,
                'first_seen': now,
                'seen_count': 0,
                'sources': [],
            })
            record.update({
                'last_seen': now,
                'ip': device.get('ip') or record.get('ip'),
                'mac': (
                    deps.normalize_mac(
                        device.get('mac') or device.get('address')
                    )
                    or record.get('mac')
                ),
                'hostname': (
                    device.get('hostname')
                    or device.get('name')
                    or record.get('hostname')
                ),
                'manufacturer': (
                    device.get('manufacturer')
                    or record.get('manufacturer')
                    or 'Unknown'
                ),
            })
            record['seen_count'] = int(record.get('seen_count') or 0) + 1
            sources = set(record.get('sources') or [])
            sources.add(source)
            record['sources'] = sorted(sources)
        seen_set = set(seen_identities)
        new_count = len(seen_set - known_before)
        quiet = [
            identity for identity in known_before if identity not in seen_set
        ]
        analytics['last_update'] = now
        analytics['total_samples'] = int(
            analytics.get('total_samples') or 0
        ) + 1
        analytics['last_seen_identities'] = sorted(seen_set)
        analytics['history'] = ([{
            'timestamp': now,
            'source': source,
            'observed_count': len(seen_set),
            'new_count': new_count,
            'quiet_count': len(quiet),
        }] + list(analytics.get('history') or []))[:100]
        snapshot = passive_observation_summary(iface, _locked=True)
    deps.save_runtime_state(f'passive-analytics:{source}')
    return snapshot


def passive_observation_summary(interface=None, _locked=False):
    """Return passive-only analytics for one interface or all interfaces."""
    deps = _dependencies()

    def build(iface, analytics):
        devices = list((analytics.get('devices') or {}).values())
        last_seen = set(analytics.get('last_seen_identities') or [])
        recently_disappeared = sorted(
            [
                dict(item)
                for item in devices
                if item.get('identity') not in last_seen
            ],
            key=lambda item: item.get('last_seen') or 0,
            reverse=True,
        )[:25]
        active = sorted(
            [
                dict(item)
                for item in devices
                if item.get('identity') in last_seen
            ],
            key=lambda item: item.get('last_seen') or 0,
            reverse=True,
        )[:25]
        return {
            'interface': iface,
            'started_at': analytics.get('started_at'),
            'last_update': analytics.get('last_update'),
            'total_samples': analytics.get('total_samples') or 0,
            'known_device_count': len(devices),
            'active_device_count': len(active),
            'recently_disappeared_count': len(recently_disappeared),
            'active_devices': active,
            'recently_disappeared': recently_disappeared,
            'history': list(analytics.get('history') or [])[:25],
        }

    empty = {'devices': {}, 'history': []}
    if _locked:
        if interface:
            return build(
                interface,
                deps.passive_observation_analytics.get(
                    interface,
                    {'interface': interface, **empty},
                ),
            )
        return {
            iface: build(iface, analytics)
            for iface, analytics in deps.passive_observation_analytics.items()
        }
    with deps.passive_analytics_lock:
        if interface:
            return build(
                interface,
                deps.passive_observation_analytics.get(
                    interface,
                    {'interface': interface, **empty},
                ),
            )
        return {
            iface: build(iface, analytics)
            for iface, analytics in deps.passive_observation_analytics.items()
        }


def passive_monitor_snapshot(interface=None):
    """Return passive ARP-cache monitor state for one interface or all interfaces."""
    deps = _dependencies()
    with deps.passive_monitor_lock:
        if interface:
            job = deps.passive_monitor_jobs.get(interface)
            return dict(job) if job else {
                'interface': interface,
                'enabled': False,
            }
        return {
            name: dict(job)
            for name, job in deps.passive_monitor_jobs.items()
        }


def _passive_monitor_worker(interface):
    """Continuously refresh passive inventory from cache or packet observations."""
    deps = _dependencies()
    while True:
        with deps.passive_monitor_lock:
            job = deps.passive_monitor_jobs.get(interface)
            if not job or not job.get('enabled'):
                return
            interval = job.get('interval', 10)
            mode = job.get('mode', 'cache')
        sleep_for = 0.1 if mode == 'packet' else interval
        try:
            if mode == 'packet':
                source = 'passive-packet-monitor'
                raw_devices = deps.packet_passive_scan(
                    interface,
                    timeout=interval,
                    packet_limit=250,
                    manufacturer_lookup=deps.lookup_manufacturer,
                )
            else:
                source = 'passive-monitor'
                raw_devices = deps.passive_scan(interface)
            devices = deps.classify_scan_results(raw_devices, interface)
            enriched = deps.record_inventory_devices(
                devices,
                source,
                interface,
            )
            analytics = record_passive_observation_analytics(
                interface,
                enriched,
                source,
            )
            with deps.passive_monitor_lock:
                current = deps.passive_monitor_jobs.get(interface)
                if current:
                    current.update({
                        'last_update': time.time(),
                        'last_count': len(enriched),
                        'analytics': analytics,
                        'mode': mode,
                        'error': None,
                    })
        except Exception as exc:
            with deps.passive_monitor_lock:
                current = deps.passive_monitor_jobs.get(interface)
                if current:
                    current.update({
                        'last_update': time.time(),
                        'error': str(exc),
                        'mode': mode,
                    })
        time.sleep(sleep_for)


def set_passive_monitor(interface, enabled, interval=10, mode='cache'):
    """Start or stop a background passive monitor for an interface."""
    deps = _dependencies()
    interface = (interface or '').strip()
    if not interface:
        raise ValueError('Missing interface')
    mode = (
        'packet'
        if str(mode or '').strip().lower() in {'packet', 'live', 'live-packet'}
        else 'cache'
    )
    if mode == 'packet':
        interval = max(
            1,
            min(
                deps.parse_int(interval, 'Capture window must be an integer'),
                10,
            ),
        )
    else:
        interval = max(
            5,
            min(deps.parse_int(interval, 'Interval must be an integer'), 300),
        )
    with deps.passive_monitor_lock:
        job = deps.passive_monitor_jobs.get(interface, {'interface': interface})
        job.update({
            'enabled': bool(enabled),
            'interval': interval,
            'mode': mode,
            'updated_at': time.time(),
        })
        if enabled and not job.get('started_at'):
            job['started_at'] = time.time()
        deps.passive_monitor_jobs[interface] = job
        should_start = enabled and not job.get('thread_alive')
        if should_start:
            job['thread_alive'] = True
    if should_start:
        def runner():
            try:
                _passive_monitor_worker(interface)
            finally:
                with deps.passive_monitor_lock:
                    current = deps.passive_monitor_jobs.get(interface)
                    if current:
                        current['thread_alive'] = False

        threading.Thread(target=runner, daemon=True).start()
    return passive_monitor_snapshot(interface)


def comprehensive_network_device_scan(
    selected_interface,
    include_passive=True,
    include_services=True,
    sweep_cidr=None,
):
    """Combine active, passive, ARP/neighbor, service, and optional ping-sweep discovery."""
    deps = _dependencies()
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
                item
                for item in enriched
                if not item.get('is_control_traffic')
            ]),
            'with_services': len([
                item
                for item in enriched
                if item.get('service_metadata')
                or item.get('service_metadata_list')
            ]),
        },
    }


__all__ = [
    'configure_passive_monitoring_context',
    'record_passive_observation_analytics',
    'passive_observation_summary',
    'passive_monitor_snapshot',
    '_passive_monitor_worker',
    'set_passive_monitor',
    'comprehensive_network_device_scan',
]
