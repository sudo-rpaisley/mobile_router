#!/usr/bin/env python3
"""Restricted remote probe for Mobile Router VLAN investigations.

The agent performs a bounded ping sweep of one configured IPv4 subnet, reads the
local neighbour table when available, and submits structured observations using
HMAC-SHA256. It does not capture payloads, attempt authentication, or scan ports.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import ipaddress
import json
import os
import platform
import re
import secrets
import subprocess
import time
from urllib.request import Request, urlopen


MAX_HOSTS = 1024


def ping_command(host):
    if os.name == "nt":
        return ["ping", "-n", "1", "-w", "1000", host]
    return ["ping", "-c", "1", "-W", "1", host]


def ping_host(host):
    started = time.monotonic()
    try:
        result = subprocess.run(
            ping_command(host), capture_output=True, text=True, timeout=3, check=False
        )
        reachable = result.returncode == 0
        detail = (result.stdout or result.stderr or "").strip()[-1000:]
    except (OSError, subprocess.TimeoutExpired) as exc:
        reachable = False
        detail = str(exc)
    return {
        "host": host,
        "reachable": reachable,
        "duration_ms": round((time.monotonic() - started) * 1000, 2),
        "detail": detail,
    }


def neighbour_records():
    commands = (["arp", "-a"],) if os.name == "nt" else (["ip", "neigh", "show"], ["arp", "-an"])
    output = ""
    for command in commands:
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0 and result.stdout:
            output = result.stdout
            break
    records = []
    seen = set()
    for line in output.splitlines():
        ip_match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", line)
        mac_match = re.search(r"\b(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\b", line)
        if not ip_match:
            continue
        ip = ip_match.group(0)
        mac = mac_match.group(0).replace("-", ":").lower() if mac_match else None
        key = (ip, mac)
        if key in seen:
            continue
        seen.add(key)
        records.append({"ip": ip, "mac": mac, "source": "local-neighbour-table"})
    return records


def signature(secret, timestamp, nonce, body):
    message = str(timestamp).encode("ascii") + b"\n" + nonce.encode("utf-8") + b"\n" + body
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def build_payload(subnet):
    network = ipaddress.ip_network(subnet, strict=False)
    if network.version != 4:
        raise ValueError("The probe currently supports IPv4 subnets only")
    hosts = list(network.hosts())
    if len(hosts) > MAX_HOSTS:
        raise ValueError(f"Subnet has {len(hosts)} usable hosts; limit is {MAX_HOSTS}")
    observations = [ping_host(str(host)) for host in hosts]
    neighbours = neighbour_records()
    neighbour_by_ip = {item["ip"]: item for item in neighbours}
    devices = []
    for item in observations:
        if not item["reachable"] and item["host"] not in neighbour_by_ip:
            continue
        neighbour = neighbour_by_ip.get(item["host"], {})
        devices.append(
            {
                "ip": item["host"],
                "mac": neighbour.get("mac"),
                "name": None,
                "sources": ["remote-probe-ping", neighbour.get("source")]
                if neighbour else ["remote-probe-ping"],
            }
        )
    for neighbour in neighbours:
        if neighbour["ip"] not in {item["ip"] for item in devices}:
            devices.append(neighbour)
    return {
        "schema": "mobile-router-vlan-probe-v1",
        "probe_host": platform.node(),
        "observed_at": time.time(),
        "subnet": str(network),
        "hosts": observations,
        "devices": devices,
        "route": {},
        "segmentation_results": [],
    }


def submit(server, probe_id, secret, payload, verify_tls=True):
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    timestamp = int(time.time())
    nonce = secrets.token_hex(16)
    request = Request(
        server.rstrip("/") + f"/api/v1/vlan-probes/{probe_id}/observations",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Probe-Timestamp": str(timestamp),
            "X-Probe-Nonce": nonce,
            "X-Probe-Signature": "sha256=" + signature(secret, timestamp, nonce, body),
        },
    )
    context = None
    if not verify_tls:
        import ssl
        context = ssl._create_unverified_context()
    with urlopen(request, timeout=30, context=context) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Submit bounded local VLAN observations to Mobile Router")
    parser.add_argument("--server", required=True, help="Mobile Router HTTPS base URL")
    parser.add_argument("--probe-id", required=True)
    parser.add_argument("--subnet", required=True)
    parser.add_argument("--secret-env", required=True)
    parser.add_argument("--no-verify-tls", action="store_true", help="Explicitly allow a self-signed local server certificate")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    secret = os.environ.get(args.secret_env)
    if not secret:
        raise SystemExit(f"Environment variable {args.secret_env} is not set")
    payload = build_payload(args.subnet)
    if args.dry_run:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    result = submit(args.server, args.probe_id, secret, payload, verify_tls=not args.no_verify_tls)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
