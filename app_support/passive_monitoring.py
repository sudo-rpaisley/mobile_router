"""Compatibility façade for passive monitoring support."""

from app_support.comprehensive_scan import comprehensive_network_device_scan
from app_support.passive_analytics import (
    passive_observation_summary,
    record_passive_observation_analytics,
)
from app_support.passive_monitor_control import (
    _passive_monitor_worker,
    passive_monitor_snapshot,
    set_passive_monitor,
)
from app_support.passive_monitoring_dependencies import (
    configure_passive_monitoring_context,
)


__all__ = [
    'configure_passive_monitoring_context',
    'record_passive_observation_analytics',
    'passive_observation_summary',
    'passive_monitor_snapshot',
    '_passive_monitor_worker',
    'set_passive_monitor',
    'comprehensive_network_device_scan',
]
