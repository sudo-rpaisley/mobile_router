"""Compatibility façade for network discovery and classification helpers.

New code should import from ``scripts.network.discovery``,
``scripts.network.classification``, or ``scripts.network.passive_capture``.
The legacy names remain available here so existing application imports and
patch-based tests keep working during the wider application refactor.
"""

from scripts.network import classification as _classification
from scripts.network import discovery as _discovery
from scripts.network.passive_capture import packet_passive_scan


# Retain the historical helper names for callers and tests that patch them.
_get_ipv4_cidr = _discovery._get_ipv4_cidr
_ping_command = _discovery._ping_command
_get_ipv4_network_impl = _discovery._get_ipv4_network
_ping_host = _discovery._ping_host
_dedupe_devices = _discovery._dedupe_devices
_parse_proc_arp = _discovery._parse_proc_arp
_parse_arp_command = _discovery._parse_arp_command
_arp_cache_candidates = _discovery._arp_cache_candidates
_normalize_mac = _classification._normalize_mac


def _sync_discovery_hooks():
    """Copy legacy patch points into the extracted discovery module."""
    _discovery._get_ipv4_cidr = _get_ipv4_cidr
    _discovery._ping_command = _ping_command
    _discovery._ping_host = _ping_host
    _discovery._dedupe_devices = _dedupe_devices
    _discovery._parse_proc_arp = _parse_proc_arp
    _discovery._parse_arp_command = _parse_arp_command
    _discovery._arp_cache_candidates = _arp_cache_candidates
    _discovery.get_mac_by_ip = get_mac_by_ip


def _get_ipv4_network(interface):
    _sync_discovery_hooks()
    return _get_ipv4_network_impl(interface)


def classify_scan_entry(device, interface=None, network=None):
    _sync_discovery_hooks()
    return _classification.classify_scan_entry(device, interface, network)


def classify_scan_results(devices, interface=None):
    _sync_discovery_hooks()
    return _classification.classify_scan_results(devices, interface)


def active_scan(interface):
    _sync_discovery_hooks()
    return _discovery.active_scan(interface)


def passive_scan(interface):
    _sync_discovery_hooks()
    return _discovery.passive_scan(interface)


def get_mac_by_ip(ip):
    _sync_discovery_hooks()
    return _discovery.get_mac_by_ip(ip)


def get_ip_by_mac(mac):
    _sync_discovery_hooks()
    return _discovery.get_ip_by_mac(mac)


__all__ = [
    "active_scan",
    "classify_scan_entry",
    "classify_scan_results",
    "get_ip_by_mac",
    "get_mac_by_ip",
    "packet_passive_scan",
    "passive_scan",
]
