"""Local authentication, account preferences, CSRF, and audit helpers."""

import re
import time
import uuid

from werkzeug.security import check_password_hash, generate_password_hash


ROLES = {'viewer', 'editor', 'credential_manager', 'admin'}
LANDING_PAGES = (
    ('Interfaces', '/'),
    ('Device inventory', '/inventory'),
    ('Network scan', '/network-scan'),
    ('Automotive', '/automotive'),
    ('Reports', '/reports'),
)
LANDING_PAGE_URLS = {url for _, url in LANDING_PAGES}
EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')


def _default_preferences():
    return {
        'default_landing_page': '/',
        'compact_layout': False,
        'reduced_motion': False,
        'favourites': [],
    }


def _bool_value(value):
    if isinstance(value, bool):
        return value
    return str(value or '').strip().casefold() in {'1', 'true', 'yes', 'on'}


def public_user(user):
    """Return account fields safe to expose to templates and browser code."""
    if not user:
        return None
    preferences = _default_preferences()
    preferences.update(dict(user.get('preferences') or {}))
    favourites = []
    for item in preferences.get('favourites') or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get('label') or '').strip()
        url = str(item.get('url') or '').strip()
        if label and url.startswith('/') and not url.startswith('//'):
            favourites.append({'label': label, 'url': url})
    preferences['favourites'] = favourites[:12]
    return {
        'id': user.get('id'),
        'username': user.get('username'),
        'display_name': user.get('display_name') or user.get('username'),
        'email': user.get('email') or '',
        'role': user.get('role'),
        'created_at': user.get('created_at'),
        'password_changed_at': user.get('password_changed_at'),
        'preferences': preferences,
    }


def create_user(username, password, role, store, lock):
    username = str(username or '').strip().casefold()
    role = str(role or 'viewer').strip().casefold()
    if len(username) < 3:
        raise ValueError('Username must be at least three characters.')
    if len(str(password or '')) < 10:
        raise ValueError('Password must be at least ten characters.')
    if role not in ROLES:
        raise ValueError('Invalid role.')
    created_at = time.time()
    with lock:
        if username in store:
            raise ValueError('Username already exists.')
        store[username] = {
            'id': str(uuid.uuid4()),
            'username': username,
            'display_name': username,
            'email': '',
            'role': role,
            'password_hash': generate_password_hash(password),
            'created_at': created_at,
            'password_changed_at': created_at,
            'preferences': _default_preferences(),
        }
        return dict(store[username])


def authenticate(username, password, store, lock):
    with lock:
        user = store.get(str(username or '').strip().casefold())
        if not user or not check_password_hash(user.get('password_hash', ''), str(password or '')):
            return None
        return dict(user)


def default_landing_page(user):
    preferences = dict((user or {}).get('preferences') or {})
    candidate = str(preferences.get('default_landing_page') or '/')
    return candidate if candidate in LANDING_PAGE_URLS else '/'


def update_user_profile(
    username,
    display_name,
    email,
    default_landing_page,
    compact_layout,
    reduced_motion,
    store,
    lock,
):
    username = str(username or '').strip().casefold()
    display_name = str(display_name or '').strip()
    email = str(email or '').strip().casefold()
    default_landing_page = str(default_landing_page or '/')
    if not display_name:
        raise ValueError('Display name is required.')
    if len(display_name) > 80:
        raise ValueError('Display name must be 80 characters or fewer.')
    if email and (len(email) > 254 or not EMAIL_RE.fullmatch(email)):
        raise ValueError('Enter a valid email address or leave it blank.')
    if default_landing_page not in LANDING_PAGE_URLS:
        raise ValueError('Select a supported default landing page.')

    with lock:
        user = store.get(username)
        if not user:
            raise ValueError('Account not found.')
        preferences = _default_preferences()
        preferences.update(dict(user.get('preferences') or {}))
        preferences.update({
            'default_landing_page': default_landing_page,
            'compact_layout': _bool_value(compact_layout),
            'reduced_motion': _bool_value(reduced_motion),
        })
        user['display_name'] = display_name
        user['email'] = email
        user['preferences'] = preferences
        return public_user(user)


def change_password(username, current_password, new_password, confirmation, store, lock):
    username = str(username or '').strip().casefold()
    current_password = str(current_password or '')
    new_password = str(new_password or '')
    confirmation = str(confirmation or '')
    if len(new_password) < 10:
        raise ValueError('The new password must be at least ten characters.')
    if new_password != confirmation:
        raise ValueError('The new passwords do not match.')

    with lock:
        user = store.get(username)
        if not user or not check_password_hash(user.get('password_hash', ''), current_password):
            raise ValueError('The current password is incorrect.')
        if check_password_hash(user.get('password_hash', ''), new_password):
            raise ValueError('Choose a password different from the current password.')
        user['password_hash'] = generate_password_hash(new_password)
        user['password_changed_at'] = time.time()
        return public_user(user)


def update_favourite(username, url, label, action, store, lock):
    username = str(username or '').strip().casefold()
    url = str(url or '').strip()
    label = str(label or '').strip()
    action = str(action or 'add').strip().casefold()
    if not url.startswith('/') or url.startswith('//') or '\\' in url or len(url) > 2048:
        raise ValueError('Favourites must use a local application page.')
    if action not in {'add', 'remove'}:
        raise ValueError('Unsupported favourite action.')
    if action == 'add' and (not label or len(label) > 80):
        raise ValueError('Favourite labels must be between 1 and 80 characters.')

    with lock:
        user = store.get(username)
        if not user:
            raise ValueError('Account not found.')
        preferences = _default_preferences()
        preferences.update(dict(user.get('preferences') or {}))
        favourites = [
            {'label': str(item.get('label') or '').strip(), 'url': str(item.get('url') or '').strip()}
            for item in preferences.get('favourites') or []
            if isinstance(item, dict)
        ]
        favourites = [item for item in favourites if item['url'] != url]
        if action == 'add':
            favourites.insert(0, {'label': label, 'url': url})
        preferences['favourites'] = favourites[:12]
        user['preferences'] = preferences
        return list(preferences['favourites'])


def record_audit(action, username, records, lock, profile_id=None, detail=None):
    record = {
        'id': str(uuid.uuid4()), 'action': action, 'username': username or 'system',
        'profile_id': profile_id, 'detail': detail, 'created_at': time.time(),
    }
    with lock:
        records.insert(0, record)
        del records[500:]
    return dict(record)
