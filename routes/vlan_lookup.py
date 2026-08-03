"""Read-only VLAN lookup for dynamically rendered device cards."""

import ipaddress
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
        networks = [
            (ipaddress.ip_network(vlan["subnet"], strict=False), vlan)
            for vlan in vlan_service.list_vlans(database_path)
        ]
        results = {}
        for address in addresses:
            try:
                ip = ipaddress.ip_address(address)
            except ValueError:
                continue
            matches = [item for item in networks if ip in item[0]]
            if not matches:
                continue
            _network, vlan = max(matches, key=lambda item: item[0].prefixlen)
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
