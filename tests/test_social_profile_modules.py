import threading

from services import social_profiles
from services.social_profile import credentials, devices, storage, validation


def normalize_mac(value):
    value = str(value or '').replace('-', ':').lower()
    return value if len(value.split(':')) == 6 else None


def test_social_profile_facade_exports_focused_services():
    assert social_profiles.validate_profile is validation.validate_profile
    assert social_profiles.create_profile is storage.create_profile
    assert social_profiles.add_credential is credentials.add_credential
    assert social_profiles.add_device is devices.add_device


def test_profile_device_and_credential_workflow():
    store = {}
    lock = threading.Lock()
    profile = social_profiles.create_profile(
        {
            'full_name': 'Alex Example',
            'email': 'alex@example.com',
            'tags': 'training, priority',
        },
        store,
        lock,
        now=10,
    )

    device = social_profiles.add_device(
        profile['id'],
        {
            'name': 'Test phone',
            'device_type': 'iphone',
            'mac': 'AC-16-2D-A2-71-9E',
        },
        store,
        lock,
        normalize_mac,
        now=11,
    )
    credential = social_profiles.add_credential(
        profile['id'],
        {
            'label': 'Apple ID',
            'username': 'alex@example.com',
            'device_id': device['id'],
            'secret_ciphertext': 'vault:v1:salt:iv:ciphertext',
        },
        store,
        lock,
        now=12,
    )

    assert device['icon'] == 'fa-mobile-alt'
    assert credential['credential_kind'] == 'device'
    assert social_profiles.get_profile(profile['id'], store, lock)[
        'credentials'
    ][0]['label'] == 'Apple ID'
    assert social_profiles.dashboard_summary(
        social_profiles.list_profiles(store, lock)
    )['profiles'] == 1


def test_search_and_merge_profiles():
    store = {}
    lock = threading.Lock()
    primary = social_profiles.create_profile(
        {
            'full_name': 'Alex Example',
            'email': 'alex@example.com',
            'tags': 'priority',
            'notes': 'Primary record',
        },
        store,
        lock,
        now=10,
    )
    duplicate = social_profiles.create_profile(
        {
            'full_name': 'Alex Duplicate',
            'email': 'alex@example.com',
            'tags': 'training',
            'notes': 'Secondary record',
        },
        store,
        lock,
        now=11,
    )
    store[primary['id']]['owner'] = 'tester'
    store[duplicate['id']]['owner'] = 'tester'

    profiles = social_profiles.list_profiles(store, lock)
    assert social_profiles.duplicate_candidates(profiles)
    assert social_profiles.search_profiles(profiles, query='training')

    merged = social_profiles.merge_profiles(
        primary['id'],
        duplicate['id'],
        store,
        lock,
        now=12,
    )
    assert merged['tags'] == ['priority', 'training']
    assert merged['notes'] == 'Primary record\n\nSecondary record'
    assert duplicate['id'] not in store
