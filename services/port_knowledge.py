"""Reusable model-specific port mappings and learned candidates."""

import hashlib
import ipaddress
import json
import os
import socket
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

SCHEMA = "mobile-router-port-knowledge-v1"
_GENERIC = {"", "unknown", "unknown service", "tcpwrapped", "unassigned", "model-specific service"}
_MAX_DOWNLOAD = 1_048_576


def database_path():
    return Path(os.environ.get("MOBILE_ROUTER_PORT_KNOWLEDGE_DB") or Path(__file__).resolve().parents[1] / "instance" / "device_port_knowledge.sqlite3")


def clean(value, limit=500):
    return " ".join(str(value or "").strip().split())[:limit]


def key(value):
    return clean(value).casefold()


def identity(device, manufacturer=None, model=None):
    device = device or {}
    assessment = device.get("identity_assessment") or {}
    manufacturer = clean(manufacturer or device.get("manufacturer") or assessment.get("manufacturer"), 160)
    model = clean(model or device.get("model") or assessment.get("model") or assessment.get("likely_device"), 200)
    if key(manufacturer) == "unknown":
        manufacturer = ""
    if key(model) in {"", "unknown", "unidentified network device", "client"}:
        model = ""
    return {"manufacturer": manufacturer, "model": model, "manufacturer_key": key(manufacturer), "model_key": key(model)}


def extract_identity(device, safe_probes=None, assessment=None):
    assessment = assessment or {}
    found = identity(device, model=assessment.get("model"))
    source = "inventory" if found["model"] else ""
    for item in (safe_probes or {}).get("upnp") or []:
        if not isinstance(item, dict) or item.get("error"):
            continue
        model = " ".join(filter(None, [clean(item.get("model_name"), 160), clean(item.get("model_number"), 100)]))
        if model:
            found = identity(device, manufacturer=item.get("manufacturer") or found["manufacturer"], model=model)
            source = "UPnP device description"
            break
    if not found["model"]:
        found = identity(device, model=assessment.get("likely_device"))
        source = "identity fingerprint" if found["model"] else ""
    found["source"] = source
    return found


def valid_port(value):
    try:
        value = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Port must be an integer") from exc
    if not 1 <= value <= 65535:
        raise ValueError("Port must be between 1 and 65535")
    return value


def valid_protocol(value):
    value = key(value or "tcp")
    if value not in {"tcp", "udp"}:
        raise ValueError("Protocol must be TCP or UDP")
    return value


def valid_url(value):
    value = str(value or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Source URL must be HTTP or HTTPS")
    return value[:1000]


def connect(path=None):
    path = Path(path or database_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.executescript("""
      CREATE TABLE IF NOT EXISTS port_knowledge (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        manufacturer_key TEXT NOT NULL, model_key TEXT NOT NULL,
        manufacturer TEXT NOT NULL, model TEXT NOT NULL,
        port INTEGER NOT NULL, protocol TEXT NOT NULL,
        service TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
        source_name TEXT NOT NULL DEFAULT '', source_url TEXT NOT NULL DEFAULT '',
        confidence TEXT NOT NULL DEFAULT 'candidate', status TEXT NOT NULL DEFAULT 'candidate',
        verified_by TEXT NOT NULL DEFAULT '', observations INTEGER NOT NULL DEFAULT 1,
        signatures_json TEXT NOT NULL DEFAULT '[]', evidence_json TEXT NOT NULL DEFAULT '{}',
        created_at REAL NOT NULL, updated_at REAL NOT NULL,
        UNIQUE(manufacturer_key, model_key, port, protocol, service, status)
      );
      CREATE INDEX IF NOT EXISTS port_knowledge_model
        ON port_knowledge(manufacturer_key, model_key, status, protocol, port);
    """)
    return db


def row_dict(row):
    if not row:
        return None
    item = dict(row)
    item["signatures"] = json.loads(item.pop("signatures_json") or "[]")
    item["evidence"] = json.loads(item.pop("evidence_json") or "{}")
    item["distinct_devices"] = len(item["signatures"])
    return item


def mappings(path, manufacturer, model):
    ident = identity({}, manufacturer, model)
    if not ident["model_key"]:
        return []
    with connect(path) as db:
        rows = db.execute("SELECT * FROM port_knowledge WHERE manufacturer_key=? AND model_key=? AND status='approved' ORDER BY protocol,port", (ident["manufacturer_key"], ident["model_key"])).fetchall()
    return [row_dict(row) for row in rows]


def candidates(path, manufacturer, model):
    ident = identity({}, manufacturer, model)
    if not ident["model_key"]:
        return []
    with connect(path) as db:
        rows = db.execute("SELECT * FROM port_knowledge WHERE manufacturer_key=? AND model_key=? AND status='candidate' ORDER BY observations DESC,protocol,port", (ident["manufacturer_key"], ident["model_key"])).fetchall()
    return [row_dict(row) for row in rows]


def add_mapping(path, *, manufacturer, model, port, service, protocol="tcp", description="", source_name="", source_url="", confidence="confirmed", verified_by="", observations=1, signatures=None):
    ident = identity({}, manufacturer, model)
    if not ident["model_key"]:
        raise ValueError("An exact or reusable device model is required")
    service = clean(service, 160)
    if not service:
        raise ValueError("Service name is required")
    port, protocol, now = valid_port(port), valid_protocol(protocol), time.time()
    signatures = sorted(set(signatures or []))
    with connect(path) as db:
        db.execute("DELETE FROM port_knowledge WHERE manufacturer_key=? AND model_key=? AND port=? AND protocol=? AND status='approved'", (ident["manufacturer_key"], ident["model_key"], port, protocol))
        cursor = db.execute("""
          INSERT INTO port_knowledge (
            manufacturer_key,model_key,manufacturer,model,port,protocol,service,description,
            source_name,source_url,confidence,status,verified_by,observations,signatures_json,
            evidence_json,created_at,updated_at
          ) VALUES (?,?,?,?,?,?,?,?,?,?,?,'approved',?,?,?,?,?,?)
        """, (
            ident["manufacturer_key"], ident["model_key"], ident["manufacturer"], ident["model"],
            port, protocol, service, clean(description,1000), clean(source_name,200),
            valid_url(source_url), key(confidence or "confirmed"), clean(verified_by,160),
            max(1,int(observations)), json.dumps(signatures), "{}", now, now,
        ))
        row = db.execute("SELECT * FROM port_knowledge WHERE id=?", (cursor.lastrowid,)).fetchone()
    return row_dict(row)


def _signature(device):
    value = clean((device or {}).get("identity_signature"))
    if value:
        return value
    raw = "|".join(str((device or {}).get(name) or "") for name in ("mac","serial_number","hostname","id","ip"))
    return hashlib.sha256(raw.encode()).hexdigest() if raw.strip("|") else ""


def _probe(safe_probes, port):
    for item in (safe_probes or {}).get("services") or []:
        try:
            if int(item.get("port")) == port:
                return item
        except (TypeError, ValueError):
            pass
    return {}


def suggestion(detail, probe, protocol):
    service = clean(detail.get("service"),160)
    if key(service) not in _GENERIC:
        return service, clean(detail.get("description"),500), True
    http = probe.get("http") or {}
    if http.get("title") or http.get("server"):
        return "HTTP management service", clean(http.get("title") or http.get("server"),300), True
    if probe.get("rtsp") and not probe["rtsp"].get("error"):
        return "RTSP media service", clean(probe["rtsp"].get("server") or probe["rtsp"].get("status"),300), True
    if probe.get("mqtt") and not probe["mqtt"].get("error"):
        return "MQTT broker", clean(json.dumps(probe["mqtt"],sort_keys=True),300), True
    if probe.get("banner"):
        banner = clean(probe["banner"],300)
        return f"{banner.split()[0][:80]} service", banner, True
    try:
        name = socket.getservbyport(valid_port(detail.get("port")), protocol)
    except (OSError, ValueError):
        name = ""
    return (name, "Suggested by the host services database.", True) if name else ("Model-specific service", "", False)


def observe(path, device, safe_probes=None):
    ident = identity(device)
    if not ident["model_key"]:
        return {"observed":0,"promoted":[],"candidates":[]}
    known = {(item["port"],item["protocol"]) for item in mappings(path,ident["manufacturer"],ident["model"])}
    signature, now, promote = _signature(device), time.time(), []
    with connect(path) as db:
        for detail in (device or {}).get("open_port_details") or []:
            try:
                port, protocol = valid_port(detail.get("port")), valid_protocol(detail.get("protocol") or "tcp")
            except ValueError:
                continue
            if (port,protocol) in known:
                continue
            service, description, promotable = suggestion(detail,_probe(safe_probes,port),protocol)
            row = db.execute("SELECT * FROM port_knowledge WHERE manufacturer_key=? AND model_key=? AND port=? AND protocol=? AND service=? AND status='candidate'", (ident["manufacturer_key"],ident["model_key"],port,protocol,service)).fetchone()
            signatures = set(json.loads(row["signatures_json"] or "[]")) if row else set()
            if signature:
                signatures.add(signature)
            observations = (row["observations"]+1) if row else 1
            evidence = {"scan":{k:detail.get(k) for k in ("service","description","http_title","http_server") if detail.get(k) not in (None,"")},"probe":_probe(safe_probes,port)}
            if row:
                db.execute("UPDATE port_knowledge SET description=?,observations=?,signatures_json=?,evidence_json=?,updated_at=? WHERE id=?", (description or row["description"],observations,json.dumps(sorted(signatures)),json.dumps(evidence,sort_keys=True),now,row["id"]))
            else:
                db.execute("""
                  INSERT INTO port_knowledge (
                    manufacturer_key,model_key,manufacturer,model,port,protocol,service,description,
                    source_name,confidence,status,observations,signatures_json,evidence_json,created_at,updated_at
                  ) VALUES (?,?,?,?,?,?,?,?,?,'candidate','candidate',?,?,?,?,?)
                """, (ident["manufacturer_key"],ident["model_key"],ident["manufacturer"],ident["model"],port,protocol,service,description,"automatic observation",observations,json.dumps(sorted(signatures)),json.dumps(evidence,sort_keys=True),now,now))
            if promotable and len(signatures)>=2:
                promote.append((port,protocol,service,description,observations,sorted(signatures)))
    promoted=[]
    for port,protocol,service,description,observations,signatures in promote:
        promoted.append(add_mapping(path,manufacturer=ident["manufacturer"],model=ident["model"],port=port,protocol=protocol,service=service,description=description,source_name="Automatic repeated observation",confidence="learned",observations=observations,signatures=signatures))
        with connect(path) as db:
            db.execute("UPDATE port_knowledge SET status='approved-observation',updated_at=? WHERE manufacturer_key=? AND model_key=? AND port=? AND protocol=? AND service=? AND status='candidate'", (time.time(),ident["manufacturer_key"],ident["model_key"],port,protocol,service))
    return {"observed":len((device or {}).get("open_port_details") or []),"promoted":promoted,"candidates":candidates(path,ident["manufacturer"],ident["model"])}


def apply(path, device):
    ident = identity(device)
    known = {(item["port"],item["protocol"]):item for item in mappings(path,ident["manufacturer"],ident["model"])}
    updated, applied = dict(device or {}), []
    details=[]
    for raw in updated.get("open_port_details") or []:
        detail=dict(raw)
        for name in list(detail):
            if name.startswith("knowledge_"):
                detail.pop(name,None)
        try:
            mapping=known.get((valid_port(detail.get("port")),valid_protocol(detail.get("protocol") or "tcp")))
        except ValueError:
            mapping=None
        if mapping:
            detail.update({
              "knowledge_mapping_id":mapping["id"],"knowledge_service":mapping["service"],
              "knowledge_description":mapping["description"],"knowledge_source_name":mapping["source_name"],
              "knowledge_source_url":mapping["source_url"],"knowledge_confidence":mapping["confidence"],
              "knowledge_model":mapping["model"],
            })
            if key(detail.get("service")) in _GENERIC:
                detail["service"]=mapping["service"]
            if not clean(detail.get("description")):
                detail["description"]=mapping["description"]
            applied.append(mapping)
        details.append(detail)
    updated["open_port_details"]=details
    if ident["model"]:
        updated["model"],updated["port_knowledge_applied_at"]=ident["model"],time.time()
    return {"device":updated,"applied":applied,"identity":ident}


def process(path, device, safe_probes=None):
    applied=apply(path,device)
    learned=observe(path,applied["device"],safe_probes)
    if learned["promoted"]:
        applied=apply(path,applied["device"])
    return {**applied,"learning":learned}


def approve(path, candidate_id, verified_by="", source_url=""):
    with connect(path) as db:
        row=db.execute("SELECT * FROM port_knowledge WHERE id=? AND status='candidate'",(int(candidate_id),)).fetchone()
    if not row:
        raise ValueError("Port knowledge candidate was not found")
    return add_mapping(path,manufacturer=row["manufacturer"],model=row["model"],port=row["port"],protocol=row["protocol"],service=row["service"],description=row["description"],source_name=row["source_name"] or "Approved local observation",source_url=source_url or row["source_url"],verified_by=verified_by,observations=row["observations"],signatures=json.loads(row["signatures_json"] or "[]"))


def delete(path, mapping_id):
    with connect(path) as db:
        return db.execute("DELETE FROM port_knowledge WHERE id=? AND status='approved'",(int(mapping_id),)).rowcount>0


def export_registry(path):
    with connect(path) as db:
        rows=db.execute("SELECT * FROM port_knowledge WHERE status='approved' ORDER BY manufacturer_key,model_key,protocol,port").fetchall()
    items=[]
    for row in rows:
        item=row_dict(row)
        for name in ("id","manufacturer_key","model_key","status","evidence","signatures"):
            item.pop(name,None)
        items.append(item)
    return {"schema":SCHEMA,"exported_at":time.time(),"mappings":items}


def import_registry(path,payload,source_name="",source_url="",verified_by=""):
    if not isinstance(payload,dict) or payload.get("schema")!=SCHEMA or not isinstance(payload.get("mappings"),list):
        raise ValueError(f"Registry must use schema {SCHEMA} and contain a mappings list")
    imported,errors=0,[]
    for index,item in enumerate(payload["mappings"][:10000]):
        try:
            add_mapping(path,manufacturer=item.get("manufacturer"),model=item.get("model"),port=item.get("port"),protocol=item.get("protocol") or "tcp",service=item.get("service"),description=item.get("description") or "",source_name=item.get("source_name") or source_name,source_url=item.get("source_url") or source_url,confidence=item.get("confidence") or "vendor",verified_by=item.get("verified_by") or verified_by,observations=item.get("observations") or 1,signatures=item.get("signatures") or [])
            imported+=1
        except (TypeError,ValueError) as exc:
            errors.append({"index":index,"message":clean(exc,300)})
    return {"imported":imported,"errors":errors[:100]}


def configured_urls(value=None):
    return [item.strip() for item in str(value if value is not None else os.environ.get("MOBILE_ROUTER_PORT_REGISTRY_URLS","")).split(",") if item.strip()]


def public_https_url(url):
    parsed=urlparse(str(url or ""))
    if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Registry URLs must be credential-free HTTPS URLs")
    try:
        addresses={item[4][0] for item in socket.getaddrinfo(parsed.hostname,parsed.port or 443)}
    except OSError as exc:
        raise ValueError("Registry hostname could not be resolved") from exc
    if any((lambda ip: ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified)(ipaddress.ip_address(address)) for address in addresses):
        raise ValueError("Registry URL resolved to a non-public address")
    return str(url)


def sync(path,urls=None,opener=urlopen):
    results=[]
    for configured in urls or configured_urls():
        try:
            url=public_https_url(configured)
            with opener(Request(url,headers={"User-Agent":"MobileRouterLab/1.0"}),timeout=10) as response:
                final=public_https_url(response.geturl())
                raw=response.read(_MAX_DOWNLOAD+1)
            if len(raw)>_MAX_DOWNLOAD:
                raise ValueError("Registry download exceeded 1 MiB")
            result=import_registry(path,json.loads(raw.decode()),"Configured online registry",final,"registry-sync")
            results.append({"url":final,"status":"success",**result})
        except (OSError,UnicodeError,json.JSONDecodeError,ValueError) as exc:
            results.append({"url":clean(configured,1000),"status":"error","message":clean(exc,500)})
    return results
