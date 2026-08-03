"""Device model profiles, applicability rules, drift analysis, and registries."""

from __future__ import annotations

import copy
import hashlib
import hmac
import ipaddress
import json
import os
import re
import socket
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

SCHEMA = "mobile-router-model-profiles-v2"
CLASSIFICATIONS = {
    "expected", "optional", "firmware-specific", "local-configuration",
    "unexpected", "investigate", "deprecated",
}
RISK_LEVELS = {"info", "low", "medium", "high", "critical"}
EXPOSURES = {"unknown", "lan-only", "management", "local-host", "wan-optional", "wan"}
SCOPES = {"exact", "family", "manufacturer"}
_MAX_DOWNLOAD = 2_097_152
_GENERIC_MODELS = {
    "", "unknown", "unidentified network device", "client", "gateway/router",
    "network infrastructure", "nas/file server", "media/tv device", "printer",
    "camera/nvr", "home automation/iot", "windows computer",
    "linux/unix computer", "mqtt/iot device", "web appliance",
    "remote admin host", "service endpoint",
}


class _ClosingConnection(sqlite3.Connection):
    """Commit or roll back and then release the database handle."""

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def database_path():
    configured = os.environ.get("MOBILE_ROUTER_PORT_KNOWLEDGE_DB")
    return Path(
        configured
        or Path(__file__).resolve().parents[1]
        / "instance"
        / "device_port_knowledge.sqlite3"
    )


def clean(value, limit=1000):
    return " ".join(str(value or "").strip().split())[:limit]


def key(value):
    return clean(value).casefold()


def json_list(value):
    if value in (None, ""):
        return []
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            decoded = [part.strip() for part in value.split(",")]
    else:
        decoded = value
    if not isinstance(decoded, (list, tuple, set)):
        decoded = [decoded]
    return sorted({clean(item, 200) for item in decoded if clean(item, 200)})


def bool_value(value, default=False):
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    return key(value) in {"1", "true", "yes", "on", "required"}


def valid_port(value):
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Port must be an integer") from exc
    if not 1 <= result <= 65535:
        raise ValueError("Port must be between 1 and 65535")
    return result


def valid_protocol(value):
    result = key(value or "tcp")
    if result not in {"tcp", "udp"}:
        raise ValueError("Protocol must be TCP or UDP")
    return result


def valid_choice(value, choices, label, default):
    result = key(value or default)
    if result not in choices:
        raise ValueError(f"{label} must be one of: {', '.join(sorted(choices))}")
    return result


def valid_url(value):
    result = str(value or "").strip()
    if not result:
        return ""
    parsed = urlparse(result)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Source URL must be HTTP or HTTPS")
    return result[:1200]


def _version_tokens(value):
    value = clean(value, 120)
    if not value:
        return ()
    tokens = re.findall(r"\d+|[A-Za-z]+", value)
    return tuple(int(token) if token.isdigit() else token.casefold() for token in tokens)


def compare_versions(left, right):
    left_tokens = list(_version_tokens(left))
    right_tokens = list(_version_tokens(right))
    length = max(len(left_tokens), len(right_tokens))
    left_tokens.extend([0] * (length - len(left_tokens)))
    right_tokens.extend([0] * (length - len(right_tokens)))
    for left_value, right_value in zip(left_tokens, right_tokens):
        if type(left_value) is type(right_value):
            if left_value < right_value:
                return -1
            if left_value > right_value:
                return 1
        else:
            left_text, right_text = str(left_value), str(right_value)
            if left_text < right_text:
                return -1
            if left_text > right_text:
                return 1
    return 0


def version_matches(value, minimum="", maximum=""):
    value, minimum, maximum = clean(value, 120), clean(minimum, 120), clean(maximum, 120)
    if not minimum and not maximum:
        return True
    if not value:
        return False
    if minimum and compare_versions(value, minimum) < 0:
        return False
    if maximum and compare_versions(value, maximum) > 0:
        return False
    return True


def _json(value, fallback):
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return copy.deepcopy(fallback)


def connect(path=None):
    path = Path(path or database_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=15, factory=_ClosingConnection)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS model_profiles (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          scope TEXT NOT NULL DEFAULT 'exact',
          manufacturer_key TEXT NOT NULL,
          model_key TEXT NOT NULL DEFAULT '',
          family_key TEXT NOT NULL DEFAULT '',
          manufacturer TEXT NOT NULL,
          model TEXT NOT NULL DEFAULT '',
          family TEXT NOT NULL DEFAULT '',
          hardware_revision TEXT NOT NULL DEFAULT '',
          firmware_min TEXT NOT NULL DEFAULT '',
          firmware_max TEXT NOT NULL DEFAULT '',
          aliases_json TEXT NOT NULL DEFAULT '[]',
          manufacturer_aliases_json TEXT NOT NULL DEFAULT '[]',
          notes TEXT NOT NULL DEFAULT '',
          risk_notes TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'active',
          created_at REAL NOT NULL,
          updated_at REAL NOT NULL,
          UNIQUE(
            scope, manufacturer_key, model_key, family_key,
            hardware_revision, firmware_min, firmware_max
          )
        );
        CREATE INDEX IF NOT EXISTS model_profiles_lookup
          ON model_profiles(manufacturer_key, model_key, family_key, scope, status);

        CREATE TABLE IF NOT EXISTS model_profile_ports (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          profile_id INTEGER NOT NULL REFERENCES model_profiles(id) ON DELETE CASCADE,
          port INTEGER NOT NULL,
          protocol TEXT NOT NULL DEFAULT 'tcp',
          service TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',
          classification TEXT NOT NULL DEFAULT 'expected',
          exposure TEXT NOT NULL DEFAULT 'unknown',
          authentication_expected INTEGER NOT NULL DEFAULT 0,
          encryption_expected INTEGER NOT NULL DEFAULT 0,
          risk TEXT NOT NULL DEFAULT 'info',
          remediation TEXT NOT NULL DEFAULT '',
          hardware_revision TEXT NOT NULL DEFAULT '',
          firmware_min TEXT NOT NULL DEFAULT '',
          firmware_max TEXT NOT NULL DEFAULT '',
          source_name TEXT NOT NULL DEFAULT '',
          source_url TEXT NOT NULL DEFAULT '',
          source_reliability INTEGER NOT NULL DEFAULT 50,
          confidence TEXT NOT NULL DEFAULT 'confirmed',
          status TEXT NOT NULL DEFAULT 'active',
          last_verified_at REAL,
          expires_at REAL,
          created_at REAL NOT NULL,
          updated_at REAL NOT NULL,
          UNIQUE(
            profile_id, port, protocol, hardware_revision,
            firmware_min, firmware_max, status
          )
        );
        CREATE INDEX IF NOT EXISTS model_profile_ports_lookup
          ON model_profile_ports(profile_id, protocol, port, status);

        CREATE TABLE IF NOT EXISTS model_profile_revisions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          profile_id INTEGER NOT NULL,
          revision INTEGER NOT NULL,
          action TEXT NOT NULL,
          actor TEXT NOT NULL DEFAULT '',
          note TEXT NOT NULL DEFAULT '',
          snapshot_json TEXT NOT NULL,
          created_at REAL NOT NULL,
          UNIQUE(profile_id, revision)
        );

        CREATE TABLE IF NOT EXISTS model_profile_conflicts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          profile_id INTEGER NOT NULL,
          port INTEGER NOT NULL,
          protocol TEXT NOT NULL,
          current_json TEXT NOT NULL,
          incoming_json TEXT NOT NULL,
          source_name TEXT NOT NULL DEFAULT '',
          source_url TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'open',
          resolution_note TEXT NOT NULL DEFAULT '',
          created_at REAL NOT NULL,
          resolved_at REAL
        );

        CREATE TABLE IF NOT EXISTS model_profile_observations (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          profile_id INTEGER NOT NULL,
          device_signature TEXT NOT NULL,
          port INTEGER NOT NULL,
          protocol TEXT NOT NULL,
          service TEXT NOT NULL DEFAULT '',
          firmware TEXT NOT NULL DEFAULT '',
          hardware_revision TEXT NOT NULL DEFAULT '',
          evidence_json TEXT NOT NULL DEFAULT '{}',
          observations INTEGER NOT NULL DEFAULT 1,
          first_seen REAL NOT NULL,
          last_seen REAL NOT NULL,
          UNIQUE(profile_id, device_signature, port, protocol)
        );

        CREATE TABLE IF NOT EXISTS model_registry_imports (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          publisher TEXT NOT NULL DEFAULT '',
          version TEXT NOT NULL DEFAULT '',
          digest TEXT NOT NULL DEFAULT '',
          signature_status TEXT NOT NULL DEFAULT '',
          source_url TEXT NOT NULL DEFAULT '',
          imported INTEGER NOT NULL DEFAULT 0,
          conflicts INTEGER NOT NULL DEFAULT 0,
          errors_json TEXT NOT NULL DEFAULT '[]',
          created_at REAL NOT NULL
        );
        """
    )
    _migrate_legacy(db)
    return db


def _row(row):
    if not row:
        return None
    item = dict(row)
    for field, fallback in (
        ("aliases_json", []),
        ("manufacturer_aliases_json", []),
        ("evidence_json", {}),
        ("current_json", {}),
        ("incoming_json", {}),
        ("snapshot_json", {}),
        ("errors_json", []),
    ):
        if field in item:
            item[field[:-5] if field.endswith("_json") else field] = _json(item.pop(field), fallback)
    for name in ("authentication_expected", "encryption_expected"):
        if name in item:
            item[name] = bool(item[name])
    return item


def _migrate_legacy(db):
    table = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='port_knowledge'"
    ).fetchone()
    if not table:
        return
    rows = db.execute(
        """
        SELECT * FROM port_knowledge
        WHERE status='approved' AND model_key != ''
        ORDER BY manufacturer_key, model_key, protocol, port
        """
    ).fetchall()
    now = time.time()
    for legacy in rows:
        profile = db.execute(
            """
            SELECT * FROM model_profiles
            WHERE scope='exact' AND manufacturer_key=? AND model_key=?
              AND hardware_revision='' AND firmware_min='' AND firmware_max=''
            """,
            (legacy["manufacturer_key"], legacy["model_key"]),
        ).fetchone()
        if profile:
            profile_id = profile["id"]
        else:
            cursor = db.execute(
                """
                INSERT INTO model_profiles (
                  scope, manufacturer_key, model_key, family_key,
                  manufacturer, model, family, hardware_revision,
                  firmware_min, firmware_max, aliases_json,
                  manufacturer_aliases_json, notes, risk_notes,
                  status, created_at, updated_at
                ) VALUES (
                  'exact', ?, ?, '', ?, ?, '', '', '', '',
                  '[]', '[]', 'Migrated from model port knowledge', '',
                  'active', ?, ?
                )
                """,
                (
                    legacy["manufacturer_key"], legacy["model_key"],
                    legacy["manufacturer"], legacy["model"], now, now,
                ),
            )
            profile_id = cursor.lastrowid
        db.execute(
            """
            INSERT OR IGNORE INTO model_profile_ports (
              profile_id, port, protocol, service, description,
              classification, exposure, authentication_expected,
              encryption_expected, risk, remediation, hardware_revision,
              firmware_min, firmware_max, source_name, source_url,
              source_reliability, confidence, status, last_verified_at,
              expires_at, created_at, updated_at
            ) VALUES (
              ?, ?, ?, ?, ?, 'expected', 'unknown', 0, 0, 'info', '',
              '', '', '', ?, ?, 60, ?, 'active', ?, NULL, ?, ?
            )
            """,
            (
                profile_id, legacy["port"], legacy["protocol"], legacy["service"],
                legacy["description"], legacy["source_name"], legacy["source_url"],
                legacy["confidence"], legacy["updated_at"], legacy["created_at"],
                legacy["updated_at"],
            ),
        )


def _profile_snapshot(db, profile_id):
    profile = _row(db.execute("SELECT * FROM model_profiles WHERE id=?", (profile_id,)).fetchone())
    if not profile:
        return {}
    ports = [
        _row(row)
        for row in db.execute(
            "SELECT * FROM model_profile_ports WHERE profile_id=? AND status='active' ORDER BY protocol, port",
            (profile_id,),
        ).fetchall()
    ]
    return {"profile": profile, "ports": ports}


def _record_revision(db, profile_id, action, actor="", note=""):
    current = db.execute(
        "SELECT COALESCE(MAX(revision), 0) FROM model_profile_revisions WHERE profile_id=?",
        (profile_id,),
    ).fetchone()[0]
    revision = int(current) + 1
    db.execute(
        """
        INSERT INTO model_profile_revisions (
          profile_id, revision, action, actor, note, snapshot_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            profile_id, revision, clean(action, 100), clean(actor, 160),
            clean(note, 1000), json.dumps(_profile_snapshot(db, profile_id), sort_keys=True),
            time.time(),
        ),
    )
    return revision


def identity(device):
    device = device or {}
    assessment = device.get("identity_assessment") or {}
    manufacturer = clean(device.get("manufacturer") or assessment.get("manufacturer") or device.get("vendor"), 200)
    model = clean(device.get("model") or assessment.get("model") or device.get("model_name"), 240)
    family = clean(device.get("model_family") or assessment.get("family"), 200)
    hardware_revision = clean(
        device.get("hardware_revision") or device.get("hardware_version") or assessment.get("hardware_revision"), 120
    )
    firmware = clean(
        device.get("firmware") or device.get("firmware_version")
        or device.get("software_version") or assessment.get("firmware"), 160
    )
    if key(manufacturer) == "unknown":
        manufacturer = ""
    if key(model) in _GENERIC_MODELS:
        model = ""
    return {
        "manufacturer": manufacturer, "manufacturer_key": key(manufacturer),
        "model": model, "model_key": key(model),
        "family": family, "family_key": key(family),
        "hardware_revision": hardware_revision, "firmware": firmware,
    }


def upsert_profile(
    path, *, manufacturer, model="", family="", scope="exact",
    hardware_revision="", firmware_min="", firmware_max="", aliases=None,
    manufacturer_aliases=None, notes="", risk_notes="", actor="",
):
    scope = valid_choice(scope, SCOPES, "Profile scope", "exact")
    manufacturer = clean(manufacturer, 200)
    model, family = clean(model, 240), clean(family, 200)
    hardware_revision = clean(hardware_revision, 120)
    firmware_min, firmware_max = clean(firmware_min, 160), clean(firmware_max, 160)
    if not manufacturer:
        raise ValueError("Manufacturer is required")
    if scope == "exact" and (not model or key(model) in _GENERIC_MODELS):
        raise ValueError("An exact reusable model is required")
    if scope == "family" and not family:
        raise ValueError("A model family is required")
    if scope == "manufacturer":
        model, family = "", ""
    now = time.time()
    with connect(path) as db:
        existing = db.execute(
            """
            SELECT * FROM model_profiles
            WHERE scope=? AND manufacturer_key=? AND model_key=?
              AND family_key=? AND hardware_revision=?
              AND firmware_min=? AND firmware_max=?
            """,
            (scope, key(manufacturer), key(model), key(family), hardware_revision, firmware_min, firmware_max),
        ).fetchone()
        if existing:
            profile_id = existing["id"]
            db.execute(
                """
                UPDATE model_profiles SET
                  manufacturer=?, model=?, family=?, aliases_json=?,
                  manufacturer_aliases_json=?, notes=?, risk_notes=?,
                  status='active', updated_at=? WHERE id=?
                """,
                (
                    manufacturer, model, family, json.dumps(json_list(aliases)),
                    json.dumps(json_list(manufacturer_aliases)), clean(notes, 4000),
                    clean(risk_notes, 4000), now, profile_id,
                ),
            )
            _record_revision(db, profile_id, "profile-updated", actor)
        else:
            cursor = db.execute(
                """
                INSERT INTO model_profiles (
                  scope, manufacturer_key, model_key, family_key,
                  manufacturer, model, family, hardware_revision,
                  firmware_min, firmware_max, aliases_json,
                  manufacturer_aliases_json, notes, risk_notes,
                  status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    scope, key(manufacturer), key(model), key(family), manufacturer,
                    model, family, hardware_revision, firmware_min, firmware_max,
                    json.dumps(json_list(aliases)), json.dumps(json_list(manufacturer_aliases)),
                    clean(notes, 4000), clean(risk_notes, 4000), now, now,
                ),
            )
            profile_id = cursor.lastrowid
            _record_revision(db, profile_id, "profile-created", actor)
    return profile_detail(path, profile_id)


def profile_detail(path, profile_id):
    with connect(path) as db:
        profile = _row(db.execute(
            "SELECT * FROM model_profiles WHERE id=? AND status='active'", (int(profile_id),)
        ).fetchone())
        if not profile:
            raise ValueError("Device model profile was not found")
        ports = [_row(row) for row in db.execute(
            "SELECT * FROM model_profile_ports WHERE profile_id=? AND status='active' ORDER BY protocol, port",
            (profile["id"],),
        ).fetchall()]
        open_conflicts = [_row(row) for row in db.execute(
            "SELECT * FROM model_profile_conflicts WHERE profile_id=? AND status='open' ORDER BY created_at DESC",
            (profile["id"],),
        ).fetchall()]
    profile["ports"] = ports
    profile["conflicts"] = open_conflicts
    return profile


def list_profiles(path, query="", scope=""):
    query_key = key(query)
    with connect(path) as db:
        rows = db.execute(
            "SELECT * FROM model_profiles WHERE status='active' ORDER BY manufacturer, model, family"
        ).fetchall()
        counts = {row["profile_id"]: row["count"] for row in db.execute(
            "SELECT profile_id, COUNT(*) AS count FROM model_profile_ports WHERE status='active' GROUP BY profile_id"
        ).fetchall()}
    results = []
    for row in rows:
        item = _row(row)
        if scope and item["scope"] != scope:
            continue
        searchable = " ".join([
            item["manufacturer"], item["model"], item["family"],
            " ".join(item.get("aliases") or []),
            " ".join(item.get("manufacturer_aliases") or []),
        ]).casefold()
        if query_key and query_key not in searchable:
            continue
        item["port_count"] = counts.get(item["id"], 0)
        results.append(item)
    return results


def _manufacturer_match(profile, found):
    aliases = {key(value) for value in profile.get("manufacturer_aliases") or []}
    if found["manufacturer_key"] == profile["manufacturer_key"]:
        return 30
    if found["manufacturer_key"] and found["manufacturer_key"] in aliases:
        return 20
    return 0


def _profile_match(profile, found):
    manufacturer_score = _manufacturer_match(profile, found)
    if not manufacturer_score:
        return None
    if profile["hardware_revision"]:
        if key(profile["hardware_revision"]) != key(found["hardware_revision"]):
            return None
        hardware_score = 20
    else:
        hardware_score = 4
    if not version_matches(found["firmware"], profile["firmware_min"], profile["firmware_max"]):
        return None
    firmware_score = 16 if (profile["firmware_min"] or profile["firmware_max"]) else 4
    if profile["scope"] == "exact":
        aliases = {key(value) for value in profile.get("aliases") or []}
        if found["model_key"] == profile["model_key"]:
            scope_score, level = 60, "exact"
        elif found["model_key"] and found["model_key"] in aliases:
            scope_score, level = 50, "alias"
        else:
            return None
    elif profile["scope"] == "family":
        if found["family_key"] == profile["family_key"]:
            scope_score, level = 35, "family"
        elif profile["family_key"] and profile["family_key"] in found["model_key"]:
            scope_score, level = 28, "family-inferred"
        else:
            return None
    else:
        scope_score, level = 10, "manufacturer"
    return {
        "profile": profile,
        "score": manufacturer_score + scope_score + hardware_score + firmware_score,
        "level": level,
    }


def resolve_profile_stack(path, device):
    found = identity(device)
    candidates = []
    manual_id = device.get("model_profile_manual_id")
    if manual_id:
        try:
            manual = profile_detail(path, manual_id)
            candidates.append({"profile": manual, "score": 1000, "level": "manual"})
        except ValueError:
            pass
    for profile in list_profiles(path):
        if manual_id and int(profile["id"]) == int(manual_id):
            continue
        matched = _profile_match(profile, found)
        if matched:
            candidates.append(matched)
    candidates.sort(key=lambda item: (item["score"], item["profile"]["id"]))
    return {"identity": found, "matches": candidates}


def _rule_applicable(rule, found):
    if rule["hardware_revision"] and key(rule["hardware_revision"]) != key(found["hardware_revision"]):
        return False
    return version_matches(found["firmware"], rule["firmware_min"], rule["firmware_max"])


def combined_rules(path, device):
    stack = resolve_profile_stack(path, device)
    combined, applied_profiles = {}, []
    for match in stack["matches"]:
        profile = profile_detail(path, match["profile"]["id"])
        applied_profiles.append({
            "id": profile["id"], "manufacturer": profile["manufacturer"],
            "model": profile["model"], "family": profile["family"],
            "scope": profile["scope"], "match_level": match["level"],
            "score": match["score"],
        })
        for rule in profile["ports"]:
            if _rule_applicable(rule, stack["identity"]):
                combined[(rule["port"], rule["protocol"])] = rule
    return {
        "identity": stack["identity"], "rules": combined,
        "profiles": applied_profiles,
        "primary_profile": applied_profiles[-1] if applied_profiles else None,
    }


def add_port_rule(
    path, *, profile_id, port, protocol="tcp", service, description="",
    classification="expected", exposure="unknown", authentication_expected=False,
    encryption_expected=False, risk="info", remediation="", hardware_revision="",
    firmware_min="", firmware_max="", source_name="", source_url="",
    source_reliability=50, confidence="confirmed", actor="", allow_replace=False,
):
    profile_id, port, protocol = int(profile_id), valid_port(port), valid_protocol(protocol)
    service = clean(service, 200)
    if not service:
        raise ValueError("Service name is required")
    classification = valid_choice(classification, CLASSIFICATIONS, "Classification", "expected")
    exposure = valid_choice(exposure, EXPOSURES, "Exposure", "unknown")
    risk = valid_choice(risk, RISK_LEVELS, "Risk", "info")
    hardware_revision = clean(hardware_revision, 120)
    firmware_min, firmware_max = clean(firmware_min, 160), clean(firmware_max, 160)
    try:
        source_reliability = max(0, min(100, int(source_reliability)))
    except (TypeError, ValueError) as exc:
        raise ValueError("Source reliability must be from 0 to 100") from exc
    incoming = {
        "profile_id": profile_id, "port": port, "protocol": protocol,
        "service": service, "description": clean(description, 2000),
        "classification": classification, "exposure": exposure,
        "authentication_expected": bool_value(authentication_expected),
        "encryption_expected": bool_value(encryption_expected), "risk": risk,
        "remediation": clean(remediation, 2000),
        "hardware_revision": hardware_revision, "firmware_min": firmware_min,
        "firmware_max": firmware_max, "source_name": clean(source_name, 240),
        "source_url": valid_url(source_url), "source_reliability": source_reliability,
        "confidence": clean(confidence or "confirmed", 80),
    }
    now = time.time()
    with connect(path) as db:
        profile = db.execute(
            "SELECT * FROM model_profiles WHERE id=? AND status='active'", (profile_id,)
        ).fetchone()
        if not profile:
            raise ValueError("Device model profile was not found")
        existing = db.execute(
            """
            SELECT * FROM model_profile_ports
            WHERE profile_id=? AND port=? AND protocol=?
              AND hardware_revision=? AND firmware_min=? AND firmware_max=?
              AND status='active'
            """,
            (profile_id, port, protocol, hardware_revision, firmware_min, firmware_max),
        ).fetchone()
        if existing:
            current = _row(existing)
            material = (
                "service", "description", "classification", "exposure", "risk",
                "remediation", "authentication_expected", "encryption_expected",
            )
            if any(current.get(name) != incoming.get(name) for name in material) and not allow_replace:
                cursor = db.execute(
                    """
                    INSERT INTO model_profile_conflicts (
                      profile_id, port, protocol, current_json, incoming_json,
                      source_name, source_url, status, resolution_note,
                      created_at, resolved_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'open', '', ?, NULL)
                    """,
                    (
                        profile_id, port, protocol, json.dumps(current, sort_keys=True),
                        json.dumps(incoming, sort_keys=True), incoming["source_name"],
                        incoming["source_url"], now,
                    ),
                )
                _record_revision(db, profile_id, "port-conflict-recorded", actor, f"Conflict {cursor.lastrowid} for {port}/{protocol}")
                return {"status": "conflict", "conflict_id": cursor.lastrowid, "current": current, "incoming": incoming}
            db.execute(
                """
                UPDATE model_profile_ports SET
                  service=?, description=?, classification=?, exposure=?,
                  authentication_expected=?, encryption_expected=?, risk=?,
                  remediation=?, source_name=?, source_url=?, source_reliability=?,
                  confidence=?, last_verified_at=?, updated_at=? WHERE id=?
                """,
                (
                    incoming["service"], incoming["description"], incoming["classification"],
                    incoming["exposure"], int(incoming["authentication_expected"]),
                    int(incoming["encryption_expected"]), incoming["risk"],
                    incoming["remediation"], incoming["source_name"], incoming["source_url"],
                    incoming["source_reliability"], incoming["confidence"], now, now,
                    existing["id"],
                ),
            )
            rule_id, action = existing["id"], "port-rule-updated"
        else:
            cursor = db.execute(
                """
                INSERT INTO model_profile_ports (
                  profile_id, port, protocol, service, description,
                  classification, exposure, authentication_expected,
                  encryption_expected, risk, remediation, hardware_revision,
                  firmware_min, firmware_max, source_name, source_url,
                  source_reliability, confidence, status, last_verified_at,
                  expires_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, NULL, ?, ?)
                """,
                (
                    profile_id, port, protocol, incoming["service"], incoming["description"],
                    incoming["classification"], incoming["exposure"],
                    int(incoming["authentication_expected"]), int(incoming["encryption_expected"]),
                    incoming["risk"], incoming["remediation"], hardware_revision,
                    firmware_min, firmware_max, incoming["source_name"], incoming["source_url"],
                    incoming["source_reliability"], incoming["confidence"], now, now, now,
                ),
            )
            rule_id, action = cursor.lastrowid, "port-rule-created"
        db.execute("UPDATE model_profiles SET updated_at=? WHERE id=?", (now, profile_id))
        _record_revision(db, profile_id, action, actor, f"{port}/{protocol} {service}")
        return _row(db.execute("SELECT * FROM model_profile_ports WHERE id=?", (rule_id,)).fetchone())


def delete_port_rule(path, profile_id, rule_id, actor=""):
    with connect(path) as db:
        row = db.execute(
            "SELECT * FROM model_profile_ports WHERE id=? AND profile_id=? AND status='active'",
            (int(rule_id), int(profile_id)),
        ).fetchone()
        if not row:
            return False
        db.execute(
            "UPDATE model_profile_ports SET status='deleted', updated_at=? WHERE id=?",
            (time.time(), int(rule_id)),
        )
        _record_revision(db, int(profile_id), "port-rule-deleted", actor, f"{row['port']}/{row['protocol']} {row['service']}")
        return True


def set_device_override(
    device, *, port, protocol="tcp", service="",
    classification="local-configuration", description="", risk="info", remediation="",
):
    updated = copy.deepcopy(device or {})
    override = {
        "port": valid_port(port), "protocol": valid_protocol(protocol),
        "service": clean(service, 200),
        "classification": valid_choice(classification, CLASSIFICATIONS, "Classification", "local-configuration"),
        "description": clean(description, 1000),
        "risk": valid_choice(risk, RISK_LEVELS, "Risk", "info"),
        "remediation": clean(remediation, 1000), "updated_at": time.time(),
    }
    overrides = [
        item for item in updated.get("model_port_overrides") or []
        if not (
            int(item.get("port") or 0) == override["port"]
            and key(item.get("protocol") or "tcp") == override["protocol"]
        )
    ]
    overrides.append(override)
    updated["model_port_overrides"] = sorted(overrides, key=lambda item: (item["protocol"], item["port"]))
    return updated


def _drift_severity(unexpected, missing, deprecated):
    score = 0
    for item in unexpected:
        score += {"critical": 40, "high": 25, "medium": 12, "low": 5}.get(item.get("risk"), 4)
    score += len(missing) * 8 + len(deprecated) * 10
    if score >= 50:
        return "critical", min(100, score)
    if score >= 25:
        return "high", min(100, score)
    if score >= 10:
        return "medium", min(100, score)
    if score:
        return "low", min(100, score)
    return "none", 0


def apply_device_profile(path, device):
    result = combined_rules(path, device)
    rules = dict(result["rules"])
    for override in device.get("model_port_overrides") or []:
        try:
            rules[(valid_port(override.get("port")), valid_protocol(override.get("protocol")))] = {
                **override, "id": None, "profile_id": None,
                "source_name": "Device-specific override", "source_url": "",
                "confidence": "local", "exposure": "unknown",
                "authentication_expected": False, "encryption_expected": False,
            }
        except ValueError:
            continue
    observed, open_details = set(), []
    unexpected, deprecated, remediation = [], [], []
    for raw in device.get("open_port_details") or []:
        detail = dict(raw)
        try:
            item_key = (valid_port(detail.get("port")), valid_protocol(detail.get("protocol") or "tcp"))
        except ValueError:
            open_details.append(detail)
            continue
        observed.add(item_key)
        rule = rules.get(item_key)
        if rule:
            detail.update({
                "model_profile_rule_id": rule.get("id"),
                "model_profile_id": rule.get("profile_id"),
                "model_profile_service": rule.get("service"),
                "model_profile_description": rule.get("description"),
                "model_profile_classification": rule.get("classification"),
                "model_profile_exposure": rule.get("exposure"),
                "model_profile_risk": rule.get("risk"),
                "model_profile_remediation": rule.get("remediation"),
                "model_profile_source_name": rule.get("source_name"),
                "model_profile_source_url": rule.get("source_url"),
            })
            if key(detail.get("service")) in {"", "unknown", "unknown service", "unassigned"}:
                detail["service"] = rule.get("service") or detail.get("service")
            if not detail.get("description") and rule.get("description"):
                detail["description"] = rule["description"]
            if rule.get("classification") == "deprecated":
                deprecated.append(detail)
            if rule.get("remediation"):
                remediation.append({
                    "port": item_key[0], "protocol": item_key[1],
                    "severity": rule.get("risk") or "info",
                    "task": rule["remediation"], "reason": rule.get("classification"),
                })
        else:
            unknown = {
                "port": item_key[0], "protocol": item_key[1],
                "service": detail.get("service") or "Unknown",
                "risk": "medium" if item_key[0] >= 1024 else "high",
                "reason": "No applicable model-profile rule",
            }
            unexpected.append(unknown)
            detail["model_profile_classification"] = "unexpected"
            detail["model_profile_risk"] = unknown["risk"]
            remediation.append({
                "port": item_key[0], "protocol": item_key[1], "severity": unknown["risk"],
                "task": "Identify the service and either approve it for this model, mark it as a local override, or restrict/disable it.",
                "reason": "unexpected",
            })
        open_details.append(detail)
    missing = []
    for item_key, rule in rules.items():
        if rule.get("classification") == "expected" and item_key not in observed:
            missing.append({
                "port": item_key[0], "protocol": item_key[1],
                "service": rule.get("service"), "risk": rule.get("risk") or "info",
                "reason": "Expected model service was not observed",
            })
            remediation.append({
                "port": item_key[0], "protocol": item_key[1], "severity": "low",
                "task": "Confirm whether the feature is disabled, the firmware differs, or the scan missed the expected service.",
                "reason": "missing-expected",
            })
    severity, score = _drift_severity(unexpected, missing, deprecated)
    drift = {
        "severity": severity, "score": score, "unexpected": unexpected,
        "missing_expected": missing, "deprecated": deprecated,
        "matches_profile": not unexpected and not missing and not deprecated,
        "observed_count": len(observed), "applicable_rule_count": len(rules),
        "digest": hashlib.sha256(json.dumps({
            "unexpected": unexpected, "missing": missing,
            "deprecated": [(item.get("port"), item.get("protocol")) for item in deprecated],
        }, sort_keys=True).encode()).hexdigest(),
    }
    updated = copy.deepcopy(device or {})
    updated["open_port_details"] = open_details
    updated["model_profile_matches"] = result["profiles"]
    updated["model_profile_id"] = result["primary_profile"]["id"] if result["primary_profile"] else None
    updated["model_profile_match_level"] = result["primary_profile"]["match_level"] if result["primary_profile"] else None
    updated["model_port_drift"] = drift
    updated["model_remediation_tasks"] = remediation
    updated["model_profile_applied_at"] = time.time()
    return {
        "device": updated, "identity": result["identity"],
        "profiles": result["profiles"], "primary_profile": result["primary_profile"],
        "rules": list(rules.values()), "drift": drift, "remediation": remediation,
    }


def record_observations(path, device, profile_id=None):
    applied = apply_device_profile(path, device)
    profile_id = int(profile_id or applied["device"].get("model_profile_id") or 0)
    if not profile_id:
        return {"recorded": 0}
    signature = clean(device.get("identity_signature"), 160)
    if not signature:
        raw = "|".join(str(device.get(name) or "") for name in ("mac", "serial_number", "hostname", "id", "ip"))
        if raw.strip("|"):
            signature = hashlib.sha256(raw.encode()).hexdigest()
    if not signature:
        return {"recorded": 0}
    now, recorded = time.time(), 0
    with connect(path) as db:
        for detail in device.get("open_port_details") or []:
            try:
                port, protocol = valid_port(detail.get("port")), valid_protocol(detail.get("protocol") or "tcp")
            except ValueError:
                continue
            evidence = {name: detail.get(name) for name in (
                "service", "description", "http_title", "http_server", "tls_certificate"
            ) if detail.get(name) not in (None, "")}
            existing = db.execute(
                "SELECT * FROM model_profile_observations WHERE profile_id=? AND device_signature=? AND port=? AND protocol=?",
                (profile_id, signature, port, protocol),
            ).fetchone()
            if existing:
                db.execute(
                    """
                    UPDATE model_profile_observations SET service=?, firmware=?,
                      hardware_revision=?, evidence_json=?, observations=observations+1,
                      last_seen=? WHERE id=?
                    """,
                    (
                        clean(detail.get("service"), 200), applied["identity"]["firmware"],
                        applied["identity"]["hardware_revision"], json.dumps(evidence, sort_keys=True),
                        now, existing["id"],
                    ),
                )
            else:
                db.execute(
                    """
                    INSERT INTO model_profile_observations (
                      profile_id, device_signature, port, protocol, service,
                      firmware, hardware_revision, evidence_json,
                      observations, first_seen, last_seen
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        profile_id, signature, port, protocol, clean(detail.get("service"), 200),
                        applied["identity"]["firmware"], applied["identity"]["hardware_revision"],
                        json.dumps(evidence, sort_keys=True), now, now,
                    ),
                )
            recorded += 1
    return {"recorded": recorded, "profile_id": profile_id}


def fleet_summary(path, inventory, profile_id):
    profile = profile_detail(path, profile_id)
    devices, port_counts, firmware_counts = [], {}, {}
    for raw in inventory or []:
        result = apply_device_profile(path, raw)
        if profile["id"] not in {item["id"] for item in result["profiles"]}:
            continue
        device = result["device"]
        firmware = result["identity"]["firmware"] or "Unknown"
        firmware_counts[firmware] = firmware_counts.get(firmware, 0) + 1
        observed = sorted({
            (int(item.get("port")), key(item.get("protocol") or "tcp"))
            for item in device.get("open_port_details") or [] if item.get("port")
        })
        for item in observed:
            port_counts[item] = port_counts.get(item, 0) + 1
        devices.append({
            "id": device.get("id"), "ip": device.get("ip"),
            "display_name": device.get("display_name") or device.get("name")
            or device.get("hostname") or device.get("ip") or "Unknown device",
            "firmware": firmware,
            "hardware_revision": result["identity"]["hardware_revision"],
            "drift": result["drift"],
            "observed_ports": [{"port": item[0], "protocol": item[1]} for item in observed],
        })
    common = [
        {"port": item[0], "protocol": item[1], "devices": count}
        for item, count in sorted(port_counts.items(), key=lambda entry: (-entry[1], entry[0][1], entry[0][0]))
    ]
    return {
        "profile": profile, "device_count": len(devices), "devices": devices,
        "common_ports": common, "firmware_counts": firmware_counts,
        "drifted_devices": len([item for item in devices if not item["drift"]["matches_profile"]]),
    }


def investigate_port(path, device, port, protocol="tcp", safe_probes=None, peers=None):
    port, protocol = valid_port(port), valid_protocol(protocol)
    detail = next((item for item in device.get("open_port_details") or []
                   if int(item.get("port") or 0) == port
                   and key(item.get("protocol") or "tcp") == protocol), {})
    service_probe = next((item for item in (safe_probes or {}).get("services") or []
                          if int(item.get("port") or 0) == port), {})
    evidence, suggestions = [], []
    http = service_probe.get("http") or {}
    if http.get("title") or http.get("server"):
        evidence.append(f"HTTP response: {clean(http.get('title') or http.get('server'), 300)}")
        suggestions.append("HTTP management or diagnostic service")
    if service_probe.get("banner"):
        evidence.append(f"Banner: {clean(service_probe['banner'], 300)}")
        suggestions.append(f"{clean(service_probe['banner'], 120).split()[0]} service")
    if service_probe.get("rtsp") and not service_probe["rtsp"].get("error"):
        evidence.append("RTSP protocol response")
        suggestions.append("RTSP media service")
    if service_probe.get("mqtt") and not service_probe["mqtt"].get("error"):
        evidence.append("MQTT protocol response")
        suggestions.append("MQTT broker")
    if detail.get("service") and key(detail.get("service")) not in {"unknown", "unknown service", "unassigned"}:
        evidence.append(f"Scanner identified {detail['service']}")
        suggestions.append(detail["service"])
    peer_matches = []
    for peer in peers or []:
        peer_detail = next((item for item in peer.get("open_port_details") or []
                            if int(item.get("port") or 0) == port
                            and key(item.get("protocol") or "tcp") == protocol), None)
        if peer_detail:
            peer_matches.append({
                "model": peer.get("model"),
                "firmware": peer.get("firmware") or peer.get("firmware_version"),
                "service": peer_detail.get("service"),
            })
    if peer_matches:
        evidence.append(f"Observed on {len(peer_matches)} peer device(s)")
    found = identity(device)
    suggested = suggestions[0] if suggestions else "Model-specific service"
    confidence = "high" if len(evidence) >= 3 else "medium" if evidence else "low"
    query = " ".join(filter(None, [
        found["manufacturer"], found["model"], found["firmware"],
        f"port {port}", protocol, "service",
    ]))
    return {
        "port": port, "protocol": protocol, "identity": found,
        "suggested_service": suggested, "confidence": confidence,
        "evidence": evidence, "peer_observations": peer_matches,
        "research_query": query,
        "recommended_actions": [
            "Check vendor manuals and support documentation.",
            "Confirm whether the service is LAN-only and authenticated.",
            "Save a model rule when the meaning and applicability are verified.",
            "Use a device-specific override when this is local configuration rather than model behaviour.",
        ],
    }


def conflicts(path, profile_id=None, status="open"):
    with connect(path) as db:
        if profile_id:
            rows = db.execute(
                "SELECT * FROM model_profile_conflicts WHERE profile_id=? AND status=? ORDER BY created_at DESC",
                (int(profile_id), status),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM model_profile_conflicts WHERE status=? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
    return [_row(row) for row in rows]


def resolve_conflict(path, conflict_id, choice, actor="", note=""):
    choice = key(choice)
    if choice not in {"current", "incoming"}:
        raise ValueError("Conflict resolution must keep current or accept incoming")
    with connect(path) as db:
        conflict = db.execute(
            "SELECT * FROM model_profile_conflicts WHERE id=? AND status='open'",
            (int(conflict_id),),
        ).fetchone()
        if not conflict:
            raise ValueError("Profile conflict was not found")
        current = _json(conflict["current_json"], {})
        incoming = _json(conflict["incoming_json"], {})
        profile_id = conflict["profile_id"]
        if choice == "incoming":
            db.execute(
                """
                UPDATE model_profile_ports SET
                  service=?, description=?, classification=?, exposure=?,
                  authentication_expected=?, encryption_expected=?, risk=?,
                  remediation=?, source_name=?, source_url=?, source_reliability=?,
                  confidence=?, updated_at=? WHERE id=?
                """,
                (
                    incoming.get("service", ""), incoming.get("description", ""),
                    incoming.get("classification", "expected"), incoming.get("exposure", "unknown"),
                    int(bool(incoming.get("authentication_expected"))),
                    int(bool(incoming.get("encryption_expected"))), incoming.get("risk", "info"),
                    incoming.get("remediation", ""), incoming.get("source_name", ""),
                    incoming.get("source_url", ""), int(incoming.get("source_reliability") or 50),
                    incoming.get("confidence", "confirmed"), time.time(), current["id"],
                ),
            )
        db.execute(
            "UPDATE model_profile_conflicts SET status='resolved', resolution_note=?, resolved_at=? WHERE id=?",
            (clean(note or f"{choice} selected by {actor}", 1000), time.time(), int(conflict_id)),
        )
        _record_revision(db, profile_id, "conflict-resolved", actor, f"Conflict {conflict_id}: {choice}")
    return profile_detail(path, profile_id)


def revision_history(path, profile_id):
    with connect(path) as db:
        rows = db.execute(
            "SELECT * FROM model_profile_revisions WHERE profile_id=? ORDER BY revision DESC",
            (int(profile_id),),
        ).fetchall()
    return [_row(row) for row in rows]


def rollback(path, profile_id, revision, actor="", note=""):
    with connect(path) as db:
        row = db.execute(
            "SELECT * FROM model_profile_revisions WHERE profile_id=? AND revision=?",
            (int(profile_id), int(revision)),
        ).fetchone()
        if not row:
            raise ValueError("Profile revision was not found")
        snapshot = _json(row["snapshot_json"], {})
        profile, ports = snapshot.get("profile") or {}, snapshot.get("ports") or []
        if not profile:
            raise ValueError("Profile revision snapshot is incomplete")
        db.execute(
            """
            UPDATE model_profiles SET
              scope=?, manufacturer_key=?, model_key=?, family_key=?,
              manufacturer=?, model=?, family=?, hardware_revision=?,
              firmware_min=?, firmware_max=?, aliases_json=?,
              manufacturer_aliases_json=?, notes=?, risk_notes=?,
              status='active', updated_at=? WHERE id=?
            """,
            (
                profile["scope"], profile["manufacturer_key"], profile["model_key"],
                profile["family_key"], profile["manufacturer"], profile["model"],
                profile["family"], profile["hardware_revision"], profile["firmware_min"],
                profile["firmware_max"], json.dumps(profile.get("aliases") or []),
                json.dumps(profile.get("manufacturer_aliases") or []), profile.get("notes") or "",
                profile.get("risk_notes") or "", time.time(), int(profile_id),
            ),
        )
        db.execute(
            "UPDATE model_profile_ports SET status='rollback-replaced', updated_at=? WHERE profile_id=? AND status='active'",
            (time.time(), int(profile_id)),
        )
        for item in ports:
            db.execute(
                """
                INSERT INTO model_profile_ports (
                  profile_id, port, protocol, service, description,
                  classification, exposure, authentication_expected,
                  encryption_expected, risk, remediation, hardware_revision,
                  firmware_min, firmware_max, source_name, source_url,
                  source_reliability, confidence, status, last_verified_at,
                  expires_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
                """,
                (
                    int(profile_id), item["port"], item["protocol"], item["service"],
                    item.get("description") or "", item.get("classification") or "expected",
                    item.get("exposure") or "unknown", int(bool(item.get("authentication_expected"))),
                    int(bool(item.get("encryption_expected"))), item.get("risk") or "info",
                    item.get("remediation") or "", item.get("hardware_revision") or "",
                    item.get("firmware_min") or "", item.get("firmware_max") or "",
                    item.get("source_name") or "", item.get("source_url") or "",
                    int(item.get("source_reliability") or 50), item.get("confidence") or "confirmed",
                    item.get("last_verified_at"), item.get("expires_at"),
                    item.get("created_at") or time.time(), time.time(),
                ),
            )
        _record_revision(db, int(profile_id), "profile-rollback", actor, note or f"Rolled back to revision {revision}")
    return profile_detail(path, profile_id)


def _canonical_registry_content(payload):
    content = copy.deepcopy(payload)
    manifest = content.setdefault("manifest", {})
    manifest.pop("digest", None)
    manifest.pop("signature", None)
    return json.dumps(content, sort_keys=True, separators=(",", ":")).encode()


def trusted_keys(value=None):
    raw = value if value is not None else os.environ.get("MOBILE_ROUTER_MODEL_REGISTRY_KEYS", "")
    if not raw:
        return {}
    if isinstance(raw, dict):
        return {str(name): str(secret) for name, secret in raw.items()}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("MOBILE_ROUTER_MODEL_REGISTRY_KEYS must be JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("MOBILE_ROUTER_MODEL_REGISTRY_KEYS must be an object")
    return {str(name): str(secret) for name, secret in parsed.items()}


def export_registry(path, *, publisher="local", version="", signing_key=None):
    profiles = []
    for summary in list_profiles(path):
        detail = profile_detail(path, summary["id"])
        detail.pop("conflicts", None)
        profiles.append(detail)
    payload = {
        "schema": SCHEMA,
        "manifest": {
            "publisher": clean(publisher, 200) or "local",
            "version": clean(version, 120) or time.strftime("%Y.%m.%d.%H%M"),
            "published_at": time.time(),
            "algorithm": "hmac-sha256" if signing_key else "sha256",
        },
        "profiles": profiles,
    }
    canonical = _canonical_registry_content(payload)
    payload["manifest"]["digest"] = hashlib.sha256(canonical).hexdigest()
    if signing_key:
        payload["manifest"]["signature"] = hmac.new(
            str(signing_key).encode(), canonical, hashlib.sha256
        ).hexdigest()
    return payload


def verify_registry(payload, trusted=None, require_signature=False):
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise ValueError(f"Registry must use schema {SCHEMA}")
    if not isinstance(payload.get("profiles"), list):
        raise ValueError("Registry must contain a profiles list")
    manifest = payload.get("manifest") or {}
    expected_digest = clean(manifest.get("digest"), 128)
    canonical = _canonical_registry_content(payload)
    actual_digest = hashlib.sha256(canonical).hexdigest()
    if not expected_digest or not hmac.compare_digest(expected_digest, actual_digest):
        raise ValueError("Registry digest verification failed")
    signature = clean(manifest.get("signature"), 256)
    publisher = clean(manifest.get("publisher"), 200)
    keys = trusted_keys(trusted)
    if signature:
        secret = keys.get(publisher)
        if not secret:
            raise ValueError(f"No trusted signing key is configured for {publisher}")
        expected = hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Registry signature verification failed")
        signature_status = "verified"
    elif require_signature:
        raise ValueError("A signed registry is required")
    else:
        signature_status = "unsigned"
    return {
        "publisher": publisher,
        "version": clean(manifest.get("version"), 120),
        "digest": actual_digest, "signature_status": signature_status,
        "profile_count": len(payload["profiles"]),
    }


def import_registry(
    path, payload, *, actor="registry-import", source_url="", trusted=None,
    require_signature=False, preview=False,
):
    verification = verify_registry(payload, trusted, require_signature)
    imported, conflict_count, errors = 0, 0, []
    for index, raw_profile in enumerate(payload["profiles"][:5000]):
        try:
            profile = upsert_profile(
                path, manufacturer=raw_profile.get("manufacturer"),
                model=raw_profile.get("model"), family=raw_profile.get("family"),
                scope=raw_profile.get("scope") or "exact",
                hardware_revision=raw_profile.get("hardware_revision"),
                firmware_min=raw_profile.get("firmware_min"),
                firmware_max=raw_profile.get("firmware_max"),
                aliases=raw_profile.get("aliases"),
                manufacturer_aliases=raw_profile.get("manufacturer_aliases"),
                notes=raw_profile.get("notes"), risk_notes=raw_profile.get("risk_notes"),
                actor=actor,
            )
            for rule in raw_profile.get("ports") or []:
                result = add_port_rule(
                    path, profile_id=profile["id"], port=rule.get("port"),
                    protocol=rule.get("protocol") or "tcp", service=rule.get("service"),
                    description=rule.get("description"),
                    classification=rule.get("classification") or "expected",
                    exposure=rule.get("exposure") or "unknown",
                    authentication_expected=rule.get("authentication_expected"),
                    encryption_expected=rule.get("encryption_expected"),
                    risk=rule.get("risk") or "info", remediation=rule.get("remediation"),
                    hardware_revision=rule.get("hardware_revision"),
                    firmware_min=rule.get("firmware_min"), firmware_max=rule.get("firmware_max"),
                    source_name=rule.get("source_name") or verification["publisher"],
                    source_url=rule.get("source_url") or source_url,
                    source_reliability=rule.get("source_reliability") or 60,
                    confidence=rule.get("confidence") or "registry", actor=actor,
                    allow_replace=False,
                )
                if result.get("status") == "conflict":
                    conflict_count += 1
            imported += 1
        except (TypeError, ValueError, KeyError) as exc:
            errors.append({"index": index, "message": clean(exc, 500)})
    result = {
        "verification": verification, "imported": imported,
        "conflicts": conflict_count, "errors": errors[:100],
    }
    if preview:
        result["would_import"] = result.pop("imported")
        result["would_conflict"] = result.pop("conflicts")
        return result
    with connect(path) as db:
        db.execute(
            """
            INSERT INTO model_registry_imports (
              publisher, version, digest, signature_status, source_url,
              imported, conflicts, errors_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                verification["publisher"], verification["version"], verification["digest"],
                verification["signature_status"], clean(source_url, 1200), imported,
                conflict_count, json.dumps(errors[:100]), time.time(),
            ),
        )
    return result


def public_https_url(url):
    parsed = urlparse(str(url or ""))
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Registry URLs must be credential-free HTTPS URLs")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443)}
    except OSError as exc:
        raise ValueError("Registry hostname could not be resolved") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise ValueError("Registry URL resolved to a non-public address")
    return str(url)


def configured_registry_urls(value=None):
    raw = value if value is not None else os.environ.get(
        "MOBILE_ROUTER_MODEL_REGISTRY_URLS",
        os.environ.get("MOBILE_ROUTER_PORT_REGISTRY_URLS", ""),
    )
    return [part.strip() for part in str(raw).split(",") if part.strip()]


def sync_registries(
    path, *, urls=None, opener=urlopen, trusted=None, require_signature=True,
):
    results = []
    for configured in urls or configured_registry_urls():
        try:
            url = public_https_url(configured)
            with opener(Request(url, headers={"User-Agent": "MobileRouterLab/2.0"}), timeout=12) as response:
                final_url = public_https_url(response.geturl())
                raw = response.read(_MAX_DOWNLOAD + 1)
            if len(raw) > _MAX_DOWNLOAD:
                raise ValueError("Registry download exceeded 2 MiB")
            payload = json.loads(raw.decode("utf-8"))
            imported = import_registry(
                path, payload, actor="registry-sync", source_url=final_url,
                trusted=trusted, require_signature=require_signature,
            )
            results.append({"url": final_url, "status": "success", **imported})
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            results.append({
                "url": clean(configured, 1200), "status": "error",
                "message": clean(exc, 500),
            })
    return results


def contribution_payload(path, profile_id, inventory=None):
    profile = profile_detail(path, profile_id)
    fleet = fleet_summary(path, inventory or [], profile_id)
    safe_profile = {name: profile.get(name) for name in (
        "scope", "manufacturer", "model", "family", "hardware_revision",
        "firmware_min", "firmware_max", "aliases", "manufacturer_aliases",
        "notes", "risk_notes",
    )}
    safe_ports = [{name: rule.get(name) for name in (
        "port", "protocol", "service", "description", "classification", "exposure",
        "authentication_expected", "encryption_expected", "risk", "remediation",
        "hardware_revision", "firmware_min", "firmware_max", "source_name",
        "source_url", "source_reliability", "confidence",
    )} for rule in profile["ports"]]
    return {
        "schema": "mobile-router-model-contribution-v1", "created_at": time.time(),
        "privacy": {"excluded": [
            "IP addresses", "MAC addresses", "serial numbers", "hostnames",
            "credentials", "private URLs",
        ]},
        "profile": safe_profile, "ports": safe_ports,
        "aggregate": {
            "observed_devices": fleet["device_count"],
            "firmware_counts": fleet["firmware_counts"],
            "common_ports": fleet["common_ports"],
        },
    }


def registry_import_history(path):
    with connect(path) as db:
        rows = db.execute(
            "SELECT * FROM model_registry_imports ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
    return [_row(row) for row in rows]
