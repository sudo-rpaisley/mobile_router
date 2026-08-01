"""Shared low-level helpers for network discovery modules."""

from __future__ import annotations


def normalize_mac(mac):
    """Return a lowercase colon-separated MAC address, when present."""

    if not mac:
        return None
    return str(mac).strip().replace("-", ":").lower()
