from flask import Flask, Response, render_template, request, jsonify, send_from_directory, send_file, redirect, url_for, session
from flask_socketio import SocketIO
import os
import json
import time
import threading
import uuid
import asyncio
import re
import shutil
import subprocess
import csv
import io
import socket
import secrets
import hashlib
from functools import wraps
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from werkzeug.utils import secure_filename

from routes import register_blueprints
from services import device_intel
from services import inventory as inventory_service
from services import diagnostics as diagnostics_service
from services import port_scans as port_scan_service
from services import wireless_clients as wireless_client_service
from services import persistence as persistence_service
from services import oui as oui_service
from services import labs as labs_service
from services import reports as reports_service
from services import alerts as alerts_service
from services import evidence as evidence_service
from services import social_profiles as social_profile_service
from services import social_auth as social_auth_service
from scripts.interfaceTools import (
    get_bluetooth_devices,
    get_network_interfaces,
    spoof_mac,
)

from scripts.bluetooth_phone import (
    BluetoothPhoneSettingsError,
    bluetooth_pairing_mode_capability,
    bluetooth_phone_feature_options,
    build_settings as build_bluetooth_phone_settings,
    load_bluetooth_phone_settings,
)
from scripts.logging_config import configure_logging
from scripts.networkScan import (
    active_scan,
    passive_scan,
    packet_passive_scan,
    classify_scan_results,
    get_mac_by_ip,
    get_ip_by_mac,
)

lookup_manufacturer = oui_service.lookup_manufacturer


app = Flask(__name__)
app.secret_key = os.environ.get('MOBILE_ROUTER_SECRET_KEY') or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
log_path = configure_logging(app)
socketio = SocketIO(app)

# Fetch network interfaces at the start
network_interfaces = get_network_interfaces()
networkTechnologies = {iface.interface_type for iface in network_interfaces}
scan_jobs = {}
scan_jobs_lock = threading.Lock()
port_scan_jobs = {}
port_scan_jobs_lock = threading.Lock()
device_inventory = {}
device_inventory_lock = threading.Lock()
bluetooth_action_histories = {}
bluetooth_action_histories_lock = threading.Lock()
new_device_alerts = []
new_device_alerts_lock = threading.Lock()
evidence_vault = []
evidence_vault_lock = threading.Lock()
evil_twin_lab_runs = []
evil_twin_lab_lock = threading.Lock()
pineap_lab_runs = []
pineap_lab_lock = threading.Lock()
handshake_lab_records = []
handshake_lab_lock = threading.Lock()
social_profiles = {}
social_profiles_lock = threading.Lock()
social_users = {}
social_users_lock = threading.Lock()
social_audit_log = []
social_audit_lock = threading.Lock()
ping_history = []
vlan_segmentation_notes = []
watched_clients = set()
client_timelines = {}
client_timelines_lock = threading.Lock()
scheduled_client_checks = {}
wireless_network_client_cache = {}
wireless_network_labels = {}
passive_monitor_jobs = {}
passive_monitor_lock = threading.Lock()
passive_observation_analytics = {}
passive_analytics_lock = threading.Lock()
HTTP_PREVIEW_DIR = os.path.join(app.instance_path, 'http_previews')
EVIDENCE_DIR = os.path.join(app.instance_path, 'evidence_vault')
SOCIAL_PROFILE_PHOTO_DIR = os.path.join(app.instance_path, 'social_profile_photos')
SOCIAL_PROFILE_ATTACHMENT_DIR = os.path.join(app.instance_path, 'social_profile_attachments')
from app_support.identifiers import MAC_RE, inventory_key, normalize_mac


runtime_state_lock = threading.Lock()


def runtime_state_snapshot():
    """Build a durable snapshot of inventory/profile state worth keeping across restarts."""
    with device_inventory_lock:
        inventory = {key: dict(value) for key, value in device_inventory.items()}
    with new_device_alerts_lock:
        alerts = [dict(item) for item in new_device_alerts]
    with evidence_vault_lock:
        evidence = [dict(item) for item in evidence_vault]
    with client_timelines_lock:
        timelines = {key: [dict(item) for item in value] for key, value in client_timelines.items()}
    with social_profiles_lock:
        profiles = {key: dict(value) for key, value in social_profiles.items()}
    with social_users_lock:
        users = {key: dict(value) for key, value in social_users.items()}
    with social_audit_lock:
        audit = [dict(value) for value in social_audit_log]
    return {
        'device_inventory': inventory,
        'new_device_alerts': alerts,
        'evidence_vault': evidence,
        'watched_clients': sorted(watched_clients),
        'client_timelines': timelines,
        'scheduled_client_checks': dict(scheduled_client_checks),
        'wireless_network_client_cache': wireless_network_client_cache,
        'wireless_network_labels': dict(wireless_network_labels),
        'passive_observation_analytics': passive_observation_analytics,
        'bluetooth_action_histories': bluetooth_action_histories,
        'evil_twin_lab_runs': evil_twin_lab_runs,
        'pineap_lab_runs': pineap_lab_runs,
        'handshake_lab_records': handshake_lab_records,
        'social_profiles': profiles,
        'social_users': users,
        'social_audit_log': audit,
    }


def save_runtime_state(reason='state-update'):
    """Persist runtime state best-effort so scan profiles survive restarts."""
    try:
        with runtime_state_lock:
            return persistence_service.save_state({'reason': reason, **runtime_state_snapshot()})
    except OSError as exc:
        app.logger.warning('Unable to persist runtime state after %s: %s', reason, exc)
        return None


def load_runtime_state():
    """Load persisted runtime state into the in-memory stores on startup."""
    state = persistence_service.load_state()
    if not state:
        return None
    with device_inventory_lock:
        device_inventory.update(state.get('device_inventory') or {})
    with new_device_alerts_lock:
        new_device_alerts.extend(state.get('new_device_alerts') or [])
        del new_device_alerts[200:]
    with evidence_vault_lock:
        evidence_vault.extend(state.get('evidence_vault') or [])
    with client_timelines_lock:
        client_timelines.update(state.get('client_timelines') or {})
    watched_clients.update(state.get('watched_clients') or [])
    scheduled_client_checks.update(state.get('scheduled_client_checks') or {})
    wireless_network_client_cache.update(state.get('wireless_network_client_cache') or {})
    wireless_network_labels.update(state.get('wireless_network_labels') or {})
    passive_observation_analytics.update(state.get('passive_observation_analytics') or {})
    bluetooth_action_histories.update(state.get('bluetooth_action_histories') or {})
    evil_twin_lab_runs.extend(state.get('evil_twin_lab_runs') or [])
    pineap_lab_runs.extend(state.get('pineap_lab_runs') or [])
    handshake_lab_records.extend(state.get('handshake_lab_records') or [])
    with social_profiles_lock:
        social_profiles.update(state.get('social_profiles') or {})
    with social_users_lock:
        social_users.update(state.get('social_users') or {})
        legacy_owner = next(
            (user.get('username') for user in social_users.values() if user.get('role') == 'admin'),
            next(iter(social_users), None),
        )
    if legacy_owner:
        with social_profiles_lock:
            for profile in social_profiles.values():
                profile.setdefault('owner', legacy_owner)
    with social_audit_lock:
        social_audit_log.extend(state.get('social_audit_log') or [])
    return state


load_runtime_state()


from app_support.roadmap import ROADMAP_SECTIONS, remaining_roadmap_items


from app_support.bluetooth_actions import (
    BLUETOOTHCTL_ACTIONS,
    BLUETOOTH_MAC_RE,
    BluetoothToolUnavailable,
    _bluetooth_device_path_from_busctl,
    _bluetooth_truthy,
    _busctl_bluez_available,
    _run_busctl_bluetooth_action,
    bluetooth_action_capability,
    bluetooth_contextual_actions,
    bluetooth_device_state,
    run_bluetoothctl_action,
    set_interface_power_state,
)


def create_new_device_alert(device, source, interface=None):
    return alerts_service.create_new_device_alert(device, source, interface, new_device_alerts, new_device_alerts_lock)


def create_grouped_device_alert(devices, source, interface=None):
    return alerts_service.create_grouped_device_alert(devices, source, interface, new_device_alerts, new_device_alerts_lock)


def evidence_records():
    return evidence_service.evidence_records(evidence_vault, evidence_vault_lock)


def create_evidence_record(title, category='note', source=None, device=None, notes=None, content=None, uploaded_file=None):
    return evidence_service.create_evidence_record(
        title, category, source, device, notes, content, uploaded_file,
        EVIDENCE_DIR, evidence_vault, evidence_vault_lock, save_runtime_state, secure_filename,
    )


def evidence_as_csv(records):
    return evidence_service.evidence_as_csv(records)


def evidence_as_markdown(records):
    return evidence_service.evidence_as_markdown(records)


def bluetooth_device_summary(device):
    summary = device.to_dict() if hasattr(device, 'to_dict') else {
        'address': getattr(device, 'address', None),
        'name': getattr(device, 'name', None),
    }
    address = summary.get('address')
    summary['address'] = address
    summary['mac'] = normalize_mac(address) if address else None
    summary['manufacturer'] = summary.get('manufacturer') or lookup_manufacturer(address)
    summary['device_type'] = 'Bluetooth device'
    return {key: value for key, value in summary.items() if value not in (None, '')}


def find_inventory_device(identifier):
    normalized = normalize_mac(identifier) if identifier else None
    with device_inventory_lock:
        if normalized:
            for key in (f'mac:{normalized}', normalized):
                if key in device_inventory:
                    return dict(device_inventory[key])
            for item in device_inventory.values():
                if normalize_mac(item.get('mac') or item.get('address')) == normalized:
                    return dict(item)
        for item in device_inventory.values():
            if item.get('ip') == identifier or item.get('id') == identifier:
                return dict(item)
    return None


def bluetooth_adapter_choices():
    choices = []
    for iface in network_interfaces:
        if str(getattr(iface, 'interface_type', '')).casefold() != 'bluetooth':
            continue
        adapter_id = None
        if hasattr(iface, 'get_mac_address'):
            adapter_id = iface.get_mac_address()
        adapter_id = adapter_id or getattr(iface, 'name', None)
        if adapter_id:
            choices.append({'id': adapter_id, 'name': getattr(iface, 'name', adapter_id), 'state': getattr(iface, 'state', None)})
    return choices


def bluetooth_action_history(address):
    normalized = normalize_mac(address) if address else None
    with bluetooth_action_histories_lock:
        return list(bluetooth_action_histories.get(normalized or address, []))


def record_bluetooth_action_history(address, action, status, message, adapter=None):
    normalized = normalize_mac(address) if address else address
    if not normalized:
        return []
    entry = {
        'time': time.time(),
        'time_label': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
        'action': action,
        'status': status,
        'message': message,
        'adapter': adapter,
    }
    with bluetooth_action_histories_lock:
        history = list(bluetooth_action_histories.get(normalized, []))
        history.insert(0, entry)
        bluetooth_action_histories[normalized] = history[:20]
        return list(bluetooth_action_histories[normalized])


def _merge_inventory_device_state(address, updates):
    normalized = normalize_mac(address) if address else None
    if not normalized:
        return find_inventory_device(address)
    with device_inventory_lock:
        key = f'mac:{normalized}'
        existing_key = key if key in device_inventory else None
        if existing_key is None:
            for candidate_key, item in device_inventory.items():
                if normalize_mac(item.get('mac') or item.get('address')) == normalized:
                    existing_key = candidate_key
                    break
        if existing_key is None:
            existing_key = key
            device_inventory[existing_key] = {'id': key, 'mac': normalized, 'address': normalized, 'device_type': 'Bluetooth device', 'sources': ['bluetooth-action'], 'interfaces': []}
        device_inventory[existing_key].update({k: v for k, v in updates.items() if v is not None})
        device_inventory[existing_key]['last_seen'] = time.time()
        return dict(device_inventory[existing_key])


def _bluetooth_state_updates_for_action(action):
    return {
        'connect': {'connected': True},
        'disconnect': {'connected': False},
        'pair': {'paired': True},
        'trust': {'trusted': True},
        'untrust': {'trusted': False},
        'block': {'blocked': True},
        'unblock': {'blocked': False},
        'remove': {'paired': False, 'connected': False, 'trusted': False},
    }.get(action, {})


def _parse_bluetooth_info_output(output):
    updates = {}
    for line in str(output or '').splitlines():
        if ':' not in line:
            continue
        key, value = [part.strip() for part in line.split(':', 1)]
        key = key.casefold()
        value_bool = _bluetooth_truthy(value)
        if key in {'connected', 'paired', 'trusted', 'blocked'}:
            updates[key] = value_bool
        elif key in {'name', 'alias'} and value:
            updates['name'] = value
    return updates

def forget_inventory_device(identifier):
    normalized = normalize_mac(identifier) if identifier else None
    removed = None
    with device_inventory_lock:
        keys = []
        if normalized:
            keys.extend([f'mac:{normalized}', normalized])
        keys.append(identifier)
        for key in keys:
            if key in device_inventory:
                removed = device_inventory.pop(key)
                break
        if removed is None and normalized:
            for key, item in list(device_inventory.items()):
                if normalize_mac(item.get('mac') or item.get('address')) == normalized:
                    removed = device_inventory.pop(key)
                    break
    return removed

def bluetooth_detail_fields(device):
    skip = {
        'id', 'name', 'display_name', 'ip', 'mac', 'address', 'manufacturer',
        'first_seen', 'last_seen', 'sources', 'interfaces', 'is_unknown_manufacturer',
    }
    labels = {
        'status': 'Status',
        'instance_id': 'Windows Instance ID',
        'device_class': 'Device Class',
        'service': 'Service',
        'pnp_manufacturer': 'PnP Manufacturer',
        'rssi': 'RSSI',
        'details': 'Adapter Details',
        'device_type': 'Device Type',
    }
    fields = []
    for key, value in sorted((device or {}).items()):
        if key in skip or value in (None, ''):
            continue
        if isinstance(value, (list, tuple, set)):
            value = ', '.join(str(item) for item in value if item not in (None, ''))
        elif isinstance(value, dict):
            value = json.dumps(value, sort_keys=True)
        fields.append({'label': labels.get(key, key.replace('_', ' ').title()), 'value': value})
    return fields

def alert_records():
    return alerts_service.alert_records(new_device_alerts, new_device_alerts_lock)


def unread_alert_count():
    return alerts_service.unread_alert_count(new_device_alerts, new_device_alerts_lock)


def record_inventory_devices(devices, source, interface=None):
    merged = inventory_service.merge_devices(
        devices, source, interface, device_inventory, device_inventory_lock,
        normalize_mac, inventory_key, lookup_manufacturer,
        create_new_device_alert, create_grouped_device_alert,
    )
    if merged:
        save_runtime_state(f'inventory:{source}')
    return merged


def record_device_open_ports(host, port_details, source='port-scan'):
    updated = inventory_service.record_open_ports(
        host, port_details, source, device_inventory, device_inventory_lock,
        enrich_port_web_url, append_client_timeline_event, is_client_watched,
        create_client_watch_alert,
    )
    if updated:
        role_guess = device_intel.infer_device_role(updated)
        with device_inventory_lock:
            key = updated.get('id')
            if key in device_inventory:
                device_inventory[key]['device_role_guess'] = role_guess
                updated = dict(device_inventory[key])
        save_runtime_state(f'ports:{source}')
    return updated


def enrich_port_web_url(host, detail):
    """Attach a clickable web URL for HTTP-like TCP services."""
    item = dict(detail)
    service = str(item.get('service') or '').lower()
    port = int(item.get('port'))
    if port in {80, 8080, 8000} or service.startswith('http '):
        item['web_url'] = f"http://{host}:{port}/"
    elif port in {443, 8443, 9443} or service.startswith('https'):
        item['web_url'] = f"https://{host}:{port}/"
    return item


def enrich_web_port_metadata(host, detail):
    """Add lightweight HTTP status/title metadata for clickable web services."""
    item = enrich_port_web_url(host, detail)
    if not item.get('web_url'):
        return item
    try:
        inspected = inspect_http_services(host, [item['port']])[0]
    except (IndexError, OSError, ValueError):
        return item
    for key in ('status', 'title', 'server', 'error', 'thumbnail_url', 'favicon'):
        if inspected.get(key) not in (None, ''):
            item[f'http_{key}'] = inspected.get(key)
    if item.get('web_url', '').startswith('https://'):
        tls_metadata = device_intel.tls_certificate_metadata(host, item['port'])
        if tls_metadata:
            item['tls_certificate'] = tls_metadata
    return item


def _clean_detected_client_name(name, ip=None):
    """Normalize display names learned from local naming protocols."""
    value = str(name or '').strip().strip('.')
    if not value or value == str(ip or ''):
        return ''
    if value.endswith('.local'):
        return value
    return value[:120]


def _reverse_dns_display_name(ip):
    """Attempt a reverse-DNS/PTR lookup for an IP client."""
    try:
        hostname, _aliases, _addresses = socket.gethostbyaddr(ip)
    except (OSError, socket.herror, socket.gaierror):
        return ''
    return _clean_detected_client_name(hostname, ip)


from app_support.client_intelligence import (
    configure_client_intelligence_context,
    _dhcp_lease_display_name,
    display_name_for_inventory_device,
    enrich_ip_client_display_name,
    client_timeline,
    client_health_summary,
    _ttl_os_hint,
    client_intelligence_profile,
    update_client_metadata,
    save_client_baseline,
    client_profile_export,
    client_relationship_map,
)
from app_support.client_services import (
    configure_client_services_context,
    fingerprint_client_services,
    save_scheduled_client_check,
    scan_common_client_ports,
    run_scheduled_client_check,
    run_due_scheduled_client_checks,
    create_client_watch_alert,
    capture_http_preview_thumbnail,
    inspect_http_services,
)
from app_support.passive_monitoring import (
    configure_passive_monitoring_context,
    record_passive_observation_analytics,
    passive_observation_summary,
    passive_monitor_snapshot,
    _passive_monitor_worker,
    set_passive_monitor,
    comprehensive_network_device_scan,
)

configure_client_intelligence_context(lambda: globals())
configure_client_services_context(lambda: globals())
configure_passive_monitoring_context(lambda: globals())


def append_client_timeline_event(identifier, event_type, message, source=None):
    """Record a lightweight per-client event shown on the client profile."""
    key = str(identifier or '').strip()
    if not key:
        return None
    event = {'timestamp': time.time(), 'type': event_type, 'message': message, 'source': source or 'client-profile'}
    with client_timelines_lock:
        client_timelines.setdefault(key, []).insert(0, event)
        del client_timelines[key][50:]
    save_runtime_state('client-timeline')
    return event


def client_reachability_history(host, limit=10):
    """Return recent ping results for a specific client."""
    target = str(host or '').strip()
    matches = [dict(item) for item in ping_history if item.get('host') == target]
    for item in matches:
        item['time_label'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(item.get('checked_at', time.time())))
    return matches[-limit:]


def _forward_dns_records(names):
    """Resolve learned client names back to addresses for identity correlation."""
    records = []
    for name in sorted({str(item or '').strip().strip('.') for item in names if item})[:6]:
        try:
            addresses = sorted({info[4][0] for info in socket.getaddrinfo(name, None)})
        except (OSError, socket.gaierror):
            addresses = []
        records.append({'name': name, 'addresses': addresses})
    return records


def client_baseline_diff(device):
    """Compare current saved observations to expected profile/baseline data."""
    device = device or {}
    expected_ports = set(device.get('expected_open_ports') or (device.get('client_baseline') or {}).get('open_ports') or [])
    current_ports = set(device.get('open_ports') or [])
    added = sorted(current_ports - expected_ports) if expected_ports else []
    missing = sorted(expected_ports - current_ports)
    return {
        'expected_ports': sorted(expected_ports),
        'current_ports': sorted(current_ports),
        'unexpected_ports': added,
        'missing_ports': missing,
        'status': 'Drift detected' if added or missing else ('Baseline saved' if expected_ports else 'No baseline'),
    }


def is_client_watched(identifier):
    key = str(identifier or '').strip()
    return key in watched_clients


def inventory_records():
    """Return inventory entries enriched with display labels and sorted by last seen."""
    interface_devices = []
    for iface in network_interfaces:
        mac = iface.get_mac_address() if hasattr(iface, 'get_mac_address') else None
        if mac:
            interface_devices.append({
                'mac': mac,
                'ip': iface.get_ipv4() if hasattr(iface, 'get_ipv4') else None,
                'name': getattr(iface, 'name', None),
                'device_type': f"Local {getattr(iface, 'interface_type', 'Interface')}",
                'manufacturer': getattr(iface, 'manufacturer', None) or lookup_manufacturer(mac),
            })
    if interface_devices:
        record_inventory_devices(interface_devices, 'local-adapter')

    with device_inventory_lock:
        records = [dict(item) for item in device_inventory.values()]
    for item in records:
        item['display_name'] = display_name_for_inventory_device(item)
        if not item.get('manufacturer') or str(item['manufacturer']).casefold() == 'unknown':
            item['manufacturer'] = lookup_manufacturer(item.get('mac') or item.get('address'))
        item['likely_randomized_mac'] = device_intel.is_locally_administered_mac(item.get('mac') or item.get('address'))
        item['device_role_guess'] = item.get('device_role_guess') or device_intel.infer_device_role(item)
        item['is_unknown_manufacturer'] = item['manufacturer'] == 'Unknown'
        item['client_health'] = client_health_summary(item, item.get('ip')) if item.get('ip') and not item.get('is_control_traffic') else None
        item['client_baseline'] = client_baseline_diff(item) if item.get('ip') and not item.get('is_control_traffic') else None
        item['is_watched_client'] = is_client_watched(item.get('ip')) if item.get('ip') else False
        item['first_seen_label'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(item.get('first_seen', 0)))
        item['last_seen_label'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(item.get('last_seen', 0)))
    return sorted(records, key=lambda item: item.get('last_seen', 0), reverse=True)


def wireless_network_cache_key(network):
    return wireless_client_service.cache_key(network, normalize_mac)


def wireless_network_client_label_key(interface, ssid, bssid, identity):
    return wireless_client_service.client_label_key(interface, ssid, bssid, identity, normalize_mac)


def network_client_display_label(network, client):
    return wireless_client_service.client_display_label(
        network, client, wireless_network_labels, normalize_mac,
    )


def sorted_network_clients(clients):
    return wireless_client_service.sort_clients(clients)


def merge_wireless_network_clients(network):
    return wireless_client_service.merge_network_clients(
        network, wireless_network_client_cache, wireless_network_labels, normalize_mac,
        inventory_records, lookup_manufacturer,
    )


def record_scan_devices_for_wireless_network(interface, ssid, bssid, devices):
    """Scope scan-discovered devices to an explicit Wi-Fi network page."""
    if not interface or not (ssid or bssid):
        return []
    scoped_clients = [
        {**dict(device), 'network_scan_scoped': True}
        for device in (devices or [])
        if not device.get('is_control_traffic') and (device.get('ip') or device.get('mac'))
    ]
    if not scoped_clients:
        return []
    network = {
        'interface': interface,
        'ssid': ssid,
        'bssid': bssid,
        'clients': scoped_clients,
    }
    merged = merge_wireless_network_clients(network)
    save_runtime_state('wireless-scan-clients')
    return merged.get('clients', [])


def inventory_export_payload(records=None):
    records = records if records is not None else inventory_records()
    return inventory_service.export_payload(records)


def import_inventory_payload(payload, source='inventory-import'):
    return inventory_service.import_payload(
        payload, source, record_inventory_devices, find_inventory_device, inventory_key,
        device_inventory, device_inventory_lock, record_device_open_ports,
    )


def manufacturer_insights(records=None):
    records = records if records is not None else inventory_records()
    return inventory_service.manufacturer_summary(records)


def json_error(message, status=400, **payload):
    """Return a consistently shaped JSON error response."""
    return jsonify({'status': 'error', 'message': message, **payload}), status


def json_success(**payload):
    """Return a consistently shaped JSON success response."""
    return jsonify({'status': 'success', **payload})


def missing_fields(data, *fields):
    """Return required form fields that are missing or blank."""
    return [field for field in fields if not data.get(field)]


def parse_int(value, error_message):
    """Parse an integer form value and raise ValueError with a route-friendly message."""
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(error_message) from exc


def run_ping_check(host, count=4, timeout=2):
    return diagnostics_service.run_ping_check(host, count, timeout, parse_int, subprocess, ping_history)


def run_ping_sweep(cidr, count=1, timeout=1):
    return diagnostics_service.run_ping_sweep(cidr, count, timeout, run_ping_check, subprocess.TimeoutExpired)


def _run_text_command(command, timeout=5):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'command': command, 'returncode': 1, 'output': str(exc)}
    return {'command': command, 'returncode': result.returncode, 'output': (result.stdout or result.stderr or '').strip()}


def build_route_diagnostics(target=None):
    return diagnostics_service.build_route_diagnostics(target, _run_text_command, os_name=os.name)


from app_support.network_discovery import (
    _parse_lldpctl_keyvalue,
    _parse_mdns_output,
    _parse_ssdp_response,
    classify_service_role,
    merge_discovered_devices,
    parse_neighbor_table,
    passive_device_identity,
)


def discover_mdns_services(selected_interface=None):
    avahi = shutil.which('avahi-browse')
    if not avahi:
        return {'available': False, 'tool': None, 'services': [], 'message': 'Install avahi-utils or use dns-sd to discover mDNS/Bonjour services.'}
    command = [avahi, '-artp']
    result = _run_text_command(command, timeout=8)
    services = _parse_mdns_output(result['output'])
    if selected_interface:
        services = [service for service in services if selected_interface in {service.get('interface'), service.get('interface_name')}]
    inventory_items = [
        {
            'ip': service.get('ip'),
            'hostname': service.get('hostname'),
            'name': service.get('name'),
            'device_type': service.get('role'),
            'service_metadata': service,
        }
        for service in services if service.get('ip')
    ]
    record_inventory_devices(inventory_items, 'mdns-discovery', selected_interface)
    return {'available': True, 'tool': avahi, 'services': services, 'message': f'Discovered {len(services)} mDNS service(s).'}


def discover_upnp_devices(timeout=2):
    request_data = '\r\n'.join([
        'M-SEARCH * HTTP/1.1',
        'HOST: 239.255.255.250:1900',
        'MAN: "ssdp:discover"',
        'MX: 1',
        'ST: ssdp:all',
        '',
        '',
    ]).encode('utf-8')
    devices = []
    seen = set()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
            sock.settimeout(timeout)
            sock.sendto(request_data, ('239.255.255.250', 1900))
            deadline = time.time() + timeout
            while time.time() < deadline:
                try:
                    data, _addr = sock.recvfrom(65535)
                except socket.timeout:
                    break
                device = _parse_ssdp_response(data.decode('utf-8', errors='ignore'))
                key = device.get('usn') or device.get('control_url') or device.get('ip')
                if key and key not in seen:
                    seen.add(key)
                    devices.append(device)
    except OSError as exc:
        return {'available': False, 'devices': [], 'message': f'SSDP discovery unavailable: {exc}'}
    record_inventory_devices([
        {
            'ip': device.get('ip'),
            'name': device.get('friendly_name'),
            'manufacturer': device.get('manufacturer'),
            'device_type': device.get('role'),
            'service_metadata': device,
        }
        for device in devices if device.get('ip')
    ], 'upnp-discovery')
    return {'available': True, 'devices': devices, 'message': f'Discovered {len(devices)} UPnP/SSDP device(s).'}


def discover_lldp_neighbors(selected_interface=None):
    lldpctl = shutil.which('lldpctl')
    if not lldpctl:
        return {'available': False, 'tool': None, 'neighbors': [], 'message': 'Install lldpd/lldpctl to reveal LLDP/CDP neighbors.'}
    command = [lldpctl, '-f', 'keyvalue']
    if selected_interface:
        command.append(selected_interface)
    result = _run_text_command(command, timeout=6)
    neighbors = _parse_lldpctl_keyvalue(result['output'])
    record_inventory_devices([
        {
            'ip': neighbor.get('management_address'),
            'name': neighbor.get('name'),
            'device_type': neighbor.get('role'),
            'service_metadata': neighbor,
        }
        for neighbor in neighbors if neighbor.get('management_address')
    ], 'lldp-cdp-discovery', selected_interface)
    return {'available': result['returncode'] == 0, 'tool': lldpctl, 'neighbors': neighbors, 'message': f'Discovered {len(neighbors)} LLDP/CDP neighbor(s).'}


def discover_vlan_context(ssid=None, vlan_id=None, notes=None):
    return diagnostics_service.discover_vlan_context(
        ssid, vlan_id, notes, _run_text_command, vlan_segmentation_notes, uuid.uuid4, os_name=os.name,
    )


def build_egress_diagnostics(selected_interface=None):
    import builtins
    import urllib.request as urllib_request

    return diagnostics_service.build_egress_diagnostics(
        selected_interface, _run_text_command, build_route_diagnostics, network_interfaces,
        os.environ, urllib_request.urlopen, builtins.open, os_name=os.name,
    )


def run_iperf3_test(mode, host=None, port=5201, seconds=5):
    return diagnostics_service.run_iperf3_test(mode, host, port, seconds, parse_int, shutil, subprocess)


def run_snmp_inventory(host, community=None, version='2c', oid='system'):
    return diagnostics_service.run_snmp_inventory(
        host, community, version, oid, shutil, subprocess, record_inventory_devices,
    )


def run_ipv6_assessment(host=None, ports=None):
    return diagnostics_service.run_ipv6_assessment(
        host, ports, _run_text_command, shutil, socket, os_name=os.name,
    )


def _scan_result_counts(result):
    result = result or {}
    return {
        'devices': len(result.get('devices') or []),
        'wlans': len(result.get('wlans') or []),
    }


def _append_scan_event(job_id, message, **updates):
    event = {'time': time.time(), 'message': message}
    with scan_jobs_lock:
        job = scan_jobs.get(job_id)
        if not job:
            return
        if job.get('status') == 'cancelled' and updates.get('status') in {'completed', 'failed'}:
            return
        events = list(job.get('events') or [])
        events.append(event)
        job.update(updates)
        job['message'] = message
        job['events'] = events[-20:]
        job['updated_at'] = time.time()


def _set_scan_job(job_id, **updates):
    with scan_jobs_lock:
        job = scan_jobs.get(job_id)
        if not job:
            return
        if job.get('status') == 'cancelled' and updates.get('status') in {'completed', 'failed'}:
            return
        result = updates.get('result')
        if result is not None:
            updates.setdefault('result_counts', _scan_result_counts(result))
        job.update(updates)
        job['updated_at'] = time.time()


def _run_scan_job(job_id, scan_type, selected_interface):
    _append_scan_event(job_id, f'Starting {scan_type} scan on {selected_interface}.', status='running', started_at=time.time())
    try:
        if scan_type == 'wlan':
            from scripts.wifi import utils as wifi_utils
            _append_scan_event(job_id, 'Refreshing wireless scan data from the selected adapter.')
            wifi_utils.scan_networks(selected_interface)
            wlans = wifi_utils.get_networks_summary()
            diagnostics = wifi_utils.get_scan_diagnostics() if hasattr(wifi_utils, 'get_scan_diagnostics') else {}
            result = {'wlans': wlans, 'scan_diagnostics': diagnostics}
            _append_scan_event(job_id, f'Parsed {len(wlans)} wireless network(s) from scan output.', result_counts=_scan_result_counts(result))
        elif scan_type == 'bluetooth':
            _append_scan_event(job_id, 'Discovering Bluetooth devices from the host adapter.')
            devices = asyncio.run(get_bluetooth_devices())
            summaries = [bluetooth_device_summary(dev) for dev in devices]
            result = {
                'devices': summaries,
                'action_capability': bluetooth_action_capability(),
            }
            _append_scan_event(job_id, f'Parsed {len(summaries)} Bluetooth device(s) from scan output.', result_counts=_scan_result_counts(result))
        else:
            raise ValueError('Unsupported scan type')
        with scan_jobs_lock:
            cancelled = scan_jobs.get(job_id, {}).get('cancel_requested')
        if cancelled:
            _append_scan_event(job_id, 'Job cancelled.', status='cancelled', completed_at=time.time())
            return
        if scan_type == 'bluetooth':
            record_inventory_devices(result.get('devices', []), 'bluetooth-scan', selected_interface)
            _append_scan_event(job_id, f'Recorded {len(result.get("devices", []))} Bluetooth device(s) in inventory.', result_counts=_scan_result_counts(result))
        _append_scan_event(job_id, f'{scan_type.title()} scan complete.', status='completed', completed_at=time.time(), result=result, result_counts=_scan_result_counts(result))
    except Exception as exc:
        _append_scan_event(job_id, f'{scan_type.title()} scan failed: {exc}', status='failed', completed_at=time.time(), error=str(exc))


def _port_scan_job_snapshot(job):
    return port_scan_service.job_snapshot(job)


def _scan_job_snapshot(job):
    status = job.get('status')
    progress = 100 if status in {'completed', 'failed', 'cancelled'} else (10 if status == 'queued' else 50)
    return {
        **job,
        'kind': 'scan',
        'label': f"{job.get('scan_type', 'scan')} scan",
        'total_ports': None,
        'scanned_ports': None,
        'progress': progress,
        'result_counts': dict(job.get('result_counts') or {'devices': 0, 'wlans': 0}),
        'events': list(job.get('events') or []),
        'cancelable': status in {'queued', 'running'},
    }


def all_job_snapshots():
    jobs = []
    with scan_jobs_lock:
        jobs.extend(_scan_job_snapshot(job) for job in scan_jobs.values())
    jobs.extend(port_scan_service.all_snapshots(port_scan_jobs, port_scan_jobs_lock))
    return sorted(jobs, key=lambda item: item.get('updated_at') or item.get('created_at') or 0, reverse=True)


def running_job_count():
    scan_count = len([job for job in all_job_snapshots() if job.get('kind') == 'scan' and job.get('status') in {'queued', 'running'}])
    return scan_count + port_scan_service.running_count(port_scan_jobs, port_scan_jobs_lock)


def update_port_scan_job(job_id, **updates):
    return port_scan_service.update_job(port_scan_jobs, port_scan_jobs_lock, job_id, **updates)


def run_port_scan_job(job_id):
    return port_scan_service.run_job(
        job_id,
        port_scan_jobs,
        port_scan_jobs_lock,
        enrich_web_port_metadata,
        record_device_open_ports,
    )


def create_port_scan_job(host, start, end, label=None):
    from scripts.portScanner import validate_port_range

    if not host or not str(host).strip():
        raise ValueError('Host is required')
    start, end = validate_port_range(start, end, max_ports=None)
    job_id = str(uuid.uuid4())
    now = time.time()
    job = {
        'id': job_id,
        'host': str(host).strip(),
        'start': start,
        'end': end,
        'label': label or f'{start}-{end}',
        'status': 'queued',
        'open_ports': [],
        'open_port_details': [],
        'scanned_ports': 0,
        'total_ports': end - start + 1,
        'current_port': None,
        'progress': 0,
        'message': 'Port scan queued.',
        'cancel_requested': False,
        'created_at': now,
        'updated_at': now,
    }
    with port_scan_jobs_lock:
        port_scan_jobs[job_id] = job
    threading.Thread(target=run_port_scan_job, args=(job_id,), daemon=True).start()
    return _port_scan_job_snapshot(job)

def create_scan_job(scan_type, selected_interface):
    if scan_type not in {'wlan', 'bluetooth'}:
        raise ValueError('Unsupported scan type')
    if not selected_interface:
        raise ValueError('Missing selected interface')
    with scan_jobs_lock:
        for existing_job in scan_jobs.values():
            if (
                existing_job.get('scan_type') == scan_type
                and existing_job.get('selected_interface') == selected_interface
                and existing_job.get('status') in {'queued', 'running'}
            ):
                return _scan_job_snapshot(existing_job)
    job_id = uuid.uuid4().hex
    with scan_jobs_lock:
        scan_jobs[job_id] = {
            'id': job_id,
            'kind': 'scan',
            'scan_type': scan_type,
            'selected_interface': selected_interface,
            'status': 'queued',
            'cancel_requested': False,
            'message': f'{scan_type.title()} scan queued for {selected_interface}.',
            'events': [{'time': time.time(), 'message': f'{scan_type.title()} scan queued for {selected_interface}.'}],
            'result_counts': {'devices': 0, 'wlans': 0},
            'created_at': time.time(),
            'updated_at': time.time(),
        }
    threading.Thread(target=_run_scan_job, args=(job_id, scan_type, selected_interface), daemon=True).start()
    with scan_jobs_lock:
        return _scan_job_snapshot(scan_jobs[job_id])


def build_report_data():
    """Collect the current application state for report exports."""
    from scripts.capabilities import build_capabilities
    return reports_service.build_report_data(
        network_interfaces, inventory_records, manufacturer_insights, all_job_snapshots,
        alert_records, evidence_records, build_capabilities,
    )


def report_as_csv(report):
    return reports_service.report_as_csv(report)


def report_as_markdown(report):
    return reports_service.report_as_markdown(report)


def bluetooth_phone_card_context():
    config_path = app.config.get('BLUETOOTH_PHONE_CONFIG')
    notice = request.args.get('bluetooth_notice')
    notice_style = request.args.get('bluetooth_notice_style', 'info')
    try:
        settings = load_bluetooth_phone_settings(config_path)
    except BluetoothPhoneSettingsError as exc:
        app.logger.warning('Unable to load Bluetooth phone settings: %s', exc)
        settings = build_bluetooth_phone_settings('Mobile Router', [])
        notice = notice or str(exc)
        notice_style = 'danger'
    return {
        'bluetooth_phone_settings': settings,
        'bluetooth_phone_feature_options': bluetooth_phone_feature_options(settings),
        'bluetooth_phone_pairing_capability': bluetooth_pairing_mode_capability(),
        'bluetooth_phone_notice': notice,
        'bluetooth_phone_notice_style': notice_style,
    }

def adapter_snapshot(interfaces=None):
    """Return a stable snapshot for adapter partial-update comparisons."""
    return json.dumps([
        {
            'name': iface.name,
            'interface_type': iface.interface_type,
            'state': getattr(iface, 'state', None),
            'addresses': getattr(iface, 'addresses', []),
            'manufacturer': getattr(iface, 'manufacturer', None),
        }
        for iface in (interfaces or network_interfaces)
    ], sort_keys=True)


def adapter_update_fragments(title='Home'):
    context = current_context()
    return {
        'primary_nav_links': render_template('_primary-nav-links.html', title=title, **context),
        'interface_categories': render_template('_interface-categories.html', title=title, **context),
    }

def current_context():
    return {
        'networkTechnologies': networkTechnologies,
        'interfaces': network_interfaces,
    }


def poll_interfaces():
    global network_interfaces, networkTechnologies
    while True:
        updated_interfaces = get_network_interfaces()
        if updated_interfaces != network_interfaces:
            network_interfaces = updated_interfaces
            networkTechnologies = {iface.interface_type for iface in network_interfaces}
            socketio.emit('update_interfaces', {'interfaces': [iface.to_dict() for iface in network_interfaces]})
        time.sleep(5)  # Poll every 5 seconds


# Start polling in a separate thread
polling_thread = threading.Thread(target=poll_interfaces, daemon=True)
polling_thread.start()


@app.route('/')
def index():
    return render_template('index.html', title='Home', **current_context())


@app.route('/about')
def about():
    return render_template('about.html', title='About', **current_context())


@app.route('/contact')
def contact_page():
    return render_template('contact.html', title='Contact', **current_context())


def social_csrf_token():
    if 'social_csrf_token' not in session:
        session['social_csrf_token'] = secrets.token_urlsafe(32)
    return session['social_csrf_token']


def social_login_required(roles=None):
    allowed_roles = set(roles or social_auth_service.ROLES)
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not social_users:
                return redirect(url_for('social_auth_setup'))
            user = session.get('social_user')
            if not user:
                return redirect(url_for('social_auth_login', next=request.path))
            if user.get('role') not in allowed_roles:
                return json_error('You do not have permission for this action.', 403)
            if request.method == 'POST' and not secrets.compare_digest(
                str(request.form.get('csrf_token') or ''), str(session.get('social_csrf_token') or ''),
            ):
                return json_error('Invalid or expired form token.', 400)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def record_social_audit(action, profile_id=None, detail=None):
    username = (session.get('social_user') or {}).get('username')
    social_auth_service.record_audit(
        action, username, social_audit_log, social_audit_lock, profile_id, detail,
    )


def recent_social_audit(limit=50):
    with social_audit_lock:
        return [dict(item) for item in social_audit_log[:limit]]


def current_user_record():
    user = current_app_user() or {}
    with social_users_lock:
        record = social_users.get(user.get('username'))
        return dict(record) if record else None


def current_app_user():
    return session.get('social_user')


def owned_social_profiles():
    username = (current_app_user() or {}).get('username')
    return [
        profile for profile in social_profile_service.list_profiles(social_profiles, social_profiles_lock)
        if profile.get('owner') == username
    ]


def owned_social_profile(profile_id):
    profile = social_profile_service.get_profile(profile_id, social_profiles, social_profiles_lock)
    if not profile or profile.get('owner') != (current_app_user() or {}).get('username'):
        return None
    return profile


def save_social_profile_photo(profile_id, upload):
    if not upload or not upload.filename:
        return None
    extension = os.path.splitext(secure_filename(upload.filename))[1].casefold()
    if extension not in {'.jpg', '.jpeg', '.png', '.gif', '.webp'}:
        raise ValueError('Profile picture must be a JPG, PNG, GIF, or WebP image.')
    content = upload.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise ValueError('Profile picture must be 5 MB or smaller.')
    os.makedirs(SOCIAL_PROFILE_PHOTO_DIR, exist_ok=True)
    filename = f'{profile_id}{extension}'
    for candidate in os.listdir(SOCIAL_PROFILE_PHOTO_DIR):
        if candidate.startswith(f'{profile_id}.'):
            os.unlink(os.path.join(SOCIAL_PROFILE_PHOTO_DIR, candidate))
    with open(os.path.join(SOCIAL_PROFILE_PHOTO_DIR, filename), 'wb') as handle:
        handle.write(content)
    with social_profiles_lock:
        social_profiles[profile_id]['photo_filename'] = filename
    return filename


@app.before_request
def require_application_login():
    """Require a local account for every application page and API except auth/static assets."""
    public_endpoints = {
        'static', 'favicon', 'social_auth_setup', 'social_auth_login',
        'legacy_social_auth_setup', 'legacy_social_auth_login',
    }
    if request.endpoint in public_endpoints:
        return None
    if not social_users:
        return redirect(url_for('social_auth_setup', next=request.path))
    session_user = current_app_user()
    if not session_user:
        return redirect(url_for('social_auth_login', next=request.path))
    with social_users_lock:
        stored_user = social_users.get(session_user.get('username'))
    if not stored_user:
        session.pop('social_user', None)
        return redirect(url_for('social_auth_login', next=request.path))
    session['social_user'] = {'username': stored_user['username'], 'role': stored_user['role']}
    return None


@app.context_processor
def inject_application_auth():
    return {'app_user': current_app_user(), 'app_csrf_token': social_csrf_token()}


from routes.social_auth import register_social_auth_routes
from routes.social_profiles import register_social_profile_routes
from routes.social_profile_resources import register_social_profile_resource_routes
from routes.social_profile_transfer import register_social_profile_transfer_routes

globals().update(register_social_auth_routes(app, lambda: globals()))
globals().update(register_social_profile_routes(app, lambda: globals()))
globals().update(register_social_profile_resource_routes(app, lambda: globals()))
globals().update(register_social_profile_transfer_routes(app, lambda: globals()))


@app.route('/submit-contact', methods=['POST'])
def submit_contact():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    message = data.get('message')
    if not name or not email or not message:
        return json_error('Missing information')
    try:
        with open('contact_messages.txt', 'a') as f:
            json.dump({'name': name, 'email': email, 'message': message, 'timestamp': time.time()}, f)
            f.write('\n')
        return json_success()
    except Exception as e:
        return json_error(str(e), 500)


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico')


@app.route('/red-team')
def red_team():
    return render_template('red-team.html', title='Red Team', **current_context())


@app.route('/roadmap')
def roadmap_page():
    return render_template(
        'roadmap.html',
        title='Roadmap',
        roadmap_sections=ROADMAP_SECTIONS,
        remaining_roadmap_items=remaining_roadmap_items(),
        **current_context(),
    )


app.config['TRAIN_CONTROLLER_EVIDENCE_RECORDER'] = create_evidence_record
register_blueprints(app, current_context)


# Endpoint to fetch the current list of network adapters
@app.route('/adapters', methods=['POST'])
def adapters():
    """Return the available network interfaces as JSON."""
    return jsonify({'interfaces': [iface.to_dict() for iface in network_interfaces]})


@app.route('/adapters/updates', methods=['POST'])
def adapter_updates():
    """Return adapter data plus replaceable page fragments when adapters changed."""
    data = request.get_json(silent=True) or {}
    current_snapshot = adapter_snapshot()
    changed = data.get('snapshot') != current_snapshot
    return jsonify({
        'changed': changed,
        'snapshot': current_snapshot,
        'interfaces': [iface.to_dict() for iface in network_interfaces],
        'fragments': adapter_update_fragments(data.get('title') or 'Home') if changed else {},
    })


@app.route('/export/interfaces.json')
def export_interfaces_json():
    return jsonify({
        'interfaces': [iface.to_dict() for iface in network_interfaces],
        'exported_at': time.time(),
    })


@app.route('/export/capabilities.json')
def export_capabilities_json():
    from scripts.capabilities import build_capabilities
    return jsonify({
        'capabilities': build_capabilities(),
        'exported_at': time.time(),
    })


@app.route('/evidence')
def evidence_page():
    return render_template('evidence.html', title='Evidence Vault', evidence=evidence_records(), **current_context())


@app.route('/evidence', methods=['POST'])
def create_evidence_route():
    try:
        record = create_evidence_record(
            request.form.get('title'),
            request.form.get('category'),
            request.form.get('source'),
            request.form.get('device'),
            request.form.get('notes'),
            request.form.get('content'),
            request.files.get('artifact'),
        )
    except ValueError as e:
        return json_error(str(e))
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return json_success(evidence=record)
    return render_template('evidence.html', title='Evidence Vault', evidence=evidence_records(), created=record, **current_context())


@app.route('/evidence.<fmt>')
def export_evidence(fmt):
    records = evidence_records()
    if fmt == 'json':
        return jsonify({'evidence': records, 'exported_at': time.time()})
    if fmt == 'csv':
        return Response(evidence_as_csv(records), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=evidence-vault.csv'})
    if fmt in {'md', 'markdown'}:
        return Response(evidence_as_markdown(records), mimetype='text/markdown', headers={'Content-Disposition': 'attachment; filename=evidence-vault.md'})
    return json_error('Unsupported evidence export format', 404)


@app.route('/evidence/<evidence_id>/download')
def download_evidence_file(evidence_id):
    with evidence_vault_lock:
        record = next((item for item in evidence_vault if item.get('id') == evidence_id), None)
    if not record or not record.get('stored_name'):
        return json_error('Evidence file not found', 404)
    path = os.path.join(EVIDENCE_DIR, record['stored_name'])
    if not os.path.isfile(path):
        return json_error('Evidence file not found', 404)
    return send_file(path, as_attachment=True, download_name=record.get('file_name') or record['stored_name'])


@app.route('/reports')
def reports_page():
    return render_template('reports.html', title='Reports', report=build_report_data(), **current_context())


@app.route('/reports.<fmt>')
def export_report(fmt):
    report = build_report_data()
    if fmt == 'json':
        return jsonify(report)
    if fmt == 'csv':
        return Response(report_as_csv(report), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=mobile-router-report.csv'})
    if fmt in {'md', 'markdown'}:
        return Response(report_as_markdown(report), mimetype='text/markdown', headers={'Content-Disposition': 'attachment; filename=mobile-router-report.md'})
    if fmt == 'html':
        return render_template('report_export.html', title='Report Export', report=report)
    return json_error('Unsupported report format', 404)


@app.route('/network-scan')
def network_scan():
    return render_template('network_scan.html', title='Network Scan', **current_context())


@app.route('/inventory')
def inventory_page(import_result=None):
    records = inventory_records()
    return render_template(
        'inventory.html',
        title='Device Inventory',
        devices=records,
        insights=manufacturer_insights(records),
        import_result=import_result,
        **current_context(),
    )


@app.route('/inventory/export.json')
def inventory_export_json():
    return jsonify(inventory_export_payload())


@app.route('/inventory/import', methods=['POST'])
def inventory_import_route():
    artifact = request.files.get('inventoryFile')
    try:
        if artifact and artifact.filename:
            payload = json.load(artifact.stream)
        else:
            payload = request.get_json(silent=True) or json.loads(request.form.get('inventoryJson') or '{}')
        result = import_inventory_payload(payload)
    except (ValueError, json.JSONDecodeError) as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return json_error(str(e))
        return inventory_page(import_result={'status': 'error', 'message': str(e)})
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return json_success(**result)
    return inventory_page(import_result={'status': 'success', **result})


@app.route('/alerts')
def alerts_page():
    return render_template('alerts.html', title='Alerts', alerts=alert_records(), **current_context())


@app.route('/alerts/status')
def alerts_status():
    alerts = alert_records()
    return json_success(alerts=alerts, unread_count=len([alert for alert in alerts if not alert.get('read')]))


@app.route('/alerts/<alert_id>/read', methods=['POST'])
def mark_alert_read(alert_id):
    alert, unread_count = alerts_service.mark_alert_read(alert_id, new_device_alerts, new_device_alerts_lock)
    if alert:
        return json_success(alert=alert, unread_count=unread_count)
    return json_error('Alert not found', 404)


@app.route('/alerts/read-all', methods=['POST'])
def mark_all_alerts_read():
    return json_success(unread_count=alerts_service.mark_all_alerts_read(new_device_alerts, new_device_alerts_lock))


@app.route('/port-scan')
def port_scan_page():
    return render_template('port_scan.html', title='Port Scan', **current_context())


@app.route('/jobs')
def jobs_page():
    return render_template('jobs.html', title='Jobs', **current_context())


@app.route('/traceroute')
def traceroute_page():
    return render_template('traceroute.html', title='Traceroute', **current_context())


@app.route('/diagnostics')
def diagnostics_page():
    return render_template('diagnostics.html', title='Diagnostics', **current_context())


@app.route('/service-discovery')
def service_discovery_page():
    return render_template('service_discovery.html', title='Service Discovery', **current_context())


@app.route('/advanced-diagnostics')
def advanced_diagnostics_page():
    return render_template('advanced_diagnostics.html', title='Advanced Diagnostics', **current_context())


@app.route('/http-previews/<path:filename>')
def http_preview_file(filename):
    """Serve locally captured HTTP preview thumbnails."""
    return send_from_directory(HTTP_PREVIEW_DIR, filename)


@app.route('/clients/<identifier>/services/<int:port>')
def client_service_detail(identifier, port):
    """Show a focused saved-service detail page for an IP client port."""
    device = enrich_ip_client_display_name(identifier, find_inventory_device(identifier) or {})
    host = device.get('ip') or identifier
    service = next((dict(item) for item in device.get('open_port_details', []) if int(item.get('port') or 0) == int(port)), None)
    if not service:
        return render_template('service_detail.html', title='Service not found', host=host, port=port, service=None, device=device, **current_context()), 404
    return render_template('service_detail.html', title=f"{host}:{port} Service", host=host, port=port, service=service, device=device, **current_context())


@app.route('/clients/<identifier>')
def client_detail(identifier):
    """Display details for a client identified by MAC or IP address."""
    mac_re = re.compile(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$')
    inventory_device = find_inventory_device(identifier)

    mac = None
    ip = None

    if mac_re.match(identifier):
        mac = normalize_mac(identifier)
        ip = (inventory_device or {}).get('ip') or get_ip_by_mac(mac)
    else:
        ip = identifier
        mac = (inventory_device or {}).get('mac') or get_mac_by_ip(ip)

    sources = set((inventory_device or {}).get('sources', []))
    device_type = str((inventory_device or {}).get('device_type') or '').casefold()
    is_bluetooth = 'bluetooth-scan' in sources or 'bluetooth' in device_type
    if is_bluetooth:
        ip = None

    display_name = (
        (inventory_device or {}).get('name')
        or (inventory_device or {}).get('display_name')
        or mac
        or ip
        or identifier
    )
    if not is_bluetooth and ip:
        inventory_device = enrich_ip_client_display_name(ip, inventory_device)
        mac = (inventory_device or {}).get('mac') or mac

    manufacturer = (inventory_device or {}).get('manufacturer')
    if not manufacturer or str(manufacturer).casefold() == 'unknown':
        manufacturer = lookup_manufacturer(mac)
    display_name = display_name_for_inventory_device(inventory_device or {}, mac or ip or identifier)

    last_port_scan = None if is_bluetooth else (inventory_device or {}).get('last_port_scan')
    health_summary = None if is_bluetooth else client_health_summary(inventory_device or {}, ip)
    timeline = [] if is_bluetooth else client_timeline(ip or mac or identifier, inventory_device)
    watched = False if is_bluetooth else is_client_watched(ip or identifier)
    reachability = [] if is_bluetooth else client_reachability_history(ip or identifier)
    baseline_diff = None if is_bluetooth else client_baseline_diff(inventory_device or {})
    relationship_map = None if is_bluetooth else client_relationship_map(ip or identifier)
    scheduled_check = None if is_bluetooth else scheduled_client_checks.get(ip or identifier)

    return render_template(
        'client_detail.html',
        title=f'Client {display_name}',
        ip=ip,
        mac=mac,
        manufacturer=manufacturer,
        display_name=display_name,
        is_bluetooth=is_bluetooth,
        display_name_source=(inventory_device or {}).get('display_name_source'),
        inventory_device=inventory_device or {},
        open_port_details=[] if is_bluetooth else (inventory_device or {}).get('open_port_details', []),
        open_ports=[] if is_bluetooth else (inventory_device or {}).get('open_ports', []),
        last_port_scan_label=(
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_port_scan))
            if last_port_scan
            else None
        ),
        health_summary=health_summary,
        client_timeline=timeline,
        watched_client=watched,
        reachability_history=reachability,
        baseline_diff=baseline_diff,
        relationship_map=relationship_map,
        scheduled_check=scheduled_check,
        bluetooth_fields=bluetooth_detail_fields(inventory_device) if is_bluetooth else [],
        bluetooth_action_capability=bluetooth_action_capability() if is_bluetooth else None,
        bluetooth_actions=bluetooth_contextual_actions(inventory_device) if is_bluetooth else [],
        bluetooth_adapters=bluetooth_adapter_choices() if is_bluetooth else [],
        bluetooth_action_history=bluetooth_action_history(mac) if is_bluetooth else [],
        **current_context(),
    )


@app.route('/clients/<identifier>/watch', methods=['POST'])
def watch_client(identifier):
    """Toggle watch notifications for an IP client."""
    watch = request.form.get('watch', 'on') == 'on'
    target = str(identifier or '').strip()
    if not target:
        return json_error('Missing client identifier')
    if watch:
        watched_clients.add(target)
        append_client_timeline_event(target, 'Watch enabled', 'This client will create alerts for notable profile changes.', 'client-watch')
        save_runtime_state('client-watch')
        return json_success(watched=True, message='Client watch enabled.')
    watched_clients.discard(target)
    append_client_timeline_event(target, 'Watch disabled', 'Client watch notifications were disabled.', 'client-watch')
    save_runtime_state('client-watch')
    return json_success(watched=False, message='Client watch disabled.')


@app.route('/clients/<identifier>/http-inspect', methods=['POST'])
def client_http_inspect(identifier):
    """Inspect saved or supplied HTTP-like services for an IP client."""
    inventory_device = find_inventory_device(identifier) or {}
    host = inventory_device.get('ip') or identifier
    raw_ports = request.form.get('ports')
    try:
        if raw_ports:
            candidates = [parse_int(item.strip(), 'Ports must be integers') for item in raw_ports.split(',') if item.strip()]
        else:
            http_names = ('http', 'https', 'web', 'proxy')
            candidates = [
                item['port'] for item in inventory_device.get('open_port_details', [])
                if any(name in str(item.get('service', '')).lower() for name in http_names) or item.get('port') in (80, 443, 8080, 8443, 8000, 9443)
            ]
    except ValueError as e:
        return json_error(str(e))
    candidates = sorted(set(port for port in candidates if 1 <= port <= 65535))[:8]
    if not candidates:
        return json_error('No HTTP-like saved ports are available for this client. Run a port scan first or supply ports.', 400)
    results = inspect_http_services(host, candidates)
    append_client_timeline_event(host, 'HTTP inspected', f"Inspected {len(results)} web service candidate(s).", 'http-inspector')
    return json_success(results=results)


@app.route('/clients/<identifier>/summary')
def client_summary_route(identifier):
    """Return the latest saved profile fields needed by inline device cards."""
    device = enrich_ip_client_display_name(identifier, find_inventory_device(identifier) or {})
    host = device.get('ip') or identifier
    return json_success(device={
        'ip': host,
        'mac': device.get('mac'),
        'display_name': display_name_for_inventory_device(device, host),
        'manufacturer': device.get('manufacturer') or 'Unknown',
        'open_port_details': device.get('open_port_details', []),
        'open_ports': device.get('open_ports', []),
        'client_tags': device.get('client_tags', []),
        'client_notes': device.get('client_notes'),
        'last_port_scan': device.get('last_port_scan'),
    })


@app.route('/clients/<identifier>/metadata', methods=['POST'])
def client_metadata_route(identifier):
    """Save user-maintained IP client profile metadata."""
    try:
        device = update_client_metadata(identifier, request.form)
    except ValueError as e:
        return json_error(str(e))
    return json_success(device=device, message='Client profile metadata saved.')


@app.route('/clients/<identifier>/baseline', methods=['POST'])
def client_baseline_route(identifier):
    """Save current device observations as the expected baseline."""
    device = save_client_baseline(identifier)
    return json_success(device=device, baseline=client_baseline_diff(device), message='Client baseline saved.')


@app.route('/clients/<identifier>/export.<fmt>')
def client_export_route(identifier, fmt):
    """Export an individual IP client profile."""
    profile = client_profile_export(identifier)
    if fmt == 'json':
        return jsonify(profile)
    if fmt == 'md':
        device = profile['device']
        lines = [
            f"# Client profile: {profile['host']}",
            '',
            f"- Manufacturer: {device.get('manufacturer') or 'Unknown'}",
            f"- MAC: {device.get('mac') or 'Unknown'}",
            f"- Tags: {', '.join(device.get('client_tags', [])) or 'None'}",
            f"- Owner: {device.get('client_owner') or 'Unknown'}",
            f"- Location: {device.get('client_location') or 'Unknown'}",
            f"- Health: {profile['health']['level']} ({profile['health']['score']}/100)",
            f"- Baseline: {profile['baseline']['status']}",
            '',
            '## Open ports',
        ]
        for item in device.get('open_port_details', []):
            lines.append(f"- {item.get('port')}/tcp {item.get('service') or 'Unknown'} — {item.get('description') or ''}")
        if not device.get('open_port_details'):
            lines.append('- No open ports saved.')
        lines.extend(['', '## Timeline'])
        for event in profile['timeline']:
            lines.append(f"- {event.get('time_label')}: {event.get('type')} — {event.get('message')}")
        return Response('\n'.join(lines), mimetype='text/markdown', headers={'Content-Disposition': f'attachment; filename=client-{profile["host"]}.md'})
    return json_error('Unsupported client export format', 404)


@app.route('/clients/<identifier>/relationship-map')
def client_relationship_map_route(identifier):
    return json_success(map=client_relationship_map(identifier))


@app.route('/clients/<identifier>/intelligence', methods=['POST'])
def client_intelligence_route(identifier):
    active_probe = request.form.get('activeProbe') in {'on', 'true', '1'}
    return json_success(intelligence=client_intelligence_profile(identifier, active_probe=active_probe))


@app.route('/clients/<identifier>/fingerprint', methods=['POST'])
def client_fingerprint_route(identifier):
    return json_success(fingerprints=fingerprint_client_services(identifier))


@app.route('/clients/<identifier>/scheduled-check', methods=['POST'])
def client_scheduled_check_route(identifier):
    try:
        plan = save_scheduled_client_check(identifier, request.form)
    except ValueError as e:
        return json_error(str(e))
    return json_success(plan=plan, message='Scheduled client check saved.')


@app.route('/clients/<identifier>/scheduled-check/run', methods=['POST'])
def client_scheduled_check_run_route(identifier):
    try:
        plan = run_scheduled_client_check(identifier)
    except ValueError as e:
        return json_error(str(e), 404)
    return json_success(plan=plan, message='Scheduled client check ran.')


@app.route('/scheduled-checks/run-due', methods=['POST'])
def scheduled_checks_run_due_route():
    results = run_due_scheduled_client_checks()
    return json_success(results=results, count=len(results), message=f'Ran {len(results)} due scheduled check(s).')


@app.route('/active-scan', methods=['POST'])
def active_scan_route():
    iface = request.form.get('selectedInterface')
    if not iface:
        return json_error('Missing interface')
    hosts = classify_scan_results(active_scan(iface), iface)
    enriched_hosts = record_inventory_devices(hosts, 'active-scan', iface)
    network_clients = record_scan_devices_for_wireless_network(
        iface, request.form.get('ssid'), request.form.get('bssid'), enriched_hosts,
    )
    return jsonify({'hosts': enriched_hosts, 'network_clients': network_clients})


@app.route('/passive-scan', methods=['POST'])
def passive_scan_route():
    iface = request.form.get('selectedInterface')
    if not iface:
        return json_error('Missing interface')
    devices = classify_scan_results(passive_scan(iface), iface)
    enriched_devices = record_inventory_devices(devices, 'passive-scan', iface)
    analytics = record_passive_observation_analytics(iface, enriched_devices, 'passive-scan')
    network_clients = record_scan_devices_for_wireless_network(
        iface, request.form.get('ssid'), request.form.get('bssid'), enriched_devices,
    )
    return jsonify({'devices': enriched_devices, 'analytics': analytics, 'network_clients': network_clients})


@app.route('/passive-analytics.json')
def passive_analytics_route():
    interface = request.args.get('selectedInterface') or request.args.get('interface')
    return json_success(analytics=passive_observation_summary(interface))


@app.route('/passive-monitor/status')
def passive_monitor_status_route():
    interface = request.args.get('selectedInterface') or request.args.get('interface')
    status = passive_monitor_snapshot(interface)
    return jsonify({'status': status})


@app.route('/passive-monitor/toggle', methods=['POST'])
def passive_monitor_toggle_route():
    data = request.form
    interface = data.get('selectedInterface') or data.get('interface')
    enabled = str(data.get('enabled') or '').strip().lower() in {'1', 'true', 'yes', 'on'}
    try:
        status = set_passive_monitor(interface, enabled, data.get('interval') or 10, data.get('mode') or 'cache')
    except ValueError as exc:
        return json_error(str(exc))
    message = 'Continuous passive capture enabled.' if enabled else 'Continuous passive capture disabled.'
    return json_success(message=message, status=status)


@app.route('/comprehensive-scan', methods=['POST'])
def comprehensive_scan_route():
    try:
        selected_interface = request.form.get('selectedInterface')
        result = comprehensive_network_device_scan(
            selected_interface,
            include_passive=request.form.get('includePassive', 'on') == 'on',
            include_services=request.form.get('includeServices', 'on') == 'on',
            sweep_cidr=(request.form.get('sweepCidr') or '').strip() or None,
        )
        result['network_clients'] = record_scan_devices_for_wireless_network(
            selected_interface, request.form.get('ssid'), request.form.get('bssid'), result.get('devices', []),
        )
    except ValueError as e:
        return json_error(str(e))
    return json_success(result=result)


@app.route('/port-scan', methods=['POST'])
def port_scan_route():
    data = request.form
    if missing_fields(data, 'host', 'start', 'end'):
        return json_error('Missing parameters')

    try:
        start_port = parse_int(data.get('start'), 'Ports must be integers')
        end_port = parse_int(data.get('end'), 'Ports must be integers')
    except ValueError as e:
        return json_error(str(e))

    from scripts.portScanner import PortScanError, describe_open_ports, scan_ports

    try:
        ports = scan_ports(data.get('host'), start_port, end_port)
    except PortScanError as e:
        return json_error(str(e))

    port_details = [enrich_web_port_metadata(data.get('host'), detail) for detail in describe_open_ports(ports)]
    record_device_open_ports(data.get('host'), port_details, source='port-scan')
    return jsonify({'ports': ports, 'port_details': port_details})


@app.route('/port-scan-jobs', methods=['POST'])
def start_port_scan_job():
    data = request.form
    if missing_fields(data, 'host', 'start', 'end'):
        return json_error('Missing parameters')
    try:
        start_port = parse_int(data.get('start'), 'Ports must be integers')
        end_port = parse_int(data.get('end'), 'Ports must be integers')
        job = create_port_scan_job(data.get('host'), start_port, end_port, data.get('label'))
        return json_success(job=job)
    except ValueError as e:
        return json_error(str(e))


@app.route('/port-scan-jobs/<job_id>')
def port_scan_job_status(job_id):
    with port_scan_jobs_lock:
        job = port_scan_jobs.get(job_id)
        if not job:
            return json_error('Port scan job not found', 404)
        return json_success(job=_port_scan_job_snapshot(job))


@app.route('/jobs/status')
def jobs_status():
    jobs = all_job_snapshots()
    return json_success(jobs=jobs, running_count=len([job for job in jobs if job.get('status') in {'queued', 'running'}]))


@app.route('/jobs/<job_id>/cancel', methods=['POST'])
def cancel_job(job_id):
    with port_scan_jobs_lock:
        port_job = port_scan_jobs.get(job_id)
        if port_job:
            if port_job.get('status') in {'queued', 'running'}:
                port_job['cancel_requested'] = True
                port_job['status'] = 'cancelled' if port_job.get('status') == 'queued' else port_job.get('status')
                port_job['message'] = 'Cancellation requested.'
                port_job['updated_at'] = time.time()
            return json_success(job=_port_scan_job_snapshot(port_job))
    with scan_jobs_lock:
        scan_job = scan_jobs.get(job_id)
        if scan_job:
            scan_job['cancel_requested'] = True
            if scan_job.get('status') in {'queued', 'running'}:
                scan_job['status'] = 'cancelled'
                scan_job['message'] = 'Cancellation requested.'
                scan_job['updated_at'] = time.time()
            return json_success(job=_scan_job_snapshot(scan_job))
    return json_error('Job not found', 404)


@app.route('/traceroute', methods=['POST'])
def traceroute_route():
    host = request.form.get('host')
    if not host:
        return json_error('Missing host')
    from scripts.traceroute import traceroute
    hops = traceroute(host)
    return jsonify({'hops': hops})


@app.route('/ping', methods=['POST'])
def ping_route():
    try:
        result = run_ping_check(request.form.get('host'), request.form.get('count') or 4, request.form.get('timeout') or 2)
    except ValueError as e:
        return json_error(str(e))
    except subprocess.TimeoutExpired:
        return json_error('Ping timed out', 504)
    return json_success(result=result, history=ping_history[-10:])


@app.route('/ping-sweep', methods=['POST'])
def ping_sweep_route():
    try:
        sweep = run_ping_sweep(request.form.get('cidr'), request.form.get('count') or 1, request.form.get('timeout') or 1)
    except ValueError as e:
        return json_error(str(e))
    return json_success(sweep=sweep, history=ping_history[-10:])


@app.route('/route-diagnostics', methods=['POST'])
def route_diagnostics_route():
    diagnostics = build_route_diagnostics(request.form.get('target'))
    return json_success(diagnostics=diagnostics)


@app.route('/mdns-discovery', methods=['POST'])
def mdns_discovery_route():
    result = discover_mdns_services(request.form.get('selectedInterface'))
    return json_success(result=result)


@app.route('/upnp-discovery', methods=['POST'])
def upnp_discovery_route():
    try:
        timeout = parse_int(request.form.get('timeout') or 2, 'Timeout must be an integer')
    except ValueError as e:
        return json_error(str(e))
    result = discover_upnp_devices(timeout=max(1, min(timeout, 5)))
    return json_success(result=result)


@app.route('/neighbor-discovery', methods=['POST'])
def neighbor_discovery_route():
    result = discover_lldp_neighbors(request.form.get('selectedInterface'))
    return json_success(result=result)


@app.route('/vlan-discovery', methods=['POST'])
def vlan_discovery_route():
    result = discover_vlan_context(request.form.get('ssid'), request.form.get('vlanId'), request.form.get('notes'))
    return json_success(result=result)


@app.route('/egress-diagnostics', methods=['POST'])
def egress_diagnostics_route():
    return json_success(result=build_egress_diagnostics(request.form.get('selectedInterface')))


@app.route('/iperf3-test', methods=['POST'])
def iperf3_test_route():
    try:
        result = run_iperf3_test(request.form.get('mode'), request.form.get('host'), request.form.get('port') or 5201, request.form.get('seconds') or 5)
    except (ValueError, subprocess.TimeoutExpired) as e:
        return json_error(str(e))
    return json_success(result=result)


@app.route('/snmp-discovery', methods=['POST'])
def snmp_discovery_route():
    if request.form.get('authorized') != 'on':
        return json_error('Confirm this is an authorized SNMP inventory check')
    try:
        result = run_snmp_inventory(request.form.get('host'), request.form.get('community'), request.form.get('version') or '2c', request.form.get('oid') or 'system')
    except ValueError as e:
        return json_error(str(e))
    return json_success(result=result)


@app.route('/ipv6-assessment', methods=['POST'])
def ipv6_assessment_route():
    result = run_ipv6_assessment(request.form.get('host'), request.form.get('ports'))
    return json_success(result=result)


@app.route('/wireless/network/label', methods=['POST'])
def wireless_network_client_label_route():
    """Save an SSID-scoped custom label for a network client card."""
    interface = request.form.get('interface')
    ssid = request.form.get('ssid')
    bssid = request.form.get('bssid')
    identity = request.form.get('identity') or request.form.get('ip') or request.form.get('mac')
    label = (request.form.get('label') or '').strip()[:80]
    if not interface or not ssid or not identity:
        return json_error('Interface, SSID, and client identity are required')
    key = wireless_network_client_label_key(interface, ssid, bssid, identity)
    if label:
        wireless_network_labels[key] = label
    else:
        wireless_network_labels.pop(key, None)
    save_runtime_state('wireless-label')
    return json_success(label=label, message='Network client label saved.')


@app.route('/wireless/network/clients.json')
def wireless_network_clients_json():
    """Return the persisted Wi-Fi network device list for in-page refreshes."""
    from scripts.wifi import utils as wifi_utils
    network = wifi_utils.get_network_detail(ssid=request.args.get('ssid'), bssid=request.args.get('bssid'), interface_name=request.args.get('interface'))
    network = merge_wireless_network_clients(network)
    return json_success(
        clients=network.get('clients', []),
        disappeared_clients=network.get('disappeared_clients', []),
        client_count=network.get('client_count', 0),
    )


@app.route('/wireless/network/clients.csv')
def wireless_network_clients_export():
    """Export the persisted Wi-Fi network device list as CSV."""
    from scripts.wifi import utils as wifi_utils
    network = wifi_utils.get_network_detail(ssid=request.args.get('ssid'), bssid=request.args.get('bssid'), interface_name=request.args.get('interface'))
    network = merge_wireless_network_clients(network)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['display_name', 'ip', 'mac', 'manufacturer', 'tags', 'notes', 'open_ports', 'open_port_details_json', 'first_seen', 'last_seen', 'state'])
    writer.writeheader()
    for client in network.get('clients', []) + network.get('disappeared_clients', []):
        writer.writerow({
            'display_name': client.get('display_name'),
            'ip': client.get('ip'),
            'mac': client.get('mac'),
            'manufacturer': client.get('manufacturer'),
            'tags': ', '.join(client.get('client_tags') or []),
            'notes': client.get('client_notes') or '',
            'open_ports': ', '.join(str(item.get('port')) for item in client.get('open_port_details') or []),
            'open_port_details_json': json.dumps(client.get('open_port_details') or []),
            'first_seen': client.get('network_first_seen'),
            'last_seen': client.get('network_last_seen'),
            'state': 'disappeared' if client in network.get('disappeared_clients', []) else 'visible',
        })
    filename = secure_filename(f"{network.get('ssid') or 'wireless-network'}-clients.csv")
    return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename="{filename}"'})


@app.route('/wireless/network')
def wireless_network_detail():
    ssid = request.args.get('ssid')
    bssid = request.args.get('bssid')
    selected_interface = request.args.get('interface')

    if not ssid and not bssid:
        return "Wireless network not specified", 400

    from scripts.wifi import utils as wifi_utils
    network = wifi_utils.get_network_detail(ssid=ssid, bssid=bssid, interface_name=selected_interface)
    network = merge_wireless_network_clients(network)
    back_url = f"/wireless/{selected_interface}" if selected_interface else "/wireless"
    return render_template(
        'wireless_network_detail.html',
        title=f"{network['ssid']} Details",
        network=network,
        back_url=back_url,
        **current_context(),
    )


@app.route('/interfaces/<interface_name>/state', methods=['POST'])
def interface_power_state(interface_name):
    desired_state = request.form.get('state')
    interface = next((iface for iface in network_interfaces if iface.name == interface_name), None)
    try:
        message = set_interface_power_state(
            interface_name,
            desired_state,
            getattr(interface, 'interface_type', None),
        )
        return json_success(message=message)
    except ValueError as exc:
        return json_error(str(exc), 400)
    except Exception as exc:
        return json_error(f'Interface power error: {exc}', 500)

@app.route('/<interface_type>')
def interfaces_by_type(interface_type):
    requested_type = interface_type.lower()
    filtered_interfaces = [iface for iface in network_interfaces if iface.interface_type.lower() == requested_type]
    if filtered_interfaces:
        display_type = filtered_interfaces[0].interface_type
        return render_template('interface_type.html', title=display_type, filtered_interfaces=filtered_interfaces, technology=display_type, **current_context())
    else:
        return "No interfaces found for this type", 404


@app.route('/<interface_type>/<interface_name>')
def interface_detail(interface_type, interface_name):
    interface_type = interface_type.lower()
    interface = next((iface for iface in network_interfaces if iface.name == interface_name and iface.interface_type.lower() == interface_type), None)
    if interface:
        return render_template(
            'interface_detail.html',
            title=interface.name,
            interface=interface,
            **current_context(),
            **(bluetooth_phone_card_context() if interface.interface_type == 'Bluetooth' else {}),
        )
    else:
        return "Interface not found", 404


@app.route('/syn-flood', methods=['POST'])
def syn_flood():
    data = request.form
    if missing_fields(data, 'destinationAddress', 'destinationPort', 'frames', 'selectedInterface'):
        return json_error('Missing required parameters')

    try:
        destination_port = parse_int(data.get('destinationPort'), 'Destination port must be an integer')
        frames = parse_int(data.get('frames'), 'Frames must be an integer')
        from scripts.network import networkAttacks
        networkAttacks.synFlood('0.0.0.0', data.get('destinationAddress'), 1234, destination_port, frames, data.get('selectedInterface'))
        return json_success(message=f"DoS successfully on {data.get('selectedInterface')}")
    except ValueError as e:
        return json_error(str(e))
    except Exception as e:
        return json_error(f'DoS error: {str(e)}', 500)


@app.route('/syn-flood-broadcast', methods=['POST'])
def syn_flood_broadcast():
    data = request.form
    if missing_fields(data, 'frames', 'selectedInterface'):
        return json_error('Missing required parameters')

    try:
        frames = parse_int(data.get('frames'), 'Frames must be an integer')
        from scripts.network import networkAttacks
        networkAttacks.broadcastFlood(frames, data.get('selectedInterface'))
        return json_success(message=f"DoS successfully on {data.get('selectedInterface')}")
    except ValueError as e:
        return json_error(str(e))
    except Exception as e:
        return json_error(f'Broadcast DoS error: {str(e)}', 500)


@app.route('/wlan-modes', methods=['GET'])
def wlan_modes():
    selected_interface = request.args.get('selectedInterface')

    if not selected_interface:
        return json_error('Missing selected interface')

    try:
        from scripts.wifi import utils as wifi_utils
        return json_success(**wifi_utils.get_adapter_modes(selected_interface))
    except Exception as e:
        return json_error(f'WLAN mode error: {str(e)}', 500)


@app.route('/wlan-mode', methods=['POST'])
def wlan_mode():
    data = request.form
    selected_interface = data.get('selectedInterface')
    mode = data.get('mode')

    if not selected_interface or not mode:
        return json_error('Missing required parameters')

    try:
        from scripts.wifi import utils as wifi_utils
        return json_success(**wifi_utils.set_adapter_mode(selected_interface, mode))
    except ValueError as e:
        return json_error(str(e))
    except Exception as e:
        return json_error(f'WLAN mode error: {str(e)}', 500)


@app.route('/scan-jobs', methods=['POST'])
def start_scan_job():
    data = request.form
    try:
        job = create_scan_job(data.get('scanType'), data.get('selectedInterface'))
        return json_success(job=job)
    except ValueError as e:
        return json_error(str(e))


@app.route('/scan-jobs/<job_id>')
def scan_job_status(job_id):
    with scan_jobs_lock:
        job = scan_jobs.get(job_id)
        if not job:
            return json_error('Scan job not found', 404)
        return json_success(job=_scan_job_snapshot(job))


@app.route('/wlan-scan', methods=['POST'])
def wlan_scan():
    data = request.form
    selected_interface = data.get('selectedInterface')

    if not selected_interface:
        return json_error('Missing selected interface')

    try:
        from scripts.wifi import utils as wifi_utils
        wifi_utils.scan_networks(selected_interface)
        wlans = wifi_utils.get_networks_summary()
        return json_success(message=f'Got wlans for {selected_interface}', wlans=wlans)
    except Exception as e:
        return json_error(f'WLAN scan error: {str(e)}', 500)


@app.route('/wlan-connect', methods=['POST'])
def wlan_connect():
    data = request.form
    selected_interface = data.get('selectedInterface')
    ssid = data.get('ssid')
    password = data.get('password')

    if not selected_interface or not ssid:
        return json_error('Missing required parameters')

    try:
        from scripts.wifi import utils as wifi_utils
        success = wifi_utils.connect_to_network(ssid, password, selected_interface)
        if success:
            return json_success(message=f'Connected to {ssid} on {selected_interface}')
        else:
            return json_error('Failed to connect', 500)
    except Exception as e:
        return json_error(f'WLAN connect error: {str(e)}', 500)


@app.route('/bluetooth-scan', methods=['POST'])
def bluetooth_scan():
    data = request.form
    selected_interface = data.get('selectedInterface')

    if not selected_interface:
        return json_error('Missing selected interface')

    try:
        devices = asyncio.run(get_bluetooth_devices())
        devices_summary = [bluetooth_device_summary(dev) for dev in devices]
        return json_success(devices=devices_summary, action_capability=bluetooth_action_capability())
    except Exception as e:
        return json_error(f'Bluetooth scan error: {str(e)}', 500)


@app.route('/bluetooth-action', methods=['POST'])
def bluetooth_action():
    data = request.form
    action = data.get('action')
    address = data.get('address')
    adapter = data.get('adapter')

    try:
        output = run_bluetoothctl_action(action, address, adapter=adapter)
        updates = _bluetooth_state_updates_for_action(action)
        if action == 'info':
            updates.update(_parse_bluetooth_info_output(output))
        device = _merge_inventory_device_state(address, updates) if updates else find_inventory_device(address)
        history = record_bluetooth_action_history(address, action, 'success', output or 'Action completed.', adapter=adapter)
        return json_success(message='Bluetooth action completed', output=output, history=history, actions=bluetooth_contextual_actions(device), device_state=bluetooth_device_state(device))
    except ValueError as e:
        history = record_bluetooth_action_history(address, action, 'error', str(e), adapter=adapter)
        return json_error(str(e), history=history)
    except BluetoothToolUnavailable as e:
        history = record_bluetooth_action_history(address, action, 'error', str(e), adapter=adapter)
        return json_error(str(e), 501, history=history)
    except Exception as e:
        message = f'Bluetooth action error: {str(e)}'
        history = record_bluetooth_action_history(address, action, 'error', message, adapter=adapter)
        return json_error(message, 500, history=history)


@app.route('/bluetooth-device/<address>/refresh', methods=['POST'])
def bluetooth_device_refresh(address):
    try:
        output = run_bluetoothctl_action('info', address, adapter=request.form.get('adapter'))
        device = _merge_inventory_device_state(address, _parse_bluetooth_info_output(output))
        history = record_bluetooth_action_history(address, 'refresh', 'success', output or 'Device info refreshed.', adapter=request.form.get('adapter'))
        return json_success(message='Bluetooth device refreshed', output=output, device=device, history=history, actions=bluetooth_contextual_actions(device), device_state=bluetooth_device_state(device))
    except ValueError as e:
        history = record_bluetooth_action_history(address, 'refresh', 'error', str(e), adapter=request.form.get('adapter'))
        return json_error(str(e), history=history)
    except BluetoothToolUnavailable as e:
        history = record_bluetooth_action_history(address, 'refresh', 'error', str(e), adapter=request.form.get('adapter'))
        return json_error(str(e), 501, history=history)
    except Exception as e:
        message = f'Bluetooth refresh error: {str(e)}'
        history = record_bluetooth_action_history(address, 'refresh', 'error', message, adapter=request.form.get('adapter'))
        return json_error(message, 500, history=history)


@app.route('/inventory/<identifier>/forget', methods=['POST'])
def forget_inventory_route(identifier):
    removed = forget_inventory_device(identifier)
    if not removed:
        return json_error('Device was not found in inventory', 404)
    return json_success(message='Device forgotten from Mobile Router inventory')


@app.route('/spoof-mac', methods=['POST'])
def spoof_mac_route():
    data = request.form
    interface = data.get("interface")
    new_mac = data.get("mac")
    if not interface or not new_mac:
        return json_error("Missing parameters")
    success = spoof_mac(interface, new_mac)
    if success:
        return json_success(message="MAC updated")
    else:
        return json_error("Failed to update MAC", 500)


@app.route('/beacon-advertise', methods=['POST'])
def beacon_advertise():
    data = request.form
    selected_interface = data.get('selectedInterface')
    ssid = data.get('ssid')
    src_mac = data.get('srcMac') or '22:22:22:22:22:22'
    bssid = data.get('bssid') or '33:33:33:33:33:33'

    if missing_fields(data, 'selectedInterface', 'ssid', 'frames'):
        return json_error('Missing required parameters')

    try:
        frames = parse_int(data.get('frames'), 'Frames must be an integer')
    except ValueError as e:
        return json_error(str(e))

    try:
        from scripts.wifi.beaconspoof import beaconSpoof
        beaconSpoof(ssid, selected_interface, frames, src=src_mac, bssid=bssid)
        return json_success(message=f'Advertising {ssid} via {selected_interface}')
    except Exception as e:
        return json_error(f'Beacon advertise error: {str(e)}', 500)


@app.route('/deauth', methods=['POST'])
def deauth_route():
    data = request.form
    selected_interface = data.get('selectedInterface')

    if missing_fields(data, 'selectedInterface', 'ap', 'frames'):
        return json_error('Missing required parameters')

    try:
        ap_mac, target_mac, frames = labs_service.validate_deauth_request(data, normalize_mac, parse_int)
    except ValueError as e:
        return json_error(str(e))

    try:
        from scripts.wifi.deauth import deauth
        deauth(ap_mac, target_mac, selected_interface, frames)
        return json_success(message=f'Sent {frames} authorized lab deauth frames on {selected_interface}')
    except Exception as e:
        return json_error(f'Deauth error: {str(e)}', 500)


@app.route('/evil-twin-lab', methods=['POST'])
def evil_twin_lab_route():
    data = request.form
    selected_interface = data.get('selectedInterface')

    if missing_fields(data, 'selectedInterface', 'ssid', 'bssid', 'channel'):
        return json_error('Missing required parameters')

    try:
        lab = labs_service.validate_evil_twin_request(data, normalize_mac, parse_int)
        run = labs_service.record_evil_twin_run(selected_interface, lab, evil_twin_lab_runs, evil_twin_lab_lock, save_runtime_state, app.logger)
    except ValueError as e:
        return json_error(str(e))

    action_messages = {
        'plan': 'Prepared evil twin and captive portal lab plan; no radio services were started by Mobile Router.',
        'start': 'Logged authorized evil twin lab start checklist; run AP services only in your isolated lab environment.',
        'cleanup': 'Logged evil twin lab cleanup checklist; verify rogue AP, DHCP, DNS, and portal services are stopped.',
    }
    return json_success(message=action_messages[run['action']], run=run)


@app.route('/pineap-lab', methods=['POST'])
def pineap_lab_route():
    data = request.form
    selected_interface = data.get('selectedInterface')
    if missing_fields(data, 'selectedInterface'):
        return json_error('Missing required parameters')
    try:
        lab = labs_service.validate_pineap_request(data, normalize_mac, parse_int)
        from scripts.wifi import utils as wifi_utils
        run = labs_service.build_pineap_result(selected_interface, lab, pineap_lab_runs, pineap_lab_lock, save_runtime_state, app.logger, wifi_utils)
    except ValueError as e:
        return json_error(str(e))
    except Exception as e:
        return json_error(f'PineAP-style lab error: {str(e)}', 500)
    return json_success(message=f"Recorded {run['action']} workflow with {len(run['module_status'])} module(s).", run=run)


@app.route('/handshake-lab', methods=['POST'])
def handshake_lab_route():
    data = request.form
    selected_interface = data.get('selectedInterface')
    if missing_fields(data, 'selectedInterface', 'ssid', 'bssid', 'channel'):
        return json_error('Missing required parameters')
    try:
        lab = labs_service.validate_handshake_request(data, normalize_mac, parse_int)
        record = labs_service.record_handshake_evidence(selected_interface, lab, request.files.get('capture'), create_evidence_record, handshake_lab_records, handshake_lab_lock, save_runtime_state, app.logger)
    except ValueError as e:
        return json_error(str(e))
    return json_success(message='Cataloged WPA handshake/PMKID lab evidence for validation and export.', record=record)


@app.route('/handshake-lab.<fmt>')
def export_handshake_lab(fmt):
    records = labs_service.export_handshake_records(handshake_lab_records, handshake_lab_lock)
    if fmt == 'json':
        return jsonify({'handshakes': records, 'exported_at': time.time()})
    if fmt == 'csv':
        return Response(labs_service.handshake_records_csv(records), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=handshake-lab.csv'})
    return json_error('Unsupported handshake export format', 404)


@app.route('/aireplay-deauth', methods=['POST'])
def aireplay_deauth_route():
    data = request.form
    selected_interface = data.get('selectedInterface')
    ap_mac = data.get('ap')
    target_mac = data.get('target') or 'ff:ff:ff:ff:ff:ff'

    if missing_fields(data, 'selectedInterface', 'ap', 'frames'):
        return json_error('Missing required parameters')

    try:
        frames = parse_int(data.get('frames'), 'Frames must be an integer')
    except ValueError as e:
        return json_error(str(e))

    try:
        from scripts.wifi.aireplay import deauth as aireplay_deauth
        output = aireplay_deauth(ap_mac, target_mac, selected_interface, frames)
        return json_success(message=output)
    except Exception as e:
        return json_error(f'Aireplay error: {str(e)}', 500)


if __name__ == '__main__':
    host = '0.0.0.0'
    port = 8080
    app.logger.info("Server running at http://%s:%s (log file: %s)", host, port, log_path)
    socketio.run(app, host=host, port=port, debug=True)
