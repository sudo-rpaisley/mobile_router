"""Explainable host facts, bounded capability probes, baselines, and secret references."""

from __future__ import annotations

import base64
import copy
import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
import ssl
import struct
import subprocess
import time
import uuid
from pathlib import Path

from services import device_identification

_MAX_TEXT = 4000
_MAX_FACTS = 240
_MAX_PORTS = 24
_CREDENTIAL_KINDS = {"snmp-v2c", "ssh", "http-basic", "api-token"}
_CONFIDENCE = {"low", "medium", "high", "very-high"}
_SENSITIVITY = {"public", "internal", "sensitive"}


def _clean(value, limit=_MAX_TEXT):
    return str(value or "").strip()[:limit]


def _value_text(value):
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, sort_keys=True, default=str)[:_MAX_TEXT]
    return _clean(value)


def fact(
    key,
    label,
    value,
    source,
    confidence="medium",
    *,
    category="identity",
    sensitivity="internal",
    observed_at=None,
):
    confidence = confidence if confidence in _CONFIDENCE else "medium"
    sensitivity = sensitivity if sensitivity in _SENSITIVITY else "internal"
    return {
        "key": _clean(key, 180),
        "label": _clean(label, 240),
        "value": value,
        "value_text": _value_text(value),
        "source": _clean(source, 240),
        "confidence": confidence,
        "category": _clean(category, 80),
        "sensitivity": sensitivity,
        "observed_at": float(observed_at or time.time()),
    }


def _ipv6_addresses(device):
    values = []
    for field in ("ipv6", "ipv6_address", "ipv6_addresses"):
        raw = (device or {}).get(field)
        if isinstance(raw, str):
            values.extend(part.strip() for part in raw.split(","))
        elif isinstance(raw, (list, tuple, set)):
            values.extend(str(item).strip() for item in raw)
    for item in (device or {}).get("addresses") or []:
        if isinstance(item, dict):
            values.append(str(item.get("address") or item.get("ip") or "").strip())
        else:
            values.append(str(item).strip())
    result = []
    for value in values:
        value = value.split("%", 1)[0]
        try:
            parsed = ipaddress.ip_address(value)
        except ValueError:
            continue
        if parsed.version == 6 and str(parsed) not in result:
            result.append(str(parsed))
    return result[:12]


def _open_ports(device):
    ports = []
    for item in (device or {}).get("open_port_details") or []:
        try:
            port = int(item.get("port"))
        except (TypeError, ValueError, AttributeError):
            continue
        if 1 <= port <= 65535 and port not in ports:
            ports.append(port)
    return ports[:_MAX_PORTS]


def _local_default_gateways():
    gateways = set()
    commands = []
    if os.name == "nt":
        commands.append(["route", "print", "-4"])
    else:
        commands.extend([["ip", "route", "show", "default"], ["route", "-n"]])
    for command in commands:
        if not shutil.which(command[0]):
            continue
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=4,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        for token in re.findall(r"(?:\d{1,3}\.){3}\d{1,3}", result.stdout or ""):
            try:
                ipaddress.ip_address(token)
            except ValueError:
                continue
            if token not in {"0.0.0.0", "255.255.255.255"}:
                gateways.add(token)
        if gateways:
            break
    return sorted(gateways)


def infer_network_role(device):
    ports = set(_open_ports(device))
    host = str((device or {}).get("ip") or "")
    gateways = _local_default_gateways()
    evidence = []
    scores = {}

    def add(role, score, reason):
        scores[role] = scores.get(role, 0) + score
        evidence.append({"role": role, "reason": reason, "weight": score})

    if host and host in gateways:
        add("Default gateway/router", 70, "Host matches a local default gateway")
    if 53 in ports:
        add("DNS server", 30, "DNS port is open")
    if ports & {67, 68}:
        add("DHCP service", 35, "DHCP port is open")
    if 53 in ports and ports & {67, 68}:
        add("Default gateway/router", 30, "DNS and DHCP services are combined")
    if ports & {445, 2049}:
        add("File server/NAS", 35, "File-sharing service is exposed")
    if ports & {631, 9100, 515}:
        add("Printer", 50, "Print service is exposed")
    if ports & {554, 8554}:
        add("Camera/NVR", 50, "RTSP service is exposed")
    if ports & {1883, 8883, 6053}:
        add("IoT or automation endpoint", 40, "MQTT or automation service is exposed")
    if 123 in ports:
        add("Time server", 25, "NTP port is open")
    if ports & {80, 443, 8443, 9443}:
        add("Managed network appliance", 12, "Web management service is exposed")
    guessed = ((device or {}).get("device_role_guess") or {}).get("role")
    if guessed:
        add(str(guessed), 20, "Existing device-role classifier")
    if not scores:
        return {"role": "Client/endpoint", "confidence": "low", "evidence": []}
    role, score = max(scores.items(), key=lambda item: item[1])
    confidence = (
        "very-high" if score >= 80
        else "high" if score >= 55
        else "medium" if score >= 30
        else "low"
    )
    return {
        "role": role,
        "confidence": confidence,
        "score": min(100, score),
        "evidence": [item for item in evidence if item["role"] == role],
        "default_gateways": gateways,
    }


def passive_facts(device, *, relationships=None, passive_summary=None, now=None):
    device = dict(device or {})
    now = float(now or time.time())
    facts = []
    fields = (
        ("identity.ipv4", "IPv4 address", device.get("ip"), "Inventory", "high", "address"),
        ("identity.mac", "MAC address", device.get("mac") or device.get("address"), "Inventory", "high", "address"),
        ("identity.manufacturer", "Manufacturer", device.get("manufacturer"), "OUI/inventory", "medium", "identity"),
        ("identity.model", "Model", device.get("model") or device.get("model_name"), "Discovery/model profile", "high", "identity"),
        ("identity.hardware", "Hardware revision", device.get("hardware_revision"), "Discovery/model profile", "high", "lifecycle"),
        ("identity.firmware", "Firmware", device.get("firmware") or device.get("firmware_version"), "Discovery/model profile", "high", "lifecycle"),
    )
    for item_key, label, value, source, confidence, category in fields:
        if value not in (None, "", "Unknown"):
            facts.append(fact(item_key, label, value, source, confidence, category=category))
    names = []
    for field_name in ("hostname", "name", "display_name", "detected_display_name"):
        if device.get(field_name):
            names.append(str(device[field_name]))
    names.extend(
        str(item.get("name"))
        for item in device.get("observed_names") or []
        if isinstance(item, dict) and item.get("name")
    )
    if names:
        facts.append(fact(
            "identity.names",
            "Observed names",
            sorted(set(names))[:16],
            "Inventory/DNS/DHCP",
            "high",
            category="identity",
        ))
    ipv6 = _ipv6_addresses(device)
    if ipv6:
        facts.append(fact(
            "identity.ipv6",
            "IPv6 addresses",
            ipv6,
            "Inventory/neighbor discovery",
            "high",
            category="address",
        ))
    if device.get("likely_randomized_mac"):
        facts.append(fact(
            "identity.private_mac",
            "Private/randomized MAC",
            True,
            "MAC bit analysis",
            "high",
            category="limitation",
        ))
    if device.get("interfaces"):
        facts.append(fact(
            "network.interfaces",
            "Observed interfaces",
            device["interfaces"],
            "Inventory",
            "high",
            category="network",
        ))
    if device.get("sources"):
        facts.append(fact(
            "network.discovery_sources",
            "Discovery sources",
            device["sources"],
            "Inventory",
            "high",
            category="network",
        ))
    open_ports = _open_ports(device)
    facts.append(fact(
        "services.open_port_count",
        "Saved open-port count",
        len(open_ports),
        "Saved service profile",
        "high",
        category="services",
    ))
    if open_ports:
        facts.append(fact(
            "services.open_ports",
            "Saved open ports",
            open_ports,
            "Saved service profile",
            "high",
            category="services",
        ))
    first_seen = device.get("first_seen")
    last_seen = device.get("last_seen")
    if first_seen:
        facts.append(fact(
            "stability.first_seen",
            "First observed",
            float(first_seen),
            "Inventory timeline",
            "high",
            category="stability",
        ))
    if last_seen:
        facts.append(fact(
            "stability.last_seen",
            "Last observed",
            float(last_seen),
            "Inventory timeline",
            "high",
            category="stability",
        ))
    if first_seen and last_seen and last_seen >= first_seen:
        facts.append(fact(
            "stability.observation_window_seconds",
            "Observed over at least",
            int(last_seen - first_seen),
            "Inventory timeline; not device uptime",
            "low",
            category="uptime",
        ))
    role = infer_network_role(device)
    facts.append(fact(
        "network.inferred_role",
        "Inferred network role",
        role,
        "Role evidence",
        role["confidence"],
        category="network",
    ))
    if relationships:
        facts.append(fact(
            "network.relationship_counts",
            "Known relationships",
            {
                "nodes": len((relationships or {}).get("nodes") or []),
                "links": len((relationships or {}).get("links") or []),
            },
            "Relationship map",
            "medium",
            category="relationships",
        ))
    summaries = passive_summary or {}
    if isinstance(summaries, dict):
        target_ip = str(device.get("ip") or "")
        target_mac = str(device.get("mac") or "").casefold()
        matches = []
        collection = (
            summaries.values()
            if summaries and "interface" not in summaries
            else [summaries]
        )
        for summary in collection:
            if not isinstance(summary, dict):
                continue
            states = (
                ("active", summary.get("active_devices")),
                ("quiet", summary.get("recently_disappeared")),
            )
            for state, items in states:
                for item in items or []:
                    if (
                        str(item.get("ip") or "") == target_ip
                        or str(item.get("mac") or "").casefold() == target_mac
                    ):
                        matches.append({
                            "interface": summary.get("interface"),
                            "state": state,
                            "seen_count": item.get("seen_count"),
                            "first_seen": item.get("first_seen"),
                            "last_seen": item.get("last_seen"),
                        })
        if matches:
            facts.append(fact(
                "behaviour.passive_presence",
                "Passive presence",
                matches,
                "Passive observation analytics",
                "medium",
                category="behaviour",
            ))
    return facts[:_MAX_FACTS]


def _ssh_banner(host, port):
    try:
        with socket.create_connection((host, int(port)), timeout=2) as sock:
            sock.settimeout(2)
            return _clean(sock.recv(512).decode("latin-1", errors="ignore"), 500)
    except OSError:
        return ""


def _ssh_host_keys(host, port):
    tool = shutil.which("ssh-keyscan")
    if not tool:
        return {"available": False, "keys": []}
    try:
        result = subprocess.run(
            [tool, "-T", "3", "-p", str(port), host],
            capture_output=True,
            text=True,
            timeout=6,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": True, "error": _clean(exc), "keys": []}
    keys = []
    for line in (result.stdout or "").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            raw = base64.b64decode(parts[2] + "===")
            fingerprint = base64.b64encode(hashlib.sha256(raw).digest()).decode().rstrip("=")
        except (ValueError, TypeError):
            fingerprint = ""
        keys.append({"type": parts[1], "sha256": fingerprint})
    return {"available": True, "keys": keys[:12], "returncode": result.returncode}


def _tls_posture(host, port):
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with socket.create_connection((host, int(port)), timeout=3) as raw:
            with context.wrap_socket(raw, server_hostname=host) as wrapped:
                cert_der = wrapped.getpeercert(binary_form=True) or b""
                cipher = wrapped.cipher()
                return {
                    "protocol": wrapped.version(),
                    "cipher": cipher[0] if cipher else None,
                    "cipher_bits": cipher[2] if cipher else None,
                    "certificate_sha256": hashlib.sha256(cert_der).hexdigest() if cert_der else None,
                    "compression": wrapped.compression(),
                    "alpn": wrapped.selected_alpn_protocol(),
                }
    except (OSError, ssl.SSLError, ValueError) as exc:
        return {"error": _clean(exc, 500)}


def _nmap_script(host, port, scripts):
    tool = shutil.which("nmap")
    if not tool:
        return {"available": False, "message": "nmap is not installed"}
    try:
        result = subprocess.run(
            [
                tool,
                "-Pn",
                "-p",
                str(port),
                "--script",
                ",".join(scripts),
                "--host-timeout",
                "20s",
                host,
            ],
            capture_output=True,
            text=True,
            timeout=24,
            check=False,
        )
        return {
            "available": True,
            "returncode": result.returncode,
            "output": _clean(result.stdout or result.stderr, 8000),
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": True, "error": _clean(exc)}


def _ntp_probe(host, port=123):
    packet = b"\x1b" + 47 * b"\0"
    started = time.time()
    try:
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        with socket.socket(family, socket.SOCK_DGRAM) as sock:
            sock.settimeout(2)
            sock.sendto(packet, (host, int(port)))
            data, _ = sock.recvfrom(512)
        elapsed_ms = round((time.time() - started) * 1000, 2)
        if len(data) < 48:
            return {"error": "Short NTP response", "response_bytes": len(data)}
        words = struct.unpack("!12I", data[:48])
        seconds = words[10] - 2208988800
        fraction = words[11] / 2**32
        remote_time = seconds + fraction
        return {
            "stratum": data[1],
            "version": (data[0] >> 3) & 7,
            "mode": data[0] & 7,
            "remote_unix_time": remote_time,
            "clock_offset_seconds": round(remote_time - time.time(), 3),
            "round_trip_ms": elapsed_ms,
        }
    except OSError as exc:
        return {"error": _clean(exc)}


def _dns_version_probe(host, port=53):
    transaction = 0x4D52
    header = struct.pack("!HHHHHH", transaction, 0x0100, 1, 0, 0, 0)
    name = (
        b"".join(
            bytes([len(part)]) + part.encode("ascii")
            for part in "version.bind".split(".")
        )
        + b"\0"
    )
    packet = header + name + struct.pack("!HH", 16, 3)
    try:
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        with socket.socket(family, socket.SOCK_DGRAM) as sock:
            sock.settimeout(2)
            sock.sendto(packet, (host, int(port)))
            data, _ = sock.recvfrom(2048)
        if len(data) < 12:
            return {"error": "Short DNS response"}
        response_id, flags, qd, an, ns, ar = struct.unpack("!HHHHHH", data[:12])
        printable = re.findall(rb"[ -~]{4,}", data[12:])
        return {
            "responded": response_id == transaction,
            "rcode": flags & 0x000F,
            "authoritative": bool(flags & 0x0400),
            "recursive_available": bool(flags & 0x0080),
            "answers": an,
            "printable_hints": [
                item.decode("latin-1", errors="ignore")[:160]
                for item in printable[:6]
            ],
            "counts": {"questions": qd, "authority": ns, "additional": ar},
        }
    except OSError as exc:
        return {"error": _clean(exc)}


def _ipv6_exposure(device, ports):
    results = []
    for address in _ipv6_addresses(device)[:4]:
        for port in list(ports)[:12]:
            try:
                with socket.create_connection((address, int(port)), timeout=0.75):
                    results.append({
                        "address": address,
                        "port": int(port),
                        "reachable": True,
                    })
            except OSError:
                continue
    return results


def safe_facts(device, host, *, base_fingerprints=None):
    device = dict(device or {})
    host = str(host or "").strip()
    if not host:
        raise ValueError("A host is required")
    observed = []
    safe = device_identification.supplement_service_probes(
        device,
        host,
        base_fingerprints=base_fingerprints,
    )
    for finding in safe.get("services") or []:
        port = finding.get("port")
        for name in ("banner", "http", "tls", "rtsp", "mqtt", "netbios"):
            value = finding.get(name)
            if value not in (None, "", [], {}):
                observed.append(fact(
                    f"service.{port}.{name}",
                    f"{name.upper()} evidence on {port}/tcp",
                    value,
                    "Bounded service negotiation",
                    "high" if name in {"tls", "rtsp", "mqtt", "netbios"} else "medium",
                    category="protocol",
                ))
    for index, description in enumerate(safe.get("upnp") or []):
        if description:
            observed.append(fact(
                f"discovery.upnp.{index}",
                "UPnP device description",
                description,
                "Same-device UPnP description",
                "high",
                category="identity",
                sensitivity=(
                    "sensitive" if description.get("serial_number") else "internal"
                ),
            ))
    details = device.get("open_port_details") or []
    for detail in details[:_MAX_PORTS]:
        try:
            port = int(detail.get("port"))
        except (TypeError, ValueError):
            continue
        service = str(detail.get("service") or "").casefold()
        if port == 22 or "ssh" in service:
            banner = _ssh_banner(host, port)
            if banner:
                observed.append(fact(
                    "protocol.ssh.banner",
                    "SSH banner",
                    banner,
                    f"SSH {port}/tcp",
                    "high",
                    category="ssh",
                ))
            keys = _ssh_host_keys(host, port)
            observed.append(fact(
                "protocol.ssh.host_keys",
                "SSH host keys",
                keys,
                f"ssh-keyscan {port}/tcp",
                "high" if keys.get("keys") else "low",
                category="ssh",
                sensitivity="sensitive",
            ))
            algos = _nmap_script(
                host,
                port,
                ["ssh2-enum-algos", "ssh-hostkey"],
            )
            observed.append(fact(
                "protocol.ssh.algorithms",
                "SSH algorithms and host keys",
                algos,
                "Nmap safe SSH scripts",
                "high" if algos.get("output") else "low",
                category="ssh",
                sensitivity="sensitive",
            ))
        if (
            port in {443, 465, 636, 853, 993, 995, 8443, 8883, 9443}
            or any(word in service for word in ("https", "ssl", "tls"))
        ):
            posture = _tls_posture(host, port)
            observed.append(fact(
                f"protocol.tls.{port}",
                f"TLS posture on {port}/tcp",
                posture,
                "TLS handshake",
                "high" if not posture.get("error") else "low",
                category="tls",
                sensitivity="sensitive",
            ))
    ports = _open_ports(device)
    if 445 in ports or 139 in ports:
        smb_port = 445 if 445 in ports else 139
        smb = _nmap_script(
            host,
            smb_port,
            ["smb-protocols", "smb2-security-mode", "smb2-capabilities"],
        )
        observed.append(fact(
            "protocol.smb.capabilities",
            "SMB capabilities",
            smb,
            "Nmap safe SMB negotiation",
            "high" if smb.get("output") else "low",
            category="smb",
            sensitivity="sensitive",
        ))
    if 123 in ports:
        ntp = _ntp_probe(host)
        observed.append(fact(
            "protocol.ntp",
            "NTP response and clock offset",
            ntp,
            "NTP client query",
            "high" if not ntp.get("error") else "low",
            category="time",
        ))
    if 53 in ports:
        dns = _dns_version_probe(host)
        observed.append(fact(
            "protocol.dns",
            "DNS server behaviour",
            dns,
            "CHAOS TXT version.bind query",
            "medium" if not dns.get("error") else "low",
            category="dns",
        ))
    ipv6 = _ipv6_exposure(device, ports)
    if _ipv6_addresses(device):
        observed.append(fact(
            "network.ipv6_exposure",
            "Known services reachable over IPv6",
            ipv6,
            "Bounded TCP connection checks",
            "high" if ipv6 else "medium",
            category="ipv6",
        ))
    return observed[:_MAX_FACTS]


def _parse_snmp_uptime(output):
    text = str(output or "")
    match = re.search(
        r"(?:sysUpTime|1\.3\.6\.1\.2\.1\.1\.3\.0).*?"
        r"(?:Timeticks:\s*\((\d+)\)|INTEGER:\s*(\d+))",
        text,
        re.I,
    )
    if not match:
        return None
    ticks = int(match.group(1) or match.group(2))
    return {"timeticks": ticks, "seconds": round(ticks / 100, 2)}


def deep_facts(device, host, *, authorized=False, snmp_community=None):
    ports = _open_ports(device)
    deep = device_identification.deep_device_probe(
        host,
        ports,
        authorized=authorized,
        snmp_community=snmp_community,
    )
    observed = []
    nmap = deep.get("nmap") or {}
    observed.append(fact(
        "deep.nmap",
        "Nmap OS and service identification",
        nmap,
        "Authorized bounded Nmap",
        "high" if nmap.get("output") else "low",
        category="deep",
        sensitivity="sensitive",
    ))
    snmp = deep.get("snmp") or {}
    observed.append(fact(
        "deep.snmp",
        "SNMP system information",
        snmp,
        "Authorized read-only SNMP",
        "very-high" if snmp.get("output") else "low",
        category="deep",
        sensitivity="sensitive",
    ))
    uptime = _parse_snmp_uptime(snmp.get("output"))
    if uptime:
        observed.append(fact(
            "uptime.snmp",
            "Device uptime",
            uptime,
            "SNMP sysUpTime",
            "very-high",
            category="uptime",
        ))
    return observed


def _baseline_map(baseline):
    if isinstance(baseline, dict):
        items = baseline.get("facts") or []
    else:
        items = baseline or []
    return {
        str(item.get("key")): item
        for item in items
        if isinstance(item, dict) and item.get("key")
    }


def merge_facts(existing, observed, *, baseline=None, now=None):
    now = float(now or time.time())
    current = {
        str(item.get("key")): dict(item)
        for item in existing or []
        if isinstance(item, dict) and item.get("key")
    }
    baseline_items = _baseline_map(baseline)
    for raw in observed or []:
        item = dict(raw)
        item_key = str(item.get("key") or "").strip()
        if not item_key:
            continue
        previous = current.get(item_key) or {}
        value_text = _value_text(item.get("value"))
        item["value_text"] = value_text
        item["first_seen"] = previous.get(
            "first_seen",
            item.get("first_seen", item.get("observed_at", now)),
        )
        item["last_seen"] = item.get(
            "last_seen",
            item.get("observed_at", now),
        )
        if previous and previous.get("value_text") != value_text:
            item["previous_value"] = previous.get("value")
            item["changed_at"] = now
        baseline_item = baseline_items.get(item_key)
        item["changed_since_baseline"] = bool(
            baseline_item
            and _value_text(baseline_item.get("value")) != value_text
        )
        current[item_key] = item
    return sorted(
        current.values(),
        key=lambda item: (item.get("category", ""), item.get("label", "")),
    )[:_MAX_FACTS]


def apply_fact_run(device, facts, *, mode, actor="unknown", now=None):
    now = float(now or time.time())
    updated = copy.deepcopy(device or {})
    updated["host_facts"] = merge_facts(
        updated.get("host_facts") or [],
        facts,
        baseline=updated.get("host_fact_baseline"),
        now=now,
    )
    runs = list(updated.get("host_fact_runs") or [])
    runs.insert(0, {
        "mode": _clean(mode, 32),
        "actor": _clean(actor, 120),
        "timestamp": now,
        "fact_count": len(facts or []),
        "changed_count": len([
            item
            for item in updated["host_facts"]
            if item.get("changed_since_baseline")
        ]),
    })
    updated["host_fact_runs"] = runs[:30]
    updated["host_facts_updated_at"] = now
    return updated


def save_baseline(device, *, actor="unknown", now=None):
    now = float(now or time.time())
    updated = copy.deepcopy(device or {})
    updated["host_fact_baseline"] = {
        "saved_at": now,
        "saved_by": _clean(actor, 120),
        "facts": copy.deepcopy(updated.get("host_facts") or []),
    }
    updated["host_facts"] = merge_facts(
        [],
        updated.get("host_facts") or [],
        baseline=updated["host_fact_baseline"],
        now=now,
    )
    return updated


def capabilities():
    return {
        "nmap": bool(shutil.which("nmap")),
        "ssh_keyscan": bool(shutil.which("ssh-keyscan")),
        "snmpwalk": bool(shutil.which("snmpwalk")),
        "safe_protocols": [
            "HTTP",
            "TLS",
            "SSH",
            "SMB",
            "IPP",
            "NTP",
            "DNS",
            "RTSP",
            "MQTT",
            "UPnP",
        ],
        "credential_policy": (
            "Only environment-variable references are persisted; secret values "
            "are never written to inventory or credential files."
        ),
    }


def load_credential_references(path):
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return []
    items = payload.get("profiles") if isinstance(payload, dict) else []
    return [dict(item) for item in items or [] if isinstance(item, dict)][:100]


def save_credential_reference(
    path,
    *,
    name,
    kind,
    secret_env,
    username="",
    notes="",
    actor="unknown",
):
    name = _clean(name, 160)
    kind = _clean(kind, 40).casefold()
    secret_env = _clean(secret_env, 128)
    if not name:
        raise ValueError("Credential profile name is required")
    if kind not in _CREDENTIAL_KINDS:
        raise ValueError("Credential type is not supported")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", secret_env):
        raise ValueError("Secret environment variable name is invalid")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    profiles = load_credential_references(path)
    profile = {
        "id": uuid.uuid4().hex,
        "name": name,
        "kind": kind,
        "username": _clean(username, 160),
        "secret_env": secret_env,
        "notes": _clean(notes, 1000),
        "created_at": time.time(),
        "created_by": _clean(actor, 120),
    }
    profiles.append(profile)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            {
                "schema": "mobile-router-host-credential-references-v1",
                "profiles": profiles,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    temporary.replace(path)
    return profile


def credential_reference(profiles, profile_id):
    for item in profiles or []:
        if str(item.get("id")) == str(profile_id):
            return dict(item)
    return None


def resolve_secret(profile, environ=None):
    if not profile:
        return ""
    environ = os.environ if environ is None else environ
    return str(environ.get(str(profile.get("secret_env") or ""), ""))
