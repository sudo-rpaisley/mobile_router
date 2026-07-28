from types import SimpleNamespace
from unittest.mock import patch

import app as app_module
from app import app


def test_bluetooth_device_page_renders_contextual_browser_controls():
    client = app.test_client()
    app_module.social_users.setdefault('browser-test', {
        'id': 'browser-test', 'username': 'browser-test', 'role': 'admin', 'password_hash': 'unused',
    })
    with client.session_transaction() as flask_session:
        flask_session['social_user'] = {'username': 'browser-test', 'role': 'admin'}
    app_module.device_inventory.clear()
    app_module.record_inventory_devices([
        {
            'address': '6a:76:8a:0c:36:80',
            'name': 'Browser Speaker',
            'connected': True,
            'paired': True,
            'trusted': False,
        }
    ], 'bluetooth-scan', 'hci0')
    bluetooth_interface = SimpleNamespace(
        name='hci0',
        interface_type='Bluetooth',
        state='UP',
        get_mac_address=lambda: '00:11:22:33:44:55',
    )

    with patch.object(app_module, 'network_interfaces', [bluetooth_interface]):
        response = client.get('/clients/6a:76:8a:0c:36:80')

    assert response.status_code == 200
    assert b'bluetooth-contextual-actions' in response.data
    assert b'data-action="disconnect"' in response.data
    assert b'data-action="trust"' in response.data
    assert b'Bluetooth Action History' in response.data
    assert b'Default host adapter' in response.data


def test_wireless_browser_script_contains_dashboard_interactions():
    script = open('static/js/wireless-adapters.js', encoding='utf-8').read()

    assert '.wireless-channel-filter' in script
    assert '.wireless-band-filter' in script
    assert '.wireless-map-close' in script
    assert 'wireless-map-open' in script
    assert '&times;' in script
    assert "event.key === 'Escape'" in script
    assert 'data-map-band-tab' in script
    assert 'wireless-heatmap-range' in script
    assert 'wireless-show-bssids' in script
    assert 'Show grouped SSIDs' in script
    assert 'renderBssidRows(interfaceName, networks, sortBy)' in script
    assert 'wireless-export' in script


def test_bluetooth_browser_script_rerenders_actions_after_ajax():
    script = open('static/js/bluetooth-scan.js', encoding='utf-8').read()

    assert 'renderContextualActions' in script
    assert 'updateBluetoothStateBadges' in script
    assert 'response.actions' in script
    assert 'response.device_state' in script


def test_social_profile_components_have_dark_theme_coverage():
    css = open('static/style.css', encoding='utf-8').read()

    assert 'html[data-theme="dark"] .social-profile-card' in css
    assert 'html[data-theme="dark"] .social-account-card' in css
    assert 'html[data-theme="dark"] .social-credential-unassigned' in css
    assert 'html[data-theme="dark"] .modal-header' in css
    assert 'html[data-theme="dark"] .form-control::placeholder' in css
    assert 'html[data-theme="dark"] input[type="date"]::-webkit-calendar-picker-indicator' in css
    assert 'color-scheme: dark' in css
