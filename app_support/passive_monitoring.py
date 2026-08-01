"""Passive observation analytics, monitor workers, and combined scans."""

from app_support.context import context_refresher


_CONTEXT_PROVIDER = None


def configure_passive_monitoring_context(provider):
    global _CONTEXT_PROVIDER
    _CONTEXT_PROVIDER = provider


_refresh_context = context_refresher(globals(), lambda: _CONTEXT_PROVIDER)


@_refresh_context
def record_passive_observation_analytics(interface, devices, source='passive-scan'):
    """Track passive-only observation counts, churn, and quiet devices per interface."""
    iface = str(interface or 'unknown').strip() or 'unknown'
    now = time.time()
    seen_identities = []
    with passive_analytics_lock:
        analytics = passive_observation_analytics.setdefault(iface, {
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
            identity = passive_device_identity(device)
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
                'mac': normalize_mac(device.get('mac') or device.get('address')) or record.get('mac'),
                'hostname': device.get('hostname') or device.get('name') or record.get('hostname'),
                'manufacturer': device.get('manufacturer') or record.get('manufacturer') or 'Unknown',
            })
            record['seen_count'] = int(record.get('seen_count') or 0) + 1
            sources = set(record.get('sources') or [])
            sources.add(source)
            record['sources'] = sorted(sources)
        seen_set = set(seen_identities)
        new_count = len(seen_set - known_before)
        quiet = [identity for identity in known_before if identity not in seen_set]
        analytics['last_update'] = now
        analytics['total_samples'] = int(analytics.get('total_samples') or 0) + 1
        analytics['last_seen_identities'] = sorted(seen_set)
        analytics['history'] = ([{
            'timestamp': now,
            'source': source,
            'observed_count': len(seen_set),
            'new_count': new_count,
            'quiet_count': len(quiet),
        }] + list(analytics.get('history') or []))[:100]
        snapshot = passive_observation_summary(iface, _locked=True)
    save_runtime_state(f'passive-analytics:{source}')
    return snapshot


@_refresh_context
def passive_observation_summary(interface=None, _locked=False):
    """Return passive-only analytics for one interface or all interfaces."""
    def build(iface, analytics):
        devices = list((analytics.get('devices') or {}).values())
        last_seen = set(analytics.get('last_seen_identities') or [])
        recently_disappeared = sorted(
            [dict(item) for item in devices if item.get('identity') not in last_seen],
            key=lambda item: item.get('last_seen') or 0,
            reverse=True,
        )[:25]
        active = sorted(
            [dict(item) for item in devices if item.get('identity') in last_seen],
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
    if _locked:
        if interface:
            return build(interface, passive_observation_analytics.get(interface, {'interface': interface, 'devices': {}, 'history': []}))
        return {iface: build(iface, analytics) for iface, analytics in passive_observation_analytics.items()}
    with passive_analytics_lock:
        if interface:
            return build(interface, passive_observation_analytics.get(interface, {'interface': interface, 'devices': {}, 'history': []}))
        return {iface: build(iface, analytics) for iface, analytics in passive_observation_analytics.items()}


@_refresh_context
def passive_monitor_snapshot(interface=None):
    """Return passive ARP-cache monitor state for one interface or all interfaces."""
    with passive_monitor_lock:
        if interface:
            job = passive_monitor_jobs.get(interface)
            return dict(job) if job else {'interface': interface, 'enabled': False}
        return {name: dict(job) for name, job in passive_monitor_jobs.items()}


@_refresh_context
def _passive_monitor_worker(interface):
    """Continuously refresh passive inventory from cache or packet observations."""
    while True:
        with passive_monitor_lock:
            job = passive_monitor_jobs.get(interface)
            if not job or not job.get('enabled'):
                return
            interval = job.get('interval', 10)
            mode = job.get('mode', 'cache')
        sleep_for = 0.1 if mode == 'packet' else interval
        try:
            if mode == 'packet':
                source = 'passive-packet-monitor'
                raw_devices = packet_passive_scan(interface, timeout=interval, packet_limit=250, manufacturer_lookup=lookup_manufacturer)
            else:
                source = 'passive-monitor'
                raw_devices = passive_scan(interface)
            devices = classify_scan_results(raw_devices, interface)
            enriched = record_inventory_devices(devices, source, interface)
            analytics = record_passive_observation_analytics(interface, enriched, source)
            with passive_monitor_lock:
                current = passive_monitor_jobs.get(interface)
                if current:
                    current.update({
                        'last_update': time.time(),
                        'last_count': len(enriched),
                        'analytics': analytics,
                        'mode': mode,
                        'error': None,
                    })
        except Exception as exc:
            with passive_monitor_lock:
                current = passive_monitor_jobs.get(interface)
                if current:
                    current.update({'last_update': time.time(), 'error': str(exc), 'mode': mode})
        time.sleep(sleep_for)


@_refresh_context
def set_passive_monitor(interface, enabled, interval=10, mode='cache'):
    """Start or stop a background passive monitor for an interface."""
    interface = (interface or '').strip()
    if not interface:
        raise ValueError('Missing interface')
    mode = 'packet' if str(mode or '').strip().lower() in {'packet', 'live', 'live-packet'} else 'cache'
    if mode == 'packet':
        interval = max(1, min(parse_int(interval, 'Capture window must be an integer'), 10))
    else:
        interval = max(5, min(parse_int(interval, 'Interval must be an integer'), 300))
    with passive_monitor_lock:
        job = passive_monitor_jobs.get(interface, {'interface': interface})
        job.update({
            'enabled': bool(enabled),
            'interval': interval,
            'mode': mode,
            'updated_at': time.time(),
        })
        if enabled and not job.get('started_at'):
            job['started_at'] = time.time()
        passive_monitor_jobs[interface] = job
        should_start = enabled and not job.get('thread_alive')
        if should_start:
            job['thread_alive'] = True
    if should_start:
        def runner():
            try:
                _passive_monitor_worker(interface)
            finally:
                with passive_monitor_lock:
                    current = passive_monitor_jobs.get(interface)
                    if current:
                        current['thread_alive'] = False
        threading.Thread(target=runner, daemon=True).start()
    return passive_monitor_snapshot(interface)


@_refresh_context
def comprehensive_network_device_scan(selected_interface, include_passive=True, include_services=True, sweep_cidr=None):
    """Combine active, passive, ARP/neighbor, service, and optional ping-sweep discovery."""
    if not selected_interface:
        raise ValueError('Missing interface')
    groups = []
    errors = []
    try:
        groups.append(('active-arp', classify_scan_results(active_scan(selected_interface), selected_interface)))
    except Exception as exc:
        errors.append(f'active scan: {exc}')
    if include_passive:
        try:
            groups.append(('passive-observation', classify_scan_results(passive_scan(selected_interface), selected_interface)))
        except Exception as exc:
            errors.append(f'passive scan: {exc}')
    if os.name != 'nt':
        neigh = _run_text_command(['ip', 'neigh', 'show', 'dev', selected_interface], timeout=5)
        groups.append(('neighbor-table', parse_neighbor_table(neigh.get('output'))))
        arp = _run_text_command(['arp', '-an'], timeout=5)
        groups.append(('arp-cache', parse_neighbor_table(arp.get('output'))))
    if sweep_cidr:
        try:
            sweep = run_ping_sweep(sweep_cidr, count=1, timeout=1)
            groups.append(('ping-sweep', [{'ip': item.get('host'), 'discovery_methods': ['ping-sweep'], 'reachable': item.get('reachable')} for item in sweep.get('results', []) if item.get('reachable')]))
        except Exception as exc:
            errors.append(f'ping sweep: {exc}')
    if include_services:
        mdns = discover_mdns_services(selected_interface)
        groups.append(('mdns', [{'ip': service.get('ip'), 'hostname': service.get('hostname'), 'name': service.get('name'), 'device_type': service.get('role'), 'service_metadata': service, 'discovery_methods': ['mdns']} for service in mdns.get('services', [])]))
        upnp = discover_upnp_devices(timeout=2)
        groups.append(('upnp-ssdp', [{'ip': device.get('ip'), 'name': device.get('friendly_name'), 'manufacturer': device.get('manufacturer'), 'device_type': device.get('role'), 'service_metadata': device, 'discovery_methods': ['upnp-ssdp']} for device in upnp.get('devices', [])]))
        lldp = discover_lldp_neighbors(selected_interface)
        groups.append(('lldp-cdp', [{'ip': neighbor.get('management_address'), 'name': neighbor.get('name'), 'device_type': neighbor.get('role'), 'service_metadata': neighbor, 'discovery_methods': ['lldp-cdp']} for neighbor in lldp.get('neighbors', [])]))
    merged = merge_discovered_devices(groups)
    enriched = record_inventory_devices(merged, 'comprehensive-network-scan', selected_interface)
    return {
        'devices': enriched,
        'methods': [method for method, _devices in groups],
        'errors': errors,
        'summary': {
            'total_devices': len(enriched),
            'host_like': len([item for item in enriched if not item.get('is_control_traffic')]),
            'with_services': len([item for item in enriched if item.get('service_metadata') or item.get('service_metadata_list')]),
        },
    }


__all__ = [
    'record_passive_observation_analytics',
    'passive_observation_summary',
    'passive_monitor_snapshot',
    '_passive_monitor_worker',
    'set_passive_monitor',
    'comprehensive_network_device_scan'
]
