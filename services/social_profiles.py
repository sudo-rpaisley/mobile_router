"""Local, consent-focused individual profile records for social-engineering training."""

import re
import time
import uuid
from urllib.parse import urlparse


EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
PROFILE_FIELDS = ('full_name', 'email', 'facebook_url', 'linkedin_url', 'notes')


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
    return sorted(profiles, key=lambda profile: profile.get('updated_at', 0), reverse=True)


def get_profile(profile_id, store, lock):
    with lock:
        profile = store.get(profile_id)
        return dict(profile) if profile else None


def create_profile(values, store, lock, now=None):
    profile = validate_profile(values)
    timestamp = now if now is not None else time.time()
    profile.update({'id': str(uuid.uuid4()), 'created_at': timestamp, 'updated_at': timestamp})
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
