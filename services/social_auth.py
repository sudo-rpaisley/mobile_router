"""Local authentication, CSRF, and audit helpers for sensitive profile records."""

import time
import uuid

from werkzeug.security import check_password_hash, generate_password_hash


ROLES = {'viewer', 'editor', 'credential_manager', 'admin'}


def create_user(username, password, role, store, lock):
    username = str(username or '').strip().casefold()
    role = str(role or 'viewer').strip().casefold()
    if len(username) < 3:
        raise ValueError('Username must be at least three characters.')
    if len(str(password or '')) < 10:
        raise ValueError('Password must be at least ten characters.')
    if role not in ROLES:
        raise ValueError('Invalid role.')
    with lock:
        if username in store:
            raise ValueError('Username already exists.')
        store[username] = {
            'id': str(uuid.uuid4()), 'username': username, 'role': role,
            'password_hash': generate_password_hash(password), 'created_at': time.time(),
        }
        return dict(store[username])


def authenticate(username, password, store, lock):
    with lock:
        user = store.get(str(username or '').strip().casefold())
        if not user or not check_password_hash(user.get('password_hash', ''), str(password or '')):
            return None
        return dict(user)


def record_audit(action, username, records, lock, profile_id=None, detail=None):
    record = {
        'id': str(uuid.uuid4()), 'action': action, 'username': username or 'system',
        'profile_id': profile_id, 'detail': detail, 'created_at': time.time(),
    }
    with lock:
        records.insert(0, record)
        del records[500:]
    return dict(record)
