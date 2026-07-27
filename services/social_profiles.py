"""Local, consent-focused individual profile records for social-engineering training."""

import re
import time
import uuid
from urllib.parse import urlparse


EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
PROFILE_FIELDS = ('full_name', 'email', 'facebook_url', 'linkedin_url', 'notes')
DEVICE_ICONS = {
    'iphone': 'fa-mobile-alt',
    'android': 'fa-mobile-alt',
    'laptop': 'fa-laptop',
    'desktop': 'fa-desktop',
    'tablet': 'fa-tablet-alt',
    'router': 'fa-wifi',
    'iot': 'fa-microchip',
    'other': 'fa-hdd',
}


def _clean_url(value, field_label):
    value = str(value or '').strip()
    if not value:
        return ''
    if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', value) and '://' not in value:
        raise ValueError(f'{field_label} must be a valid HTTP or HTTPS URL.')
    if '://' not in value:
        value = f'https://{value}'
    parsed = urlparse(value)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise ValueError(f'{field_label} must be a valid HTTP or HTTPS URL.')
    return value


def validate_profile(values):
    """Normalize submitted profile fields and reject unsafe or invalid links."""
    profile = {field: str(values.get(field) or '').strip() for field in PROFILE_FIELDS}
    if not profile['full_name']:
        raise ValueError('Full name is required.')
    if len(profile['full_name']) > 160:
        raise ValueError('Full name must be 160 characters or fewer.')
    if profile['email'] and not EMAIL_RE.fullmatch(profile['email']):
        raise ValueError('Email must be a valid address.')
    profile['facebook_url'] = _clean_url(profile['facebook_url'], 'Facebook link')
    profile['linkedin_url'] = _clean_url(profile['linkedin_url'], 'LinkedIn link')
    if len(profile['notes']) > 10000:
        raise ValueError('Notes must be 10,000 characters or fewer.')
    return profile


def list_profiles(store, lock):
    with lock:
        profiles = [dict(profile) for profile in store.values()]
    for profile in profiles:
        profile.setdefault('credentials', [])
        profile.setdefault('devices', [])
    return sorted(profiles, key=lambda profile: profile.get('updated_at', 0), reverse=True)


def get_profile(profile_id, store, lock):
    with lock:
        profile = store.get(profile_id)
        if not profile:
            return None
        result = dict(profile)
        result.setdefault('credentials', [])
        result.setdefault('devices', [])
        return result


def create_profile(values, store, lock, now=None):
    profile = validate_profile(values)
    timestamp = now if now is not None else time.time()
    profile.update({
        'id': str(uuid.uuid4()), 'created_at': timestamp, 'updated_at': timestamp,
        'credentials': [], 'devices': [],
    })
    with lock:
        store[profile['id']] = profile
    return dict(profile)


def update_profile(profile_id, values, store, lock, now=None):
    updates = validate_profile(values)
    with lock:
        if profile_id not in store:
            raise KeyError(profile_id)
        profile = {**store[profile_id], **updates, 'updated_at': now if now is not None else time.time()}
        store[profile_id] = profile
    return dict(profile)


def delete_profile(profile_id, store, lock):
    with lock:
        return store.pop(profile_id, None) is not None


def add_credential(profile_id, values, store, lock, now=None):
    """Add a website or device credential to a profile."""
    label = str(values.get('label') or '').strip()
    username = str(values.get('username') or '').strip()
    secret = str(values.get('secret') or '')
    website_url = _clean_url(values.get('website_url'), 'Website link')
    device_id = str(values.get('device_id') or '').strip()
    if not label:
        raise ValueError('Credential label is required.')
    if not username and not secret:
        raise ValueError('Enter a username or password/secret.')
    if len(secret) > 10000:
        raise ValueError('Password/secret must be 10,000 characters or fewer.')
    credential = {
        'id': str(uuid.uuid4()), 'label': label[:160], 'username': username[:320],
        'secret': secret, 'website_url': website_url, 'device_id': device_id,
        'created_at': now if now is not None else time.time(),
    }
    with lock:
        if profile_id not in store:
            raise KeyError(profile_id)
        if device_id and not any(item.get('id') == device_id for item in store[profile_id].get('devices', [])):
            raise ValueError('Selected device was not found on this profile.')
        store[profile_id].setdefault('credentials', []).append(credential)
        store[profile_id]['updated_at'] = credential['created_at']
    return dict(credential)


def delete_credential(profile_id, credential_id, store, lock):
    with lock:
        if profile_id not in store:
            raise KeyError(profile_id)
        credentials = store[profile_id].setdefault('credentials', [])
        remaining = [item for item in credentials if item.get('id') != credential_id]
        if len(remaining) == len(credentials):
            return False
        store[profile_id]['credentials'] = remaining
        store[profile_id]['updated_at'] = time.time()
        return True


def add_device(profile_id, values, store, lock, normalize_mac, now=None):
    """Add a device card with an optional inventory-match MAC address."""
    name = str(values.get('name') or '').strip()
    device_type = str(values.get('device_type') or 'other').strip().casefold()
    raw_mac = str(values.get('mac') or '').strip()
    mac = normalize_mac(raw_mac) if raw_mac else None
    if not name:
        raise ValueError('Device name is required.')
    if raw_mac and not mac:
        raise ValueError('MAC address must contain six hexadecimal octets.')
    if device_type not in DEVICE_ICONS:
        device_type = 'other'
    device = {
        'id': str(uuid.uuid4()), 'name': name[:160], 'device_type': device_type,
        'icon': DEVICE_ICONS[device_type], 'mac': mac,
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
        remaining = [item for item in devices if item.get('id') != device_id]
        if len(remaining) == len(devices):
            return False
        store[profile_id]['devices'] = remaining
        for credential in store[profile_id].setdefault('credentials', []):
            if credential.get('device_id') == device_id:
                credential['device_id'] = ''
        store[profile_id]['updated_at'] = time.time()
        return True
