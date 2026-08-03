"""Editable saved-service records that survive later port scans."""

from __future__ import annotations

import copy
import time
from urllib.parse import urlsplit


_PROTOCOLS = {"tcp", "udp"}
_MANUAL_DETAIL_FIELDS = {
    "service_manual_override",
    "detected_service",
    "detected_description",
    "service_notes",
    "service_source_name",
    "service_source_url",
    "service_updated_at",
    "service_updated_by",
}


def _clean(value, limit):
    return str(value or "").strip()[:limit]


def valid_port(value):
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Port must be an integer") from exc
    if not 1 <= port <= 65535:
        raise ValueError("Port must be between 1 and 65535")
    return port


def valid_protocol(value):
    protocol = _clean(value or "tcp", 8).casefold()
    if protocol not in _PROTOCOLS:
        raise ValueError("Protocol must be TCP or UDP")
    return protocol


def valid_source_url(value):
    url = _clean(value, 1000)
    if not url:
        return ""
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Source URL must be a complete HTTP or HTTPS URL")
    if parsed.username or parsed.password:
        raise ValueError("Source URL must not contain credentials")
    return url


def _key(item):
    try:
        return valid_port(item.get("port")), valid_protocol(item.get("protocol") or "tcp")
    except (AttributeError, ValueError):
        return None


def override_for(device, port, protocol="tcp"):
    target = valid_port(port), valid_protocol(protocol)
    for item in (device or {}).get("service_record_overrides") or []:
        if _key(item) == target:
            return dict(item)
    return None


def apply_overrides(device):
    """Return a device copy with saved manual values applied to port details."""
    updated = copy.deepcopy(device or {})
    overrides = {
        item_key: dict(item)
        for item in updated.get("service_record_overrides") or []
        if (item_key := _key(item)) is not None
    }
    details = []
    for raw in updated.get("open_port_details") or []:
        detail = dict(raw)
        item_key = _key(detail)
        override = overrides.get(item_key)
        was_manual = bool(detail.get("service_manual_override"))
        if override:
            detected_service = (
                detail.get("detected_service") if was_manual else detail.get("service")
            ) or "Unknown"
            detected_description = (
                detail.get("detected_description") if was_manual else detail.get("description")
            ) or ""
            detail.update({
                "detected_service": detected_service,
                "detected_description": detected_description,
                "service": override["service"],
                "description": override.get("description") or detected_description,
                "service_notes": override.get("notes") or "",
                "service_source_name": override.get("source_name") or "",
                "service_source_url": override.get("source_url") or "",
                "service_updated_at": override.get("updated_at"),
                "service_updated_by": override.get("updated_by") or "",
                "service_manual_override": True,
            })
        elif was_manual:
            detail["service"] = detail.get("detected_service") or "Unknown"
            detail["description"] = detail.get("detected_description") or ""
            for field in _MANUAL_DETAIL_FIELDS:
                detail.pop(field, None)
        details.append(detail)
    updated["open_port_details"] = details
    return updated


def update_override(
    device,
    *,
    port,
    protocol="tcp",
    service="",
    description="",
    notes="",
    source_name="",
    source_url="",
    updated_by="",
    clear=False,
):
    """Create, replace, or remove a device-specific saved-service override."""
    port, protocol = valid_port(port), valid_protocol(protocol)
    updated = copy.deepcopy(device or {})
    details = updated.get("open_port_details") or []
    if not any(_key(item) == (port, protocol) for item in details):
        raise ValueError(f"No saved {port}/{protocol} service exists for this device")

    overrides = [
        dict(item)
        for item in updated.get("service_record_overrides") or []
        if _key(item) != (port, protocol)
    ]
    if not clear:
        service = _clean(service, 200)
        if not service:
            raise ValueError("Service name is required")
        overrides.append({
            "port": port,
            "protocol": protocol,
            "service": service,
            "description": _clean(description, 2000),
            "notes": _clean(notes, 2000),
            "source_name": _clean(source_name, 240),
            "source_url": valid_source_url(source_url),
            "updated_at": time.time(),
            "updated_by": _clean(updated_by, 120),
        })
    updated["service_record_overrides"] = sorted(
        overrides, key=lambda item: (item["protocol"], item["port"])
    )
    return apply_overrides(updated)
