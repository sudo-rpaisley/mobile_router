"""Device cards attached to consent-based individual profiles."""

import time
import uuid
from copy import deepcopy

from .validation import DEVICE_ICONS


def add_device(profile_id, values, store, lock, normalize_mac, now=None):
    """Add a device card with an optional inventory-match MAC address."""
    name = str(values.get('name') or '').strip()
    device_type = str(
        values.get('device_type') or 'other'
    ).strip().casefold()
    raw_mac = str(
        values.get('inventory_mac') or values.get('mac') or ''
    ).strip()
    mac = normalize_mac(raw_mac) if raw_mac else None
    if not name:
        raise ValueError('Device name is required.')
    if raw_mac and not mac:
        raise ValueError('MAC address must contain six hexadecimal octets.')
    if device_type not in DEVICE_ICONS:
        device_type = 'other'

    device = {
        'id': str(uuid.uuid4()),
        'name': name[:160],
        'device_type': device_type,
        'icon': DEVICE_ICONS[device_type],
        'mac': mac,
        'manufacturer': str(
            values.get('manufacturer') or ''
        ).strip()[:160],
        'model': str(values.get('model') or '').strip()[:160],
        'operating_system': str(
            values.get('operating_system') or ''
        ).strip()[:160],
        'hostname': str(values.get('hostname') or '').strip()[:253],
        'status': str(
            values.get('device_status') or 'active'
        ).strip().casefold()[:40],
        'notes': str(values.get('notes') or '').strip()[:2000],
        'created_at': now if now is not None else time.time(),
    }
    with lock:
        if profile_id not in store:
            raise KeyError(profile_id)
        store[profile_id].setdefault('devices', []).append(device)
        store[profile_id]['updated_at'] = device['created_at']
    return dict(device)


def delete_device(profile_id, device_id, store, lock):
    with lock:
        if profile_id not in store:
            raise KeyError(profile_id)
        devices = store[profile_id].setdefault('devices', [])
        remaining = [
            item for item in devices if item.get('id') != device_id
        ]
        if len(remaining) == len(devices):
            return False
        store[profile_id]['devices'] = remaining
        for credential in store[profile_id].setdefault('credentials', []):
            if credential.get('device_id') == device_id:
                credential['device_id'] = ''
        store[profile_id]['updated_at'] = time.time()
        return True


def update_device(
    profile_id,
    device_id,
    values,
    store,
    lock,
    normalize_mac,
    now=None,
):
    with lock:
        if profile_id not in store:
            raise KeyError(profile_id)
        device = next(
            (
                item
                for item in store[profile_id].get('devices', [])
                if item.get('id') == device_id
            ),
            None,
        )
        if not device:
            raise KeyError(device_id)
        raw_mac = str(
            values.get('inventory_mac') or values.get('mac') or ''
        ).strip()
        mac = normalize_mac(raw_mac) if raw_mac else None
        if raw_mac and not mac:
            raise ValueError('MAC address must contain six hexadecimal octets.')
        device_type = str(
            values.get('device_type')
            or device.get('device_type')
            or 'other'
        ).casefold()
        if device_type not in DEVICE_ICONS:
            device_type = 'other'
        device.update(
            {
                'name': (
                    str(values.get('name') or '').strip()[:160]
                    or device.get('name')
                ),
                'device_type': device_type,
                'icon': DEVICE_ICONS[device_type],
                'mac': mac,
                'manufacturer': str(
                    values.get('manufacturer') or ''
                ).strip()[:160],
                'model': str(values.get('model') or '').strip()[:160],
                'operating_system': str(
                    values.get('operating_system') or ''
                ).strip()[:160],
                'hostname': str(
                    values.get('hostname') or ''
                ).strip()[:253],
                'status': str(
                    values.get('device_status') or 'active'
                ).strip().casefold()[:40],
                'notes': str(
                    values.get('notes') or ''
                ).strip()[:2000],
                'updated_at': now if now is not None else time.time(),
            }
        )
        store[profile_id]['updated_at'] = device['updated_at']
        return deepcopy(device)
