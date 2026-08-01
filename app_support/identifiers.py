"""Normalization and stable-key helpers for discovered devices."""

import re

MAC_RE = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$')

def normalize_mac(mac):
    """Normalize a MAC-like value to colon-separated lowercase format."""
    if not mac:
        return None
    value = str(mac).strip().replace('-', ':').lower()
    if MAC_RE.match(value):
        return value
    return None

def inventory_key(device):
    mac = normalize_mac(device.get('mac') or device.get('address'))
    if mac:
        return f"mac:{mac}"
    ip = device.get('ip')
    if ip:
        return f"ip:{ip}"
    ssid = device.get('ssid')
    bssid = normalize_mac(device.get('bssid'))
    if ssid or bssid:
        return f"wifi:{ssid or 'hidden'}:{bssid or 'unknown'}"
    return None
