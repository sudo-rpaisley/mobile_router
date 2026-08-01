"""Explicit dependency access for client service support modules."""

from __future__ import annotations

from .context import ContextProvider, DependencyProxy, dependency_proxy


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


ClientServicesDependencies = DependencyProxy
_DEPENDENCIES: DependencyProxy | None = None


def configure_client_services_context(provider: ContextProvider) -> None:
    """Configure the explicit dependency resolver used by client services."""
    global _DEPENDENCIES
    _DEPENDENCIES = dependency_proxy(
        provider,
        _REQUIRED_DEPENDENCIES,
        label='client services',
    )


def client_service_dependencies() -> DependencyProxy:
    """Return the configured dependency resolver."""
    if _DEPENDENCIES is None:
        raise RuntimeError('Client services context has not been configured')
    return _DEPENDENCIES
