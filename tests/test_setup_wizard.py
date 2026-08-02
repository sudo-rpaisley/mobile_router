from copy import deepcopy
from unittest.mock import patch

import pytest

import app as app_module
from app import app
from app_support.navigation import build_navigation_context
from services import setup_wizard


@pytest.fixture
def isolated_users():
    with app_module.social_users_lock:
        original = deepcopy(app_module.social_users)
        app_module.social_users.clear()
    yield
    with app_module.social_users_lock:
        app_module.social_users.clear()
        app_module.social_users.update(original)


def authenticated_client(username='setup-admin', role='admin', csrf_token='setup-token'):
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session['social_user'] = {'username': username, 'role': role}
        flask_session['social_csrf_token'] = csrf_token
    return client, csrf_token


def add_admin(username='setup-admin', enrolled=True):
    with app_module.social_users_lock:
        app_module.social_users[username] = {
            'id': username,
            'username': username,
            'display_name': 'Setup Administrator',
            'email': '',
            'role': 'admin',
            'password_hash': 'unused',
            'preferences': {'default_landing_page': '/'},
        }
    if enrolled:
        setup_wizard.begin_setup(
            username, app_module.social_users, app_module.social_users_lock
        )


def test_legacy_accounts_are_not_forced_into_new_setup():
    user = {'username': 'existing-admin', 'role': 'admin'}

    assert setup_wizard.setup_required(user) is False
    assert setup_wizard.setup_state(user)['completion_mode'] == 'legacy'


def test_first_account_creation_redirects_to_setup_wizard(isolated_users):
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session['social_csrf_token'] = 'first-run-token'

    with patch('app.save_runtime_state'):
        response = client.post('/setup', data={
            'username': 'first-admin',
            'password': 'a-secure-first-password',
            'csrf_token': 'first-run-token',
        })

    assert response.status_code == 302
    assert response.location.endswith('/setup-wizard')
    assert setup_wizard.setup_required(app_module.social_users['first-admin']) is True


def test_setup_wizard_page_explains_optional_downloads(isolated_users):
    add_admin()
    client, _ = authenticated_client()

    response = client.get('/setup-wizard')

    assert response.status_code == 200
    assert b'Welcome to Mobile Router' in response.data
    assert b'Would you like to download the full IEEE OUI database?' in response.data
    assert b'Nothing on this page is required' in response.data
    assert b'Skip optional downloads and continue' in response.data


def test_setup_component_install_is_allow_listed_and_recorded(isolated_users):
    add_admin()
    client, csrf_token = authenticated_client()
    result = {
        'component': 'oui-database',
        'installed': True,
        'message': 'Downloaded 35,000 IEEE OUI entries.',
    }

    with patch('routes.setup_wizard.setup_wizard_service.install_component', return_value=result), \
            patch('app.save_runtime_state') as save_state:
        response = client.post('/setup-wizard/install', data={
            'component': 'oui-database',
            'csrf_token': csrf_token,
        }, headers={'X-Requested-With': 'XMLHttpRequest'})

    assert response.status_code == 200
    recorded = app_module.social_users['setup-admin']['setup_wizard']['components']['oui-database']
    assert recorded['status'] == 'installed'
    assert '35,000' in recorded['message']
    save_state.assert_called_once_with('setup-component-install')


def test_setup_completion_persists_and_returns_to_landing_page(isolated_users):
    add_admin()
    client, csrf_token = authenticated_client()

    with patch('app.save_runtime_state') as save_state:
        response = client.post('/setup-wizard/complete', data={
            'mode': 'skipped',
            'csrf_token': csrf_token,
        })

    assert response.status_code == 302
    assert response.location == '/'
    state = app_module.social_users['setup-admin']['setup_wizard']
    assert state['status'] == 'complete'
    assert state['completion_mode'] == 'skipped'
    assert setup_wizard.setup_required(app_module.social_users['setup-admin']) is False
    save_state.assert_called_once_with('setup-wizard-complete')


def test_setup_catalog_is_platform_aware():
    linux_components = {item['id']: item for item in setup_wizard.component_catalog('Linux')}
    windows_components = {item['id']: item for item in setup_wizard.component_catalog('Windows')}

    assert linux_components['oui-database']['recommended'] is True
    assert 'browser-screenshot' in linux_components
    assert 'python-pywifi' not in linux_components
    assert 'python-pywifi' in windows_components
    assert 'browser-screenshot' not in windows_components


def test_setup_wizard_search_item_is_admin_only():
    common = (None, (), ())
    admin_context = build_navigation_context(
        '/', 'Home', *common, {'role': 'admin'}, (), ()
    )
    viewer_context = build_navigation_context(
        '/', 'Home', *common, {'role': 'viewer'}, (), ()
    )

    assert any(item['url'] == '/setup-wizard' for item in admin_context['search_items'])
    assert all(item['url'] != '/setup-wizard' for item in viewer_context['search_items'])


def test_unknown_setup_components_are_rejected():
    with pytest.raises(ValueError, match='Unsupported setup component'):
        setup_wizard.install_component('arbitrary-shell-command')
