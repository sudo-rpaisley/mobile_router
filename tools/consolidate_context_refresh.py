"""Consolidate copied context-refresh decorators into one shared helper."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTE_FILES = (
    "routes/client_routes.py",
    "routes/core_routes.py",
    "routes/diagnostic_routes.py",
    "routes/interface_routes.py",
    "routes/lab_routes.py",
    "routes/social_auth.py",
    "routes/social_profile_resources.py",
    "routes/social_profile_transfer.py",
    "routes/social_profiles.py",
)
SUPPORT_FILES = (
    "app_support/client_intelligence.py",
    "app_support/client_services.py",
    "app_support/passive_monitoring.py",
)

ROUTE_IMPORT = "from functools import wraps\n"
ROUTE_REPLACEMENT_IMPORT = "from app_support.context import bind_context\n"
ROUTE_BLOCK = """    globals().update(context_provider())

    def _refresh_context(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            globals().update(context_provider())
            return view(*args, **kwargs)
        return wrapped
"""
ROUTE_REPLACEMENT_BLOCK = """    _refresh_context = bind_context(globals(), context_provider)
"""

SUPPORT_IMPORT = "from functools import wraps\n"
SUPPORT_REPLACEMENT_IMPORT = "from app_support.context import context_refresher\n"
SUPPORT_BLOCK = """def _refresh_context(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if _CONTEXT_PROVIDER is not None:
            globals().update(_CONTEXT_PROVIDER())
        return view(*args, **kwargs)
    return wrapped
"""
SUPPORT_REPLACEMENT_BLOCK = """_refresh_context = context_refresher(globals(), lambda: _CONTEXT_PROVIDER)
"""


def replace_once(path: Path, old: str, new: str) -> None:
    source = path.read_text(encoding="utf-8")
    if old in source:
        path.write_text(source.replace(old, new, 1), encoding="utf-8")
        return
    if new not in source:
        raise RuntimeError(f"Expected code not found in {path}")


def main() -> None:
    for relative in ROUTE_FILES:
        path = ROOT / relative
        replace_once(path, ROUTE_IMPORT, ROUTE_REPLACEMENT_IMPORT)
        replace_once(path, ROUTE_BLOCK, ROUTE_REPLACEMENT_BLOCK)

    for relative in SUPPORT_FILES:
        path = ROOT / relative
        replace_once(path, SUPPORT_IMPORT, SUPPORT_REPLACEMENT_IMPORT)
        replace_once(path, SUPPORT_BLOCK, SUPPORT_REPLACEMENT_BLOCK)


if __name__ == "__main__":
    main()
