"""First-run setup state and approved optional component installers."""

from __future__ import annotations

import platform
import shutil
import time
from copy import deepcopy

from scripts.capabilities import (
    OPTIONAL_PACKAGE_SPECS,
    command_status,
    install_host_dependency,
    install_optional_package,
    package_status,
)
from scripts.update_oui_db import download_oui_database
from services.oui import oui_database_status, refresh_oui_database


SETUP_VERSION = 1
_SETUP_STATUSES = {'in_progress', 'complete'}
_BROWSER_COMMANDS = ['wkhtmltoimage', 'chromium', 'chromium-browser', 'google-chrome']
_PACKAGE_MANAGERS = ['apt-get', 'apk', 'dnf', 'yum', 'pacman']


def _blank_state():
    return {
        'version': SETUP_VERSION,
        'status': 'in_progress',
        'started_at': None,
        'completed_at': None,
        'completed_by': None,
        'completion_mode': None,
        'components': {},
    }


def setup_state(user):
    """Return normalized setup state without forcing legacy users into onboarding."""
    raw = (user or {}).get('setup_wizard')
    if not isinstance(raw, dict):
        return {
            'version': SETUP_VERSION,
            'status': 'complete',
            'legacy_installation': True,
            'started_at': None,
            'completed_at': None,
            'completed_by': None,
            'completion_mode': 'legacy',
            'components': {},
        }
    state = _blank_state()
    state.update(deepcopy(raw))
    if state.get('status') not in _SETUP_STATUSES:
        state['status'] = 'in_progress'
    if not isinstance(state.get('components'), dict):
        state['components'] = {}
    return state


def setup_required(user):
    """Return True only for accounts explicitly enrolled in first-run setup."""
    raw = (user or {}).get('setup_wizard')
    return isinstance(raw, dict) and setup_state(user).get('status') != 'complete'


def begin_setup(username, store, lock):
    """Enroll the first administrator in guided setup."""
    username = str(username or '').strip().casefold()
    with lock:
        user = store.get(username)
        if not user:
            raise ValueError('Account not found.')
        previous = setup_state(user)
        state = _blank_state()
        state['started_at'] = time.time()
        state['components'] = deepcopy(previous.get('components') or {})
        user['setup_wizard'] = state
        return deepcopy(state)


def record_component_result(username, component_id, status, message, details, store, lock):
    """Persist one installer result in the enrolled administrator account."""
    username = str(username or '').strip().casefold()
    component_id = str(component_id or '').strip()
    with lock:
        user = store.get(username)
        if not user:
            raise ValueError('Account not found.')
        state = setup_state(user)
        state.setdefault('components', {})[component_id] = {
            'status': str(status or 'unknown'),
            'message': str(message or ''),
            'details': deepcopy(details or {}),
            'updated_at': time.time(),
        }
        user['setup_wizard'] = state
        return deepcopy(state['components'][component_id])


def complete_setup(username, mode, store, lock):
    """Mark guided setup complete while retaining component results."""
    username = str(username or '').strip().casefold()
    mode = str(mode or 'completed').strip().casefold()
    if mode not in {'completed', 'skipped'}:
        raise ValueError('Unsupported setup completion mode.')
    with lock:
        user = store.get(username)
        if not user:
            raise ValueError('Account not found.')
        state = setup_state(user)
        state.update({
            'version': SETUP_VERSION,
            'status': 'complete',
            'completed_at': time.time(),
            'completed_by': username,
            'completion_mode': mode,
        })
        user['setup_wizard'] = state
        return deepcopy(state)


def _python_component(package, name, description, question, recommended=False, applicable=True):
    installed = package_status([package]).get(package, False)
    return {
        'id': f'python-{package}',
        'category': 'Python integration',
        'name': name,
        'description': description,
        'question': question,
        'recommended': recommended,
        'applicable': applicable,
        'installable': applicable,
        'installed': installed,
        'status_label': 'Installed' if installed else 'Not installed',
        'impact': f'Installs {OPTIONAL_PACKAGE_SPECS[package]} into the current Python environment.',
    }


def component_catalog(system_name=None):
    """Return platform-aware optional downloads for the setup interface."""
    system_name = system_name or platform.system()
    oui_status = oui_database_status()
    browser_commands = command_status(_BROWSER_COMMANDS)
    browser_installed = any(item.get('available') for item in browser_commands.values())
    browser_supported = system_name == 'Linux' and any(shutil.which(name) for name in _PACKAGE_MANAGERS)

    components = [
        {
            'id': 'oui-database',
            'category': 'Vendor data',
            'name': 'Full IEEE OUI vendor database',
            'description': 'Improves MAC-address manufacturer identification across inventory, scans, and reports. Core lookups still work with the compact bundled fallback.',
            'question': 'Would you like to download the full IEEE OUI database?',
            'recommended': True,
            'applicable': True,
            'installable': True,
            'installed': not bool(oui_status.get('needs_refresh')),
            'status_label': (
                f"Full database available ({int(oui_status.get('entries') or 0):,} entries)"
                if not oui_status.get('needs_refresh')
                else f"Compact database active ({int(oui_status.get('entries') or 0):,} entries)"
            ),
            'impact': 'Downloads a public IEEE CSV and stores it locally for offline vendor lookup.',
        },
        _python_component(
            'bleak',
            'Bluetooth Low Energy support',
            'Adds cross-platform BLE discovery when the host Bluetooth stack is available.',
            'Would you like to install enhanced Bluetooth discovery support?',
            recommended=False,
        ),
        _python_component(
            'scapy',
            'Advanced packet and wireless support',
            'Enables deeper packet parsing and Linux monitor-mode workflows where the adapter and driver support them.',
            'Would you like to install advanced packet support?',
            recommended=False,
        ),
        _python_component(
            'pywifi',
            'Windows Wi-Fi management support',
            'Adds optional Windows Wi-Fi connection management beyond the built-in netsh integration.',
            'Would you like to install Windows Wi-Fi management support?',
            recommended=False,
            applicable=system_name == 'Windows',
        ),
        {
            'id': 'browser-screenshot',
            'category': 'Host integration',
            'name': 'Browser screenshot tooling',
            'description': 'Enables preview thumbnails for discovered HTTP services and saved service pages.',
            'question': 'Would you like to install browser preview support?',
            'recommended': False,
            'applicable': system_name == 'Linux',
            'installable': browser_supported,
            'installed': browser_installed,
            'status_label': (
                'Installed'
                if browser_installed
                else ('Available to install' if browser_supported else 'Manual installation required')
            ),
            'impact': 'Uses the host package manager to install Chromium. This is larger than the Python-only options.',
        },
    ]
    return [component for component in components if component.get('applicable')]


def install_component(component_id):
    """Install one allow-listed setup component and return a safe result."""
    component_id = str(component_id or '').strip()
    catalog = {component['id']: component for component in component_catalog()}
    component = catalog.get(component_id)
    if not component:
        raise ValueError('Unsupported setup component.')
    if not component.get('installable'):
        raise ValueError('This component must be installed manually on this host.')
    if component.get('installed'):
        return {
            'component': component_id,
            'installed': True,
            'message': f"{component['name']} is already available.",
        }

    if component_id == 'oui-database':
        path, count = download_oui_database()
        status = refresh_oui_database()
        return {
            'component': component_id,
            'installed': not bool(status.get('needs_refresh')),
            'message': f'Downloaded {count:,} IEEE OUI entries.',
            'path': path,
            'count': count,
            'oui_database': status,
        }
    if component_id == 'browser-screenshot':
        result = install_host_dependency('browser-screenshot')
        return {'component': component_id, **result}
    if component_id.startswith('python-'):
        package = component_id.removeprefix('python-')
        result = install_optional_package(package)
        return {
            'component': component_id,
            'message': f"Installed {OPTIONAL_PACKAGE_SPECS[package]}.",
            **result,
        }
    raise ValueError('Unsupported setup component.')
