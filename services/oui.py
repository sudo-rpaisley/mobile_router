"""Canonical OUI/vendor lookup service.

All app features should resolve MAC vendors through this module so cards,
inventory records, wireless details, and capabilities use the same local IEEE
OUI database plus the same built-in fallback map.
"""

from scripts import interfaceTools


def lookup_manufacturer(mac):
    """Return the vendor for a MAC address using the shared OUI backend."""
    return interfaceTools.lookup_manufacturer(mac)


def refresh_oui_database():
    """Reload the shared OUI backend after the local database is updated."""
    return interfaceTools.refresh_oui_database()


def oui_database_status():
    """Return status for the shared OUI backend."""
    return interfaceTools.oui_database_status()
