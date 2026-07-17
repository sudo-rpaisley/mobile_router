from flask import Flask, Response, render_template, request, jsonify, send_from_directory, send_file
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
from urllib.parse import quote
from werkzeug.utils import secure_filename

from routes import register_blueprints
from scripts.interfaceTools import (
    get_bluetooth_devices,
    get_network_interfaces,
    lookup_manufacturer,
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
bluetooth_action_histories = {}
bluetooth_action_histories_lock = threading.Lock()
new_device_alerts = []
new_device_alerts_lock = threading.Lock()
evidence_vault = []
evidence_vault_lock = threading.Lock()
EVIDENCE_DIR = os.path.join(app.instance_path, 'evidence_vault')
MAC_RE = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$')



ROADMAP_SECTIONS = [
    {
        'title': 'High-impact UX',
        'items': [
            {'title': 'Adapter health badges', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Shows Ready/state, No address, and adapter type directly on adapter cards.', 'description': 'Show Ready, Missing tools, Down, No address, monitor-mode, and action availability directly on adapter cards.'},
            {'title': 'Adapter action readiness panel', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Interface detail pages include an Action Readiness panel with available actions and dependency guidance.', 'description': 'Summarize exactly what each adapter can do and why unavailable actions are disabled.'},
            {'title': 'Better empty and error states', 'priority': 'High', 'priority_class': 'danger', 'description': 'Replace generic scan failures with actionable install/setup guidance and links to capabilities.'},
            {'title': 'Layout density and navigation review', 'priority': 'High', 'priority_class': 'danger', 'description': 'Compare tabs, accordions, split panels, compact/advanced modes, and dashboard drill-downs before adding more controls to dense pages.'},
            {'title': 'Tabbed interface detail layout', 'priority': 'High', 'priority_class': 'danger', 'description': 'Adopt option A: organize dense interface pages into tabs such as Overview, Scan Results, Charts, Actions, Diagnostics, and History.'},
            {'title': 'Export reports', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Reports page exports inventory, interfaces, capabilities, jobs, alerts, and evidence as JSON, CSV, Markdown, or HTML.', 'description': 'Export interfaces, scan results, capabilities, and discovered devices as JSON, CSV, Markdown, or HTML.'},
        ],
    },
    {
        'title': 'Network visibility',
        'items': [
            {'title': 'Device inventory page', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'The /inventory page aggregates discovered devices, sources, interfaces, manufacturers, and first/last seen timestamps.', 'description': 'Aggregate discovered IPs, MACs, manufacturers, ports, SSIDs, and first/last seen timestamps.'},
            {'title': 'Network map', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Visualize adapters, SSIDs, access points, clients, and wired hosts as a simple topology map.'},
            {'title': 'Dedicated wireless occupancy report page', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Create a drill-down page that compares adapters, channel congestion, BSSID detail, historical heatmaps, and exportable recommendations.'},
            {'title': 'Manufacturer/OUI insights', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Inventory groups devices by manufacturer and highlights unknown OUIs for review.', 'description': 'Group discovered devices by vendor and highlight unknown or unusual manufacturers.'},
            {'title': 'New device alerts', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'New devices create unread alerts with a navbar badge and alert center.', 'description': 'Notify when a newly observed MAC, IP, SSID, or Bluetooth device appears.'},
        ],
    },
    {
        'title': 'Wireless and Bluetooth',
        'items': [
            {'title': 'Wi-Fi channel and band charts', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Wireless scan results include channel and band occupancy charts.', 'description': 'Chart 2.4/5 GHz occupancy, overlapping channels, security, and signal strength.'},
            {'title': 'Wireless network timelines', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Track signal, channel, security, AP count, and seen timestamps per SSID/BSSID.'},
            {'title': 'Server-side wireless occupancy history', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Persist repeated scan occupancy by adapter so heatmaps, channel recommendations, and reports survive browser sessions and server restarts.'},
            {'title': 'Bluetooth metadata refresh pipeline', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Parse single-device Bluetooth refresh output into inventory fields, update contextual controls, and show last-refreshed timestamps without a full page reload.'},
            {'title': 'Bluetooth destructive-action confirmations', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Add clearer confirmation modals, host-stack vs inventory-only explanations, and undo for inventory-only forget actions.'},
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
            {'title': 'WPS exposure checks', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Wireless scan results and network detail pages now flag APs advertising WPS and explain why WPS can weaken credential protection.', 'description': 'Identify lab networks advertising WPS and explain why WPS increases wireless credential risk.'},
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
            {'title': 'Evidence and loot vault', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Evidence Vault stores timestamped notes, scan output, captures, screenshots, and file metadata with JSON/CSV/Markdown export controls.', 'description': 'Collect scan outputs, captures, screenshots, and notes into a time-stamped class report with export controls.'},
            {'title': 'HID and USB training module', 'priority': 'Low', 'priority_class': 'secondary', 'description': 'Provide Rubber Ducky/Bash Bunny-inspired HID and composite-USB workflows for managed lab machines with logging and cleanup.'},
            {'title': 'Screen capture risk module', 'priority': 'Low', 'priority_class': 'secondary', 'description': 'Model Screen Crab-style HDMI observation risk with explicit lab device selection, consent state, and detection/reporting guidance.'},
        ],
    },
    {
        'title': 'Safety and architecture',
        'items': [
            {'title': 'Central capability registry', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Capabilities now come from a central registry with required commands, packages, platforms, runtime checks, install hints, UI rendering, and JSON export.', 'description': 'Describe each feature once with required commands, packages, platforms, checks, and install hints.'},
            {'title': 'Background scan jobs', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Wireless, Bluetooth, and port scans now use tracked background jobs with live status polling and cancellation controls.', 'description': 'Move long-running scans into cancellable jobs with progress updates over Socket.IO.'},
            {'title': 'Partial adapter updates', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Adapter polling now returns targeted navbar/card fragments for DOM replacement without a full-page reload.', 'description': 'Update adapter cards and navbar content without full-page reloads when interfaces change.'},
            {'title': 'Browser-level UI smoke tests', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Browser-oriented tests now assert the Bluetooth contextual controls, AJAX re-render hooks, Wi-Fi dashboard controls, BSSID mode, export buttons, and full-screen map hooks.', 'description': 'Cover high-value template and JavaScript behavior so richer UI controls do not regress.'},
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


def run_bluetoothctl_action(action, address, timeout=15, adapter=None):
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

    if adapter:
        result = subprocess.run(
            [tool],
            input=f'select {adapter}\n{command} {address}\n',
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    else:
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



def create_new_device_alert(device, source, interface=None):
    """Record an unread alert for a newly observed inventory device."""
    display_name = device.get('name') or device.get('hostname') or device.get('ssid') or device.get('ip') or device.get('mac') or 'Unknown device'
    device_identifier = device.get('mac') or device.get('bssid') or device.get('ip')
    device_url = f"/clients/{quote(str(device_identifier))}" if device_identifier else None
    alert = {
        'id': uuid.uuid4().hex,
        'device_id': device.get('id'),
        'display_name': display_name,
        'ip': device.get('ip'),
        'mac': device.get('mac') or device.get('bssid'),
        'manufacturer': device.get('manufacturer') or 'Unknown',
        'device_url': device_url,
        'source': source,
        'interface': interface,
        'created_at': time.time(),
        'read': False,
    }
    with new_device_alerts_lock:
        new_device_alerts.insert(0, alert)
        del new_device_alerts[200:]
    return alert



def evidence_records():
    """Return evidence vault records with display labels."""
    with evidence_vault_lock:
        records = [dict(item) for item in evidence_vault]
    for item in records:
        item['created_at_label'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(item.get('created_at', 0)))
    return records


def create_evidence_record(title, category='note', source=None, device=None, notes=None, content=None, uploaded_file=None):
    """Store a timestamped evidence record and optional uploaded file metadata."""
    title = (title or '').strip()
    if not title:
        raise ValueError('Evidence title is required')
    category = (category or 'note').strip().lower()
    if category not in {'note', 'scan-output', 'capture', 'screenshot', 'artifact'}:
        raise ValueError('Unsupported evidence category')

    now = time.time()
    record = {
        'id': uuid.uuid4().hex,
        'title': title,
        'category': category,
        'source': (source or '').strip(),
        'device': (device or '').strip(),
        'notes': (notes or '').strip(),
        'content': (content or '').strip(),
        'created_at': now,
        'file_name': None,
        'file_size': None,
        'download_url': None,
    }

    if uploaded_file and uploaded_file.filename:
        os.makedirs(EVIDENCE_DIR, exist_ok=True)
        safe_name = secure_filename(uploaded_file.filename)
        if not safe_name:
            raise ValueError('Uploaded file name is not valid')
        stored_name = f"{record['id']}-{safe_name}"
        path = os.path.join(EVIDENCE_DIR, stored_name)
        uploaded_file.save(path)
        record.update({
            'file_name': safe_name,
            'stored_name': stored_name,
            'file_size': os.path.getsize(path),
            'download_url': f"/evidence/{record['id']}/download",
        })

    with evidence_vault_lock:
        evidence_vault.insert(0, record)
        del evidence_vault[500:]
    return dict(record)


def evidence_as_csv(records):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Title', 'Category', 'Source', 'Device', 'File', 'Created', 'Notes', 'Content'])
    for item in records:
        writer.writerow([
            item.get('title'),
            item.get('category'),
            item.get('source'),
            item.get('device'),
            item.get('file_name'),
            item.get('created_at_label'),
            item.get('notes'),
            item.get('content'),
        ])
    return output.getvalue()


def evidence_as_markdown(records):
    lines = ['# Evidence Vault', '']
    if not records:
        lines.append('_No evidence records captured yet._')
    for item in records:
        lines.extend([
            f"## {item.get('title', 'Untitled')}",
            f"- Category: {item.get('category') or 'note'}",
            f"- Source: {item.get('source') or '—'}",
            f"- Device: {item.get('device') or '—'}",
            f"- Created: {item.get('created_at_label')}",
        ])
        if item.get('file_name'):
            lines.append(f"- File: {item.get('file_name')} ({item.get('file_size') or 0} bytes)")
        if item.get('notes'):
            lines.extend(['', item.get('notes')])
        if item.get('content'):
            lines.extend(['', '```', item.get('content'), '```'])
        lines.append('')
    return '\n'.join(lines)



def set_interface_power_state(interface_name, desired_state, interface_type=None):
    state = str(desired_state or '').casefold()
    if state not in {'up', 'down'}:
        raise ValueError('Interface state must be up or down')
    system = os.name
    normalized_type = str(interface_type or '').casefold()

    if system == 'nt':
        if normalized_type == 'bluetooth':
            powershell = shutil.which('powershell') or shutil.which('pwsh')
            if not powershell:
                raise RuntimeError('PowerShell is required to toggle Bluetooth adapters on Windows')
            verb = 'Enable-PnpDevice' if state == 'up' else 'Disable-PnpDevice'
            escaped_name = str(interface_name).replace("'", "''")
            command = (
                "$device = Get-PnpDevice -Class Bluetooth -PresentOnly:$false | "
                f"Where-Object {{ $_.FriendlyName -eq '{escaped_name}' -or $_.Name -eq '{escaped_name}' }} | "
                "Select-Object -First 1; "
                "if (-not $device) { throw 'Bluetooth adapter was not found.' }; "
                f"{verb} -InstanceId $device.InstanceId -Confirm:$false"
            )
            result = subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-Command', command], capture_output=True, text=True, timeout=20, check=False)
        else:
            result = subprocess.run(['netsh', 'interface', 'set', 'interface', f'name={interface_name}', f'admin={"enabled" if state == "up" else "disabled"}'], capture_output=True, text=True, timeout=20, check=False)
    else:
        if normalized_type == 'bluetooth':
            bluetoothctl = shutil.which('bluetoothctl')
            if bluetoothctl:
                result = subprocess.run([bluetoothctl, 'power', 'on' if state == 'up' else 'off'], capture_output=True, text=True, timeout=15, check=False)
            else:
                ip_tool = shutil.which('ip')
                if not ip_tool:
                    raise RuntimeError('Toggling this interface requires bluetoothctl or ip')
                result = subprocess.run([ip_tool, 'link', 'set', 'dev', interface_name, state], capture_output=True, text=True, timeout=15, check=False)
        else:
            ip_tool = shutil.which('ip')
            if not ip_tool:
                raise RuntimeError('Toggling interfaces requires the ip command on this host')
            result = subprocess.run([ip_tool, 'link', 'set', 'dev', interface_name, state], capture_output=True, text=True, timeout=15, check=False)

    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or 'Interface state change failed').strip())
    return f'{interface_name} was turned {"on" if state == "up" else "off"}.'

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



def _bluetooth_truthy(value):
    return str(value or '').strip().casefold() in {'1', 'true', 'yes', 'on', 'connected', 'paired', 'trusted', 'blocked'}


def bluetooth_device_state(device):
    device = device or {}
    status = str(device.get('status') or '').casefold()
    return {
        'connected': _bluetooth_truthy(device.get('connected')) or 'connected' in status,
        'paired': _bluetooth_truthy(device.get('paired')) or 'paired' in status,
        'trusted': _bluetooth_truthy(device.get('trusted')) or 'trusted' in status,
        'blocked': _bluetooth_truthy(device.get('blocked')) or 'blocked' in status,
    }


def bluetooth_contextual_actions(device):
    state = bluetooth_device_state(device)
    actions = [{'action': 'info', 'label': 'Info', 'style': 'outline-secondary', 'icon': 'circle-info'}]
    if state['blocked']:
        actions.append({'action': 'unblock', 'label': 'Unblock', 'style': 'outline-success', 'icon': 'check'})
    else:
        if state['connected']:
            actions.append({'action': 'disconnect', 'label': 'Disconnect', 'style': 'outline-warning', 'icon': 'link-slash'})
        else:
            actions.append({'action': 'connect', 'label': 'Connect', 'style': 'outline-primary', 'icon': 'link'})
        if not state['paired']:
            actions.append({'action': 'pair', 'label': 'Pair', 'style': 'outline-primary', 'icon': 'handshake'})
        if state['trusted']:
            actions.append({'action': 'untrust', 'label': 'Untrust', 'style': 'outline-secondary', 'icon': 'shield'})
        else:
            actions.append({'action': 'trust', 'label': 'Trust', 'style': 'outline-success', 'icon': 'shield-halved'})
        actions.append({'action': 'block', 'label': 'Block', 'style': 'outline-danger', 'icon': 'ban'})
    actions.append({'action': 'remove', 'label': 'Remove Pairing', 'style': 'outline-danger', 'icon': 'trash'})
    return actions


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
    """Return alert records with display labels."""
    with new_device_alerts_lock:
        records = [dict(alert) for alert in new_device_alerts]
    for alert in records:
        alert['created_at_label'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(alert.get('created_at', 0)))
    return records


def unread_alert_count():
    with new_device_alerts_lock:
        return len([alert for alert in new_device_alerts if not alert.get('read')])

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
            is_new_device = not existing
            device_inventory[key] = merged
            if is_new_device and not merged.get('is_control_traffic'):
                create_new_device_alert(merged, source, interface)
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
    return {
        **job,
        'kind': 'port-scan',
        'open_ports': list(job.get('open_ports', [])),
        'open_port_details': list(job.get('open_port_details', [])),
        'cancelable': job.get('status') in {'queued', 'running'},
    }


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
    with port_scan_jobs_lock:
        jobs.extend(_port_scan_job_snapshot(job) for job in port_scan_jobs.values())
    return sorted(jobs, key=lambda item: item.get('updated_at') or item.get('created_at') or 0, reverse=True)


def running_job_count():
    return len([job for job in all_job_snapshots() if job.get('status') in {'queued', 'running'}])


def update_port_scan_job(job_id, **updates):
    with port_scan_jobs_lock:
        job = port_scan_jobs.get(job_id)
        if not job:
            return None
        job.update(updates)
        job['updated_at'] = time.time()
        return _port_scan_job_snapshot(job)


def run_port_scan_job(job_id):
    from scripts.portScanner import PortScanError, describe_open_ports, identify_port_service, scan_ports

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
        service_detail = identify_port_service(port)
        with port_scan_jobs_lock:
            current = port_scan_jobs.get(job_id)
            if not current:
                return
            if port not in current['open_ports']:
                current['open_ports'].append(port)
                current['open_ports'].sort()
                current.setdefault('open_port_details', []).append(service_detail)
                current['open_port_details'] = sorted(current['open_port_details'], key=lambda item: item['port'])
            current['message'] = f"Open port found: {port} ({service_detail['service']})"
            current['updated_at'] = time.time()

    def should_cancel():
        with port_scan_jobs_lock:
            return bool(port_scan_jobs.get(job_id, {}).get('cancel_requested'))

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
        ports = scan_ports(host, start, end, on_open=on_open, on_progress=on_progress, should_cancel=should_cancel, max_ports=None)
        if should_cancel():
            update_port_scan_job(job_id, status='cancelled', completed_at=time.time(), message='Port scan cancelled.')
            return
        update_port_scan_job(
            job_id,
            status='complete',
            open_ports=ports,
            open_port_details=describe_open_ports(ports),
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

    devices = inventory_records()
    exported_at = time.time()
    return {
        'exported_at': exported_at,
        'exported_at_label': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(exported_at)),
        'interfaces': [iface.to_dict() for iface in network_interfaces],
        'devices': devices,
        'insights': manufacturer_insights(devices),
        'jobs': all_job_snapshots(),
        'alerts': alert_records(),
        'evidence': evidence_records(),
        'capabilities': build_capabilities(),
    }


def report_as_csv(report):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Mobile Router Report'])
    writer.writerow(['Exported at', report['exported_at_label']])
    writer.writerow([])
    writer.writerow(['Devices'])
    writer.writerow(['Name', 'IP', 'MAC', 'Manufacturer', 'Sources', 'Interfaces', 'First seen', 'Last seen'])
    for device in report['devices']:
        writer.writerow([
            device.get('display_name'),
            device.get('ip'),
            device.get('mac') or device.get('bssid'),
            device.get('manufacturer'),
            ', '.join(device.get('sources', [])),
            ', '.join(device.get('interfaces', [])),
            device.get('first_seen_label'),
            device.get('last_seen_label'),
        ])
    writer.writerow([])
    writer.writerow(['Interfaces'])
    writer.writerow(['Name', 'Type', 'State', 'Manufacturer'])
    for iface in report['interfaces']:
        writer.writerow([iface.get('name'), iface.get('interface_type'), iface.get('state'), iface.get('manufacturer')])
    writer.writerow([])
    writer.writerow(['Jobs'])
    writer.writerow(['ID', 'Kind', 'Label', 'Status', 'Progress'])
    for job in report['jobs']:
        writer.writerow([job.get('id'), job.get('kind'), job.get('label') or job.get('scan_type'), job.get('status'), job.get('progress')])
    writer.writerow([])
    writer.writerow(['Evidence'])
    writer.writerow(['Title', 'Category', 'Source', 'Device', 'File', 'Created'])
    for item in report['evidence']:
        writer.writerow([item.get('title'), item.get('category'), item.get('source'), item.get('device'), item.get('file_name'), item.get('created_at_label')])
    writer.writerow([])
    writer.writerow(['Alerts'])
    writer.writerow(['Device', 'IP', 'MAC', 'Manufacturer', 'Source', 'Read', 'Created'])
    for alert in report['alerts']:
        writer.writerow([alert.get('display_name'), alert.get('ip'), alert.get('mac'), alert.get('manufacturer'), alert.get('source'), alert.get('read'), alert.get('created_at_label')])
    return output.getvalue()


def report_as_markdown(report):
    lines = [
        '# Mobile Router Report',
        '',
        f"Exported at: {report['exported_at_label']}",
        '',
        '## Summary',
        f"- Devices: {report['insights']['total_devices']}",
        f"- Known manufacturers: {report['insights']['known_manufacturers']}",
        f"- Unknown manufacturers: {report['insights']['unknown_manufacturers']}",
        f"- Interfaces: {len(report['interfaces'])}",
        f"- Jobs: {len(report['jobs'])}",
        f"- Alerts: {len(report['alerts'])}",
        f"- Evidence records: {len(report['evidence'])}",
        '',
        '## Devices',
        '| Name | IP | MAC/BSSID | Manufacturer | Sources |',
        '| --- | --- | --- | --- | --- |',
    ]
    for device in report['devices']:
        lines.append(f"| {device.get('display_name', '')} | {device.get('ip') or ''} | {device.get('mac') or device.get('bssid') or ''} | {device.get('manufacturer') or ''} | {', '.join(device.get('sources', []))} |")
    lines.extend(['', '## Interfaces', '| Name | Type | State | Manufacturer |', '| --- | --- | --- | --- |'])
    for iface in report['interfaces']:
        lines.append(f"| {iface.get('name', '')} | {iface.get('interface_type', '')} | {iface.get('state', '')} | {iface.get('manufacturer', '')} |")
    lines.extend(['', '## Evidence', '| Title | Category | Source | Device | File | Created |', '| --- | --- | --- | --- | --- | --- |'])
    for item in report['evidence']:
        lines.append(f"| {item.get('title', '')} | {item.get('category', '')} | {item.get('source') or ''} | {item.get('device') or ''} | {item.get('file_name') or ''} | {item.get('created_at_label') or ''} |")
    lines.extend(['', '## Alerts', '| Device | IP | MAC | Source | Read |', '| --- | --- | --- | --- | --- |'])
    for alert in report['alerts']:
        lines.append(f"| {alert.get('display_name', '')} | {alert.get('ip') or ''} | {alert.get('mac') or ''} | {alert.get('source') or ''} | {alert.get('read')} |")
    return '\n'.join(lines) + '\n'



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
def inventory_page():
    records = inventory_records()
    return render_template(
        'inventory.html',
        title='Device Inventory',
        devices=records,
        insights=manufacturer_insights(records),
        **current_context(),
    )


@app.route('/alerts')
def alerts_page():
    return render_template('alerts.html', title='Alerts', alerts=alert_records(), **current_context())


@app.route('/alerts/status')
def alerts_status():
    alerts = alert_records()
    return json_success(alerts=alerts, unread_count=len([alert for alert in alerts if not alert.get('read')]))


@app.route('/alerts/<alert_id>/read', methods=['POST'])
def mark_alert_read(alert_id):
    with new_device_alerts_lock:
        for alert in new_device_alerts:
            if alert['id'] == alert_id:
                alert['read'] = True
                unread_count = len([item for item in new_device_alerts if not item.get('read')])
                return json_success(alert=dict(alert), unread_count=unread_count)
    return json_error('Alert not found', 404)


@app.route('/alerts/read-all', methods=['POST'])
def mark_all_alerts_read():
    with new_device_alerts_lock:
        for alert in new_device_alerts:
            alert['read'] = True
    return json_success(unread_count=0)


@app.route('/port-scan')
def port_scan_page():
    return render_template('port_scan.html', title='Port Scan', **current_context())


@app.route('/jobs')
def jobs_page():
    return render_template('jobs.html', title='Jobs', **current_context())


@app.route('/traceroute')
def traceroute_page():
    return render_template('traceroute.html', title='Traceroute', **current_context())


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

    manufacturer = (inventory_device or {}).get('manufacturer') or (lookup_manufacturer(mac) if mac else 'Unknown')
    display_name = (
        (inventory_device or {}).get('name')
        or (inventory_device or {}).get('display_name')
        or mac
        or ip
        or identifier
    )

    return render_template(
        'client_detail.html',
        title=f'Client {display_name}',
        ip=ip,
        mac=mac,
        manufacturer=manufacturer,
        display_name=display_name,
        is_bluetooth=is_bluetooth,
        bluetooth_fields=bluetooth_detail_fields(inventory_device) if is_bluetooth else [],
        bluetooth_action_capability=bluetooth_action_capability() if is_bluetooth else None,
        bluetooth_actions=bluetooth_contextual_actions(inventory_device) if is_bluetooth else [],
        bluetooth_adapters=bluetooth_adapter_choices() if is_bluetooth else [],
        bluetooth_action_history=bluetooth_action_history(mac) if is_bluetooth else [],
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

    from scripts.portScanner import PortScanError, describe_open_ports, scan_ports

    try:
        ports = scan_ports(data.get('host'), start_port, end_port)
    except PortScanError as e:
        return json_error(str(e))

    return jsonify({'ports': ports, 'port_details': describe_open_ports(ports)})


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
