"""Lazy-rendered panels for the six-part IP client workspace."""

import time

from flask import Blueprint, render_template


WORKSPACE_SECTIONS = {"network", "services", "security", "history"}


def _client_context(app_module, context_provider, identifier):
    device = app_module.find_inventory_device(identifier) or {}
    if not device:
        return None

    device = app_module.enrich_ip_client_display_name(identifier, device)
    host = device.get("ip") or identifier
    if not device.get("ip"):
        return None

    mac = device.get("mac") or app_module.get_mac_by_ip(host)
    manufacturer = device.get("manufacturer")
    if not manufacturer or str(manufacturer).casefold() == "unknown":
        manufacturer = app_module.lookup_manufacturer(mac)

    last_port_scan = device.get("last_port_scan")
    context = {
        "identifier": identifier,
        "ip": host,
        "mac": mac,
        "manufacturer": manufacturer or "Unknown",
        "display_name": app_module.display_name_for_inventory_device(
            device,
            host,
        ),
        "inventory_device": device,
        "open_port_details": device.get("open_port_details", []),
        "open_ports": device.get("open_ports", []),
        "last_port_scan_label": (
            time.strftime(
                "%Y-%m-%d %H:%M:%S",
                time.localtime(last_port_scan),
            )
            if last_port_scan
            else None
        ),
        "health_summary": app_module.client_health_summary(device, host),
        "watched_client": app_module.is_client_watched(host),
        "baseline_diff": app_module.client_baseline_diff(device),
        **context_provider(),
    }
    return context


def create_client_workspace_blueprint(context_provider):
    blueprint = Blueprint("client_workspace", __name__)

    @blueprint.get("/clients/<path:identifier>/workspace/<section>")
    def client_workspace_panel(identifier, section):
        if section not in WORKSPACE_SECTIONS:
            return "Unknown client workspace section", 404

        import app as app_module

        context = _client_context(app_module, context_provider, identifier)
        if context is None:
            return "Client was not found in inventory", 404

        host = context["ip"]
        device = context["inventory_device"]
        if section == "network":
            context.update(
                relationship_map=app_module.client_relationship_map(host),
                scheduled_check=app_module.scheduled_client_checks.get(host),
                reachability_history=app_module.client_reachability_history(host),
            )
        elif section == "security":
            context.update(
                host_fact_changes=[
                    fact
                    for fact in device.get("host_facts", [])
                    if fact.get("changed_since_baseline")
                ],
                identity_assessment=device.get("identity_assessment") or {},
                model_drift=(
                    device.get("model_profile_drift")
                    or device.get("port_profile_drift")
                    or {}
                ),
            )
        elif section == "history":
            context.update(
                client_timeline=app_module.client_timeline(host, device),
                reachability_history=app_module.client_reachability_history(host),
            )

        return render_template(
            f"client_workspace/_{section}.html",
            **context,
        )

    return blueprint
