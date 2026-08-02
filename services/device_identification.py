"""Explainable device identification from passive, service, and deep-probe evidence."""

from __future__ import annotations

import hashlib
import ipaddress
import re
import shutil
import socket
import ssl
import subprocess
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from urllib.request import Request, urlopen

_MAX_TEXT = 500
_MAX_UPNP_BYTES = 262144
_MAX_PROBE_PORTS = 24


FINGERPRINT_RULES = (
    {
        "label": "Synology NAS",
        "category": "NAS/file server",
        "terms": ("synology", "diskstation", "dsm"),
        "vendors": ("synology",),
        "ports": (445, 5000, 5001),
    },
    {
        "label": "QNAP NAS",
        "category": "NAS/file server",
        "terms": ("qnap", "qts", "qumagie"),
        "vendors": ("qnap",),
        "ports": (445, 8080, 443),
    },
    {
        "label": "TrueNAS server",
        "category": "NAS/file server",
        "terms": ("truenas", "freenas", "ixsystems"),
        "vendors": ("ixsystems",),
        "ports": (80, 443, 445),
    },
    {
        "label": "UniFi network device",
        "category": "Network infrastructure",
        "terms": ("unifi", "ubiquiti", "ubnt"),
        "vendors": ("ubiquiti",),
        "ports": (3478, 8080, 8443),
    },
    {
        "label": "pfSense/Netgate gateway",
        "category": "Gateway/router",
        "terms": ("pfsense", "netgate"),
        "vendors": ("netgate",),
        "ports": (53, 80, 443),
    },
    {
        "label": "OpenWrt gateway",
        "category": "Gateway/router",
        "terms": ("openwrt", "luci"),
        "vendors": (),
        "ports": (22, 53, 80, 443),
    },
    {
        "label": "Home Assistant server",
        "category": "Home automation/IoT",
        "terms": ("home assistant", "homeassistant", "hassio"),
        "vendors": (),
        "ports": (8123,),
    },
    {
        "label": "ESPHome device",
        "category": "Home automation/IoT",
        "terms": ("esphome",),
        "vendors": ("espressif",),
        "ports": (6053,),
    },
    {
        "label": "Tasmota device",
        "category": "Home automation/IoT",
        "terms": ("tasmota",),
        "vendors": ("espressif",),
        "ports": (80, 1883),
    },
    {
        "label": "Philips Hue Bridge",
        "category": "Home automation/IoT",
        "terms": ("philips hue", "hue bridge", "signify"),
        "vendors": ("philips", "signify"),
        "ports": (80, 443),
    },
    {
        "label": "Chromecast/Google TV device",
        "category": "Media/TV device",
        "terms": ("chromecast", "google cast", "eureka_info"),
        "vendors": ("google",),
        "ports": (8008, 8009, 8443),
    },
    {
        "label": "Apple TV/HomePod",
        "category": "Media/TV device",
        "terms": ("apple tv", "homepod", "airplay", "raop"),
        "vendors": ("apple",),
        "ports": (7000, 7100, 49152),
    },
    {
        "label": "Roku media player",
        "category": "Media/TV device",
        "terms": ("roku", "ecp"),
        "vendors": ("roku",),
        "ports": (8060,),
    },
    {
        "label": "Network printer",
        "category": "Printer",
        "terms": ("printer", "ipp", "cups", "laserjet", "jetdirect"),
        "vendors": ("hewlett packard", "brother", "epson", "canon", "xerox"),
        "ports": (515, 631, 9100),
    },
    {
        "label": "IP camera/NVR",
        "category": "Camera/NVR",
        "terms": ("camera", "nvr", "rtsp", "onvif", "hikvision", "dahua"),
        "vendors": ("hikvision", "dahua"),
        "ports": (554, 8000, 8554),
    },
    {
        "label": "Windows host",
        "category": "Computer/server",
        "terms": ("microsoft", "windows", "smb", "rdp"),
        "vendors": ("microsoft",),
        "ports": (135, 139, 445, 3389),
    },
    {
        "label": "Linux/Unix host",
        "category": "Computer/server",
        "terms": ("openssh", "ubuntu", "debian", "linux", "freebsd"),
        "vendors": (),
        "ports": (22,),
    },
    {
        "label": "MQTT IoT endpoint",
        "category": "Home automation/IoT",
        "terms": ("mqtt", "mosquitto"),
        "vendors": (),
        "ports": (1883, 8883),
    },
    {
        "label": "Gateway/router",
        "category": "Gateway/router",
        "terms": ("gateway", "router", "internetgatewaydevice", "dnsmasq"),
        "vendors": (),
        "ports": (53, 67, 80, 443),
    },
)


def _bounded(value, limit=_MAX_TEXT):
    return str(value or "").strip()[:limit]


def _valid_host(host):
    value = str(host or "").strip().strip("[]")
    if not value or len(value) > 253:
        raise ValueError("A valid device host is required")
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        if not re.fullmatch(r"[A-Za-z0-9._-]+", value):
            raise ValueError("Device host contains unsupported characters")
        return value


def _service_metadata(device):
    items = []
    metadata = (device or {}).get("service_metadata")
    if isinstance(metadata, dict):
        items.append(metadata)
    for item in (device or {}).get("service_metadata_list") or []:
        if isinstance(item, dict):
            items.append(item)
    return items[:20]


def _same_device_url(url, host):
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    target = parsed.hostname.strip("[]").casefold()
    expected = str(host or "").strip("[]").casefold()
    if target == expected:
        return True
    try:
        expected_addresses = {item[4][0] for item in socket.getaddrinfo(expected, None)}
        target_addresses = {item[4][0] for item in socket.getaddrinfo(target, None)}
        return bool(expected_addresses & target_addresses)
    except OSError:
        return False


def _xml_text(root, name):
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] == name and element.text:
            return _bounded(element.text, 200)
    return None


def probe_upnp_descriptions(device, host, opener=urlopen):
    """Retrieve bounded same-device UPnP descriptions advertised by SSDP metadata."""
    host = _valid_host(host)
    urls = []
    for item in _service_metadata(device):
        for key in ("control_url", "location", "description_url"):
            value = item.get(key)
            if value and value not in urls:
                urls.append(value)
    results = []
    for url in urls[:4]:
        if not _same_device_url(url, host):
            results.append({"url": _bounded(url), "error": "Description URL did not resolve to this device"})
            continue
        try:
            request = Request(url, headers={"User-Agent": "MobileRouterLab/1.0"})
            with opener(request, timeout=3) as response:
                raw = response.read(_MAX_UPNP_BYTES + 1)
            if len(raw) > _MAX_UPNP_BYTES:
                raise ValueError("UPnP description exceeded the size limit")
            root = ET.fromstring(raw)
            result = {
                "url": url,
                "friendly_name": _xml_text(root, "friendlyName"),
                "manufacturer": _xml_text(root, "manufacturer"),
                "manufacturer_url": _xml_text(root, "manufacturerURL"),
                "model_description": _xml_text(root, "modelDescription"),
                "model_name": _xml_text(root, "modelName"),
                "model_number": _xml_text(root, "modelNumber"),
                "serial_number": _xml_text(root, "serialNumber"),
                "device_type": _xml_text(root, "deviceType"),
                "presentation_url": _xml_text(root, "presentationURL"),
            }
            results.append({key: value for key, value in result.items() if value})
        except (OSError, ValueError, ET.ParseError) as exc:
            results.append({"url": _bounded(url), "error": _bounded(exc)})
    return results


def _tls_probe(host, port):
    try:
        context = ssl._create_unverified_context()
        with socket.create_connection((host, int(port)), timeout=2) as raw:
            with context.wrap_socket(raw, server_hostname=host) as wrapped:
                cert = wrapped.getpeercert()
                cipher = wrapped.cipher()
        subject = dict(part[0] for part in cert.get("subject", []) if part)
        issuer = dict(part[0] for part in cert.get("issuer", []) if part)
        return {
            "subject_common_name": subject.get("commonName"),
            "issuer_common_name": issuer.get("commonName"),
            "dns_names": [value for key, value in cert.get("subjectAltName", []) if key.lower() == "dns"][:12],
            "not_before": cert.get("notBefore"),
            "not_after": cert.get("notAfter"),
            "cipher": cipher[0] if cipher else None,
        }
    except (OSError, ssl.SSLError, ValueError):
        return None


def _rtsp_probe(host, port):
    request = (
        f"OPTIONS rtsp://{host}:{port}/ RTSP/1.0\r\n"
        "CSeq: 1\r\n"
        "User-Agent: MobileRouterLab/1.0\r\n\r\n"
    ).encode("ascii", errors="ignore")
    try:
        with socket.create_connection((host, int(port)), timeout=2) as sock:
            sock.settimeout(2)
            sock.sendall(request)
            data = sock.recv(4096).decode("latin-1", errors="ignore")
        headers = {}
        lines = data.splitlines()
        for line in lines[1:]:
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = _bounded(value, 200)
        return {
            "status": _bounded(lines[0], 160) if lines else None,
            "server": headers.get("server"),
            "public": headers.get("public"),
        }
    except OSError as exc:
        return {"error": _bounded(exc)}


def _mqtt_probe(host, port, tls=False):
    client_id = b"mobile-router-identify"
    variable = b"\x00\x04MQTT\x04\x02\x00\x05" + bytes([0, len(client_id)]) + client_id
    packet = bytes([0x10, len(variable)]) + variable
    try:
        raw = socket.create_connection((host, int(port)), timeout=2)
        sock = raw
        if tls:
            sock = ssl._create_unverified_context().wrap_socket(raw, server_hostname=host)
        with sock:
            sock.settimeout(2)
            sock.sendall(packet)
            response = sock.recv(4)
        if len(response) >= 4 and response[0] == 0x20:
            return {
                "protocol": "MQTT",
                "session_present": bool(response[2] & 1),
                "return_code": int(response[3]),
                "accepted": response[3] == 0,
            }
        return {"protocol": "MQTT", "response_hex": response.hex()[:32]}
    except (OSError, ssl.SSLError) as exc:
        return {"error": _bounded(exc)}


def _netbios_probe(host):
    tool = shutil.which("nmblookup")
    if not tool:
        return {"available": False, "message": "nmblookup is not installed"}
    try:
        result = subprocess.run(
            [tool, "-A", host],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": True, "error": _bounded(exc)}
    names = []
    for line in (result.stdout or "").splitlines():
        match = re.match(r"\s*([^\s<]+)\s+<([0-9A-Fa-f]{2})>", line)
        if match:
            names.append({"name": match.group(1), "suffix": match.group(2).upper()})
    return {
        "available": True,
        "returncode": result.returncode,
        "names": names[:16],
        "message": _bounded(result.stderr or "") or None,
    }


def supplement_service_probes(device, host, base_fingerprints=None):
    """Add protocol-aware safe probes to existing saved-service fingerprints."""
    host = _valid_host(host)
    findings = [dict(item) for item in (base_fingerprints or [])]
    by_port = {int(item.get("port")): item for item in findings if item.get("port")}
    open_details = (device or {}).get("open_port_details") or []
    for detail in open_details[:_MAX_PROBE_PORTS]:
        try:
            port = int(detail.get("port"))
        except (TypeError, ValueError):
            continue
        service = str(detail.get("service") or "").casefold()
        finding = by_port.setdefault(port, {
            "port": port,
            "service": detail.get("service") or "Unknown",
            "confidence": "low",
            "notes": [],
        })
        if port in {443, 465, 636, 853, 993, 995, 8443, 8883, 9443} or any(
            word in service for word in ("https", "ssl", "tls")
        ):
            tls = _tls_probe(host, port)
            if tls:
                finding["tls"] = tls
                finding["confidence"] = "high"
        if port in {554, 8554} or "rtsp" in service:
            finding["rtsp"] = _rtsp_probe(host, port)
            if not finding["rtsp"].get("error"):
                finding["confidence"] = "high"
        if port in {1883, 8883} or "mqtt" in service:
            finding["mqtt"] = _mqtt_probe(host, port, tls=port == 8883)
            if not finding["mqtt"].get("error"):
                finding["confidence"] = "high"
        if port in {139, 445} or "smb" in service:
            finding["netbios"] = _netbios_probe(host)
            if finding["netbios"].get("names"):
                finding["confidence"] = "high"
    for port, finding in by_port.items():
        if port not in {int(item.get("port")) for item in findings if item.get("port")}:
            findings.append(finding)
    return {
        "services": findings,
        "upnp": probe_upnp_descriptions(device, host),
    }


def deep_device_probe(host, ports, *, authorized=False, snmp_community=None):
    """Run optional bounded Nmap/SNMP identification after explicit authorization."""
    if not authorized:
        raise ValueError("Confirm authorization before running deep device identification")
    host = _valid_host(host)
    cleaned_ports = []
    for value in ports or []:
        try:
            port = int(value)
        except (TypeError, ValueError):
            continue
        if 1 <= port <= 65535 and port not in cleaned_ports:
            cleaned_ports.append(port)
    cleaned_ports = cleaned_ports[:_MAX_PROBE_PORTS]
    result = {"authorized": True, "nmap": None, "snmp": None}
    nmap = shutil.which("nmap")
    if nmap:
        command = [nmap, "-Pn", "-O", "-sV", "--version-light", "--host-timeout", "30s"]
        if cleaned_ports:
            command.extend(["-p", ",".join(str(port) for port in cleaned_ports)])
        command.append(host)
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=35, check=False)
            result["nmap"] = {
                "available": True,
                "returncode": completed.returncode,
                "output": _bounded(completed.stdout or completed.stderr, 12000),
            }
        except (OSError, subprocess.TimeoutExpired) as exc:
            result["nmap"] = {"available": True, "error": _bounded(exc)}
    else:
        result["nmap"] = {"available": False, "message": "nmap is not installed"}
    community = str(snmp_community or "").strip()
    snmpwalk = shutil.which("snmpwalk")
    if community and snmpwalk:
        if len(community) > 128 or any(char in community for char in "\r\n\x00"):
            raise ValueError("SNMP community value is invalid")
        command = [snmpwalk, "-v2c", "-c", community, "-t", "2", "-r", "0", host, "1.3.6.1.2.1.1"]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=12, check=False)
            result["snmp"] = {
                "available": True,
                "returncode": completed.returncode,
                "output": _bounded(completed.stdout or completed.stderr, 8000),
            }
        except (OSError, subprocess.TimeoutExpired) as exc:
            result["snmp"] = {"available": True, "error": _bounded(exc)}
    elif community:
        result["snmp"] = {"available": False, "message": "snmpwalk is not installed"}
    else:
        result["snmp"] = {"available": bool(snmpwalk), "message": "No SNMP community supplied"}
    return result


def _flatten_values(value):
    values = []
    if isinstance(value, dict):
        for item in value.values():
            values.extend(_flatten_values(item))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            values.extend(_flatten_values(item))
    elif value not in (None, ""):
        values.append(_bounded(value, 300))
    return values


def _evidence(source, value, weight, category="identity"):
    return {
        "source": source,
        "value": _bounded(value, 300),
        "weight": int(weight),
        "category": category,
    }


def _confidence(score):
    if score >= 85:
        return "very high"
    if score >= 65:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _nmap_hints(deep):
    output = str(((deep or {}).get("nmap") or {}).get("output") or "")
    hints = []
    for pattern in (
        r"OS details:\s*(.+)",
        r"Running:\s*(.+)",
        r"Service Info:\s*(.+)",
        r"Aggressive OS guesses:\s*(.+)",
    ):
        match = re.search(pattern, output, re.I)
        if match:
            hints.append(_bounded(match.group(1), 240))
    return hints[:8]


def identify_device(
    device,
    *,
    reverse_name="",
    dhcp_name="",
    os_hint=None,
    safe_probes=None,
    deep_probe=None,
    passive_summary=None,
):
    """Return a ranked, explainable identity assessment and stable signature."""
    device = dict(device or {})
    evidence = []
    manufacturer = str(device.get("manufacturer") or "").strip()
    private_mac = bool(device.get("likely_randomized_mac"))
    if manufacturer and manufacturer.casefold() != "unknown" and not private_mac:
        evidence.append(_evidence("MAC vendor", manufacturer, 16, "vendor"))
    elif private_mac:
        evidence.append(_evidence("MAC address", "Locally administered/private MAC; OUI is not trusted", 3, "limitation"))
    names = []
    for field in ("hostname", "name", "display_name", "detected_display_name"):
        if device.get(field):
            names.append(str(device[field]))
    names.extend(str(item.get("name")) for item in device.get("observed_names", []) if item.get("name"))
    names.extend([reverse_name, dhcp_name])
    for name in dict.fromkeys(name for name in names if name):
        evidence.append(_evidence("Observed name", name, 14, "name"))
    open_ports = []
    for detail in device.get("open_port_details") or []:
        try:
            port = int(detail.get("port"))
        except (TypeError, ValueError):
            continue
        open_ports.append(port)
        text = " ".join(str(detail.get(key) or "") for key in ("service", "description", "http_title", "http_server"))
        if text.strip():
            evidence.append(_evidence(f"Service {port}/tcp", text, 10, "service"))
        else:
            evidence.append(_evidence("Open port", f"{port}/tcp", 3, "port"))
    safe_probes = safe_probes or {}
    for finding in safe_probes.get("services") or []:
        port = finding.get("port")
        for key in ("banner", "http", "tls", "rtsp", "mqtt", "netbios"):
            values = _flatten_values(finding.get(key))
            if values:
                evidence.append(_evidence(f"{key.upper()} probe {port}/tcp", "; ".join(values[:8]), 18, "probe"))
    for description in safe_probes.get("upnp") or []:
        values = _flatten_values(description)
        if values:
            evidence.append(_evidence("UPnP device description", "; ".join(values[:12]), 26, "probe"))
    os_data = os_hint or {}
    if os_data.get("hint") and str(os_data.get("hint")).casefold() != "unknown":
        evidence.append(_evidence("Passive OS hint", os_data.get("hint"), 8, "passive"))
    for hint in _nmap_hints(deep_probe):
        evidence.append(_evidence("Nmap OS/service identification", hint, 22, "deep"))
    snmp_output = str(((deep_probe or {}).get("snmp") or {}).get("output") or "")
    if snmp_output:
        evidence.append(_evidence("SNMP system description", snmp_output, 28, "deep"))
    passive_values = _flatten_values(passive_summary or {})
    if passive_values:
        evidence.append(_evidence("Passive behaviour", "; ".join(passive_values[:12]), 8, "passive"))

    searchable = " ".join(item["value"] for item in evidence).casefold()
    vendor_text = manufacturer.casefold()
    candidates = []
    for rule in FINGERPRINT_RULES:
        matched_terms = [term for term in rule["terms"] if term in searchable]
        matched_vendors = [term for term in rule["vendors"] if term in vendor_text]
        matched_ports = sorted(set(open_ports) & set(rule["ports"]))
        score = min(100, len(matched_terms) * 28 + len(matched_vendors) * 24 + len(matched_ports) * 9)
        if matched_terms and matched_ports:
            score = min(100, score + 12)
        if matched_vendors and matched_terms:
            score = min(100, score + 12)
        if score:
            reasons = []
            if matched_terms:
                reasons.append("terms: " + ", ".join(matched_terms[:4]))
            if matched_vendors:
                reasons.append("vendor: " + ", ".join(matched_vendors[:3]))
            if matched_ports:
                reasons.append("ports: " + ", ".join(str(port) for port in matched_ports[:6]))
            candidates.append({
                "label": rule["label"],
                "category": rule["category"],
                "score": score,
                "confidence": _confidence(score),
                "reasons": reasons,
            })
    candidates.sort(key=lambda item: (-item["score"], item["label"]))
    if candidates:
        best = candidates[0]
    else:
        fallback = device.get("network_role") or device.get("device_type") or "Unidentified network device"
        best = {"label": fallback, "category": fallback, "score": min(35, len(evidence) * 4), "confidence": "low", "reasons": ["No strong fingerprint rule matched"]}
        candidates = [best]
    signature_tokens = []
    for item in evidence:
        if item["category"] in {"name", "service", "probe", "deep"}:
            signature_tokens.append(f"{item['category']}:{item['value'].casefold()}")
    signature_tokens.extend(f"port:{port}" for port in sorted(set(open_ports)))
    if manufacturer and not private_mac:
        signature_tokens.append(f"vendor:{manufacturer.casefold()}")
    signature_tokens = sorted(set(signature_tokens))[:80]
    digest = hashlib.sha256("\n".join(signature_tokens).encode("utf-8")).hexdigest() if signature_tokens else None
    limitations = []
    if private_mac:
        limitations.append("The MAC address is private/randomised, so vendor correlation was down-weighted.")
    if not open_ports:
        limitations.append("No saved open ports were available.")
    if not safe_probes:
        limitations.append("No active service probes were included in this assessment.")
    if best["score"] < 65:
        limitations.append("The result is a hypothesis and should be confirmed with another independent signal.")
    return {
        "likely_device": best["label"],
        "category": best["category"],
        "confidence": best["confidence"],
        "score": best["score"],
        "candidates": candidates[:5],
        "evidence": sorted(evidence, key=lambda item: (-item["weight"], item["source"]))[:40],
        "limitations": limitations,
        "identity_signature": digest,
        "signature_tokens": signature_tokens,
        "assessed_at": time.time(),
    }
