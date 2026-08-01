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


def _value_at(items, index, default=''):
    return items[index] if index < len(items) else default


def _confidence(value):
    confidence = str(value or 'unverified').casefold()
    return confidence if confidence in CONFIDENCE_LEVELS else 'unverified'


def _parse_emails(values):
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
        status = 'partial' if _value_at(email_statuses, index) == 'partial' else 'complete'
        if status == 'complete' and not EMAIL_RE.fullmatch(email):
            raise ValueError(f'Email #{index + 1} must be a valid address.')
        emails.append(
            {
                'id': str(_value_at(email_ids, index)).strip() or str(uuid.uuid4()),
                'label': str(_value_at(email_labels, index, 'Email')).strip()[:40] or 'Email',
                'value': email[:320],
                'status': status,
                'source': str(_value_at(email_sources, index)).strip()[:160],
                'confidence': _confidence(_value_at(email_confidences, index, 'unverified')),
                'verified_date': str(_value_at(email_verified_dates, index)).strip()[:10],
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
    return emails


def _comma_separated(value, limit=None):
    items = []
    for item in str(value or '').split(','):
        item = item.strip()
        if item:
            items.append(item[:limit] if limit else item)
    return items


def _parse_social_links(values):
    fields = {
        'ids': _list_values(values, 'social_id'),
        'platforms': _list_values(values, 'social_platform'),
        'urls': _list_values(values, 'social_url'),
        'statuses': _list_values(values, 'social_status'),
        'accounts': _list_values(values, 'social_account'),
        'recovery_emails': _list_values(values, 'social_recovery_emails'),
        'recovery_phones': _list_values(values, 'social_recovery_phone'),
        'recovery_notes': _list_values(values, 'social_recovery_notes'),
        'recovery_refs': _list_values(values, 'social_recovery_refs'),
        'sources': _list_values(values, 'social_source'),
        'confidences': _list_values(values, 'social_confidence'),
        'verified_dates': _list_values(values, 'social_verified_date'),
    }

    social_links = []
    for index, raw_url in enumerate(fields['urls']):
        if not str(raw_url or '').strip():
            continue
        platform = str(_value_at(fields['platforms'], index, 'Website')).strip()[:40] or 'Website'
        status = 'partial' if _value_at(fields['statuses'], index) == 'partial' else 'complete'
        url = (
            str(raw_url).strip()[:1000]
            if status == 'partial'
            else _clean_url(raw_url, f'{platform} link')
        )
        social_links.append(
            {
                'id': str(_value_at(fields['ids'], index)).strip() or str(uuid.uuid4()),
                'platform': platform,
                'url': url,
                'status': status,
                'account': str(_value_at(fields['accounts'], index)).strip()[:320],
                'recovery_emails': _comma_separated(
                    _value_at(fields['recovery_emails'], index), 320
                ),
                'recovery_phone': str(
                    _value_at(fields['recovery_phones'], index)
                ).strip()[:100],
                'recovery_notes': str(
                    _value_at(fields['recovery_notes'], index)
                ).strip()[:1000],
                'recovery_refs': _comma_separated(
                    _value_at(fields['recovery_refs'], index)
                ),
                'source': str(_value_at(fields['sources'], index)).strip()[:160],
                'confidence': _confidence(
                    _value_at(fields['confidences'], index, 'unverified')
                ),
                'verified_date': str(
                    _value_at(fields['verified_dates'], index)
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
    return social_links


def _apply_phone_fields(profile, values):
    profile['phone_status'] = (
        'partial' if values.get('phone_status') == 'partial' else 'complete'
    )
    profile['phone_source'] = str(values.get('phone_source') or '').strip()[:160]
    profile['phone_confidence'] = _confidence(values.get('phone_confidence'))
    profile['phone_verified_date'] = str(
        values.get('phone_verified_date') or ''
    ).strip()[:10]


def _apply_profile_metadata(profile, values):
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


def _parse_custom_fields(values):
    custom_names = _list_values(values, 'custom_field_name')
    custom_values = _list_values(values, 'custom_field_value')
    custom_types = _list_values(values, 'custom_field_type')
    return [
        {
            'id': str(uuid.uuid4()),
            'name': str(name).strip()[:80],
            'value': str(_value_at(custom_values, index)).strip()[:2000],
            'type': str(_value_at(custom_types, index, 'text')).strip()[:20],
        }
        for index, name in enumerate(custom_names)
        if str(name or '').strip()
    ]


def _platform_url(social_links, platform):
    return next(
        (
            link['url']
            for link in social_links
            if link['platform'] == platform
        ),
        '',
    )


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
    if len(profile['notes']) > 10000:
        raise ValueError('Notes must be 10,000 characters or fewer.')

    emails = _parse_emails(values)
    social_links = _parse_social_links(values)

    profile['emails'] = emails
    profile['email'] = emails[0]['value'] if emails else ''
    profile['social_links'] = social_links
    _apply_phone_fields(profile, values)
    _apply_profile_metadata(profile, values)
    profile['custom_fields'] = _parse_custom_fields(values)
    profile['facebook_url'] = _platform_url(social_links, 'Facebook')
    profile['linkedin_url'] = _platform_url(social_links, 'LinkedIn')
    return profile
