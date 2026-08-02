"""Explicit dynamic dependencies for client-intelligence helpers."""

from app_support.context import ContextProvider, DependencyProxy, dependency_proxy


_REQUIRED_DEPENDENCIES = frozenset({
    'MAC_RE',
    '_clean_detected_client_name',
    '_dhcp_lease_display_name',
    '_forward_dns_records',
    '_reverse_dns_display_name',
    '_ttl_os_hint',
    'append_client_timeline_event',
    'client_baseline_diff',
    'client_health_summary',
    'client_profile_export',
    'client_reachability_history',
    'client_relationship_map',
    'client_timeline',
    'client_timelines',
    'client_timelines_lock',
    'device_inventory',
    'device_inventory_lock',
    'display_name_for_inventory_device',
    'enrich_ip_client_display_name',
    'evidence_records',
    'find_inventory_device',
    'fingerprint_client_services',
    'inventory_key',
    'parse_int',
    'update_client_metadata',
})
_DEPENDENCIES: DependencyProxy | None = None


def configure_client_intelligence_context(provider: ContextProvider) -> None:
    """Configure the allow-listed application dependencies for this family."""
    global _DEPENDENCIES
    _DEPENDENCIES = dependency_proxy(
        provider,
        _REQUIRED_DEPENDENCIES,
        label='client intelligence',
    )


def client_intelligence_dependencies() -> DependencyProxy:
    """Return the configured client-intelligence dependency proxy."""
    if _DEPENDENCIES is None:
        raise RuntimeError('Client intelligence dependencies are not configured')
    return _DEPENDENCIES
