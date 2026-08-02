from pathlib import Path
from types import SimpleNamespace

from flask import render_template

from app import app


def render_navigation(**overrides):
    context = {
        'title': 'Home',
        'networkTechnologies': ['Ethernet', 'Wireless', 'Loopback'],
        'interfaces': [
            SimpleNamespace(interface_type='Ethernet', name='eth0'),
            SimpleNamespace(interface_type='Wireless', name='wlan0'),
        ],
        'app_user': {'username': 'admin', 'role': 'admin'},
        'app_csrf_token': 'test-token',
    }
    context.update(overrides)
    with app.app_context():
        return render_template('_navbar.html', **context)


def test_navigation_groups_interfaces_and_account_utilities():
    navigation = render_navigation()

    assert 'navbar-expand-lg' in navigation
    assert navigation.count('data-navigation-toggle="dropdown"') == 5
    assert '>Interfaces<' in navigation
    assert '/ethernet/eth0' in navigation
    assert '/wireless/wlan0' in navigation
    assert '/loopback' not in navigation
    assert navigation.count('User management') == 1
    assert 'id="theme-toggle"' in navigation
    assert 'class="sr-only" aria-live="polite">Auto updating' in navigation


def test_navigation_keeps_user_management_in_account_menu():
    primary_navigation = Path('templates/_primary-nav-links.html').read_text(
        encoding='utf-8'
    )
    navbar = Path('templates/_navbar.html').read_text(encoding='utf-8')

    assert '/users' not in primary_navigation
    assert '/users' in navbar
    assert 'account-menu' in navbar


def test_navigation_uses_click_and_keyboard_dropdowns_not_hover():
    script = Path('static/js/navbar.js').read_text(encoding='utf-8')
    styles = Path('static/css/navbar.css').read_text(encoding='utf-8')

    assert 'data-navigation-toggle' in script
    assert "event.key === 'ArrowDown'" in script
    assert "event.key === 'Escape'" in script
    assert 'mouseenter' not in script
    assert '.dropdown:hover' not in styles
