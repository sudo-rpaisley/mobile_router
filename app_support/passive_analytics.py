"""Passive observation analytics and summaries."""

import time

from app_support.passive_monitoring_dependencies import (
    passive_monitoring_dependencies,
)


def record_passive_observation_analytics(
    interface,
    devices,
    source='passive-scan',
):
    """Track passive-only observation counts, churn, and quiet devices."""
    deps = passive_monitoring_dependencies()
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
            'new_count': len(seen_set - known_before),
            'quiet_count': len(quiet),
        }] + list(analytics.get('history') or []))[:100]
        snapshot = passive_observation_summary(iface, _locked=True)
    deps.save_runtime_state(f'passive-analytics:{source}')
    return snapshot


def passive_observation_summary(interface=None, _locked=False):
    """Return passive-only analytics for one interface or all interfaces."""
    deps = passive_monitoring_dependencies()

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

    def snapshots():
        if interface:
            empty = {'interface': interface, 'devices': {}, 'history': []}
            return build(
                interface,
                deps.passive_observation_analytics.get(interface, empty),
            )
        return {
            iface: build(iface, analytics)
            for iface, analytics in deps.passive_observation_analytics.items()
        }

    if _locked:
        return snapshots()
    with deps.passive_analytics_lock:
        return snapshots()
