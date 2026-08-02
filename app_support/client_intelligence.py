"""Compatibility façade for client intelligence support."""

from app_support.client_identity import (
    _dhcp_lease_display_name,
    _ttl_os_hint,
    display_name_for_inventory_device,
    enrich_ip_client_display_name,
)
from app_support.client_intelligence_dependencies import (
    configure_client_intelligence_context,
)
from app_support.client_metadata import (
    save_client_baseline,
    update_client_metadata,
)
from app_support.client_profile import (
    client_health_summary,
    client_intelligence_profile,
    client_profile_export,
    client_relationship_map,
    client_timeline,
)


__all__ = [
    'configure_client_intelligence_context',
    '_dhcp_lease_display_name',
    'display_name_for_inventory_device',
    'enrich_ip_client_display_name',
    'client_timeline',
    'client_health_summary',
    '_ttl_os_hint',
    'client_intelligence_profile',
    'update_client_metadata',
    'save_client_baseline',
    'client_profile_export',
    'client_relationship_map',
]
