"""Explicit dynamic dependencies for passive-monitoring helpers."""

from app_support.context import ContextProvider, DependencyProxy, dependency_proxy


_REQUIRED_DEPENDENCIES = frozenset({
    '_run_text_command',
    'active_scan',
    'classify_scan_results',
    'discover_lldp_neighbors',
    'discover_mdns_services',
    'discover_upnp_devices',
    'lookup_manufacturer',
    'merge_discovered_devices',
    'normalize_mac',
    'os',
    'packet_passive_scan',
    'parse_int',
    'parse_neighbor_table',
    'passive_analytics_lock',
    'passive_device_identity',
    'passive_monitor_jobs',
    'passive_monitor_lock',
    'passive_observation_analytics',
    'passive_scan',
    'record_inventory_devices',
    'run_ping_sweep',
    'save_runtime_state',
})
_DEPENDENCIES: DependencyProxy | None = None


def configure_passive_monitoring_context(provider: ContextProvider) -> None:
    """Configure the allow-listed application dependencies for this family."""
    global _DEPENDENCIES
    _DEPENDENCIES = dependency_proxy(
        provider,
        _REQUIRED_DEPENDENCIES,
        label='passive monitoring',
    )


def passive_monitoring_dependencies() -> DependencyProxy:
    """Return the configured passive-monitoring dependency proxy."""
    if _DEPENDENCIES is None:
        raise RuntimeError('Passive monitoring dependencies are not configured')
    return _DEPENDENCIES
