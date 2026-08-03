"""VLAN inventory, routed investigations, policy tests, and probe ingestion.

The module intentionally keeps network access outside the persistence helpers so
routes can apply application-level authorisation and bounded execution policies.
"""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import ssl
import time
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
import uuid


SCHEMA_VERSION = 1
MAX_INVESTIGATION_HOSTS = 1024
MAX_INVESTIGATION_PORTS = 16
MAX_IMPORT_BYTES = 2 * 1024 * 1024
MAX_PROBE_BYTES = 1024 * 1024
PROBE_CLOCK_SKEW_SECONDS = 300
ALLOWED_PROBE_MODES = {"local", "routed", "infrastructure", "remote-agent"}
ALLOWED_EXPECTATIONS = {"allow", "block"}
ALLOWED_PROTOCOLS = {"tcp", "udp", "icmp"}
_ENV_REF_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")
_NONCE_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


@contextmanager
def _connection(database_path):
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialise_database(database_path):
    with _connection(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS vlan_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS vlans (
                id TEXT PRIMARY KEY,
                tag INTEGER,
                name TEXT NOT NULL,
                subnet TEXT NOT NULL UNIQUE,
                gateway TEXT,
                interface_name TEXT,
                router_name TEXT,
                description TEXT,
                probe_mode TEXT NOT NULL DEFAULT 'routed',
                source_type TEXT NOT NULL DEFAULT 'manual',
                source_ip TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS investigations (
                id TEXT PRIMARY KEY,
                vlan_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                route_json TEXT NOT NULL DEFAULT '{}',
                hosts_json TEXT NOT NULL DEFAULT '[]',
                summary_json TEXT NOT NULL DEFAULT '{}',
                started_at REAL NOT NULL,
                finished_at REAL,
                FOREIGN KEY(vlan_id) REFERENCES vlans(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS segmentation_rules (
                id TEXT PRIMARY KEY,
                source_vlan_id TEXT NOT NULL,
                destination_vlan_id TEXT,
                destination TEXT NOT NULL,
                protocol TEXT NOT NULL,
                port INTEGER,
                expectation TEXT NOT NULL,
                description TEXT,
                source_probe_id TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY(source_vlan_id) REFERENCES vlans(id) ON DELETE CASCADE,
                FOREIGN KEY(destination_vlan_id) REFERENCES vlans(id) ON DELETE SET NULL
            );
            CREATE TABLE IF NOT EXISTS segmentation_results (
                id TEXT PRIMARY KEY,
                rule_id TEXT NOT NULL,
                observed TEXT NOT NULL,
                mismatch INTEGER NOT NULL,
                source TEXT NOT NULL,
                latency_ms REAL,
                detail TEXT,
                checked_at REAL NOT NULL,
                FOREIGN KEY(rule_id) REFERENCES segmentation_rules(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS integrations (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                base_url TEXT,
                token_env TEXT,
                header_name TEXT NOT NULL DEFAULT 'Authorization',
                token_prefix TEXT NOT NULL DEFAULT 'Bearer',
                verify_tls INTEGER NOT NULL DEFAULT 1,
                config_json TEXT NOT NULL DEFAULT '{}',
                last_sync REAL,
                last_status TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS remote_probes (
                id TEXT PRIMARY KEY,
                vlan_id TEXT NOT NULL,
                name TEXT NOT NULL,
                secret_env TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'never-seen',
                last_seen REAL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY(vlan_id) REFERENCES vlans(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS probe_nonces (
                probe_id TEXT NOT NULL,
                nonce TEXT NOT NULL,
                seen_at REAL NOT NULL,
                PRIMARY KEY(probe_id, nonce),
                FOREIGN KEY(probe_id) REFERENCES remote_probes(id) ON DELETE CASCADE
            );
            """
        )
        connection.execute(
            "INSERT OR REPLACE INTO vlan_meta(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )


def _row_dict(row):
    return dict(row) if row is not None else None


def _clean_text(value, maximum=255):
    return str(value or "").strip()[:maximum]


def _json_load(value, default):
    try:
        return json.loads(value or "")
    except (TypeError, ValueError):
        return default


def _normalise_network(value):
    try:
        network = ipaddress.ip_network(str(value or "").strip(), strict=False)
    except ValueError as exc:
        raise ValueError("Subnet must be a valid CIDR, for example 192.168.20.0/24") from exc
    if network.version != 4:
        raise ValueError("The first VLAN investigation release supports IPv4 subnets only")
    return network


def _normalise_ip(value, label="Address"):
    if not value:
        return ""
    try:
        address = ipaddress.ip_address(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"{label} must be a valid IP address") from exc
    if address.version != 4:
        raise ValueError(f"{label} must be IPv4 in this release")
    return str(address)


def _usable_host_count(network):
    if network.prefixlen >= 31:
        return network.num_addresses
    return max(0, network.num_addresses - 2)


def validate_vlan_payload(payload, existing=(), vlan_id=None):
    payload = payload or {}
    name = _clean_text(payload.get("name"), 120)
    if not name:
        raise ValueError("VLAN name is required")
    network = _normalise_network(payload.get("subnet"))
    raw_tag = str(payload.get("tag") or "").strip()
    tag = None
    if raw_tag:
        try:
            tag = int(raw_tag)
        except ValueError as exc:
            raise ValueError("VLAN tag must be an integer from 1 to 4094") from exc
        if not 1 <= tag <= 4094:
            raise ValueError("VLAN tag must be from 1 to 4094")

    gateway = _normalise_ip(payload.get("gateway"), "Gateway")
    source_ip = _normalise_ip(payload.get("source_ip"), "Source address")
    for value, label in ((gateway, "Gateway"), (source_ip, "Source address")):
        if value and ipaddress.ip_address(value) not in network:
            raise ValueError(f"{label} must be inside the VLAN subnet")

    probe_mode = _clean_text(payload.get("probe_mode") or "routed", 40)
    if probe_mode not in ALLOWED_PROBE_MODES:
        raise ValueError("Unknown VLAN probe mode")

    for item in existing:
        if str(item.get("id")) == str(vlan_id or ""):
            continue
        other = _normalise_network(item.get("subnet"))
        if network.overlaps(other):
            raise ValueError(
                f"Subnet {network} overlaps existing VLAN {item.get('name') or other} ({other})"
            )
        if tag is not None and item.get("tag") is not None and int(item["tag"]) == tag:
            raise ValueError(f"VLAN tag {tag} is already assigned to {item.get('name')}")

    return {
        "tag": tag,
        "name": name,
        "subnet": str(network),
        "gateway": gateway,
        "interface_name": _clean_text(payload.get("interface_name") or payload.get("interface"), 120),
        "router_name": _clean_text(payload.get("router_name") or payload.get("router"), 120),
        "description": _clean_text(payload.get("description"), 1000),
        "probe_mode": probe_mode,
        "source_type": _clean_text(payload.get("source_type") or "manual", 80),
        "source_ip": source_ip,
    }


def _vlan_label(vlan):
    if vlan.get("tag") is not None:
        return f"VLAN {vlan['tag']} · {vlan['name']}"
    return f"{vlan['name']} · {vlan['subnet']}"


def _decorate_vlan(vlan):
    if not vlan:
        return None
    item = dict(vlan)
    item["label"] = _vlan_label(item)
    item["usable_hosts"] = _usable_host_count(_normalise_network(item["subnet"]))
    return item


def list_vlans(database_path):
    initialise_database(database_path)
    with _connection(database_path) as connection:
        rows = connection.execute(
            "SELECT * FROM vlans ORDER BY CASE WHEN tag IS NULL THEN 1 ELSE 0 END, tag, name"
        ).fetchall()
    return [_decorate_vlan(_row_dict(row)) for row in rows]


def get_vlan(database_path, vlan_id):
    initialise_database(database_path)
    with _connection(database_path) as connection:
        row = connection.execute("SELECT * FROM vlans WHERE id = ?", (str(vlan_id),)).fetchone()
    return _decorate_vlan(_row_dict(row))


def save_vlan(database_path, payload, vlan_id=None, now=None):
    now = float(now or time.time())
    existing = list_vlans(database_path)
    item = validate_vlan_payload(payload, existing, vlan_id=vlan_id)
    item_id = str(vlan_id or uuid.uuid4())
    with _connection(database_path) as connection:
        if vlan_id and not connection.execute("SELECT 1 FROM vlans WHERE id = ?", (item_id,)).fetchone():
            raise ValueError("VLAN definition was not found")
        created = connection.execute(
            "SELECT created_at FROM vlans WHERE id = ?", (item_id,)
        ).fetchone()
        connection.execute(
            """
            INSERT OR REPLACE INTO vlans(
                id, tag, name, subnet, gateway, interface_name, router_name,
                description, probe_mode, source_type, source_ip, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_id, item["tag"], item["name"], item["subnet"], item["gateway"],
                item["interface_name"], item["router_name"], item["description"],
                item["probe_mode"], item["source_type"], item["source_ip"],
                float(created["created_at"]) if created else now, now,
            ),
        )
    return get_vlan(database_path, item_id)


def delete_vlan(database_path, vlan_id):
    initialise_database(database_path)
    with _connection(database_path) as connection:
        cursor = connection.execute("DELETE FROM vlans WHERE id = ?", (str(vlan_id),))
        return cursor.rowcount > 0


def vlan_for_ip(database_path, address):
    try:
        ip = ipaddress.ip_address(str(address or "").strip())
    except ValueError:
        return None
    candidates = []
    for vlan in list_vlans(database_path):
        network = _normalise_network(vlan["subnet"])
        if ip in network:
            candidates.append((network.prefixlen, vlan))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def decorate_device(database_path, device):
    item = dict(device or {})
    vlan = None
    explicit_id = item.get("vlan_id")
    if explicit_id:
        vlan = get_vlan(database_path, explicit_id)
    if vlan is None and item.get("ip"):
        vlan = vlan_for_ip(database_path, item.get("ip"))
    if not vlan:
        return item

    source = "explicit" if explicit_id and str(explicit_id) == str(vlan["id"]) else "subnet-match"
    item.update(
        vlan_id=vlan["id"],
        vlan_tag=vlan.get("tag"),
        vlan_name=vlan["name"],
        vlan_subnet=vlan["subnet"],
        vlan_gateway=vlan.get("gateway"),
        vlan_interface=vlan.get("interface_name"),
        vlan_label=vlan["label"],
        vlan_assignment_source=source,
        vlan_confidence="high",
    )
    return item


def decorate_devices(database_path, devices):
    return [decorate_device(database_path, item) for item in devices]


def bounded_investigation_network(cidr, maximum=MAX_INVESTIGATION_HOSTS):
    network = _normalise_network(cidr)
    count = _usable_host_count(network)
    if count > int(maximum):
        raise ValueError(
            f"Investigation covers {count} usable addresses; the safety limit is {maximum}"
        )
    return network


def parse_ports(value, maximum=MAX_INVESTIGATION_PORTS):
    if value is None or value == "":
        return []
    source = value if isinstance(value, (list, tuple, set)) else str(value).split(",")
    ports = []
    for raw in source:
        try:
            port = int(str(raw).strip())
        except ValueError as exc:
            raise ValueError("Selected ports must be comma-separated integers") from exc
        if not 1 <= port <= 65535:
            raise ValueError("Selected ports must be from 1 to 65535")
        if port not in ports:
            ports.append(port)
    if len(ports) > int(maximum):
        raise ValueError(f"At most {maximum} selected ports may be investigated")
    return sorted(ports)


def safe_tcp_check(host, ports, timeout=0.35, source_ip=None):
    results = []
    for port in parse_ports(ports):
        started = time.monotonic()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(float(timeout))
        try:
            if source_ip:
                sock.bind((str(source_ip), 0))
            result = sock.connect_ex((str(host), int(port)))
            is_open = result == 0
            detail = "connection accepted" if is_open else f"connection result {result}"
        except OSError as exc:
            is_open = False
            detail = str(exc)
        finally:
            sock.close()
        results.append(
            {
                "port": port,
                "open": is_open,
                "latency_ms": round((time.monotonic() - started) * 1000, 2),
                "detail": detail,
            }
        )
    return results


def save_investigation(database_path, vlan_id, mode, status, route, hosts, summary, started_at=None, finished_at=None, investigation_id=None):
    if not get_vlan(database_path, vlan_id):
        raise ValueError("VLAN definition was not found")
    item_id = str(investigation_id or uuid.uuid4())
    started_at = float(started_at or time.time())
    finished_at = float(finished_at or time.time())
    with _connection(database_path) as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO investigations(
                id, vlan_id, mode, status, route_json, hosts_json, summary_json,
                started_at, finished_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_id, str(vlan_id), _clean_text(mode, 40), _clean_text(status, 40),
                json.dumps(route or {}, sort_keys=True),
                json.dumps(hosts or [], sort_keys=True),
                json.dumps(summary or {}, sort_keys=True),
                started_at, finished_at,
            ),
        )
    return get_investigation(database_path, item_id)


def get_investigation(database_path, investigation_id):
    initialise_database(database_path)
    with _connection(database_path) as connection:
        row = connection.execute(
            "SELECT * FROM investigations WHERE id = ?", (str(investigation_id),)
        ).fetchone()
    if not row:
        return None
    item = _row_dict(row)
    item["route"] = _json_load(item.pop("route_json"), {})
    item["hosts"] = _json_load(item.pop("hosts_json"), [])
    item["summary"] = _json_load(item.pop("summary_json"), {})
    return item


def list_investigations(database_path, vlan_id, limit=20):
    initialise_database(database_path)
    with _connection(database_path) as connection:
        rows = connection.execute(
            "SELECT id FROM investigations WHERE vlan_id = ? ORDER BY started_at DESC LIMIT ?",
            (str(vlan_id), int(limit)),
        ).fetchall()
    return [get_investigation(database_path, row["id"]) for row in rows]


def save_segmentation_rule(database_path, payload, rule_id=None, now=None):
    now = float(now or time.time())
    source_vlan_id = _clean_text(payload.get("source_vlan_id"), 80)
    destination_vlan_id = _clean_text(payload.get("destination_vlan_id"), 80)
    if not get_vlan(database_path, source_vlan_id):
        raise ValueError("Source VLAN was not found")
    if destination_vlan_id and not get_vlan(database_path, destination_vlan_id):
        raise ValueError("Destination VLAN was not found")
    destination = _clean_text(payload.get("destination"), 255)
    if not destination:
        raise ValueError("Destination host or address is required")
    try:
        ipaddress.ip_address(destination)
    except ValueError:
        if len(destination) > 253 or any(part == "" for part in destination.split(".")):
            raise ValueError("Destination must be an IP address or hostname")
    protocol = _clean_text(payload.get("protocol") or "tcp", 10).casefold()
    if protocol not in ALLOWED_PROTOCOLS:
        raise ValueError("Protocol must be TCP, UDP, or ICMP")
    raw_port = str(payload.get("port") or "").strip()
    port = None
    if protocol in {"tcp", "udp"}:
        if not raw_port:
            raise ValueError("TCP and UDP policy rules require a destination port")
        port = parse_ports(raw_port, maximum=1)[0]
    expectation = _clean_text(payload.get("expectation") or "block", 10).casefold()
    if expectation not in ALLOWED_EXPECTATIONS:
        raise ValueError("Expected result must be allow or block")
    item_id = str(rule_id or uuid.uuid4())
    with _connection(database_path) as connection:
        created = connection.execute(
            "SELECT created_at FROM segmentation_rules WHERE id = ?", (item_id,)
        ).fetchone()
        connection.execute(
            """
            INSERT OR REPLACE INTO segmentation_rules(
                id, source_vlan_id, destination_vlan_id, destination, protocol,
                port, expectation, description, source_probe_id, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_id, source_vlan_id, destination_vlan_id or None, destination,
                protocol, port, expectation, _clean_text(payload.get("description"), 1000),
                _clean_text(payload.get("source_probe_id"), 80) or None,
                float(created["created_at"]) if created else now, now,
            ),
        )
    return get_segmentation_rule(database_path, item_id)


def get_segmentation_rule(database_path, rule_id):
    initialise_database(database_path)
    with _connection(database_path) as connection:
        row = connection.execute(
            "SELECT * FROM segmentation_rules WHERE id = ?", (str(rule_id),)
        ).fetchone()
    return _row_dict(row)


def list_segmentation_rules(database_path):
    initialise_database(database_path)
    with _connection(database_path) as connection:
        rows = connection.execute(
            "SELECT * FROM segmentation_rules ORDER BY created_at, id"
        ).fetchall()
        results = connection.execute(
            """
            SELECT r.* FROM segmentation_results r
            JOIN (
                SELECT rule_id, MAX(checked_at) AS latest
                FROM segmentation_results GROUP BY rule_id
            ) latest ON latest.rule_id = r.rule_id AND latest.latest = r.checked_at
            """
        ).fetchall()
    latest_by_rule = {row["rule_id"]: _row_dict(row) for row in results}
    items = []
    for row in rows:
        item = _row_dict(row)
        item["latest_result"] = latest_by_rule.get(item["id"])
        items.append(item)
    return items


def record_segmentation_result(database_path, rule_id, observed, source, detail="", latency_ms=None, now=None):
    rule = get_segmentation_rule(database_path, rule_id)
    if not rule:
        raise ValueError("Segmentation rule was not found")
    observed_value = _clean_text(observed, 10).casefold()
    if observed_value not in {"allow", "block", "error"}:
        raise ValueError("Observed result must be allow, block, or error")
    mismatch = observed_value != rule["expectation"]
    item = {
        "id": str(uuid.uuid4()),
        "rule_id": str(rule_id),
        "observed": observed_value,
        "mismatch": bool(mismatch),
        "source": _clean_text(source, 120),
        "latency_ms": latency_ms,
        "detail": _clean_text(detail, 2000),
        "checked_at": float(now or time.time()),
    }
    with _connection(database_path) as connection:
        connection.execute(
            """
            INSERT INTO segmentation_results(
                id, rule_id, observed, mismatch, source, latency_ms, detail, checked_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["id"], item["rule_id"], item["observed"], int(item["mismatch"]),
                item["source"], item["latency_ms"], item["detail"], item["checked_at"],
            ),
        )
    return item


def segmentation_matrix(database_path):
    vlans = {item["id"]: item for item in list_vlans(database_path)}
    rows = []
    for rule in list_segmentation_rules(database_path):
        item = dict(rule)
        item["source_vlan"] = vlans.get(rule["source_vlan_id"])
        item["destination_vlan"] = vlans.get(rule.get("destination_vlan_id"))
        rows.append(item)
    return rows


def validate_integration_payload(payload):
    payload = payload or {}
    name = _clean_text(payload.get("name") or "pfSense", 120)
    base_url = _clean_text(payload.get("base_url"), 500).rstrip("/")
    if base_url:
        parsed = urlsplit(base_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("pfSense base URL must be an explicit HTTPS URL")
    token_env = _clean_text(payload.get("token_env"), 128)
    if token_env and not _ENV_REF_RE.match(token_env):
        raise ValueError("Token environment reference must look like MOBILE_ROUTER_PFSENSE_TOKEN")
    config = {
        "vlans_path": _clean_text(payload.get("vlans_path") or "/api/v1/vlans", 255),
        "leases_path": _clean_text(payload.get("leases_path") or "/api/v1/services/dhcpd/leases", 255),
        "arp_path": _clean_text(payload.get("arp_path") or "/api/v1/diagnostics/arp_table", 255),
    }
    return {
        "kind": "pfsense",
        "name": name,
        "base_url": base_url,
        "token_env": token_env,
        "header_name": _clean_text(payload.get("header_name") or "Authorization", 120),
        "token_prefix": _clean_text(payload.get("token_prefix") or "Bearer", 40),
        "verify_tls": str(payload.get("verify_tls") or "").casefold() not in {"0", "false", "off", "no"},
        "config": config,
    }


def save_integration(database_path, payload, integration_id=None, now=None):
    item = validate_integration_payload(payload)
    item_id = str(integration_id or uuid.uuid4())
    now = float(now or time.time())
    with _connection(database_path) as connection:
        created = connection.execute(
            "SELECT created_at FROM integrations WHERE id = ?", (item_id,)
        ).fetchone()
        connection.execute(
            """
            INSERT OR REPLACE INTO integrations(
                id, kind, name, base_url, token_env, header_name, token_prefix,
                verify_tls, config_json, last_sync, last_status, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT last_sync FROM integrations WHERE id = ?), NULL), COALESCE((SELECT last_status FROM integrations WHERE id = ?), NULL), ?, ?)
            """,
            (
                item_id, item["kind"], item["name"], item["base_url"], item["token_env"],
                item["header_name"], item["token_prefix"], int(item["verify_tls"]),
                json.dumps(item["config"], sort_keys=True), item_id, item_id,
                float(created["created_at"]) if created else now, now,
            ),
        )
    return get_integration(database_path, item_id)


def get_integration(database_path, integration_id):
    initialise_database(database_path)
    with _connection(database_path) as connection:
        row = connection.execute(
            "SELECT * FROM integrations WHERE id = ?", (str(integration_id),)
        ).fetchone()
    if not row:
        return None
    item = _row_dict(row)
    item["verify_tls"] = bool(item["verify_tls"])
    item["config"] = _json_load(item.pop("config_json"), {})
    item["token_configured"] = bool(item.get("token_env") and os.environ.get(item["token_env"]))
    return item


def list_integrations(database_path):
    initialise_database(database_path)
    with _connection(database_path) as connection:
        rows = connection.execute("SELECT id FROM integrations ORDER BY name").fetchall()
    return [get_integration(database_path, row["id"]) for row in rows]


def update_integration_status(database_path, integration_id, status, now=None):
    with _connection(database_path) as connection:
        connection.execute(
            "UPDATE integrations SET last_sync = ?, last_status = ?, updated_at = ? WHERE id = ?",
            (float(now or time.time()), _clean_text(status, 1000), float(now or time.time()), str(integration_id)),
        )
    return get_integration(database_path, integration_id)


def _iter_mapping_records(value):
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                yield item
    elif isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, dict):
                record = dict(item)
                record.setdefault("name", key)
                yield record


def parse_pfsense_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("pfSense import must be a JSON object")
    vlan_sources = payload.get("vlans") or payload.get("interfaces") or []
    vlans = []
    for record in _iter_mapping_records(vlan_sources):
        tag = record.get("tag") or record.get("vlan") or record.get("vlan_id")
        name = record.get("descr") or record.get("description") or record.get("name") or (f"VLAN {tag}" if tag else "Imported network")
        subnet = record.get("subnet") or record.get("network") or record.get("cidr")
        gateway = record.get("gateway") or record.get("ipaddr") or record.get("address")
        prefix = record.get("prefix") or record.get("subnet_bits")
        if subnet and "/" not in str(subnet) and prefix:
            subnet = f"{subnet}/{prefix}"
        if not subnet and gateway and record.get("subnet") and str(record.get("subnet")).isdigit():
            subnet = f"{gateway}/{record['subnet']}"
        if not subnet and gateway and prefix:
            subnet = str(ipaddress.ip_network(f"{gateway}/{prefix}", strict=False))
        if not subnet:
            continue
        network = _normalise_network(subnet)
        if gateway:
            try:
                gateway_value = _normalise_ip(gateway, "Gateway")
            except ValueError:
                gateway_value = ""
        else:
            gateway_value = ""
        vlans.append(
            {
                "tag": tag,
                "name": str(name),
                "subnet": str(network),
                "gateway": gateway_value,
                "interface_name": record.get("if") or record.get("interface") or record.get("port"),
                "router_name": payload.get("hostname") or "pfSense",
                "description": "Imported from read-only pfSense data",
                "probe_mode": "infrastructure",
                "source_type": "pfsense",
            }
        )

    devices_by_key = {}
    for collection_name in ("leases", "dhcp_leases", "arp", "arp_table", "devices"):
        for record in _iter_mapping_records(payload.get(collection_name) or []):
            ip = record.get("ip") or record.get("ip_address") or record.get("address")
            mac = record.get("mac") or record.get("mac_address")
            if not ip and not mac:
                continue
            key = str(mac or ip).casefold()
            current = devices_by_key.setdefault(key, {})
            current.update({key: value for key, value in {
                "ip": ip,
                "mac": mac,
                "hostname": record.get("hostname") or record.get("name"),
                "manufacturer": record.get("manufacturer") or record.get("vendor"),
                "interface": record.get("interface") or record.get("if"),
                "vlan_tag": record.get("vlan") or record.get("tag") or record.get("vlan_id"),
            }.items() if value not in (None, "")})
    return {"vlans": vlans, "devices": list(devices_by_key.values())}


def fetch_integration_payload(integration, opener=urlopen):
    if not integration or not integration.get("base_url"):
        raise ValueError("Integration does not have a base URL")
    token = os.environ.get(integration.get("token_env") or "") if integration.get("token_env") else ""
    headers = {"Accept": "application/json", "User-Agent": "Mobile-Router-VLAN/1"}
    if token:
        prefix = str(integration.get("token_prefix") or "").strip()
        headers[integration.get("header_name") or "Authorization"] = f"{prefix} {token}".strip()
    context = None
    if not integration.get("verify_tls", True):
        context = ssl._create_unverified_context()  # Explicit administrator opt-in for local appliances.

    combined = {"hostname": integration.get("name") or "pfSense"}
    for key, path in (integration.get("config") or {}).items():
        if not path:
            continue
        url = urljoin(integration["base_url"] + "/", str(path).lstrip("/"))
        request = Request(url, headers=headers, method="GET")
        response = opener(request, timeout=10, context=context)
        data = response.read(MAX_IMPORT_BYTES + 1)
        if len(data) > MAX_IMPORT_BYTES:
            raise ValueError("pfSense response exceeded the 2 MiB safety limit")
        decoded = json.loads(data.decode("utf-8"))
        logical_key = key.removesuffix("_path")
        combined[logical_key] = decoded.get("data", decoded) if isinstance(decoded, dict) else decoded
    return combined


def save_remote_probe(database_path, payload, probe_id=None, now=None):
    vlan_id = _clean_text(payload.get("vlan_id"), 80)
    if not get_vlan(database_path, vlan_id):
        raise ValueError("Probe VLAN was not found")
    name = _clean_text(payload.get("name"), 120)
    if not name:
        raise ValueError("Probe name is required")
    secret_env = _clean_text(payload.get("secret_env"), 128)
    if not _ENV_REF_RE.match(secret_env):
        raise ValueError("Probe secret environment reference must look like MOBILE_ROUTER_VLAN20_PROBE_KEY")
    item_id = str(probe_id or uuid.uuid4())
    now = float(now or time.time())
    with _connection(database_path) as connection:
        created = connection.execute(
            "SELECT created_at FROM remote_probes WHERE id = ?", (item_id,)
        ).fetchone()
        connection.execute(
            """
            INSERT OR REPLACE INTO remote_probes(
                id, vlan_id, name, secret_env, status, last_seen, created_at, updated_at
            ) VALUES(
                ?, ?, ?, ?,
                COALESCE((SELECT status FROM remote_probes WHERE id = ?), 'never-seen'),
                (SELECT last_seen FROM remote_probes WHERE id = ?), ?, ?
            )
            """,
            (
                item_id, vlan_id, name, secret_env, item_id, item_id,
                float(created["created_at"]) if created else now, now,
            ),
        )
    return get_remote_probe(database_path, item_id)


def get_remote_probe(database_path, probe_id):
    initialise_database(database_path)
    with _connection(database_path) as connection:
        row = connection.execute(
            "SELECT * FROM remote_probes WHERE id = ?", (str(probe_id),)
        ).fetchone()
    if not row:
        return None
    item = _row_dict(row)
    item["secret_configured"] = bool(os.environ.get(item.get("secret_env") or ""))
    return item


def list_remote_probes(database_path, vlan_id=None):
    initialise_database(database_path)
    with _connection(database_path) as connection:
        if vlan_id:
            rows = connection.execute(
                "SELECT id FROM remote_probes WHERE vlan_id = ? ORDER BY name", (str(vlan_id),)
            ).fetchall()
        else:
            rows = connection.execute("SELECT id FROM remote_probes ORDER BY name").fetchall()
    return [get_remote_probe(database_path, row["id"]) for row in rows]


def probe_signature(secret, timestamp, nonce, body):
    message = str(timestamp).encode("ascii") + b"\n" + str(nonce).encode("utf-8") + b"\n" + bytes(body)
    return hmac.new(str(secret).encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_probe_submission(database_path, probe_id, body, timestamp, nonce, signature, now=None):
    body = bytes(body or b"")
    if len(body) > MAX_PROBE_BYTES:
        raise ValueError("Probe payload exceeded the 1 MiB safety limit")
    probe = get_remote_probe(database_path, probe_id)
    if not probe:
        raise ValueError("Unknown remote probe")
    secret = os.environ.get(probe.get("secret_env") or "")
    if not secret:
        raise ValueError("Remote probe secret is not configured on the server")
    try:
        sent_at = int(timestamp)
    except (TypeError, ValueError) as exc:
        raise ValueError("Probe timestamp is invalid") from exc
    current = int(now or time.time())
    if abs(current - sent_at) > PROBE_CLOCK_SKEW_SECONDS:
        raise ValueError("Probe timestamp is outside the five-minute acceptance window")
    if not _NONCE_RE.match(str(nonce or "")):
        raise ValueError("Probe nonce is invalid")
    expected = probe_signature(secret, sent_at, nonce, body)
    supplied = str(signature or "").removeprefix("sha256=")
    if not hmac.compare_digest(expected, supplied):
        raise ValueError("Probe signature is invalid")

    with _connection(database_path) as connection:
        connection.execute(
            "DELETE FROM probe_nonces WHERE seen_at < ?", (current - (PROBE_CLOCK_SKEW_SECONDS * 2),)
        )
        try:
            connection.execute(
                "INSERT INTO probe_nonces(probe_id, nonce, seen_at) VALUES(?, ?, ?)",
                (str(probe_id), str(nonce), current),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Probe submission nonce has already been used") from exc
        connection.execute(
            "UPDATE remote_probes SET status = 'online', last_seen = ?, updated_at = ? WHERE id = ?",
            (current, current, str(probe_id)),
        )

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Probe payload is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Probe payload must be a JSON object")
    devices = payload.get("devices") or []
    if not isinstance(devices, list) or len(devices) > 4096:
        raise ValueError("Probe devices must be a list containing at most 4096 records")
    return probe, payload
