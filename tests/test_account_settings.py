import threading

import pytest

from app_support.navigation import build_navigation_context
from services import social_auth


def user_store():
    store = {}
    lock = threading.Lock()
    user = social_auth.create_user('operator', 'initial-password', 'editor', store, lock)
    return store, lock, user


def test_profile_update_preserves_credentials_and_saves_preferences():
    store, lock, _ = user_store()
    original_hash = store['operator']['password_hash']

    updated = social_auth.update_user_profile(
        'operator',
        'Workshop Operator',
        'operator@example.test',
        '/automotive',
        'on',
        'on',
        store,
        lock,
    )

    assert updated['username'] == 'operator'
    assert updated['role'] == 'editor'
    assert updated['display_name'] == 'Workshop Operator'
    assert updated['email'] == 'operator@example.test'
    assert updated['preferences']['default_landing_page'] == '/automotive'
    assert updated['preferences']['compact_layout'] is True
    assert updated['preferences']['reduced_motion'] is True
    assert 'password_hash' not in updated
    assert store['operator']['password_hash'] == original_hash


def test_password_change_requires_current_password_and_confirmation():
    store, lock, _ = user_store()

    with pytest.raises(ValueError, match='current password'):
        social_auth.change_password(
            'operator', 'wrong-password', 'replacement-password',
            'replacement-password', store, lock,
        )

    social_auth.change_password(
        'operator', 'initial-password', 'replacement-password',
        'replacement-password', store, lock,
    )

    assert social_auth.authenticate('operator', 'initial-password', store, lock) is None
    assert social_auth.authenticate('operator', 'replacement-password', store, lock)


def test_favourites_are_local_deduplicated_and_bounded():
    store, lock, _ = user_store()

    social_auth.update_favourite(
        'operator', '/inventory', 'Inventory', 'add', store, lock,
    )
    favourites = social_auth.update_favourite(
        'operator', '/inventory', 'Device Inventory', 'add', store, lock,
    )

    assert favourites == [{'label': 'Device Inventory', 'url': '/inventory'}]
    with pytest.raises(ValueError, match='local application page'):
        social_auth.update_favourite(
            'operator', 'https://example.com', 'External', 'add', store, lock,
        )


def test_navigation_context_builds_breadcrumbs_tabs_search_and_favourites():
    user = {
        'preferences': {
            'favourites': [{'label': 'My inventory', 'url': '/inventory'}],
        }
    }
    context = build_navigation_context(
        '/automotive/codes',
        'Code Lookup',
        'automotive.code_lookup',
        user,
        {'Ethernet', 'Wireless'},
        [
            {'interface_type': 'Ethernet', 'name': 'eth0'},
            {'interface_type': 'Wireless', 'name': 'wlan0'},
        ],
    )

    assert [item['label'] for item in context['breadcrumbs']] == [
        'Home', 'Automotive', 'Code Lookup'
    ]
    assert next(item for item in context['section_items'] if item['label'] == 'Code Lookup')['active'] is True
    assert context['search_items'][0]['label'] == 'My inventory'
    assert any(item['label'] == 'wlan0' for item in context['search_items'])
