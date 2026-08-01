"""Validation and normalization for submitted social profile data."""

import re
import uuid
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


def _list_values(values, key):
    if hasattr(values, 'getlist'):
        return values.getlist(key)
    raw_value = values.get(key, [])
    return raw_value if isinstance(raw_value, list) else [raw_value]


def validate_profile(values):
    """Normalize submitted profile fields and reject unsafe or invalid links."""
    profile = {
        field: str(values.get(field) or '').strip()
        for field in PROFILE_FIELDS
    }
    if not profile['full_name']:
        raise ValueError('Full name is required.')
    if len(profile['full_name']) > 160:
        raise ValueError('Full name must be 160 characters or fewer.')

    email_ids = _list_values(values, 'email_id')
    email_labels = _list_values(values, 'email_label')
    email_values = _list_values(values, 'email_value')
    email_statuses = _list_values(values, 'email_status')
    email_sources = _list_values(values, 'email_source')
    email_confidences = _list_values(values, 'email_confidence')
    email_verified_dates = _list_values(values, 'email_verified_date')
    emails = []
    for index, raw_email in enumerate(email_values):
        email = str(raw_email or '').strip()
        if not email:
            continue
        status = (
            'partial'
            if index < len(email_statuses)
            and email_statuses[index] == 'partial'
            else 'complete'
        )
        if status == 'complete' and not EMAIL_RE.fullmatch(email):
            raise ValueError(f'Email #{index + 1} must be a valid address.')
        confidence = str(
            email_confidences[index]
            if index < len(email_confidences)
            else 'unverified'
        ).casefold()
        emails.append(
            {
                'id': (
                    str(email_ids[index] if index < len(email_ids) else '').strip()
                    or str(uuid.uuid4())
                ),
                'label': (
                    str(
                        email_labels[index]
                        if index < len(email_labels)
                        else 'Email'
                    ).strip()[:40]
                    or 'Email'
                ),
                'value': email[:320],
                'status': status,
                'source': str(
                    email_sources[index]
                    if index < len(email_sources)
                    else ''
                ).strip()[:160],
                'confidence': (
                    confidence
                    if confidence in CONFIDENCE_LEVELS
                    else 'unverified'
                ),
                'verified_date': str(
                    email_verified_dates[index]
                    if index < len(email_verified_dates)
                    else ''
                ).strip()[:10],
            }
        )

    legacy_email = str(values.get('email') or '').strip()
    if legacy_email and not emails:
        if not EMAIL_RE.fullmatch(legacy_email):
            raise ValueError('Email must be a valid address.')
        emails.append(
            {
                'id': str(uuid.uuid4()),
                'label': 'Email',
                'value': legacy_email,
                'status': 'complete',
                'source': '',
                'confidence': 'unverified',
                'verified_date': '',
            }
        )

    social_platforms = _list_values(values, 'social_platform')
    social_urls = _list_values(values, 'social_url')
    social_statuses = _list_values(values, 'social_status')
    social_accounts = _list_values(values, 'social_account')
    social_recovery_emails = _list_values(values, 'social_recovery_emails')
    social_recovery_phones = _list_values(values, 'social_recovery_phone')
    social_recovery_notes = _list_values(values, 'social_recovery_notes')
    social_recovery_refs = _list_values(values, 'social_recovery_refs')
    social_sources = _list_values(values, 'social_source')
    social_confidences = _list_values(values, 'social_confidence')
    social_verified_dates = _list_values(values, 'social_verified_date')
    social_ids = _list_values(values, 'social_id')
    social_links = []
    for index, raw_url in enumerate(social_urls):
        if not str(raw_url or '').strip():
            continue
        platform = (
            str(
                social_platforms[index]
                if index < len(social_platforms)
                else 'Website'
            ).strip()[:40]
            or 'Website'
        )
        status = (
            'partial'
            if index < len(social_statuses)
            and social_statuses[index] == 'partial'
            else 'complete'
        )
        url = (
            str(raw_url).strip()[:1000]
            if status == 'partial'
            else _clean_url(raw_url, f'{platform} link')
        )
        recovery_emails = [
            item.strip()[:320]
            for item in str(
                social_recovery_emails[index]
                if index < len(social_recovery_emails)
                else ''
            ).split(',')
            if item.strip()
        ]
        confidence = str(
            social_confidences[index]
            if index < len(social_confidences)
            else 'unverified'
        ).casefold()
        social_links.append(
            {
                'id': (
                    str(social_ids[index] if index < len(social_ids) else '').strip()
                    or str(uuid.uuid4())
                ),
                'platform': platform,
                'url': url,
                'status': status,
                'account': str(
                    social_accounts[index]
                    if index < len(social_accounts)
                    else ''
                ).strip()[:320],
                'recovery_emails': recovery_emails,
                'recovery_phone': str(
                    social_recovery_phones[index]
                    if index < len(social_recovery_phones)
                    else ''
                ).strip()[:100],
                'recovery_notes': str(
                    social_recovery_notes[index]
                    if index < len(social_recovery_notes)
                    else ''
                ).strip()[:1000],
                'recovery_refs': [
                    item.strip()
                    for item in str(
                        social_recovery_refs[index]
                        if index < len(social_recovery_refs)
                        else ''
                    ).split(',')
                    if item.strip()
                ],
                'source': str(
                    social_sources[index]
                    if index < len(social_sources)
                    else ''
                ).strip()[:160],
                'confidence': (
                    confidence
                    if confidence in CONFIDENCE_LEVELS
                    else 'unverified'
                ),
                'verified_date': str(
                    social_verified_dates[index]
                    if index < len(social_verified_dates)
                    else ''
                ).strip()[:10],
            }
        )

    for platform, key in (
        ('Facebook', 'facebook_url'),
        ('LinkedIn', 'linkedin_url'),
    ):
        legacy_url = str(values.get(key) or '').strip()
        if legacy_url and not any(
            link['platform'] == platform for link in social_links
        ):
            social_links.append(
                {
                    'id': str(uuid.uuid4()),
                    'platform': platform,
                    'url': _clean_url(legacy_url, f'{platform} link'),
                }
            )

    profile['emails'] = emails
    profile['email'] = emails[0]['value'] if emails else ''
    profile['social_links'] = social_links
    profile['phone_status'] = (
        'partial' if values.get('phone_status') == 'partial' else 'complete'
    )
    profile['phone_source'] = str(
        values.get('phone_source') or ''
    ).strip()[:160]
    phone_confidence = str(
        values.get('phone_confidence') or 'unverified'
    ).casefold()
    profile['phone_confidence'] = (
        phone_confidence
        if phone_confidence in CONFIDENCE_LEVELS
        else 'unverified'
    )
    profile['phone_verified_date'] = str(
        values.get('phone_verified_date') or ''
    ).strip()[:10]
    profile['tags'] = sorted(
        {
            tag.strip()[:40]
            for tag in str(values.get('tags') or '').split(',')
            if tag.strip()
        },
        key=str.casefold,
    )
    status = str(values.get('profile_status') or 'active').casefold()
    profile['profile_status'] = (
        status if status in PROFILE_STATUSES else 'active'
    )
    profile['retention_until'] = str(
        values.get('retention_until') or ''
    ).strip()[:10]
    profile['review_date'] = str(
        values.get('review_date') or ''
    ).strip()[:10]
    if any(
        value and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value)
        for value in (profile['retention_until'], profile['review_date'])
    ):
        raise ValueError('Review and retention dates must use YYYY-MM-DD.')
    profile['authorization_basis'] = str(
        values.get('authorization_basis') or ''
    ).strip()[:500]

    custom_names = _list_values(values, 'custom_field_name')
    custom_values = _list_values(values, 'custom_field_value')
    custom_types = _list_values(values, 'custom_field_type')
    profile['custom_fields'] = [
        {
            'id': str(uuid.uuid4()),
            'name': str(name).strip()[:80],
            'value': str(
                custom_values[index]
                if index < len(custom_values)
                else ''
            ).strip()[:2000],
            'type': str(
                custom_types[index]
                if index < len(custom_types)
                else 'text'
            ).strip()[:20],
        }
        for index, name in enumerate(custom_names)
        if str(name or '').strip()
    ]
    profile['facebook_url'] = next(
        (
            link['url']
            for link in social_links
            if link['platform'] == 'Facebook'
        ),
        '',
    )
    profile['linkedin_url'] = next(
        (
            link['url']
            for link in social_links
            if link['platform'] == 'LinkedIn'
        ),
        '',
    )
    if len(profile['notes']) > 10000:
        raise ValueError('Notes must be 10,000 characters or fewer.')
    return profile
