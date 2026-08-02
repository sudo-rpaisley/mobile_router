"""Restore refactored helpers overwritten during the automotive merge."""

from pathlib import Path


APP_PATH = Path('app.py')
FACADE_PATH = Path('services/social_profiles.py')
STORAGE_PATH = Path('services/social_profile/storage.py')
RELATIONSHIPS_PATH = Path('services/social_profile/relationships.py')


FACADE = '''"""Compatibility façade for consent-focused individual profile services.

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
'''


def repair_app_imports():
    source = APP_PATH.read_text(encoding='utf-8')
    legacy = "MAC_RE = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$')"
    replacement = 'from app_support.identifiers import MAC_RE, inventory_key, normalize_mac'
    if legacy in source:
        source = source.replace(legacy, replacement, 1)
    if replacement not in source:
        raise RuntimeError('Shared identifier import was not restored')
    APP_PATH.write_text(source, encoding='utf-8')


def restore_social_profile_facade():
    FACADE_PATH.write_text(FACADE, encoding='utf-8')


def preserve_identity_collections():
    source = STORAGE_PATH.read_text(encoding='utf-8')
    marker = "    profile.setdefault('attachments', [])\n"
    replacement = marker + "    profile.setdefault('identity_documents', [])\n    profile.setdefault('signatures', [])\n"
    if "profile.setdefault('identity_documents', [])" not in source:
        if marker not in source:
            raise RuntimeError('Profile collection marker not found')
        source = source.replace(marker, replacement, 1)
    STORAGE_PATH.write_text(source, encoding='utf-8')

    source = RELATIONSHIPS_PATH.read_text(encoding='utf-8')
    marker = "            'attachments',\n            'custom_fields',\n"
    replacement = (
        "            'attachments',\n"
        "            'identity_documents',\n"
        "            'signatures',\n"
        "            'custom_fields',\n"
    )
    if "            'identity_documents',\n" not in source:
        if marker not in source:
            raise RuntimeError('Profile merge collection marker not found')
        source = source.replace(marker, replacement, 1)
    RELATIONSHIPS_PATH.write_text(source, encoding='utf-8')


def main():
    repair_app_imports()
    restore_social_profile_facade()
    preserve_identity_collections()


if __name__ == '__main__':
    main()
