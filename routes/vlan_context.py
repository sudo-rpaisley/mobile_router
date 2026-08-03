"""Template helpers for showing first-class VLAN metadata consistently."""

from pathlib import Path

from flask import Blueprint, current_app

from services import vlan_investigations as vlan_service


def create_vlan_context_blueprint(_context_provider):
    blueprint = Blueprint("vlan_context", __name__)

    @blueprint.app_context_processor
    def inject_vlan_helpers():
        database_path = Path(current_app.instance_path) / "vlan_investigations.sqlite3"

        def vlan_device(device):
            return vlan_service.decorate_device(database_path, device or {})

        return {"vlan_device": vlan_device}

    return blueprint
