"""Credential records attached to consent-based individual profiles."""

import time
import uuid
from copy import deepcopy

from .validation import _clean_url


def credential_health(profiles):
    credentials = [
        item
        for profile in profiles
        for item in profile.get('credentials', [])
    ]
    return {
        'total': len(credentials),
        'unknown_purpose': sum(
            item.get('credential_kind') == 'unassigned'
            for item in credentials
        ),
        'missing_username': sum(
            not item.get('username') for item in credentials
        ),
        'never_rotated': sum(
            not item.get('rotated_at') for item in credentials
        ),
    }


def add_credential(profile_id, values, store, lock, now=None):
    """Add a website or device credential to a profile."""
    label = str(values.get('label') or '').strip()
    username = str(values.get('username') or '').strip()
    secret_ciphertext = str(values.get('secret_ciphertext') or '')
    website_url = _clean_url(values.get('website_url'), 'Website link')
    device_id = str(values.get('device_id') or '').strip()
    credential_kind = str(
        values.get('credential_kind') or ''
    ).strip().casefold()
    if credential_kind not in {'unassigned', 'website', 'device'}:
        credential_kind = (
            'device'
            if device_id
            else ('website' if website_url else 'unassigned')
        )
    if not label:
        raise ValueError('Credential label is required.')
    if not username and not secret_ciphertext:
        raise ValueError('Enter a username or password/secret.')
    if secret_ciphertext and not secret_ciphertext.startswith('vault:v1:'):
        raise ValueError(
            'Password/secret must be encrypted by the credential vault.'
        )
    if len(secret_ciphertext) > 20000:
        raise ValueError('Encrypted password/secret is too large.')

    credential = {
        'id': str(uuid.uuid4()),
        'label': label[:160],
        'username': username[:320],
        'secret_ciphertext': secret_ciphertext,
        'website_url': website_url,
        'device_id': device_id,
        'credential_kind': credential_kind,
        'purpose': str(values.get('purpose') or '').strip()[:500],
        'notes': str(values.get('credential_notes') or '').strip()[:2000],
        'created_at': now if now is not None else time.time(),
    }
    with lock:
        if profile_id not in store:
            raise KeyError(profile_id)
        if device_id and not any(
            item.get('id') == device_id
            for item in store[profile_id].get('devices', [])
        ):
            raise ValueError('Selected device was not found on this profile.')
        store[profile_id].setdefault('credentials', []).append(credential)
        store[profile_id]['updated_at'] = credential['created_at']
    return dict(credential)


def delete_credential(profile_id, credential_id, store, lock):
    with lock:
        if profile_id not in store:
            raise KeyError(profile_id)
        credentials = store[profile_id].setdefault('credentials', [])
        remaining = [
            item
            for item in credentials
            if item.get('id') != credential_id
        ]
        if len(remaining) == len(credentials):
            return False
        store[profile_id]['credentials'] = remaining
        store[profile_id]['updated_at'] = time.time()
        return True


def update_credential(
    profile_id,
    credential_id,
    values,
    store,
    lock,
    now=None,
):
    """Update credential metadata and optionally rotate its encrypted secret."""
    with lock:
        if profile_id not in store:
            raise KeyError(profile_id)
        credential = next(
            (
                item
                for item in store[profile_id].get('credentials', [])
                if item.get('id') == credential_id
            ),
            None,
        )
        if not credential:
            raise KeyError(credential_id)
        device_id = str(values.get('device_id') or '').strip()
        if device_id and not any(
            item.get('id') == device_id
            for item in store[profile_id].get('devices', [])
        ):
            raise ValueError('Selected device was not found on this profile.')
        website_url = _clean_url(
            values.get('website_url'),
            'Website link',
        )
        kind = str(
            values.get('credential_kind')
            or credential.get('credential_kind')
            or 'unassigned'
        ).casefold()
        if kind not in {'unassigned', 'website', 'device'}:
            kind = 'unassigned'
        rotated_ciphertext = str(values.get('secret_ciphertext') or '')
        if rotated_ciphertext and not rotated_ciphertext.startswith('vault:v1:'):
            raise ValueError(
                'Password/secret must be encrypted by the credential vault.'
            )
        credential.update(
            {
                'label': (
                    str(values.get('label') or '').strip()[:160]
                    or credential.get('label')
                ),
                'username': str(
                    values.get('username') or ''
                ).strip()[:320],
                'website_url': website_url,
                'device_id': device_id,
                'credential_kind': kind,
                'purpose': str(
                    values.get('purpose') or ''
                ).strip()[:500],
                'notes': str(
                    values.get('credential_notes') or ''
                ).strip()[:2000],
                'updated_at': now if now is not None else time.time(),
            }
        )
        if rotated_ciphertext:
            credential['secret_ciphertext'] = rotated_ciphertext
            credential['rotated_at'] = credential['updated_at']
        store[profile_id]['updated_at'] = credential['updated_at']
        return deepcopy(credential)
