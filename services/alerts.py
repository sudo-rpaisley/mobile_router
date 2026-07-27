"""Alert record helpers for newly discovered devices and watched clients."""

import time
import uuid
from urllib.parse import quote


def create_new_device_alert(device, source, interface, alert_store, lock):
    """Record an unread alert for a newly observed inventory device."""
    display_name = device.get('name') or device.get('hostname') or device.get('ssid') or device.get('ip') or device.get('mac') or 'Unknown device'
    device_identifier = device.get('mac') or device.get('bssid') or device.get('ip')
    device_url = f"/clients/{quote(str(device_identifier))}" if device_identifier else None
    alert = {
        'id': uuid.uuid4().hex,
        'device_id': device.get('id'),
        'display_name': display_name,
        'ip': device.get('ip'),
        'mac': device.get('mac') or device.get('bssid'),
        'manufacturer': device.get('manufacturer') or 'Unknown',
        'device_url': device_url,
        'source': source,
        'interface': interface,
        'created_at': time.time(),
        'read': False,
    }
    with lock:
        alert_store.insert(0, alert)
        del alert_store[200:]
    return alert


def create_grouped_device_alert(devices, source, interface, alert_store, lock):
    """Record one unread alert for a batch of newly observed devices."""
    devices = [dict(device) for device in devices or []]
    alert = {
        'id': uuid.uuid4().hex,
        'alert_type': 'grouped-discovery',
        'display_name': f"{len(devices)} new devices discovered",
        'ip': None,
        'mac': None,
        'manufacturer': 'Multiple',
        'device_url': '/inventory',
        'source': source,
        'interface': interface,
        'created_at': time.time(),
        'read': False,
        'device_count': len(devices),
        'devices': [
            {
                'id': device.get('id'),
                'display_name': device.get('name') or device.get('hostname') or device.get('ssid') or device.get('ip') or device.get('mac') or 'Unknown device',
                'ip': device.get('ip'),
                'mac': device.get('mac') or device.get('bssid'),
                'manufacturer': device.get('manufacturer') or 'Unknown',
            }
            for device in devices[:10]
        ],
    }
    with lock:
        alert_store.insert(0, alert)
        del alert_store[200:]
    return alert


def alert_records(alert_store, lock):
    """Return alert records with display labels."""
    with lock:
        records = [dict(alert) for alert in alert_store]
    for alert in records:
        alert['created_at_label'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(alert.get('created_at', 0)))
    return records


def unread_alert_count(alert_store, lock):
    with lock:
        return len([alert for alert in alert_store if not alert.get('read')])


def mark_alert_read(alert_id, alert_store, lock):
    with lock:
        for alert in alert_store:
            if alert['id'] == alert_id:
                alert['read'] = True
                unread_count = len([item for item in alert_store if not item.get('read')])
                return dict(alert), unread_count
    return None, None


def mark_all_alerts_read(alert_store, lock):
    with lock:
        for alert in alert_store:
            alert['read'] = True
    return 0
