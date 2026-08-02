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
        'app_user': {
            'username': 'admin',
            'display_name': 'Router Admin',
            'email': 'admin@example.test',
            'role': 'admin',
            'preferences': {'favourites': []},
        },
        'app_csrf_token': 'test-token',
        'navigation': {
            'favourites': [],
            'search_items': [
                {'label': 'Inventory', 'url': '/inventory', 'keywords': 'devices', 'favourite': False},
            ],
            'current_url': '/',
            'current_label': 'Home',
        },
    }
    context.update(overrides)
    with app.test_request_context('/'):
        return render_template('_navbar.html', **context)


def test_navigation_groups_interfaces_status_and_account_utilities():
    navigation = render_navigation()

    assert 'navbar-expand-lg' in navigation
    assert navigation.count('data-navigation-toggle="dropdown"') == 8
    assert '>Interfaces<' in navigation
    assert '/ethernet/eth0' in navigation
    assert '/wireless/wlan0' in navigation
    assert '/loopback' not in navigation
    assert navigation.count('User management') == 1
    assert 'My account' in navigation
    assert 'id="theme-toggle"' in navigation
    assert 'id="navigation-search-panel"' in navigation
    assert 'id="job-preview-list"' in navigation
    assert 'id="alert-preview-list"' in navigation
    assert 'class="sr-only" aria-live="polite">Auto updating' in navigation


def test_navigation_keeps_user_management_and_profile_in_account_menu():
    primary_navigation = Path('templates/_primary-nav-links.html').read_text(
        encoding='utf-8'
    )
    navbar = Path('templates/_navbar.html').read_text(encoding='utf-8')

    assert '/users' not in primary_navigation
    assert '/account' in navbar
    assert '/users' in navbar
    assert 'account-menu' in navbar


def test_navigation_uses_click_keyboard_and_quick_search_not_hover():
    script = Path('static/js/navbar.js').read_text(encoding='utf-8')
    styles = Path('static/css/navbar.css').read_text(encoding='utf-8')

    assert 'data-navigation-toggle' in script
    assert "event.key === 'ArrowDown'" in script
    assert "event.key === 'Escape'" in script
    assert "String(event.key).toLowerCase() === 'k'" in script
    assert 'renderJobPreview' in script
    assert 'renderAlertPreview' in script
    assert 'data-favourite-action' in script
    assert 'mouseenter' not in script
    assert '.dropdown:hover' not in styles


def test_navigation_marks_current_items_and_exposes_skip_link():
    primary_navigation = Path('templates/_primary-nav-links.html').read_text(
        encoding='utf-8'
    )
    header = Path('templates/_header.html').read_text(encoding='utf-8')
    trail = Path('templates/_navigation_trail.html').read_text(encoding='utf-8')

    assert 'aria-current="page"' in primary_navigation
    assert 'Skip to main content' in header
    assert 'aria-label="Breadcrumb"' in trail
    assert 'aria-label="Section navigation"' in trail
