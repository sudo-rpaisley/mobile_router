"""Compatibility façade for consent-focused individual profile services.

The implementation is split by responsibility under ``services.social_profile``.
Existing callers can continue importing this module while newer code may import
the focused validation, storage, relationship, credential, and device services.
"""

from .social_profile.credentials import (
    add_credential,
    credential_health,
    delete_credential,
    update_credential,
)
from .social_profile.devices import (
    add_device,
    delete_device,
    update_device,
)
from .social_profile.relationships import (
    add_relationship,
    delete_relationship,
    duplicate_candidates,
    merge_profiles,
)
from .social_profile.storage import (
    _normalize_profile,
    add_attachment,
    create_profile,
    dashboard_summary,
    delete_attachment,
    delete_profile,
    get_profile,
    list_profiles,
    search_profiles,
    update_profile,
)
from .social_profile.validation import (
    CONFIDENCE_LEVELS,
    DEVICE_ICONS,
    EMAIL_RE,
    PROFILE_FIELDS,
    PROFILE_STATUSES,
    _clean_url,
    validate_profile,
)


__all__ = [
    'CONFIDENCE_LEVELS',
    'DEVICE_ICONS',
    'EMAIL_RE',
    'PROFILE_FIELDS',
    'PROFILE_STATUSES',
    'add_attachment',
    'add_credential',
    'add_device',
    'add_relationship',
    'create_profile',
    'credential_health',
    'dashboard_summary',
    'delete_attachment',
    'delete_credential',
    'delete_device',
    'delete_profile',
    'delete_relationship',
    'duplicate_candidates',
    'get_profile',
    'list_profiles',
    'merge_profiles',
    'search_profiles',
    'update_credential',
    'update_device',
    'update_profile',
    'validate_profile',
]
