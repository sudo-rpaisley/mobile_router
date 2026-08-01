"""Compatibility façade for client service support functions."""

from .client_service_dependencies import (
    ClientServicesDependencies,
    configure_client_services_context,
)
from .client_service_http import (
    capture_http_preview_thumbnail,
    fingerprint_client_services,
    inspect_http_services,
)
from .client_service_scheduling import (
    create_client_watch_alert,
    run_due_scheduled_client_checks,
    run_scheduled_client_check,
    save_scheduled_client_check,
    scan_common_client_ports,
)


__all__ = [
    'ClientServicesDependencies',
    'capture_http_preview_thumbnail',
    'configure_client_services_context',
    'create_client_watch_alert',
    'fingerprint_client_services',
    'inspect_http_services',
    'run_due_scheduled_client_checks',
    'run_scheduled_client_check',
    'save_scheduled_client_check',
    'scan_common_client_ports',
]
