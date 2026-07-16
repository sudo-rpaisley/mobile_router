#!/usr/bin/env python3
"""Bundled Windows Bluetooth helper for Mobile Router.

This helper implements the Mobile Router JSON helper protocol so Windows users
can use the bundled file without setting PATH or environment variables. Windows
restricts programmatic classic Bluetooth discoverability, so the advertising
action opens the Bluetooth settings page and tells the operator what to do next.
"""

import json
import os
import platform
import subprocess
import sys

PROTOCOL_VERSION = 1
MAX_REQUEST_BYTES = 1024 * 1024


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


def open_bluetooth_settings():
    if platform.system() != "Windows":
        return False
    try:
        os.startfile("ms-settings:bluetooth")
        return True
    except OSError:
        try:
            subprocess.Popen(["cmd", "/c", "start", "", "ms-settings:bluetooth"])
            return True
        except OSError:
            return False


def handle_set_advertising(request):
    enabled = request.get("enabled") is True
    display_name = str(request.get("display_name") or "Mobile Router").strip()
    if enabled:
        opened = open_bluetooth_settings()
        if not opened:
            return response(
                status="error",
                message="Open Windows Bluetooth settings manually, enable Bluetooth, and pair the phone with this PC.",
            )
        return response(
            status="success",
            enabled=True,
            message=(
                f'Windows Bluetooth settings opened. Enable Bluetooth and pair the phone with "{display_name}" from the phone; Windows controls discoverability prompts.'
            ),
        )
    return response(
        status="success",
        enabled=False,
        message="Windows controls Bluetooth discoverability. Remove or disconnect phones from Windows Bluetooth settings when needed.",
    )


def main():
    try:
        request = read_request()
        action = request.get("action")
        if action == "capabilities":
            return response(
                status="success",
                capabilities={
                    "advertising": True,
                    "pbap": False,
                    "map": False,
                    "note": "Bundled helper opens Windows Bluetooth settings for pairing; PBAP/MAP sync requires a full native helper.",
                },
            )
        if action == "set_advertising":
            return handle_set_advertising(request)
        return response(status="error", message=f"Unsupported helper action: {action}")
    except Exception as exc:
        return response(status="error", message=str(exc))


if __name__ == "__main__":
    main()
