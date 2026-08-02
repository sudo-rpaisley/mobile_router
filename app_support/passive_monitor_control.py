"""Passive monitor worker lifecycle and state control."""

import threading
import time

from app_support.passive_analytics import record_passive_observation_analytics
from app_support.passive_monitoring_dependencies import (
    passive_monitoring_dependencies,
)


def passive_monitor_snapshot(interface=None):
    """Return passive monitor state for one interface or all interfaces."""
    deps = passive_monitoring_dependencies()
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
    deps = passive_monitoring_dependencies()
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
    deps = passive_monitoring_dependencies()
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
