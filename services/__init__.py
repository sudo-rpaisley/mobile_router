"""Application service helpers split from Flask route wiring."""

# The VLAN service normally initialises its schema through list/read operations.
# A pfSense integration can also be the first VLAN operation in a fresh instance,
# so guard that direct writer at the package boundary as well. Keeping the guard
# here avoids coupling the persistence module to Flask application startup.
from . import vlan_investigations as vlan_investigations


_save_vlan_integration = vlan_investigations.save_integration


def _save_initialised_vlan_integration(database_path, payload, integration_id=None, now=None):
    vlan_investigations.initialise_database(database_path)
    return _save_vlan_integration(
        database_path,
        payload,
        integration_id=integration_id,
        now=now,
    )


vlan_investigations.save_integration = _save_initialised_vlan_integration
