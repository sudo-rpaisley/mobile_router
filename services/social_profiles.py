"""Local, consent-focused individual profile records for social-engineering training."""

import re
import time
import uuid
from copy import deepcopy
from urllib.parse import urlparse


EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
PROFILE_FIELDS = ('full_name', 'organization', 'job_title', 'phone', 'notes')
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
    getlist = values.getlist if hasattr(values, 'getlist') else lambda key: values.get(key, []) if isinstance(values.get(key, []), list) else [values.get(key, '')]
    email_labels = getlist('email_label')
    email_values = getlist('email_value')
    emails = []
    for index, raw_email in enumerate(email_values):
        email = str(raw_email or '').strip()
        if not email:
            continue
        if not EMAIL_RE.fullmatch(email):
            raise ValueError(f'Email #{index + 1} must be a valid address.')
        emails.append({'label': str(email_labels[index] if index < len(email_labels) else 'Email').strip()[:40] or 'Email', 'value': email})
    legacy_email = str(values.get('email') or '').strip()
    if legacy_email and not emails:
        if not EMAIL_RE.fullmatch(legacy_email):
            raise ValueError('Email must be a valid address.')
        emails.append({'label': 'Email', 'value': legacy_email})
    social_platforms = getlist('social_platform')
    social_urls = getlist('social_url')
    social_links = []
    for index, raw_url in enumerate(social_urls):
        if not str(raw_url or '').strip():
            continue
        platform = str(social_platforms[index] if index < len(social_platforms) else 'Website').strip()[:40] or 'Website'
        social_links.append({'platform': platform, 'url': _clean_url(raw_url, f'{platform} link')})
    for platform, key in (('Facebook', 'facebook_url'), ('LinkedIn', 'linkedin_url')):
        legacy_url = str(values.get(key) or '').strip()
        if legacy_url and not any(link['platform'] == platform for link in social_links):
            social_links.append({'platform': platform, 'url': _clean_url(legacy_url, f'{platform} link')})
    profile['emails'] = emails
    profile['email'] = emails[0]['value'] if emails else ''
    profile['social_links'] = social_links
    profile['facebook_url'] = next((link['url'] for link in social_links if link['platform'] == 'Facebook'), '')
    profile['linkedin_url'] = next((link['url'] for link in social_links if link['platform'] == 'LinkedIn'), '')
    if len(profile['notes']) > 10000:
        raise ValueError('Notes must be 10,000 characters or fewer.')
    return profile


def list_profiles(store, lock):
    with lock:
        profiles = [deepcopy(profile) for profile in store.values()]
    for profile in profiles:
        profile.setdefault('credentials', [])
        profile.setdefault('devices', [])
        profile.setdefault('emails', [{'label': 'Email', 'value': profile['email']}] if profile.get('email') else [])
        profile.setdefault('social_links', [
            {'platform': platform, 'url': profile.get(key)}
            for platform, key in (('Facebook', 'facebook_url'), ('LinkedIn', 'linkedin_url')) if profile.get(key)
        ])
        for credential in profile['credentials']:
            credential.setdefault('credential_kind', 'device' if credential.get('device_id') else ('website' if credential.get('website_url') else 'unassigned'))
            credential.setdefault('purpose', '')
            credential.setdefault('notes', '')
    return sorted(profiles, key=lambda profile: profile.get('updated_at', 0), reverse=True)


def get_profile(profile_id, store, lock):
    with lock:
        profile = store.get(profile_id)
        if not profile:
            return None
        result = deepcopy(profile)
        result.setdefault('credentials', [])
        result.setdefault('devices', [])
        result.setdefault('emails', [{'label': 'Email', 'value': result['email']}] if result.get('email') else [])
        result.setdefault('social_links', [
            {'platform': platform, 'url': result.get(key)}
            for platform, key in (('Facebook', 'facebook_url'), ('LinkedIn', 'linkedin_url')) if result.get(key)
        ])
        for credential in result['credentials']:
            credential.setdefault('credential_kind', 'device' if credential.get('device_id') else ('website' if credential.get('website_url') else 'unassigned'))
            credential.setdefault('purpose', '')
            credential.setdefault('notes', '')
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
    secret_ciphertext = str(values.get('secret_ciphertext') or '')
    website_url = _clean_url(values.get('website_url'), 'Website link')
    device_id = str(values.get('device_id') or '').strip()
    credential_kind = str(values.get('credential_kind') or '').strip().casefold()
    if credential_kind not in {'unassigned', 'website', 'device'}:
        credential_kind = 'device' if device_id else ('website' if website_url else 'unassigned')
    if not label:
        raise ValueError('Credential label is required.')
    if not username and not secret_ciphertext:
        raise ValueError('Enter a username or password/secret.')
    if secret_ciphertext and not secret_ciphertext.startswith('vault:v1:'):
        raise ValueError('Password/secret must be encrypted by the credential vault.')
    if len(secret_ciphertext) > 20000:
        raise ValueError('Encrypted password/secret is too large.')
    credential = {
        'id': str(uuid.uuid4()), 'label': label[:160], 'username': username[:320],
        'secret_ciphertext': secret_ciphertext, 'website_url': website_url, 'device_id': device_id,
        'credential_kind': credential_kind,
        'purpose': str(values.get('purpose') or '').strip()[:500],
        'notes': str(values.get('credential_notes') or '').strip()[:2000],
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
