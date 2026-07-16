from flask import Flask, render_template, request, jsonify, send_from_directory
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

from routes import register_blueprints
from scripts.interfaceTools import (
    get_bluetooth_devices,
    get_network_interfaces,
    lookup_manufacturer,
    spoof_mac,
)
from scripts.logging_config import configure_logging
from scripts.networkScan import (
    active_scan,
    passive_scan,
    classify_scan_results,
    get_mac_by_ip,
    get_ip_by_mac,
)


app = Flask(__name__)
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
MAC_RE = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$')



ROADMAP_SECTIONS = [
    {
        'title': 'High-impact UX',
        'items': [
            {'title': 'Adapter health badges', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Shows Ready/state, No address, and adapter type directly on adapter cards.', 'description': 'Show Ready, Missing tools, Down, No address, monitor-mode, and action availability directly on adapter cards.'},
            {'title': 'Adapter action readiness panel', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Interface detail pages include an Action Readiness panel with available actions and dependency guidance.', 'description': 'Summarize exactly what each adapter can do and why unavailable actions are disabled.'},
            {'title': 'Better empty and error states', 'priority': 'High', 'priority_class': 'danger', 'description': 'Replace generic scan failures with actionable install/setup guidance and links to capabilities.'},
            {'title': 'Export reports', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Export interfaces, scan results, capabilities, and discovered devices as JSON, CSV, Markdown, or HTML.'},
        ],
    },
    {
        'title': 'Network visibility',
        'items': [
            {'title': 'Device inventory page', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'The /inventory page aggregates discovered devices, sources, interfaces, manufacturers, and first/last seen timestamps.', 'description': 'Aggregate discovered IPs, MACs, manufacturers, ports, SSIDs, and first/last seen timestamps.'},
            {'title': 'Network map', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Visualize adapters, SSIDs, access points, clients, and wired hosts as a simple topology map.'},
            {'title': 'Manufacturer/OUI insights', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Inventory groups devices by manufacturer and highlights unknown OUIs for review.', 'description': 'Group discovered devices by vendor and highlight unknown or unusual manufacturers.'},
            {'title': 'New device alerts', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Notify when a newly observed MAC, IP, SSID, or Bluetooth device appears.'},
        ],
    },
    {
        'title': 'Wireless and Bluetooth',
        'items': [
            {'title': 'Wi-Fi channel and band charts', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Chart 2.4/5 GHz occupancy, overlapping channels, security, and signal strength.'},
            {'title': 'Wireless network timelines', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Track signal, channel, security, AP count, and seen timestamps per SSID/BSSID.'},
            {'title': 'Known network labels', 'priority': 'Low', 'priority_class': 'secondary', 'description': 'Let users mark SSIDs as trusted, lab, suspicious, or ignored.'},
            {'title': 'Bluetooth action checklist', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Bluetooth scans report action capability and show host-tool guidance for bluetoothctl or BlueZ D-Bus support.', 'description': 'Show bluetoothctl, busctl, BlueZ D-Bus, adapter power, pairing, trust, and action readiness.'},
        ],
    },

    {
        'title': 'Wireless risk lab',
        'items': [
            {'title': 'WPA handshake capture lab', 'priority': 'High', 'priority_class': 'danger', 'description': 'Capture, validate, catalog, and export WPA/WPA2 handshake or PMKID evidence from authorized lab networks.'},
            {'title': 'Scoped deauthentication actions', 'priority': 'High', 'priority_class': 'danger', 'description': 'Run AP-wide or client-specific deauthentication actions against authorized lab networks with targeting controls, rate limits, and clear logs.'},
            {'title': 'Remote cracking orchestration', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Queue authorized handshake material to stronger remote workers such as Spark, track job progress, and import results for password-strength review.'},
            {'title': 'PineAP-style recon and campaign engine', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Build functional WiFi Pineapple-style recon, campaign, handshake, module, and Cloud C2-inspired workflows for authorized labs.'},
            {'title': 'Evil twin and captive portal lab', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Run controlled rogue-AP and captive-portal lab workflows with explicit SSID targeting, logging, cleanup, and detection guidance.'},
            {'title': 'WPS exposure checks', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Identify lab networks advertising WPS and explain why WPS increases wireless credential risk.'},
            {'title': 'Client privacy and probe request monitor', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Monitor probe behavior to show device presence, preferred-network leakage, and tracking risk in authorized training environments.'},
            {'title': 'Rogue DHCP, DNS, and portal lab', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Run isolated post-association lab workflows for rogue DHCP, DNS manipulation, and portal redirection with validation checks.'},
            {'title': 'RF interference awareness', 'priority': 'Low', 'priority_class': 'secondary', 'description': 'Provide detection-only views for congestion and interference risks without implementing jamming behavior.'},
        ],
    },

    {
        'title': 'Hak5-inspired lab features',
        'items': [
            {'title': 'Payload profile switchboard', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Create selectable, named operational profiles with prerequisites, status feedback, logs, and operator review before execution.'},
            {'title': 'Inline network tap mode', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Offer Packet Squirrel-style lab views for packet capture, transparent bridge/NAT/VPN concepts, and defensive visibility.'},
            {'title': 'DNS manipulation lab', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Run DNS spoofing or redirection workflows inside isolated lab networks, with validation, logging, and cleanup controls.'},
            {'title': 'Cloud C2-style operations controller', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Coordinate approved jobs, progress, artifacts, and remote workers across local and remote lab devices from one dashboard.'},
            {'title': 'Payload/module marketplace', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Add a curated module library with prerequisites, expected outputs, configuration, cleanup steps, and professional operator notes.'},
            {'title': 'Quick wired recon profile', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Add Shark Jack-style rapid wired-network assessment views for host discovery, service summaries, and risk scoring.'},
            {'title': 'Evidence and loot vault', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Collect scan outputs, captures, screenshots, and notes into a time-stamped class report with export controls.'},
            {'title': 'HID and USB training module', 'priority': 'Low', 'priority_class': 'secondary', 'description': 'Provide Rubber Ducky/Bash Bunny-inspired HID and composite-USB workflows for managed lab machines with logging and cleanup.'},
            {'title': 'Screen capture risk module', 'priority': 'Low', 'priority_class': 'secondary', 'description': 'Model Screen Crab-style HDMI observation risk with explicit lab device selection, consent state, and detection/reporting guidance.'},
        ],
    },
    {
        'title': 'Safety and architecture',
        'items': [
            {'title': 'Authorization guardrails', 'priority': 'High', 'priority_class': 'danger', 'description': 'Require explicit authorization confirmation and add clearer logs before noisy red-team actions.'},
            {'title': 'Demo/simulation mode', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Provide fake adapters, devices, networks, and scan results for demos and UI testing without hardware.'},
            {'title': 'Central capability registry', 'priority': 'High', 'priority_class': 'danger', 'description': 'Describe each feature once with required commands, packages, platforms, checks, and install hints.'},
            {'title': 'Background scan jobs', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Move long-running scans into cancellable jobs with progress updates over Socket.IO.'},
            {'title': 'Partial adapter updates', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Update adapter cards and navbar content without full-page reloads when interfaces change.'},
        ],
    },
]


def remaining_roadmap_items():
    """Return roadmap entries that have not been checked off as done."""
    remaining = []
    for section in ROADMAP_SECTIONS:
        for item in section['items']:
            if item.get('status') != 'Done':
                remaining.append({**item, 'section': section['title']})
    return remaining


BLUETOOTHCTL_ACTIONS = {
    'info': 'info',
    'connect': 'connect',
    'disconnect': 'disconnect',
    'pair': 'pair',
    'trust': 'trust',
    'untrust': 'untrust',
    'block': 'block',
    'unblock': 'unblock',
    'remove': 'remove',
}
BLUETOOTH_MAC_RE = re.compile(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$')

DEAUTH_FRAME_LIMIT = 5
BROADCAST_MAC = 'ff:ff:ff:ff:ff:ff'


def normalize_mac(value):
    """Return a lowercase colon-separated MAC address or raise ValueError."""
    if not value or not MAC_RE.match(value):
        raise ValueError('Enter a valid MAC address in the form aa:bb:cc:dd:ee:ff')
    return value.lower().replace('-', ':')


def validate_lab_deauth_request(data):
    """Validate bounded deauth lab inputs for an authorized classroom exercise."""
    ap_mac = normalize_mac(data.get('ap'))
    target_mac = normalize_mac(data.get('target') or BROADCAST_MAC)
    if ap_mac == BROADCAST_MAC:
        raise ValueError('AP MAC must be a specific lab access point, not broadcast')
    if data.get('authorized') != 'on':
        raise ValueError('Confirm this is an authorized isolated lab network before running deauth')
    frames = parse_int(data.get('frames'), 'Frames must be an integer')
    if frames < 1 or frames > DEAUTH_FRAME_LIMIT:
        raise ValueError(f'Frames must be between 1 and {DEAUTH_FRAME_LIMIT} for first-year labs')
    return ap_mac, target_mac, frames


class BluetoothToolUnavailable(RuntimeError):
    """Raised when host-local Bluetooth actions cannot be executed."""


def _busctl_bluez_available(busctl):
    try:
        result = subprocess.run(
            [busctl, 'tree', 'org.bluez'],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def bluetooth_action_capability():
    bluetoothctl = shutil.which('bluetoothctl')
    if bluetoothctl:
        return {
            'available': True,
            'tool': 'bluetoothctl',
            'path': bluetoothctl,
            'message': 'Bluetooth actions are available through bluetoothctl.',
        }
    busctl = shutil.which('busctl')
    if busctl and _busctl_bluez_available(busctl):
        return {
            'available': True,
            'tool': 'busctl',
            'path': busctl,
            'message': 'Bluetooth actions are available through BlueZ D-Bus via busctl.',
        }
    return {
        'available': False,
        'tool': None,
        'path': None,
        'message': 'Bluetooth actions require BlueZ bluetoothctl, or busctl with a running BlueZ D-Bus service on this host.',
    }


def _bluetooth_device_path_from_busctl(busctl, address, timeout=10):
    device_token = 'dev_' + address.upper().replace(':', '_')
    result = subprocess.run(
        [busctl, 'tree', 'org.bluez'],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or 'BlueZ D-Bus tree lookup failed').strip())

    for line in result.stdout.splitlines():
        if device_token in line:
            match = re.search(r'(/org/bluez/[^\s]+)', line)
            if match:
                return match.group(1)
    raise RuntimeError(f'Bluetooth device {address} was not found in BlueZ D-Bus. Scan or pair the device first.')


def _run_busctl_bluetooth_action(busctl, action, address, timeout=15):
    path = _bluetooth_device_path_from_busctl(busctl, address, timeout=timeout)

    if action in {'connect', 'disconnect', 'pair'}:
        method = {'connect': 'Connect', 'disconnect': 'Disconnect', 'pair': 'Pair'}[action]
        command = [busctl, 'call', 'org.bluez', path, 'org.bluez.Device1', method]
    elif action in {'trust', 'untrust', 'block', 'unblock'}:
        property_name = 'Trusted' if action in {'trust', 'untrust'} else 'Blocked'
        value = 'true' if action in {'trust', 'block'} else 'false'
        command = [busctl, 'set-property', 'org.bluez', path, 'org.bluez.Device1', property_name, 'b', value]
    elif action == 'remove':
        adapter_path = path.rsplit('/dev_', 1)[0]
        command = [busctl, 'call', 'org.bluez', adapter_path, 'org.bluez.Adapter1', 'RemoveDevice', 'o', path]
    elif action == 'info':
        outputs = []
        for property_name in ['Address', 'Name', 'Alias', 'Paired', 'Connected', 'Trusted', 'Blocked']:
            result = subprocess.run(
                [busctl, 'get-property', 'org.bluez', path, 'org.bluez.Device1', property_name],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            if result.returncode == 0:
                outputs.append(f'{property_name}: {(result.stdout or '').strip()}')
        return '\n'.join(outputs) or f'BlueZ D-Bus info completed for {address}'
    else:
        raise ValueError('Unsupported Bluetooth action')

    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    output = (result.stdout or result.stderr or '').strip()
    if result.returncode != 0:
        raise RuntimeError(output or f'busctl Bluetooth {action} failed')
    return output or f'busctl Bluetooth {action} completed for {address}'


def run_bluetoothctl_action(action, address, timeout=15):
    """Run a safe local bluetoothctl action against a device visible to this host."""
    command = BLUETOOTHCTL_ACTIONS.get(action)
    if not command:
        raise ValueError('Unsupported Bluetooth action')
    if not BLUETOOTH_MAC_RE.match(address or ''):
        raise ValueError('A valid Bluetooth device address is required')

    capability = bluetooth_action_capability()
    tool = capability['path']
    if not tool:
        raise BluetoothToolUnavailable(capability['message'])
    if capability['tool'] == 'busctl':
        return _run_busctl_bluetooth_action(tool, action, address, timeout=timeout)

    result = subprocess.run(
        [tool, command, address],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    output = (result.stdout or result.stderr or '').strip()
    if result.returncode != 0:
        raise RuntimeError(output or f'bluetoothctl {command} failed')
    return output or f'bluetoothctl {command} completed'


def normalize_mac(mac):
    """Normalize a MAC-like value to colon-separated lowercase format."""
    if not mac:
        return None
    value = str(mac).strip().replace('-', ':').lower()
    if MAC_RE.match(value):
        return value
    return None


def inventory_key(device):
    mac = normalize_mac(device.get('mac') or device.get('address'))
    if mac:
        return f"mac:{mac}"
    ip = device.get('ip')
    if ip:
        return f"ip:{ip}"
    ssid = device.get('ssid')
    bssid = normalize_mac(device.get('bssid'))
    if ssid or bssid:
        return f"wifi:{ssid or 'hidden'}:{bssid or 'unknown'}"
    return None


def record_inventory_devices(devices, source, interface=None):
    """Merge discovered devices into the in-memory inventory with OUI metadata."""
    now = time.time()
    changed_devices = []
    with device_inventory_lock:
        for raw_device in devices or []:
            device = dict(raw_device)
            mac = normalize_mac(device.get('mac') or device.get('address') or device.get('bssid'))
            if mac:
                device['mac'] = mac
            key = inventory_key(device)
            if not key:
                continue
            existing = device_inventory.get(key, {})
            first_seen = existing.get('first_seen', now)
            sources = sorted(set(existing.get('sources', [])) | {source})
            interfaces_seen = sorted(set(existing.get('interfaces', [])) | ({interface} if interface else set()))
            manufacturer = device.get('manufacturer') or (lookup_manufacturer(mac) if mac else None) or existing.get('manufacturer') or 'Unknown'
            merged = {
                **existing,
                **{k: v for k, v in device.items() if v not in (None, '')},
                'id': key,
                'mac': mac or existing.get('mac'),
                'manufacturer': manufacturer,
                'first_seen': first_seen,
                'last_seen': now,
                'sources': sources,
                'interfaces': interfaces_seen,
            }
            device_inventory[key] = merged
            changed_devices.append(dict(merged))
    return changed_devices


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
        item['display_name'] = item.get('name') or item.get('hostname') or item.get('ssid') or item.get('ip') or item.get('mac') or 'Unknown device'
        item['manufacturer'] = item.get('manufacturer') or 'Unknown'
        item['is_unknown_manufacturer'] = item['manufacturer'] == 'Unknown'
        item['first_seen_label'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(item.get('first_seen', 0)))
        item['last_seen_label'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(item.get('last_seen', 0)))
    return sorted(records, key=lambda item: item.get('last_seen', 0), reverse=True)


def manufacturer_insights(records=None):
    """Summarize the current inventory by manufacturer/OUI."""
    records = records if records is not None else inventory_records()
    vendors = {}
    unknown = 0
    for item in records:
        vendor = item.get('manufacturer') or 'Unknown'
        vendors.setdefault(vendor, {'manufacturer': vendor, 'count': 0, 'devices': []})
        vendors[vendor]['count'] += 1
        vendors[vendor]['devices'].append(item)
        if vendor == 'Unknown':
            unknown += 1
    top_vendors = sorted(vendors.values(), key=lambda item: (-item['count'], item['manufacturer']))
    return {
        'total_devices': len(records),
        'known_manufacturers': len([vendor for vendor in vendors if vendor != 'Unknown']),
        'unknown_manufacturers': unknown,
        'top_vendors': top_vendors,
    }


def json_error(message, status=400):
    """Return a consistently shaped JSON error response."""
    return jsonify({'status': 'error', 'message': message}), status


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


def _set_scan_job(job_id, **updates):
    with scan_jobs_lock:
        scan_jobs[job_id].update(updates)


def _run_scan_job(job_id, scan_type, selected_interface):
    _set_scan_job(job_id, status='running', started_at=time.time())
    try:
        if scan_type == 'wlan':
            from scripts.wifi import utils as wifi_utils
            wifi_utils.scan_networks(selected_interface)
            result = {'wlans': wifi_utils.get_networks_summary()}
        elif scan_type == 'bluetooth':
            devices = asyncio.run(get_bluetooth_devices())
            result = {
                'devices': [
                    {'address': dev.address, 'name': dev.name, 'manufacturer': lookup_manufacturer(dev.address)}
                    for dev in devices
                ],
                'action_capability': bluetooth_action_capability(),
            }
        else:
            raise ValueError('Unsupported scan type')
        if scan_type == 'bluetooth':
            record_inventory_devices(result.get('devices', []), 'bluetooth-scan', selected_interface)
        _set_scan_job(job_id, status='completed', completed_at=time.time(), result=result)
    except Exception as exc:
        _set_scan_job(job_id, status='failed', completed_at=time.time(), error=str(exc))



def _port_scan_job_snapshot(job):
    return {
        **job,
        'open_ports': list(job.get('open_ports', [])),
    }


def update_port_scan_job(job_id, **updates):
    with port_scan_jobs_lock:
        job = port_scan_jobs.get(job_id)
        if not job:
            return None
        job.update(updates)
        job['updated_at'] = time.time()
        return _port_scan_job_snapshot(job)


def run_port_scan_job(job_id):
    from scripts.portScanner import PortScanError, scan_ports

    with port_scan_jobs_lock:
        job = port_scan_jobs.get(job_id)
        if not job:
            return
        host = job['host']
        start = job['start']
        end = job['end']
        total = job['total_ports']
        job['status'] = 'running'
        job['started_at'] = time.time()
        job['updated_at'] = job['started_at']

    scanned = 0

    def on_open(port):
        with port_scan_jobs_lock:
            current = port_scan_jobs.get(job_id)
            if not current:
                return
            if port not in current['open_ports']:
                current['open_ports'].append(port)
                current['open_ports'].sort()
            current['message'] = f'Open port found: {port}'
            current['updated_at'] = time.time()

    def on_progress(port):
        nonlocal scanned
        scanned += 1
        with port_scan_jobs_lock:
            current = port_scan_jobs.get(job_id)
            if not current:
                return
            current['scanned_ports'] = scanned
            current['current_port'] = port
            current['progress'] = round((scanned / total) * 100, 1) if total else 100
            current['updated_at'] = time.time()

    try:
        ports = scan_ports(host, start, end, on_open=on_open, on_progress=on_progress, max_ports=None)
        update_port_scan_job(
            job_id,
            status='complete',
            open_ports=ports,
            scanned_ports=total,
            current_port=end,
            progress=100,
            completed_at=time.time(),
            message=f'Port scan complete: {len(ports)} open port(s) found.',
        )
    except PortScanError as e:
        update_port_scan_job(job_id, status='failed', error=str(e), message=str(e), completed_at=time.time())
    except Exception as e:
        update_port_scan_job(job_id, status='failed', error=str(e), message=f'Port scan failed: {e}', completed_at=time.time())


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
        'scanned_ports': 0,
        'total_ports': end - start + 1,
        'current_port': None,
        'progress': 0,
        'message': 'Port scan queued.',
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
    job_id = uuid.uuid4().hex
    with scan_jobs_lock:
        scan_jobs[job_id] = {
            'id': job_id,
            'scan_type': scan_type,
            'selected_interface': selected_interface,
            'status': 'queued',
            'created_at': time.time(),
        }
    threading.Thread(target=_run_scan_job, args=(job_id, scan_type, selected_interface), daemon=True).start()
    return scan_jobs[job_id]


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


register_blueprints(app, current_context)


# Endpoint to fetch the current list of network adapters
@app.route('/adapters', methods=['POST'])
def adapters():
    """Return the available network interfaces as JSON."""
    return jsonify({'interfaces': [iface.to_dict() for iface in network_interfaces]})




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


@app.route('/network-scan')
def network_scan():
    return render_template('network_scan.html', title='Network Scan', **current_context())


@app.route('/inventory')
def inventory_page():
    records = inventory_records()
    return render_template(
        'inventory.html',
        title='Device Inventory',
        devices=records,
        insights=manufacturer_insights(records),
        **current_context(),
    )


@app.route('/port-scan')
def port_scan_page():
    return render_template('port_scan.html', title='Port Scan', **current_context())


@app.route('/traceroute')
def traceroute_page():
    return render_template('traceroute.html', title='Traceroute', **current_context())


@app.route('/clients/<identifier>')
def client_detail(identifier):
    """Display details for a client identified by MAC or IP address."""
    mac_re = re.compile(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$')

    mac = None
    ip = None

    if mac_re.match(identifier):
        # Identifier is a MAC address
        mac = identifier
        ip = get_ip_by_mac(mac)
    else:
        # Identifier is likely an IP address
        ip = identifier
        mac = get_mac_by_ip(ip)

    manufacturer = lookup_manufacturer(mac) if mac else 'Unknown'

    return render_template(
        'client_detail.html',
        title=f'Client {identifier}',
        ip=ip,
        mac=mac,
        manufacturer=manufacturer,
        **current_context(),
    )


@app.route('/active-scan', methods=['POST'])
def active_scan_route():
    iface = request.form.get('selectedInterface')
    if not iface:
        return json_error('Missing interface')
    hosts = classify_scan_results(active_scan(iface), iface)
    enriched_hosts = record_inventory_devices(hosts, 'active-scan', iface)
    return jsonify({'hosts': enriched_hosts})


@app.route('/passive-scan', methods=['POST'])
def passive_scan_route():
    iface = request.form.get('selectedInterface')
    if not iface:
        return json_error('Missing interface')
    devices = classify_scan_results(passive_scan(iface), iface)
    enriched_devices = record_inventory_devices(devices, 'passive-scan', iface)
    return jsonify({'devices': enriched_devices})


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

    from scripts.portScanner import PortScanError, scan_ports

    try:
        ports = scan_ports(data.get('host'), start_port, end_port)
    except PortScanError as e:
        return json_error(str(e))

    return jsonify({'ports': ports})


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


@app.route('/traceroute', methods=['POST'])
def traceroute_route():
    host = request.form.get('host')
    if not host:
        return json_error('Missing host')
    from scripts.traceroute import traceroute
    hops = traceroute(host)
    return jsonify({'hops': hops})


@app.route('/wireless/network')
def wireless_network_detail():
    ssid = request.args.get('ssid')
    bssid = request.args.get('bssid')
    selected_interface = request.args.get('interface')

    if not ssid and not bssid:
        return "Wireless network not specified", 400

    from scripts.wifi import utils as wifi_utils
    network = wifi_utils.get_network_detail(ssid=ssid, bssid=bssid, interface_name=selected_interface)
    back_url = f"/wireless/{selected_interface}" if selected_interface else "/wireless"
    return render_template(
        'wireless_network_detail.html',
        title=f"{network['ssid']} Details",
        network=network,
        back_url=back_url,
        **current_context(),
    )


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
        return render_template('interface_detail.html', title=interface.name, interface=interface, **current_context())
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
        return json_success(job=dict(job))


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
        devices_summary = [
            {'address': dev.address, 'name': dev.name, 'manufacturer': lookup_manufacturer(dev.address)}
            for dev in devices
        ]
        return json_success(devices=devices_summary, action_capability=bluetooth_action_capability())
    except Exception as e:
        return json_error(f'Bluetooth scan error: {str(e)}', 500)


@app.route('/bluetooth-action', methods=['POST'])
def bluetooth_action():
    data = request.form
    action = data.get('action')
    address = data.get('address')

    try:
        output = run_bluetoothctl_action(action, address)
        return json_success(message='Bluetooth action completed', output=output)
    except ValueError as e:
        return json_error(str(e))
    except BluetoothToolUnavailable as e:
        return json_error(str(e), 501)
    except Exception as e:
        return json_error(f'Bluetooth action error: {str(e)}', 500)


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
        ap_mac, target_mac, frames = validate_lab_deauth_request(data)
    except ValueError as e:
        return json_error(str(e))

    try:
        from scripts.wifi.deauth import deauth
        deauth(ap_mac, target_mac, selected_interface, frames)
        return json_success(message=f'Sent {frames} authorized lab deauth frames on {selected_interface}')
    except Exception as e:
        return json_error(f'Deauth error: {str(e)}', 500)


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
