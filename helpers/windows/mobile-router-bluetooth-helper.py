#!/usr/bin/env python3
"""Bundled Windows Bluetooth helper for Mobile Router.

This helper implements the Mobile Router JSON helper protocol so Windows users
can use the bundled file without setting PATH or environment variables. The
bundled helper intentionally does not open system-wide Windows Bluetooth pairing
or rename the PC: pairing through Windows settings pairs the phone with the
whole laptop, not only with Mobile Router. App-scoped pairing requires a full
native helper that owns its own Bluetooth service/profile.
"""

import json
import sys

PROTOCOL_VERSION = 1
MAX_REQUEST_BYTES = 1024 * 1024
APP_SCOPED_PAIRING_UNAVAILABLE = (
    "The bundled Windows helper will not pair phones through the whole laptop. "
    "Install a full Mobile Router native Bluetooth helper that provides an "
    "app-scoped Bluetooth service/profile to pair only with this app."
)


def response(**payload):
    json.dump({"protocol_version": PROTOCOL_VERSION, **payload}, sys.stdout)


def read_request():
    raw = sys.stdin.read(MAX_REQUEST_BYTES + 1)
    if len(raw.encode("utf-8")) > MAX_REQUEST_BYTES:
        raise ValueError("Helper request is too large")
    request = json.loads(raw or "{}")
    if request.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("Helper protocol version does not match")
    return request


def handle_set_advertising(request):
    enabled = request.get("enabled") is True
    return response(
        status="error" if enabled else "success",
        enabled=False,
        app_scoped_pairing=False,
        message=APP_SCOPED_PAIRING_UNAVAILABLE,
    )


def main():
    try:
        request = read_request()
        action = request.get("action")
        if action == "capabilities":
            return response(
                status="success",
                capabilities={
                    "advertising": False,
                    "app_scoped_pairing": False,
                    "pbap": False,
                    "map": False,
                    "note": APP_SCOPED_PAIRING_UNAVAILABLE,
                },
            )
        if action == "set_advertising":
            return handle_set_advertising(request)
        return response(status="error", message=f"Unsupported helper action: {action}")
    except Exception as exc:
        return response(status="error", message=str(exc))


if __name__ == "__main__":
    main()
