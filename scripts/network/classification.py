"""Classify discovered addresses for display and reporting."""

import ipaddress

from . import discovery


def _normalize_mac(mac):
    if not mac:
        return None
    return str(mac).strip().replace("-", ":").lower()


def classify_scan_entry(device, interface=None, network=None):
    """Classify a scan result as a host, control address, or special range."""
    ip_text = device.get("ip") if device else None
    mac = _normalize_mac(
        device.get("mac") or device.get("address") if device else None
    )
    if network is None and interface:
        network = discovery._get_ipv4_network(interface)

    classification = {
        "network_role": "Host",
        "network_scope": "Unknown",
        "is_internal": False,
        "is_control_traffic": False,
        "scan_note": "Unicast device observed in ARP cache.",
    }

    ip_obj = None
    if ip_text:
        try:
            ip_obj = ipaddress.ip_address(ip_text)
        except ValueError:
            ip_obj = None

    if mac == "ff:ff:ff:ff:ff:ff":
        classification.update(
            {
                "network_role": "Broadcast",
                "network_scope": "Local segment",
                "is_internal": True,
                "is_control_traffic": True,
                "scan_note": (
                    "Broadcast address used by the local network; "
                    "not an individual client."
                ),
            }
        )
    elif mac and mac.startswith("01:00:5e"):
        classification.update(
            {
                "network_role": "Multicast",
                "network_scope": "Local segment",
                "is_internal": True,
                "is_control_traffic": True,
                "scan_note": (
                    "IPv4 multicast group for service discovery or routing; "
                    "not an individual client."
                ),
            }
        )

    if ip_obj:
        if ip_obj == ipaddress.ip_address("255.255.255.255"):
            classification.update(
                {
                    "network_role": "Limited broadcast",
                    "network_scope": "Local segment",
                    "is_internal": True,
                    "is_control_traffic": True,
                    "scan_note": "All-hosts limited broadcast; not a physical device.",
                }
            )
        elif ip_obj.is_multicast:
            classification.update(
                {
                    "network_role": "Multicast",
                    "network_scope": "Local segment",
                    "is_internal": True,
                    "is_control_traffic": True,
                    "scan_note": (
                        "Multicast group address; used by protocols such as "
                        "mDNS, LLMNR, IGMP, or SSDP."
                    ),
                }
            )
        elif network and ip_obj == network.broadcast_address:
            classification.update(
                {
                    "network_role": "Subnet broadcast",
                    "network_scope": "Local subnet",
                    "is_internal": True,
                    "is_control_traffic": True,
                    "scan_note": (
                        f"Broadcast address for {network}; "
                        "not an individual client."
                    ),
                }
            )
        elif ip_obj.is_private:
            classification.update(
                {
                    "network_scope": "Private LAN",
                    "is_internal": True,
                    "scan_note": (
                        "Private RFC1918 unicast address; likely a local host "
                        "or router."
                    ),
                }
            )
            if ip_text.endswith(".1") or ip_text.endswith(".254"):
                classification.update(
                    {
                        "network_role": "Likely gateway/router",
                        "scan_note": (
                            "Private unicast address commonly used by gateways "
                            "or virtual network routers."
                        ),
                    }
                )
        elif ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved:
            classification.update(
                {
                    "network_scope": "Special-use",
                    "is_internal": True,
                    "scan_note": (
                        "Special-use address range; review before treating as "
                        "an external host."
                    ),
                }
            )
        elif ip_obj.is_global:
            classification.update(
                {
                    "network_scope": "Public Internet",
                    "scan_note": "Globally routable unicast address.",
                }
            )

    return classification


def classify_scan_results(devices, interface=None):
    """Return scan results with network-role metadata attached."""
    network = discovery._get_ipv4_network(interface) if interface else None
    return [
        {**device, **classify_scan_entry(device, interface, network)}
        for device in devices or []
    ]
