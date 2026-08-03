"""Read-only VLAN lookup for dynamically rendered device cards."""

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, session

from services import vlan_investigations as vlan_service


def create_vlan_lookup_blueprint(_context_provider):
    blueprint = Blueprint("vlan_lookup", __name__)

    @blueprint.get("/api/v1/vlans/lookup")
    def lookup_vlans():
        if not session.get("social_user"):
            return jsonify({"status": "error", "message": "Login required"}), 401
        raw = request.args.get("ips") or ""
        addresses = []
        for value in raw.split(","):
            value = value.strip()
            if value and value not in addresses:
                addresses.append(value)
        if len(addresses) > 256:
            return jsonify({"status": "error", "message": "At most 256 addresses may be looked up"}), 400
        database_path = Path(current_app.instance_path) / "vlan_investigations.sqlite3"
        results = {}
        for address in addresses:
            vlan = vlan_service.vlan_for_ip(database_path, address)
            if vlan:
                results[address] = {
                    "id": vlan["id"],
                    "tag": vlan.get("tag"),
                    "name": vlan["name"],
                    "subnet": vlan["subnet"],
                    "gateway": vlan.get("gateway"),
                    "label": vlan["label"],
                    "url": f"/vlans/{vlan['id']}",
                    "source": "subnet-match",
                    "confidence": "high",
                }
        return jsonify({"status": "success", "vlans": results})

    return blueprint
