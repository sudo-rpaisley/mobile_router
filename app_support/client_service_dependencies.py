"""Explicit dependency access for client service support modules."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


ContextProvider = Callable[[], Mapping[str, Any]]
_REQUIRED_DEPENDENCIES = {
    'HTTP_PREVIEW_DIR',
    'append_client_timeline_event',
    'capture_http_preview_thumbnail',
    'client_baseline_diff',
    'create_client_watch_alert',
    'enrich_web_port_metadata',
    'find_inventory_device',
    'fingerprint_client_services',
    'inspect_http_services',
    'is_client_watched',
    'new_device_alerts',
    'new_device_alerts_lock',
    'parse_int',
    'record_device_open_ports',
    'run_ping_check',
    'run_scheduled_client_check',
    'save_runtime_state',
    'scan_common_client_ports',
    'scheduled_client_checks',
}


class ClientServicesDependencies:
    """Resolve only the application dependencies used by client services.

    The provider stays dynamic so tests may monkey-patch names on ``app``.
    Unlike the legacy bridge, this object never mutates a module namespace.
    """

    def __init__(self, provider: ContextProvider):
        self._provider = provider

    def __getattr__(self, name: str) -> Any:
        if name not in _REQUIRED_DEPENDENCIES:
            raise AttributeError(name)
        context = self._provider()
        try:
            return context[name]
        except KeyError as exc:
            raise RuntimeError(
                f'Client services dependency {name!r} is not configured'
            ) from exc


_DEPENDENCIES: ClientServicesDependencies | None = None


def configure_client_services_context(provider: ContextProvider) -> None:
    """Configure the explicit dependency resolver used by client services."""
    global _DEPENDENCIES
    _DEPENDENCIES = ClientServicesDependencies(provider)


def client_service_dependencies() -> ClientServicesDependencies:
    """Return the configured dependency resolver."""
    if _DEPENDENCIES is None:
        raise RuntimeError('Client services context has not been configured')
    return _DEPENDENCIES
