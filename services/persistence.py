"""Small JSON persistence helpers for runtime inventory/profile state."""

import json
import os
import tempfile
import time

DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
STATE_SCHEMA_VERSION = 1


def state_path():
    return os.environ.get('MOBILE_ROUTER_STATE_PATH') or os.path.join(
        os.environ.get('MOBILE_ROUTER_DATA_DIR', DEFAULT_DATA_DIR),
        'runtime_state.json',
    )


def _json_safe(value):
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def load_state(path=None):
    path = path or state_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding='utf-8') as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def save_state(state, path=None):
    path = path or state_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        'schema_version': STATE_SCHEMA_VERSION,
        'saved_at': time.time(),
        **_json_safe(state),
    }
    fd, tmp_path = tempfile.mkstemp(prefix='.runtime-state-', suffix='.json', dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    return path
