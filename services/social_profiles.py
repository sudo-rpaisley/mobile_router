"""Local, consent-focused individual profile records for social-engineering training."""

import re
import time
import uuid
from datetime import date
from copy import deepcopy
from urllib.parse import urlparse


EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
PROFILE_FIELDS = ('full_name', 'organization', 'job_title', 'phone', 'notes')
PROFILE_STATUSES = {'active', 'needs_review', 'archived'}
CONFIDENCE_LEVELS = {'confirmed', 'likely', 'possible', 'unverified'}
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
    email_ids = getlist('email_id')
    email_labels = getlist('email_label')
    email_values = getlist('email_value')
    email_statuses = getlist('email_status')
    email_sources = getlist('email_source')
    email_confidences = getlist('email_confidence')
    email_verified_dates = getlist('email_verified_date')
    emails = []
    for index, raw_email in enumerate(email_values):
        email = str(raw_email or '').strip()
        if not email:
            continue
        status = 'partial' if index < len(email_statuses) and email_statuses[index] == 'partial' else 'complete'
        if status == 'complete' and not EMAIL_RE.fullmatch(email):
            raise ValueError(f'Email #{index + 1} must be a valid address.')
        confidence = str(email_confidences[index] if index < len(email_confidences) else 'unverified').casefold()
        emails.append({
            'id': str(email_ids[index] if index < len(email_ids) else '').strip() or str(uuid.uuid4()),
            'label': str(email_labels[index] if index < len(email_labels) else 'Email').strip()[:40] or 'Email',
            'value': email[:320], 'status': status,
            'source': str(email_sources[index] if index < len(email_sources) else '').strip()[:160],
            'confidence': confidence if confidence in CONFIDENCE_LEVELS else 'unverified',
            'verified_date': str(email_verified_dates[index] if index < len(email_verified_dates) else '').strip()[:10],
        })
    legacy_email = str(values.get('email') or '').strip()
    if legacy_email and not emails:
        if not EMAIL_RE.fullmatch(legacy_email):
            raise ValueError('Email must be a valid address.')
        emails.append({'id': str(uuid.uuid4()), 'label': 'Email', 'value': legacy_email, 'status': 'complete', 'source': '', 'confidence': 'unverified', 'verified_date': ''})
    social_platforms = getlist('social_platform')
    social_urls = getlist('social_url')
    social_statuses = getlist('social_status')
    social_accounts = getlist('social_account')
    social_recovery_emails = getlist('social_recovery_emails')
    social_recovery_phones = getlist('social_recovery_phone')
    social_recovery_notes = getlist('social_recovery_notes')
    social_recovery_refs = getlist('social_recovery_refs')
    social_sources = getlist('social_source')
    social_confidences = getlist('social_confidence')
    social_verified_dates = getlist('social_verified_date')
    social_ids = getlist('social_id')
    social_links = []
    for index, raw_url in enumerate(social_urls):
        if not str(raw_url or '').strip():
            continue
        platform = str(social_platforms[index] if index < len(social_platforms) else 'Website').strip()[:40] or 'Website'
        status = 'partial' if index < len(social_statuses) and social_statuses[index] == 'partial' else 'complete'
        url = str(raw_url).strip()[:1000] if status == 'partial' else _clean_url(raw_url, f'{platform} link')
        recovery_emails = [item.strip()[:320] for item in str(social_recovery_emails[index] if index < len(social_recovery_emails) else '').split(',') if item.strip()]
        social_links.append({
            'id': str(social_ids[index] if index < len(social_ids) else '').strip() or str(uuid.uuid4()),
            'platform': platform, 'url': url, 'status': status,
            'account': str(social_accounts[index] if index < len(social_accounts) else '').strip()[:320],
            'recovery_emails': recovery_emails,
            'recovery_phone': str(social_recovery_phones[index] if index < len(social_recovery_phones) else '').strip()[:100],
            'recovery_notes': str(social_recovery_notes[index] if index < len(social_recovery_notes) else '').strip()[:1000],
            'recovery_refs': [item.strip() for item in str(social_recovery_refs[index] if index < len(social_recovery_refs) else '').split(',') if item.strip()],
            'source': str(social_sources[index] if index < len(social_sources) else '').strip()[:160],
            'confidence': (str(social_confidences[index] if index < len(social_confidences) else 'unverified').casefold()
                           if str(social_confidences[index] if index < len(social_confidences) else 'unverified').casefold() in CONFIDENCE_LEVELS else 'unverified'),
            'verified_date': str(social_verified_dates[index] if index < len(social_verified_dates) else '').strip()[:10],
        })
    for platform, key in (('Facebook', 'facebook_url'), ('LinkedIn', 'linkedin_url')):
        legacy_url = str(values.get(key) or '').strip()
        if legacy_url and not any(link['platform'] == platform for link in social_links):
            social_links.append({'id': str(uuid.uuid4()), 'platform': platform, 'url': _clean_url(legacy_url, f'{platform} link')})
    profile['emails'] = emails
    profile['email'] = emails[0]['value'] if emails else ''
    profile['social_links'] = social_links
    profile['phone_status'] = 'partial' if values.get('phone_status') == 'partial' else 'complete'
    profile['phone_source'] = str(values.get('phone_source') or '').strip()[:160]
    phone_confidence = str(values.get('phone_confidence') or 'unverified').casefold()
    profile['phone_confidence'] = phone_confidence if phone_confidence in CONFIDENCE_LEVELS else 'unverified'
    profile['phone_verified_date'] = str(values.get('phone_verified_date') or '').strip()[:10]
    profile['tags'] = sorted({tag.strip()[:40] for tag in str(values.get('tags') or '').split(',') if tag.strip()}, key=str.casefold)
    status = str(values.get('profile_status') or 'active').casefold()
    profile['profile_status'] = status if status in PROFILE_STATUSES else 'active'
    profile['retention_until'] = str(values.get('retention_until') or '').strip()[:10]
    profile['review_date'] = str(values.get('review_date') or '').strip()[:10]
    if any(value and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) for value in (profile['retention_until'], profile['review_date'])):
        raise ValueError('Review and retention dates must use YYYY-MM-DD.')
    profile['authorization_basis'] = str(values.get('authorization_basis') or '').strip()[:500]
    custom_names = getlist('custom_field_name')
    custom_values = getlist('custom_field_value')
    custom_types = getlist('custom_field_type')
    profile['custom_fields'] = [
        {'id': str(uuid.uuid4()), 'name': str(name).strip()[:80],
         'value': str(custom_values[index] if index < len(custom_values) else '').strip()[:2000],
         'type': str(custom_types[index] if index < len(custom_types) else 'text').strip()[:20]}
        for index, name in enumerate(custom_names) if str(name or '').strip()
    ]
    profile['facebook_url'] = next((link['url'] for link in social_links if link['platform'] == 'Facebook'), '')
    profile['linkedin_url'] = next((link['url'] for link in social_links if link['platform'] == 'LinkedIn'), '')
    if len(profile['notes']) > 10000:
        raise ValueError('Notes must be 10,000 characters or fewer.')
    return profile


def _normalize_profile(profile):
    """Apply backward-compatible defaults to a detached profile record."""
    profile.setdefault('credentials', [])
    profile.setdefault('devices', [])
    profile.setdefault('emails', [{'label': 'Email', 'value': profile['email']}] if profile.get('email') else [])
    profile.setdefault('social_links', [
        {'platform': platform, 'url': profile.get(key)}
        for platform, key in (('Facebook', 'facebook_url'), ('LinkedIn', 'linkedin_url')) if profile.get(key)
    ])
    profile.setdefault('phone_status', 'complete')
    profile.setdefault('phone_source', '')
    profile.setdefault('phone_confidence', 'unverified')
    profile.setdefault('phone_verified_date', '')
    profile.setdefault('tags', [])
    profile.setdefault('profile_status', 'active')
    profile.setdefault('relationships', [])
    profile.setdefault('attachments', [])
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
        credential.setdefault('credential_kind', 'device' if credential.get('device_id') else ('website' if credential.get('website_url') else 'unassigned'))
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
        profiles = [_normalize_profile(deepcopy(profile)) for profile in store.values()]
    return sorted(profiles, key=lambda profile: profile.get('updated_at', 0), reverse=True)


def get_profile(profile_id, store, lock):
    with lock:
        profile = store.get(profile_id)
        return _normalize_profile(deepcopy(profile)) if profile else None

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


def add_relationship(profile_id, values, store, lock, now=None):
    target_id = str(values.get('target_profile_id') or '')
    relationship = str(values.get('relationship') or '').strip()[:80]
    if not relationship or target_id == profile_id:
        raise ValueError('Choose another individual and enter a relationship.')
    with lock:
        if profile_id not in store or target_id not in store:
            raise KeyError(target_id)
        if store[profile_id].get('owner') != store[target_id].get('owner'):
            raise ValueError('Relationships can only link your own profiles.')
        item = {'id': str(uuid.uuid4()), 'target_profile_id': target_id,
                'relationship': relationship, 'notes': str(values.get('notes') or '').strip()[:500],
                'created_at': now if now is not None else time.time()}
        store[profile_id].setdefault('relationships', []).append(item)
        store[profile_id]['updated_at'] = item['created_at']
        return deepcopy(item)


def delete_relationship(profile_id, relationship_id, store, lock):
    with lock:
        if profile_id not in store:
            raise KeyError(profile_id)
        items = store[profile_id].setdefault('relationships', [])
        store[profile_id]['relationships'] = [item for item in items if item.get('id') != relationship_id]
        return len(items) != len(store[profile_id]['relationships'])


def duplicate_candidates(profiles):
    """Return likely duplicate pairs based on normalized identity values."""
    candidates = []
    for index, left in enumerate(profiles):
        left_values = {str(left.get('full_name') or '').casefold().strip()}
        left_values.update(str(item.get('value') or '').casefold() for item in left.get('emails', []))
        left_values.update(str(item.get('mac') or '').casefold() for item in left.get('devices', []))
        left_values.discard('')
        for right in profiles[index + 1:]:
            right_values = {str(right.get('full_name') or '').casefold().strip()}
            right_values.update(str(item.get('value') or '').casefold() for item in right.get('emails', []))
            right_values.update(str(item.get('mac') or '').casefold() for item in right.get('devices', []))
            matches = sorted(left_values & (right_values - {''}))
            if matches:
                candidates.append({'primary': left, 'duplicate': right, 'matches': matches})
    return candidates


def merge_profiles(primary_id, duplicate_id, store, lock, now=None):
    if primary_id == duplicate_id:
        raise ValueError('Choose two different profiles.')
    with lock:
        primary, duplicate = store.get(primary_id), store.get(duplicate_id)
        if not primary or not duplicate:
            raise KeyError(duplicate_id)
        if primary.get('owner') != duplicate.get('owner'):
            raise ValueError('Profiles must have the same owner.')
        for field in ('emails', 'social_links', 'devices', 'credentials', 'relationships', 'attachments', 'custom_fields'):
            existing = {item.get('id') for item in primary.setdefault(field, [])}
            primary[field].extend(deepcopy(item) for item in duplicate.get(field, []) if item.get('id') not in existing)
        primary['tags'] = sorted(set(primary.get('tags', [])) | set(duplicate.get('tags', [])), key=str.casefold)
        primary['notes'] = '\n\n'.join(filter(None, [primary.get('notes'), duplicate.get('notes')]))[:10000]
        primary['updated_at'] = now if now is not None else time.time()
        del store[duplicate_id]
        for profile in store.values():
            for relation in profile.get('relationships', []):
                if relation.get('target_profile_id') == duplicate_id:
                    relation['target_profile_id'] = primary_id
        return deepcopy(primary)


def add_attachment(profile_id, metadata, store, lock, now=None):
    item = {'id': str(uuid.uuid4()), 'filename': metadata['filename'],
            'original_name': metadata['original_name'][:255], 'description': str(metadata.get('description') or '')[:500],
            'sha256': metadata['sha256'], 'size': metadata['size'], 'created_at': now if now is not None else time.time()}
    with lock:
        if profile_id not in store:
            raise KeyError(profile_id)
        store[profile_id].setdefault('attachments', []).append(item)
        return deepcopy(item)


def credential_health(profiles):
    credentials = [item for profile in profiles for item in profile.get('credentials', [])]
    return {
        'total': len(credentials),
        'unknown_purpose': sum(item.get('credential_kind') == 'unassigned' for item in credentials),
        'missing_username': sum(not item.get('username') for item in credentials),
        'never_rotated': sum(not item.get('rotated_at') for item in credentials),
    }


def dashboard_summary(profiles):
    today = date.today().isoformat()
    health = credential_health(profiles)
    return {**health, 'profiles': len(profiles),
            'needs_review': sum(item.get('profile_status') == 'needs_review' for item in profiles),
            'retention_due': sum(bool(item.get('retention_until')) and item['retention_until'] <= today for item in profiles),
            'unmatched_devices': sum(not device.get('mac') for item in profiles for device in item.get('devices', []))}


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
        removed = store.pop(profile_id, None)
        if removed:
            for profile in store.values():
                profile['relationships'] = [item for item in profile.get('relationships', []) if item.get('target_profile_id') != profile_id]
        return removed is not None


def delete_attachment(profile_id, attachment_id, store, lock):
    with lock:
        if profile_id not in store:
            raise KeyError(profile_id)
        items = store[profile_id].setdefault('attachments', [])
        item = next((entry for entry in items if entry.get('id') == attachment_id), None)
        if item:
            store[profile_id]['attachments'] = [entry for entry in items if entry.get('id') != attachment_id]
        return deepcopy(item) if item else None


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


def update_credential(profile_id, credential_id, values, store, lock, now=None):
    """Update credential metadata and optionally rotate its encrypted secret."""
    with lock:
        if profile_id not in store:
            raise KeyError(profile_id)
        credential = next((item for item in store[profile_id].get('credentials', []) if item.get('id') == credential_id), None)
        if not credential:
            raise KeyError(credential_id)
        device_id = str(values.get('device_id') or '').strip()
        if device_id and not any(item.get('id') == device_id for item in store[profile_id].get('devices', [])):
            raise ValueError('Selected device was not found on this profile.')
        website_url = _clean_url(values.get('website_url'), 'Website link')
        kind = str(values.get('credential_kind') or credential.get('credential_kind') or 'unassigned').casefold()
        if kind not in {'unassigned', 'website', 'device'}:
            kind = 'unassigned'
        rotated_ciphertext = str(values.get('secret_ciphertext') or '')
        if rotated_ciphertext and not rotated_ciphertext.startswith('vault:v1:'):
            raise ValueError('Password/secret must be encrypted by the credential vault.')
        credential.update({
            'label': str(values.get('label') or '').strip()[:160] or credential.get('label'),
            'username': str(values.get('username') or '').strip()[:320],
            'website_url': website_url, 'device_id': device_id, 'credential_kind': kind,
            'purpose': str(values.get('purpose') or '').strip()[:500],
            'notes': str(values.get('credential_notes') or '').strip()[:2000],
            'updated_at': now if now is not None else time.time(),
        })
        if rotated_ciphertext:
            credential['secret_ciphertext'] = rotated_ciphertext
            credential['rotated_at'] = credential['updated_at']
        store[profile_id]['updated_at'] = credential['updated_at']
        return deepcopy(credential)


def add_device(profile_id, values, store, lock, normalize_mac, now=None):
    """Add a device card with an optional inventory-match MAC address."""
    name = str(values.get('name') or '').strip()
    device_type = str(values.get('device_type') or 'other').strip().casefold()
    raw_mac = str(values.get('inventory_mac') or values.get('mac') or '').strip()
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
        'manufacturer': str(values.get('manufacturer') or '').strip()[:160],
        'model': str(values.get('model') or '').strip()[:160],
        'operating_system': str(values.get('operating_system') or '').strip()[:160],
        'hostname': str(values.get('hostname') or '').strip()[:253],
        'status': str(values.get('device_status') or 'active').strip().casefold()[:40],
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


def update_device(profile_id, device_id, values, store, lock, normalize_mac, now=None):
    with lock:
        if profile_id not in store:
            raise KeyError(profile_id)
        device = next((item for item in store[profile_id].get('devices', []) if item.get('id') == device_id), None)
        if not device:
            raise KeyError(device_id)
        raw_mac = str(values.get('inventory_mac') or values.get('mac') or '').strip()
        mac = normalize_mac(raw_mac) if raw_mac else None
        if raw_mac and not mac:
            raise ValueError('MAC address must contain six hexadecimal octets.')
        device_type = str(values.get('device_type') or device.get('device_type') or 'other').casefold()
        if device_type not in DEVICE_ICONS:
            device_type = 'other'
        device.update({
            'name': str(values.get('name') or '').strip()[:160] or device.get('name'),
            'device_type': device_type, 'icon': DEVICE_ICONS[device_type], 'mac': mac,
            'manufacturer': str(values.get('manufacturer') or '').strip()[:160],
            'model': str(values.get('model') or '').strip()[:160],
            'operating_system': str(values.get('operating_system') or '').strip()[:160],
            'hostname': str(values.get('hostname') or '').strip()[:253],
            'status': str(values.get('device_status') or 'active').strip().casefold()[:40],
            'notes': str(values.get('notes') or '').strip()[:2000],
            'updated_at': now if now is not None else time.time(),
        })
        store[profile_id]['updated_at'] = device['updated_at']
        return deepcopy(device)


def search_profiles(profiles, query='', status='', tag=''):
    query = str(query or '').strip().casefold()
    status = str(status or '').strip().casefold()
    tag = str(tag or '').strip().casefold()
    results = []
    for profile in profiles:
        if status and profile.get('profile_status') != status:
            continue
        if tag and tag not in {item.casefold() for item in profile.get('tags', [])}:
            continue
        searchable = [profile.get('full_name'), profile.get('organization'), profile.get('job_title'), profile.get('phone'), profile.get('notes')]
        searchable.extend(profile.get('tags', []))
        searchable.extend([profile.get('authorization_basis'), profile.get('review_date'), profile.get('retention_until')])
        for field in profile.get('custom_fields', []):
            searchable.extend([field.get('name'), field.get('value')])
        searchable.extend(item.get('value') for item in profile.get('emails', []))
        for item in profile.get('social_links', []):
            searchable.extend([item.get('platform'), item.get('account'), item.get('url'), item.get('source')])
            searchable.extend(item.get('recovery_emails', []))
            searchable.append(item.get('recovery_phone'))
        for item in profile.get('devices', []):
            searchable.extend([item.get('name'), item.get('mac'), item.get('manufacturer'), item.get('model'), item.get('hostname')])
        for item in profile.get('credentials', []):
            searchable.extend([item.get('label'), item.get('username'), item.get('purpose'), item.get('notes')])
        if query and query not in ' '.join(str(value or '') for value in searchable).casefold():
            continue
        results.append(profile)
    return results
