"""Profile records, attachments, searching, and summary workflows."""

import time
import uuid
from copy import deepcopy
from datetime import date

from .credentials import credential_health
from .validation import validate_profile


def _normalize_profile(profile):
    """Apply backward-compatible defaults to a detached profile record."""
    profile.setdefault('credentials', [])
    profile.setdefault('devices', [])
    profile.setdefault(
        'emails',
        [{'label': 'Email', 'value': profile['email']}]
        if profile.get('email')
        else [],
    )
    profile.setdefault(
        'social_links',
        [
            {'platform': platform, 'url': profile.get(key)}
            for platform, key in (
                ('Facebook', 'facebook_url'),
                ('LinkedIn', 'linkedin_url'),
            )
            if profile.get(key)
        ],
    )
    profile.setdefault('phone_status', 'complete')
    profile.setdefault('phone_source', '')
    profile.setdefault('phone_confidence', 'unverified')
    profile.setdefault('phone_verified_date', '')
    profile.setdefault('tags', [])
    profile.setdefault('profile_status', 'active')
    profile.setdefault('relationships', [])
    profile.setdefault('attachments', [])
    profile.setdefault('identity_documents', [])
    profile.setdefault('signatures', [])
    profile.setdefault('custom_fields', [])
    profile.setdefault('retention_until', '')
    profile.setdefault('review_date', '')
    profile.setdefault('authorization_basis', '')

    for email in profile['emails']:
        email.setdefault('id', str(uuid.uuid4()))
        email.setdefault('status', 'complete')
        email.setdefault('source', '')
        email.setdefault('confidence', 'unverified')
        email.setdefault('verified_date', '')
    for link in profile['social_links']:
        link.setdefault('id', str(uuid.uuid4()))
        link.setdefault('status', 'complete')
        link.setdefault('account', '')
        link.setdefault('recovery_emails', [])
        link.setdefault('recovery_phone', '')
        link.setdefault('recovery_notes', '')
        link.setdefault('recovery_refs', [])
        link.setdefault('source', '')
        link.setdefault('confidence', 'unverified')
        link.setdefault('verified_date', '')
    for credential in profile['credentials']:
        credential.setdefault(
            'credential_kind',
            'device'
            if credential.get('device_id')
            else (
                'website'
                if credential.get('website_url')
                else 'unassigned'
            ),
        )
        credential.setdefault('purpose', '')
        credential.setdefault('notes', '')
    for device in profile['devices']:
        device.setdefault('manufacturer', '')
        device.setdefault('model', '')
        device.setdefault('operating_system', '')
        device.setdefault('hostname', '')
        device.setdefault('status', 'active')
    return profile


def list_profiles(store, lock):
    with lock:
        profiles = [
            _normalize_profile(deepcopy(profile))
            for profile in store.values()
        ]
    return sorted(
        profiles,
        key=lambda profile: profile.get('updated_at', 0),
        reverse=True,
    )


def get_profile(profile_id, store, lock):
    with lock:
        profile = store.get(profile_id)
        return _normalize_profile(deepcopy(profile)) if profile else None


def create_profile(values, store, lock, now=None):
    profile = validate_profile(values)
    timestamp = now if now is not None else time.time()
    profile.update(
        {
            'id': str(uuid.uuid4()),
            'created_at': timestamp,
            'updated_at': timestamp,
            'credentials': [],
            'devices': [],
        }
    )
    with lock:
        store[profile['id']] = profile
    return dict(profile)


def update_profile(profile_id, values, store, lock, now=None):
    updates = validate_profile(values)
    with lock:
        if profile_id not in store:
            raise KeyError(profile_id)
        profile = {
            **store[profile_id],
            **updates,
            'updated_at': now if now is not None else time.time(),
        }
        store[profile_id] = profile
    return dict(profile)


def delete_profile(profile_id, store, lock):
    with lock:
        removed = store.pop(profile_id, None)
        if removed:
            for profile in store.values():
                profile['relationships'] = [
                    item
                    for item in profile.get('relationships', [])
                    if item.get('target_profile_id') != profile_id
                ]
        return removed is not None


def add_attachment(profile_id, metadata, store, lock, now=None):
    item = {
        'id': str(uuid.uuid4()),
        'filename': metadata['filename'],
        'original_name': metadata['original_name'][:255],
        'description': str(metadata.get('description') or '')[:500],
        'sha256': metadata['sha256'],
        'size': metadata['size'],
        'created_at': now if now is not None else time.time(),
    }
    with lock:
        if profile_id not in store:
            raise KeyError(profile_id)
        store[profile_id].setdefault('attachments', []).append(item)
        return deepcopy(item)


def delete_attachment(profile_id, attachment_id, store, lock):
    with lock:
        if profile_id not in store:
            raise KeyError(profile_id)
        items = store[profile_id].setdefault('attachments', [])
        item = next(
            (
                entry
                for entry in items
                if entry.get('id') == attachment_id
            ),
            None,
        )
        if item:
            store[profile_id]['attachments'] = [
                entry
                for entry in items
                if entry.get('id') != attachment_id
            ]
        return deepcopy(item) if item else None


def dashboard_summary(profiles):
    today = date.today().isoformat()
    health = credential_health(profiles)
    return {
        **health,
        'profiles': len(profiles),
        'needs_review': sum(
            item.get('profile_status') == 'needs_review'
            for item in profiles
        ),
        'retention_due': sum(
            bool(item.get('retention_until'))
            and item['retention_until'] <= today
            for item in profiles
        ),
        'unmatched_devices': sum(
            not device.get('mac')
            for item in profiles
            for device in item.get('devices', [])
        ),
    }


def search_profiles(profiles, query='', status='', tag=''):
    query = str(query or '').strip().casefold()
    status = str(status or '').strip().casefold()
    tag = str(tag or '').strip().casefold()
    results = []
    for profile in profiles:
        if status and profile.get('profile_status') != status:
            continue
        if tag and tag not in {
            item.casefold() for item in profile.get('tags', [])
        }:
            continue
        searchable = [
            profile.get('full_name'),
            profile.get('organization'),
            profile.get('job_title'),
            profile.get('phone'),
            profile.get('notes'),
        ]
        searchable.extend(profile.get('tags', []))
        searchable.extend(
            [
                profile.get('authorization_basis'),
                profile.get('review_date'),
                profile.get('retention_until'),
            ]
        )
        for field in profile.get('custom_fields', []):
            searchable.extend([field.get('name'), field.get('value')])
        searchable.extend(
            item.get('value') for item in profile.get('emails', [])
        )
        for item in profile.get('social_links', []):
            searchable.extend(
                [
                    item.get('platform'),
                    item.get('account'),
                    item.get('url'),
                    item.get('source'),
                ]
            )
            searchable.extend(item.get('recovery_emails', []))
            searchable.append(item.get('recovery_phone'))
        for item in profile.get('devices', []):
            searchable.extend(
                [
                    item.get('name'),
                    item.get('mac'),
                    item.get('manufacturer'),
                    item.get('model'),
                    item.get('hostname'),
                ]
            )
        for item in profile.get('credentials', []):
            searchable.extend(
                [
                    item.get('label'),
                    item.get('username'),
                    item.get('purpose'),
                    item.get('notes'),
                ]
            )
        if query and query not in ' '.join(
            str(value or '') for value in searchable
        ).casefold():
            continue
        results.append(profile)
    return results
