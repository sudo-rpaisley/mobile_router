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
import ipaddress
import socket
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
evil_twin_lab_runs = []
evil_twin_lab_lock = threading.Lock()
pineap_lab_runs = []
pineap_lab_lock = threading.Lock()
handshake_lab_records = []
handshake_lab_lock = threading.Lock()
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
HTTP_PREVIEW_DIR = os.path.join(app.instance_path, 'http_previews')
EVIDENCE_DIR = os.path.join(app.instance_path, 'evidence_vault')
MAC_RE = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$')


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
    return {
        'device_inventory': inventory,
        'new_device_alerts': alerts,
        'evidence_vault': evidence,
        'watched_clients': sorted(watched_clients),
        'client_timelines': timelines,
        'scheduled_client_checks': dict(scheduled_client_checks),
        'wireless_network_client_cache': wireless_network_client_cache,
        'wireless_network_labels': dict(wireless_network_labels),
        'bluetooth_action_histories': bluetooth_action_histories,
        'evil_twin_lab_runs': evil_twin_lab_runs,
        'pineap_lab_runs': pineap_lab_runs,
        'handshake_lab_records': handshake_lab_records,
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
    bluetooth_action_histories.update(state.get('bluetooth_action_histories') or {})
    evil_twin_lab_runs.extend(state.get('evil_twin_lab_runs') or [])
    pineap_lab_runs.extend(state.get('pineap_lab_runs') or [])
    handshake_lab_records.extend(state.get('handshake_lab_records') or [])
    return state


load_runtime_state()


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
        'title': 'Guided modes and progression',
        'items': [
            {'title': 'Full and training mode switch', 'priority': 'High', 'priority_class': 'danger', 'description': 'Add a mode selector where Full mode exposes every available feature and Training mode starts with a limited guided toolset.'},
            {'title': 'Progressive training unlocks', 'priority': 'High', 'priority_class': 'danger', 'description': 'In Training mode, unlock the next control only after the learner completes the current step, such as scanning before connection, diagnostics, exports, or advanced actions.'},
            {'title': 'Guided focus overlay', 'priority': 'High', 'priority_class': 'danger', 'description': 'Guide learners by dimming the layout and spotlighting/circling the next control, with step instructions and progress state.'},
            {'title': 'Training trophies and milestones', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Award trophies for milestones such as 20 completed scans, first Bluetooth refresh, first OUI lookup, first export, and completion of each guided module.'},
        ],
    },
    {
        'title': 'Training trophies',
        'items': [
            {'title': 'Scan milestone trophies', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Award first Wi-Fi scan, first Bluetooth scan, 10 scans, 20 scans, first scan with more than five networks, first multi-BSSID SSID, and first hidden network discovered.'},
            {'title': 'Wireless analysis trophies', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Award channel congestion review, 2.4/5 GHz comparison, occupancy export, BSSID drill-down, OUI/vendor lookup, WPS exposure finding, and best-channel recommendation review.'},
            {'title': 'Bluetooth workflow trophies', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Award first Bluetooth device discovery, metadata refresh, state interpretation, vendor identification, action history entry, and inventory-only forget action.'},
            {'title': 'Reporting and evidence trophies', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Award first report export, evidence note, saved scan evidence, complete training report, and explain-this-finding write-up.'},
            {'title': 'Training completion trophies', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Award Wireless Basics, Bluetooth Basics, Diagnostics, Reports, and Full Training Path completion trophies as learners finish guided modules.'},
        ],
    },
    {
        'title': 'Network visibility',
        'items': [
            {'title': 'Device inventory page', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'The /inventory page aggregates discovered devices, sources, interfaces, manufacturers, and first/last seen timestamps.', 'description': 'Aggregate discovered IPs, MACs, manufacturers, ports, SSIDs, and first/last seen timestamps.'},
            {'title': 'Persistent local inventory state', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Inventory devices, saved port profiles, client timelines, labels, watched clients, scheduled check plans, evidence, alerts, and lab records are now snapshotted to data/runtime_state.json and loaded on startup.', 'description': 'Persist device profiles, ports, labels, timelines, alerts, and evidence locally so large scans do not need to be rerun after restart.'},
            {'title': 'Comprehensive network device scan', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Network Scan now combines active ARP, passive observations, local ARP/neighbor tables, optional ping sweeps, mDNS, UPnP/SSDP, and LLDP/CDP metadata into one inventory-building workflow.', 'description': 'Scan local networks for devices using multiple discovery methods and merge results into inventory with source attribution.'},
            {'title': 'IP client profiles and watchlists', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Client pages now include health scoring, saved service history, web inspection, watch alerts, timeline events, owner/location/tags, baselines, drift checks, reachability history, and per-client JSON/Markdown exports.', 'description': 'Turn discovered IP clients into investigation profiles with health, ownership, baseline, watch, timeline, and export workflows.'},
            {'title': 'Network map', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Visualize adapters, SSIDs, access points, clients, and wired hosts as a simple topology map.'},
            {'title': 'Client relationship map', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Client profiles now show relationship nodes and links for interfaces, discovery sources, saved services, and related evidence records.', 'description': 'Show each IP client connected to interfaces, SSIDs, gateways, VLAN context, services, evidence records, and alerts.'},
            {'title': 'Scheduled client checks', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Client profiles can save recurring check plans and run due/on-demand ping, bounded common-port refresh, HTTP inspection, service fingerprinting, and baseline drift checks.', 'description': 'Run recurring reachability, common-port, service-fingerprint, and drift checks for watched clients with alerting.'},
            {'title': 'Client remediation checklist', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Turn baseline drift, sensitive services, and unknown identity hints into suggested remediation tasks with resolved/accepted-risk state.'},
            {'title': 'Client change approval log', 'priority': 'Low', 'priority_class': 'secondary', 'description': 'Let users approve expected port, owner, location, and tag changes with reviewer notes for audit-friendly inventory maintenance.'},
            {'title': 'Dedicated wireless occupancy report page', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Create a drill-down page that compares adapters, channel congestion, BSSID detail, historical heatmaps, and exportable recommendations.'},
            {'title': 'Manufacturer/OUI insights', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Inventory groups devices by manufacturer and highlights unknown OUIs for review.', 'description': 'Group discovered devices by vendor and highlight unknown or unusual manufacturers.'},
            {'title': 'New device alerts', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'New devices create unread alerts with a navbar badge and alert center.', 'description': 'Notify when a newly observed MAC, IP, SSID, or Bluetooth device appears.'},
            {'title': 'Grouped discovery notifications', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Inventory discovery now creates one grouped alert for multi-device active/job scans while preserving individual passive-scan alerts.', 'description': 'When multiple devices are discovered in the same scan, group them into one notification while keeping individual passive-discovery alerts for devices that appear later.'},
        ],
    },
    {
        'title': 'Core network tools',
        'items': [
            {'title': 'Ping and reachability testing', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Diagnostics now includes single-host ping, bounded subnet sweeps, packet loss, latency parsing, and recent reachability history.', 'description': 'Add single-host ping, subnet ping sweeps, packet-loss summaries, latency stats, and IPv4/IPv6 reachability history.'},
            {'title': 'ARP and neighbor discovery viewer', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Comprehensive network scans now include local ARP cache and neighbor-table observations with OUI/vendor enrichment and inventory links.', 'description': 'Show local ARP and IPv6 neighbor tables with interface, state, OUI/vendor enrichment, and inventory links.'},
            {'title': 'DNS lookup and diagnostics toolkit', 'priority': 'High', 'priority_class': 'danger', 'description': 'Support A, AAAA, PTR, MX, TXT, NS, and CNAME lookups, resolver comparison, timing, and split-horizon troubleshooting.'},
            {'title': 'Route table and gateway diagnostics', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Diagnostics now reports default gateways, parsed IPv4/IPv6 routes, per-interface metrics, VPN route hints, and target scan-path context.', 'description': 'Display default gateways, per-interface routes, metrics, IPv4/IPv6 routes, VPN route hints, and scan-path context.'},
            {'title': 'Connectivity health check', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Check gateway, DNS, HTTP, HTTPS, NTP, IPv4, IPv6, captive portal state, and explain which layer is failing.'},
            {'title': 'Packet capture and protocol summary', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Start and stop scoped packet captures, export PCAP files, summarize protocols/top talkers, and attach captures to evidence.'},
            {'title': 'Live traffic monitor', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Show bandwidth, packets per second, top talkers, protocol mix, and short history per interface.'},
            {'title': 'Local socket and listener inventory', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'List local listening ports and established connections with process names where available and highlight externally exposed listeners.'},
            {'title': 'Service fingerprinting and banner detection', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'IP client profiles can run safe banner probes and HTTP checks against saved open ports with confidence labels.', 'description': 'Identify services beyond port numbers using banners and safe protocol checks with confidence labels.'},
            {'title': 'HTTP service inspector', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Inspect HTTP/HTTPS services for status, redirects, page title, server headers, login forms, TLS details, and basic security headers.'},
        ],
    },
    {
        'title': 'Extended network tools',
        'items': [
            {'title': 'TLS certificate inspection', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Show certificate subject, issuer, SANs, expiration, self-signed status, hostname mismatch, and chain details.'},
            {'title': 'DHCP lease and server inspection', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Display DHCP lease details, DNS/router options, renewal timing, and warnings for multiple or unexpected DHCP servers.'},
            {'title': 'mDNS and Bonjour service discovery', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Service Discovery now parses mDNS/Bonjour service records, hostnames, ports, TXT records, roles, and inventory metadata.', 'description': 'Discover local mDNS services, hostnames, ports, TXT records, device roles, and add service metadata to inventory.'},
            {'title': 'UPnP and SSDP discovery', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Service Discovery now performs bounded SSDP discovery and catalogs friendly names, model/manufacturer hints, service types, and control URLs.', 'description': 'Discover UPnP devices, friendly names, model/manufacturer metadata, service lists, and exposed control URLs.'},
            {'title': 'LLDP and CDP neighbor discovery', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Service Discovery now surfaces lldpctl neighbor data including switch/router names, ports, VLAN hints, and management addresses when visible.', 'description': 'Reveal switch/router neighbors, port IDs, chassis IDs, VLAN hints, and management addresses when packets are visible.'},
            {'title': 'VLAN discovery and segmentation notes', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Advanced Diagnostics now inventories VLAN interfaces/tags and stores SSID-to-VLAN segmentation validation notes.', 'description': 'Track VLAN interfaces, observed tags, SSID-to-VLAN notes, and segmentation validation context.'},
            {'title': 'Egress and public IP diagnostics', 'priority': 'Low', 'priority_class': 'secondary', 'status': 'Done', 'completed_note': 'Advanced Diagnostics now reports public IP hints, NAT context, DNS resolvers, IPv6 egress, VPN/proxy hints, and per-interface route context.', 'description': 'Show public IP, NAT context, DNS egress resolver, IPv6 egress, VPN/proxy hints, and per-interface egress differences.'},
            {'title': 'iperf3 performance testing', 'priority': 'Low', 'priority_class': 'secondary', 'status': 'Done', 'completed_note': 'Advanced Diagnostics now runs bounded iperf3 client/server checks for LAN throughput baselines when iperf3 is installed.', 'description': 'Run controlled iperf3 client/server tests for throughput, jitter, loss, and LAN performance baselines.'},
            {'title': 'SNMP inventory discovery', 'priority': 'Low', 'priority_class': 'secondary', 'status': 'Done', 'completed_note': 'Advanced Diagnostics now safely collects SNMP system and interface metadata from authorized targets when credentials are supplied.', 'description': 'Safely collect SNMP system identity and interface metadata from authorized devices when credentials are provided.'},
            {'title': 'IPv6 assessment toolkit', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Advanced Diagnostics now includes IPv6 ping, traceroute, neighbor/default-route views, AAAA lookup, and bounded IPv6 TCP checks.', 'description': 'Add IPv6 ping, traceroute, neighbor discovery, router advertisement visibility, DNS records, and IPv6 port scanning support.'},
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
            {'title': 'WPA handshake capture lab', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Red Team now catalogs authorized WPA/WPA2 handshake or PMKID evidence with validation status, Evidence Vault mirroring, and JSON/CSV exports.', 'description': 'Capture, validate, catalog, and export WPA/WPA2 handshake or PMKID evidence from authorized lab networks.'},
            {'title': 'Scoped deauthentication actions', 'priority': 'High', 'priority_class': 'danger', 'description': 'Run AP-wide or client-specific deauthentication actions against authorized lab networks with targeting controls, rate limits, and clear logs.'},
            {'title': 'Remote cracking orchestration', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Queue authorized handshake material to stronger remote workers such as Spark, track job progress, and import results for password-strength review.'},
            {'title': 'PineAP-style recon and campaign engine', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Red Team now includes a PineAP-style lab console for authorized recon, campaign, handshake, and module workflow logging.', 'description': 'Build functional WiFi Pineapple-style recon, campaign, handshake, module, and Cloud C2-inspired workflows for authorized labs.'},
            {'title': 'Evil twin and captive portal lab', 'priority': 'Medium', 'priority_class': 'warning', 'status': 'Done', 'completed_note': 'Red Team now records authorized evil-twin/captive-portal lab plans with explicit SSID/BSSID/channel targeting, cleanup steps, and detection guidance.', 'description': 'Run controlled rogue-AP and captive-portal lab workflows with explicit SSID targeting, logging, cleanup, and detection guidance.'},
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
EVIL_TWIN_MAX_DURATION_MINUTES = 30
EVIL_TWIN_ACTIONS = {'plan', 'start', 'cleanup'}
PINEAP_ACTIONS = {'recon', 'campaign', 'handshake', 'module'}
PINEAP_MODULES = {'recon', 'evil-twin-lab', 'handshake-capture', 'portal-awareness', 'detection-report'}
HANDSHAKE_CAPTURE_TYPES = {'wpa-handshake', 'pmkid'}


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


def validate_evil_twin_lab_request(data):
    """Validate a controlled rogue-AP/captive-portal lab workflow request."""
    action = (data.get('action') or 'plan').strip().lower()
    if action not in EVIL_TWIN_ACTIONS:
        raise ValueError('Choose plan, start, or cleanup for the lab workflow')
    if data.get('authorized') != 'on':
        raise ValueError('Confirm this is an authorized isolated lab before preparing an evil twin lab workflow')

    ssid = (data.get('ssid') or '').strip()
    if not ssid or len(ssid) > 32:
        raise ValueError('Enter the exact lab SSID, up to 32 characters')

    bssid = normalize_mac(data.get('bssid'))
    channel = parse_int(data.get('channel'), 'Channel must be an integer')
    if channel < 1 or channel > 196:
        raise ValueError('Channel must be between 1 and 196')

    duration = parse_int(data.get('durationMinutes') or '10', 'Duration must be an integer')
    if duration < 1 or duration > EVIL_TWIN_MAX_DURATION_MINUTES:
        raise ValueError(f'Duration must be between 1 and {EVIL_TWIN_MAX_DURATION_MINUTES} minutes')

    portal_message = (data.get('portalMessage') or 'Training portal: do not enter real credentials.').strip()
    if len(portal_message) > 200:
        raise ValueError('Portal message must be 200 characters or fewer')

    return {
        'action': action,
        'ssid': ssid,
        'bssid': bssid,
        'channel': channel,
        'duration_minutes': duration,
        'portal_message': portal_message,
    }


def build_evil_twin_lab_guidance(run):
    """Return safe operator, cleanup, and defensive guidance for the lab."""
    return {
        'operator_steps': [
            f"Verify the isolated lab AP broadcasting '{run['ssid']}' has BSSID {run['bssid']} on channel {run['channel']}.",
            'Use a dedicated lab radio and avoid bridging the portal to production networks.',
            'Display only the training message; do not request, collect, or store credentials.',
            f"Stop the workflow within {run['duration_minutes']} minutes and confirm clients reconnect to the legitimate lab AP.",
        ],
        'cleanup_steps': [
            'Stop hostapd/dnsmasq or any lab AP service started outside Mobile Router.',
            'Remove temporary DHCP/DNS/portal configuration files for this SSID.',
            'Restore interface mode, channel, IP addressing, forwarding, and firewall rules.',
            'Record the cleanup result in the lab log and evidence notes.',
        ],
        'detection_guidance': [
            'Alert on duplicate SSIDs with a new BSSID, mismatched channel, or weaker security than baseline.',
            'Compare beacon RSN/capability fields and vendor OUIs against the approved AP inventory.',
            'Watch DHCP/DNS gateway changes and captive-portal redirects from unknown MAC addresses.',
            'Train users to report unexpected portal prompts and never enter real credentials in drills.',
        ],
    }


def record_evil_twin_lab_run(selected_interface, lab):
    """Record a non-credential evil-twin/captive-portal lab workflow event."""
    run = {
        'id': uuid.uuid4().hex,
        'created_at': time.time(),
        'interface': selected_interface,
        **lab,
    }
    run.update(build_evil_twin_lab_guidance(run))
    with evil_twin_lab_lock:
        evil_twin_lab_runs.append(run)
        del evil_twin_lab_runs[:-25]
    save_runtime_state('evil-twin-lab')
    app.logger.info(
        'Evil twin lab %s recorded for SSID %r BSSID %s channel %s on %s',
        run['action'], run['ssid'], run['bssid'], run['channel'], selected_interface,
    )
    return run


def _split_module_ids(value):
    modules = []
    for item in re.split(r'[,\s]+', value or ''):
        item = item.strip().lower()
        if item:
            modules.append(item)
    return modules


def validate_pineap_lab_request(data):
    """Validate a WiFi Pineapple-style lab controller request."""
    if data.get('authorized') != 'on':
        raise ValueError('Confirm this is an authorized isolated lab before running a campaign workflow')
    action = (data.get('action') or 'recon').strip().lower()
    if action not in PINEAP_ACTIONS:
        raise ValueError('Choose recon, campaign, handshake, or module')
    ssid = (data.get('ssid') or '').strip()
    if ssid and len(ssid) > 32:
        raise ValueError('SSID must be 32 characters or fewer')
    bssid = normalize_mac(data.get('bssid')) if data.get('bssid') else None
    channel = None
    if data.get('channel'):
        channel = parse_int(data.get('channel'), 'Channel must be an integer')
        if channel < 1 or channel > 196:
            raise ValueError('Channel must be between 1 and 196')
    modules = _split_module_ids(data.get('modules') or 'recon,detection-report')
    unknown = [module for module in modules if module not in PINEAP_MODULES]
    if unknown:
        raise ValueError(f"Unknown lab module: {', '.join(unknown)}")
    if action in {'campaign', 'handshake', 'module'} and not ssid:
        raise ValueError('Enter an explicit lab SSID for campaign, handshake, or module workflows')
    return {
        'action': action,
        'ssid': ssid,
        'bssid': bssid,
        'channel': channel,
        'modules': modules,
        'notes': (data.get('notes') or '').strip()[:500],
    }


def build_pineap_lab_result(selected_interface, lab):
    """Build an auditable, non-destructive PineAP-style lab result."""
    recon = []
    if lab['action'] == 'recon':
        from scripts.wifi import utils as wifi_utils
        wifi_utils.scan_networks(selected_interface)
        recon = wifi_utils.get_networks_summary()
    run = {
        'id': uuid.uuid4().hex,
        'created_at': time.time(),
        'interface': selected_interface,
        **lab,
        'recon': recon,
        'campaign_steps': [
            'Recon: inventory authorized lab SSIDs, BSSIDs, channels, security, and WPS exposure.',
            'Campaign: select only approved training modules and log operator intent before execution.',
            'Handshake: capture or upload WPA/WPA2 handshake or PMKID evidence without password cracking.',
            'Report: export findings, cleanup actions, and detection opportunities for defenders.',
        ],
        'module_status': [
            {'id': module, 'status': 'queued' if lab['action'] != 'recon' else 'available'}
            for module in lab['modules']
        ],
        'safety': 'This controller records authorized lab workflow state and recon output; it does not collect credentials or run cracking jobs.',
    }
    with pineap_lab_lock:
        pineap_lab_runs.insert(0, run)
        del pineap_lab_runs[100:]
    save_runtime_state('pineap-lab')
    app.logger.info('PineAP-style lab %s recorded for SSID %r on %s', run['action'], run['ssid'], selected_interface)
    return run


def validate_handshake_lab_request(data):
    """Validate handshake/PMKID evidence catalog inputs."""
    if data.get('authorized') != 'on':
        raise ValueError('Confirm this is an authorized isolated lab before cataloging handshake evidence')
    ssid = (data.get('ssid') or '').strip()
    if not ssid or len(ssid) > 32:
        raise ValueError('Enter the exact lab SSID, up to 32 characters')
    bssid = normalize_mac(data.get('bssid'))
    channel = parse_int(data.get('channel'), 'Channel must be an integer')
    if channel < 1 or channel > 196:
        raise ValueError('Channel must be between 1 and 196')
    capture_type = (data.get('captureType') or 'wpa-handshake').strip().lower()
    if capture_type not in HANDSHAKE_CAPTURE_TYPES:
        raise ValueError('Capture type must be WPA handshake or PMKID')
    return {
        'ssid': ssid,
        'bssid': bssid,
        'channel': channel,
        'capture_type': capture_type,
        'client': normalize_mac(data.get('client')) if data.get('client') else '',
        'validation_notes': (data.get('validationNotes') or '').strip()[:500],
    }


def validate_handshake_evidence(record, uploaded_file=None):
    """Attach lightweight validation status for uploaded WPA/PMKID evidence."""
    file_name = uploaded_file.filename if uploaded_file and uploaded_file.filename else ''
    extension = os.path.splitext(file_name.lower())[1]
    accepted = {'.cap', '.pcap', '.pcapng', '.hc22000', '.hccapx'}
    checks = [
        'SSID/BSSID/channel are explicitly scoped to the authorized lab target.',
        'Evidence is cataloged for validation/export only; password cracking is out of scope.',
    ]
    if file_name:
        checks.append('Uploaded capture extension is recognized.' if extension in accepted else 'Uploaded capture extension is unusual; verify manually.')
    else:
        checks.append('No capture uploaded yet; record is ready for later evidence attachment.')
    status = 'needs-review' if file_name and extension not in accepted else 'cataloged'
    return {'validation_status': status, 'validation_checks': checks}


def record_handshake_lab_evidence(selected_interface, lab, uploaded_file=None):
    """Catalog handshake/PMKID lab evidence and mirror it into the evidence vault."""
    validation = validate_handshake_evidence(lab, uploaded_file=uploaded_file)
    evidence = create_evidence_record(
        f"{lab['capture_type'].upper()} evidence for {lab['ssid']}",
        category='capture',
        source='WPA handshake capture lab',
        device=lab['bssid'],
        notes=lab['validation_notes'],
        content='\n'.join(validation['validation_checks']),
        uploaded_file=uploaded_file,
    )
    record = {
        'id': uuid.uuid4().hex,
        'created_at': time.time(),
        'interface': selected_interface,
        **lab,
        **validation,
        'evidence_id': evidence['id'],
        'download_url': evidence.get('download_url'),
        'file_name': evidence.get('file_name'),
        'file_size': evidence.get('file_size'),
    }
    with handshake_lab_lock:
        handshake_lab_records.insert(0, record)
        del handshake_lab_records[200:]
    save_runtime_state('handshake-lab')
    app.logger.info('Handshake lab evidence %s cataloged for SSID %r BSSID %s', record['capture_type'], record['ssid'], record['bssid'])
    return record


def handshake_lab_export_records():
    with handshake_lab_lock:
        records = [dict(item) for item in handshake_lab_records]
    for item in records:
        item['created_at_label'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(item.get('created_at', 0)))
    return records


def handshake_records_as_csv(records):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['SSID', 'BSSID', 'Channel', 'Type', 'Client', 'Status', 'File', 'Created'])
    for item in records:
        writer.writerow([item.get('ssid'), item.get('bssid'), item.get('channel'), item.get('capture_type'), item.get('client'), item.get('validation_status'), item.get('file_name'), item.get('created_at_label')])
    return output.getvalue()


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


def create_grouped_device_alert(devices, source, interface=None):
    """Record one unread alert for a batch of newly observed devices."""
    devices = [dict(device) for device in devices or []]
    alert = {
        'id': uuid.uuid4().hex,
        'alert_type': 'grouped-discovery',
        'display_name': f"{len(devices)} new devices discovered",
        'ip': None,
        'mac': None,
        'manufacturer': 'Multiple',
        'device_url': '/inventory',
        'source': source,
        'interface': interface,
        'created_at': time.time(),
        'read': False,
        'device_count': len(devices),
        'devices': [
            {
                'id': device.get('id'),
                'display_name': device.get('name') or device.get('hostname') or device.get('ssid') or device.get('ip') or device.get('mac') or 'Unknown device',
                'ip': device.get('ip'),
                'mac': device.get('mac') or device.get('bssid'),
                'manufacturer': device.get('manufacturer') or 'Unknown',
            }
            for device in devices[:10]
        ],
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
    save_runtime_state('evidence')
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
    return inventory_service.find_device(identifier, device_inventory, device_inventory_lock, normalize_mac)


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


def _dhcp_lease_display_name(ip):
    """Look for a client hostname in common local DHCP lease files."""
    lease_paths = [
        '/var/lib/misc/dnsmasq.leases',
        '/tmp/dhcp.leases',
        '/var/lib/dhcp/dhcpd.leases',
        '/var/lib/dhcp/dhclient.leases',
    ]
    for path in lease_paths:
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding='utf-8', errors='ignore') as handle:
                content = handle.read()
        except OSError:
            continue
        for line in content.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[2] == ip:
                return _clean_detected_client_name(parts[3], ip)
        block_match = re.search(rf'lease\s+{re.escape(ip)}\s+\{{(.*?)\}}', content, re.S)
        if block_match:
            host_match = re.search(r'client-hostname\s+"([^"]+)"', block_match.group(1))
            if host_match:
                return _clean_detected_client_name(host_match.group(1), ip)
    return ''


def display_name_for_inventory_device(device, fallback=None):
    """Choose the best human-readable name for an inventory device."""
    device = device or {}
    return (
        device.get('preferred_name')
        or device.get('detected_display_name')
        or device.get('name')
        or device.get('hostname')
        or device.get('friendly_name')
        or device.get('ssid')
        or device.get('ip')
        or device.get('mac')
        or fallback
        or 'Unknown device'
    )


def enrich_ip_client_display_name(identifier, device=None):
    """Detect and persist a better display name for an IP client when possible."""
    device = dict(device or find_inventory_device(identifier) or {})
    ip = device.get('ip') or (identifier if identifier and not MAC_RE.match(str(identifier)) else None)
    if not ip:
        return device
    existing = display_name_for_inventory_device(device, ip)
    if existing and existing not in {ip, device.get('mac'), device.get('id')}:
        device['display_name'] = existing
        return device
    detected = _clean_detected_client_name(device.get('hostname') or device.get('name'), ip)
    source = 'inventory'
    if not detected:
        detected = _dhcp_lease_display_name(ip)
        source = 'dhcp-lease'
    if not detected:
        detected = _reverse_dns_display_name(ip)
        source = 'reverse-dns'
    if not detected:
        device['display_name'] = existing or ip
        return device
    updates = {'detected_display_name': detected, 'display_name': detected, 'hostname': device.get('hostname') or detected, 'display_name_source': source}
    with device_inventory_lock:
        key = device.get('id') or f'ip:{ip}'
        existing_record = device_inventory.get(key)
        if existing_record is None:
            for candidate_key, item in device_inventory.items():
                if item.get('ip') == ip or item.get('mac') == device.get('mac'):
                    key = candidate_key
                    existing_record = item
                    break
        existing_record = dict(existing_record or {'id': key, 'ip': ip, 'manufacturer': device.get('manufacturer') or 'Unknown', 'first_seen': time.time(), 'sources': [], 'interfaces': []})
        existing_record.update({k: v for k, v in updates.items() if v})
        existing_record['last_seen'] = time.time()
        device_inventory[key] = existing_record
        device = dict(existing_record)
    append_client_timeline_event(ip, 'Display name detected', f'Detected "{detected}" from {source}.', source)
    return device


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


def client_timeline(identifier, inventory_device=None):
    """Return explicit and inferred timeline entries for a client."""
    keys = {str(identifier or '').strip()}
    for field in ('ip', 'mac', 'id'):
        value = (inventory_device or {}).get(field)
        if value:
            keys.add(str(value))
    events = []
    with client_timelines_lock:
        for key in keys:
            events.extend(dict(item) for item in client_timelines.get(key, []))
    if inventory_device:
        if inventory_device.get('first_seen'):
            events.append({'timestamp': inventory_device['first_seen'], 'type': 'First discovered', 'message': 'Device first entered inventory.', 'source': ', '.join(inventory_device.get('sources', []))})
        if inventory_device.get('last_seen'):
            events.append({'timestamp': inventory_device['last_seen'], 'type': 'Last seen', 'message': 'Device was refreshed by discovery or scan activity.', 'source': ', '.join(inventory_device.get('sources', []))})
        if inventory_device.get('last_port_scan'):
            events.append({'timestamp': inventory_device['last_port_scan'], 'type': 'Port scan', 'message': f"{len(inventory_device.get('open_ports', []))} open port(s) saved to this profile.", 'source': 'port-scan'})
    unique = {(round(item.get('timestamp', 0), 3), item.get('type'), item.get('message')): item for item in events}
    ordered = sorted(unique.values(), key=lambda item: item.get('timestamp', 0), reverse=True)[:12]
    for item in ordered:
        item['time_label'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(item.get('timestamp', time.time())))
    return ordered


def client_health_summary(device, ip=None):
    """Build a simple client health/risk summary from inventory evidence."""
    device = device or {}
    flags = []
    score = 100
    open_ports = device.get('open_port_details') or []
    if not device.get('manufacturer') or device.get('manufacturer') == 'Unknown':
        flags.append('Unknown manufacturer')
        score -= 10
    risky_ports = {21: 'FTP', 23: 'Telnet', 445: 'SMB', 3389: 'RDP', 5900: 'VNC'}
    exposed = [item for item in open_ports if item.get('port') in risky_ports]
    if exposed:
        flags.append(f"{len(exposed)} sensitive service(s) exposed")
        score -= 25
    if len(open_ports) >= 8:
        flags.append('Large open-port surface')
        score -= 15
    if not device.get('hostname') and not device.get('name'):
        flags.append('No hostname learned')
        score -= 5
    if not open_ports:
        flags.append('No service baseline yet')
        score -= 5
    score = max(0, min(100, score))
    if score >= 85:
        level = 'Good'
        badge = 'success'
    elif score >= 60:
        level = 'Review'
        badge = 'warning'
    else:
        level = 'Attention'
        badge = 'danger'
    return {'score': score, 'level': level, 'badge': badge, 'flags': flags or ['No notable client concerns from saved data'], 'open_port_count': len(open_ports), 'identity': device.get('hostname') or device.get('name') or ip or 'Unknown client'}


def client_reachability_history(host, limit=10):
    """Return recent ping results for a specific client."""
    target = str(host or '').strip()
    matches = [dict(item) for item in ping_history if item.get('host') == target]
    for item in matches:
        item['time_label'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(item.get('checked_at', time.time())))
    return matches[-limit:]


def _ttl_os_hint(history):
    """Infer a coarse OS/device family hint from observed ping TTL values."""
    ttl_values = []
    for item in history or []:
        for match in re.findall(r'ttl[= ](\d+)', item.get('output') or '', flags=re.I):
            try:
                ttl_values.append(int(match))
            except ValueError:
                continue
    if not ttl_values:
        return {'hint': 'Unknown', 'confidence': 'low', 'evidence': []}
    ttl = max(ttl_values)
    if ttl <= 64:
        hint = 'Linux/Unix, Android, or embedded IoT family'
    elif ttl <= 128:
        hint = 'Windows-family host or appliance'
    else:
        hint = 'Network appliance or BSD-derived stack'
    return {'hint': hint, 'confidence': 'low', 'evidence': [f'Observed TTL {ttl} in reachability history']}


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


def client_intelligence_profile(identifier, active_probe=False):
    """Build a richer client intelligence snapshot from saved and optional safe probes."""
    device = enrich_ip_client_display_name(identifier, find_inventory_device(identifier) or {})
    host = device.get('ip') or identifier
    observed_names = [item.get('name') for item in device.get('observed_names', []) if item.get('name')]
    detected_names = [device.get('hostname'), device.get('name'), device.get('display_name'), device.get('detected_display_name'), *observed_names]
    reverse_name = _reverse_dns_display_name(host) if host else ''
    if reverse_name:
        detected_names.append(reverse_name)
    dhcp_name = _dhcp_lease_display_name(host) if host else ''
    if dhcp_name:
        detected_names.append(dhcp_name)
    reachability = client_reachability_history(host, limit=10)
    fingerprints = fingerprint_client_services(identifier) if active_probe else []
    open_ports = device.get('open_port_details') or []
    web_ports = [item for item in open_ports if item.get('web_url') or str(item.get('service') or '').lower() in {'http', 'https'}]
    sensitive = [item for item in open_ports if item.get('port') in {21, 23, 445, 3389, 5900}]
    stability = {
        'first_seen': device.get('first_seen'),
        'last_seen': device.get('last_seen'),
        'sources': device.get('sources', []),
        'interfaces': device.get('interfaces', []),
        'seen_count_hint': len(device.get('sources', [])) + len(device.get('interfaces', [])),
    }
    recommendations = []
    if device.get('likely_randomized_mac'):
        recommendations.append('MAC appears locally administered/private; correlate by hostname, services, and SSID-scoped labels instead of OUI alone.')
    if not device.get('manufacturer') or device.get('manufacturer') == 'Unknown':
        recommendations.append('Manufacturer is unknown; refresh the OUI database or collect mDNS/DHCP/UPnP identity metadata.')
    if sensitive:
        recommendations.append('Sensitive remote-access or file-sharing ports are present; verify they are expected for this device.')
    if not open_ports:
        recommendations.append('No saved port/service baseline yet; run common ports once and reuse the saved profile before any larger scan.')
    if web_ports:
        recommendations.append('Web services are present; inspect titles, headers, favicon hashes, TLS certificates, and preview thumbnails for app identification.')
    if not recommendations:
        recommendations.append('Saved identity and service data is sufficient for a lightweight baseline; monitor for drift over time.')
    return {
        'host': host,
        'manufacturer': device.get('manufacturer') or 'Unknown',
        'mac': device.get('mac'),
        'names': sorted({name for name in detected_names if name and name != host})[:12],
        'dns': {'reverse': reverse_name, 'forward': _forward_dns_records(detected_names)},
        'dhcp': {'hostname': dhcp_name},
        'os_hint': _ttl_os_hint(reachability),
        'services': {'open_port_count': len(open_ports), 'web_port_count': len(web_ports), 'sensitive_port_count': len(sensitive), 'fingerprints': fingerprints},
        'stability': stability,
        'relationships': client_relationship_map(identifier),
        'recommendations': recommendations[:8],
    }


def update_client_metadata(identifier, data):
    """Persist user-maintained client tags, ownership, notes, and expected ports."""
    target = str(identifier or '').strip()
    if not target:
        raise ValueError('Missing client identifier')
    raw_tags = data.get('tags') or ''
    tags = sorted({tag.strip() for tag in raw_tags.split(',') if tag.strip()})[:12]
    expected_ports = []
    raw_expected_ports = data.get('expectedPorts') or ''
    for raw_port in raw_expected_ports.split(','):
        raw_port = raw_port.strip()
        if not raw_port:
            continue
        port = parse_int(raw_port, 'Expected ports must be integers')
        if not 1 <= port <= 65535:
            raise ValueError('Expected ports must be between 1 and 65535')
        expected_ports.append(port)
    updates = {
        'client_tags': tags,
        'client_owner': (data.get('owner') or '').strip()[:80],
        'client_location': (data.get('location') or '').strip()[:80],
        'client_notes': (data.get('notes') or '').strip()[:500],
        'expected_open_ports': sorted(set(expected_ports)),
    }
    with device_inventory_lock:
        key = f'ip:{target}'
        existing = device_inventory.get(key)
        if existing is None:
            for candidate_key, item in device_inventory.items():
                if item.get('ip') == target or item.get('mac') == target or item.get('id') == target:
                    key = candidate_key
                    existing = item
                    break
        existing = dict(existing or {'id': key, 'ip': target, 'manufacturer': 'Unknown', 'first_seen': time.time(), 'sources': [], 'interfaces': []})
        key = existing.get('id') or inventory_key(existing) or key
        existing.update({k: v for k, v in updates.items() if v not in (None, '')})
        existing['last_seen'] = time.time()
        device_inventory[key] = existing
    append_client_timeline_event(target, 'Profile updated', 'Client tags, ownership, notes, or expected ports were updated.', 'client-metadata')
    return dict(existing)


def save_client_baseline(identifier):
    """Save current observed identity/service details as the expected baseline."""
    device = find_inventory_device(identifier) or {}
    target = device.get('ip') or identifier
    baseline = {
        'saved_at': time.time(),
        'hostname': device.get('hostname') or device.get('name'),
        'manufacturer': device.get('manufacturer'),
        'open_ports': sorted(device.get('open_ports', [])),
        'mac': device.get('mac'),
        'sources': list(device.get('sources', [])),
    }
    updated = update_client_metadata(target, {'expectedPorts': ','.join(str(port) for port in baseline['open_ports'])})
    with device_inventory_lock:
        key = updated.get('id')
        device_inventory[key]['client_baseline'] = baseline
        updated = dict(device_inventory[key])
    append_client_timeline_event(target, 'Baseline saved', f"Saved {len(baseline['open_ports'])} expected open port(s).", 'client-baseline')
    return updated


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


def client_profile_export(identifier):
    """Build an exportable IP client profile."""
    device = find_inventory_device(identifier) or {}
    host = device.get('ip') or identifier
    related_evidence = [
        item for item in evidence_records()
        if str(item.get('device') or '') in {str(host), str(device.get('mac') or ''), str(device.get('id') or '')}
    ]
    return {
        'exported_at': time.time(),
        'host': host,
        'device': device,
        'health': client_health_summary(device, host),
        'baseline': client_baseline_diff(device),
        'reachability_history': client_reachability_history(host, limit=25),
        'timeline': client_timeline(host, device),
        'evidence': related_evidence,
    }


def client_relationship_map(identifier):
    """Build a lightweight client relationship map for profile rendering/export."""
    device = find_inventory_device(identifier) or {}
    host = device.get('ip') or identifier
    nodes = [{'id': f'client:{host}', 'label': host, 'type': 'client'}]
    links = []
    for iface in device.get('interfaces', []):
        nodes.append({'id': f'interface:{iface}', 'label': iface, 'type': 'interface'})
        links.append({'source': f'client:{host}', 'target': f'interface:{iface}', 'label': 'seen on'})
    for source in device.get('sources', []):
        nodes.append({'id': f'source:{source}', 'label': source, 'type': 'source'})
        links.append({'source': f'client:{host}', 'target': f'source:{source}', 'label': 'discovered by'})
    for port in device.get('open_port_details', [])[:12]:
        node_id = f"service:{host}:{port.get('port')}"
        nodes.append({'id': node_id, 'label': f"{port.get('port')}/tcp {port.get('service') or 'Unknown'}", 'type': 'service'})
        links.append({'source': f'client:{host}', 'target': node_id, 'label': 'exposes'})
    for item in client_profile_export(identifier).get('evidence', [])[:8]:
        node_id = f"evidence:{item.get('id')}"
        nodes.append({'id': node_id, 'label': item.get('title') or 'Evidence', 'type': 'evidence'})
        links.append({'source': f'client:{host}', 'target': node_id, 'label': 'has evidence'})
    unique_nodes = {node['id']: node for node in nodes}
    return {'nodes': list(unique_nodes.values()), 'links': links}


def fingerprint_client_services(identifier):
    """Run safe, lightweight service fingerprint checks against saved open ports."""
    device = find_inventory_device(identifier) or {}
    host = device.get('ip') or identifier
    fingerprints = []
    http_ports = []
    for detail in device.get('open_port_details', []):
        port = detail.get('port')
        service = str(detail.get('service') or '').lower()
        finding = {'port': port, 'service': detail.get('service') or 'Unknown', 'confidence': 'low', 'banner': None, 'notes': []}
        if port in (80, 443, 8080, 8443, 8000, 9443) or any(name in service for name in ('http', 'https', 'web')):
            http_ports.append(port)
            finding['confidence'] = 'medium'
            finding['notes'].append('HTTP-like port selected for web inspection.')
        elif port in (21, 22, 25, 110, 143, 587, 993, 995):
            try:
                with socket.create_connection((host, int(port)), timeout=2) as sock:
                    sock.settimeout(2)
                    try:
                        banner = sock.recv(256).decode('utf-8', errors='ignore').strip()
                    except socket.timeout:
                        banner = ''
                if banner:
                    finding['banner'] = banner[:160]
                    finding['confidence'] = 'high'
                else:
                    finding['notes'].append('Port accepted TCP connection but did not send a banner quickly.')
                    finding['confidence'] = 'medium'
            except OSError as exc:
                finding['notes'].append(f'Banner probe unavailable: {exc}')
        else:
            finding['notes'].append('Service inferred from port number; no active banner probe selected.')
        fingerprints.append(finding)
    if http_ports:
        web_results = inspect_http_services(host, sorted(set(http_ports))[:8])
        by_port = {item['port']: item for item in web_results}
        for finding in fingerprints:
            web = by_port.get(finding.get('port'))
            if web:
                finding['http'] = web
                if web.get('title') or web.get('server') or web.get('status'):
                    finding['confidence'] = 'high'
    append_client_timeline_event(host, 'Services fingerprinted', f"Checked {len(fingerprints)} saved service(s).", 'service-fingerprint')
    return fingerprints


def save_scheduled_client_check(identifier, data):
    """Store a recurring-check plan for a watched or important client."""
    target = str(identifier or '').strip()
    if not target:
        raise ValueError('Missing client identifier')
    interval = max(5, min(parse_int(data.get('intervalMinutes') or 60, 'Interval must be an integer'), 10080))
    checks = sorted({
        check for check in (data.get('checks') or 'ping,common-ports,baseline-drift').split(',')
        if check in {'ping', 'common-ports', 'http-inspect', 'service-fingerprint', 'baseline-drift'}
    })
    if not checks:
        raise ValueError('Select at least one supported scheduled check')
    plan = {
        'client': target,
        'interval_minutes': interval,
        'checks': checks,
        'created_at': time.time(),
        'last_run': None,
        'status': 'scheduled',
    }
    scheduled_client_checks[target] = plan
    append_client_timeline_event(target, 'Scheduled checks updated', f"Scheduled {', '.join(checks)} every {interval} minute(s).", 'scheduled-checks')
    save_runtime_state('scheduled-check')
    return dict(plan)



def scan_common_client_ports(host, timeout=0.35):
    """Run a bounded common-port refresh for scheduled checks."""
    from scripts.portScanner import COMMON_SERVICE_HINTS, identify_port_service

    target = str(host or '').strip()
    if not target:
        return []
    open_details = []
    for port in sorted(COMMON_SERVICE_HINTS):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                is_open = sock.connect_ex((target, int(port))) == 0
        except OSError:
            is_open = False
        if is_open:
            open_details.append(enrich_web_port_metadata(target, identify_port_service(int(port))))
    if open_details:
        record_device_open_ports(target, open_details, source='scheduled-common-ports')
    return open_details


def run_scheduled_client_check(identifier, now=None):
    """Execute one saved scheduled-check plan and persist its summary."""
    target = str(identifier or '').strip()
    plan = scheduled_client_checks.get(target)
    if not plan:
        raise ValueError('No scheduled check plan found for this client')
    now = now or time.time()
    results = {}
    checks = plan.get('checks') or []
    if 'ping' in checks:
        results['ping'] = run_ping_check(target, count=2, timeout=2)
    if 'common-ports' in checks:
        results['common_ports'] = scan_common_client_ports(target)
    if 'http-inspect' in checks:
        device = find_inventory_device(target) or {}
        ports = [item.get('port') for item in device.get('open_port_details', []) if item.get('web_url') or str(item.get('service') or '').lower().startswith('http')]
        results['http_inspect'] = inspect_http_services(target, sorted({int(port) for port in ports if port})[:8])
    if 'service-fingerprint' in checks:
        results['service_fingerprint'] = fingerprint_client_services(target)
    if 'baseline-drift' in checks:
        results['baseline_drift'] = client_baseline_diff(find_inventory_device(target) or {})
    plan.update({
        'last_run': now,
        'next_run': now + (int(plan.get('interval_minutes') or 60) * 60),
        'last_result': results,
        'status': 'completed',
    })
    append_client_timeline_event(target, 'Scheduled check run', f"Completed scheduled checks: {', '.join(checks)}.", 'scheduled-checks')
    drift = (results.get('baseline_drift') or {})
    if is_client_watched(target) and drift.get('status') == 'Drift detected':
        create_client_watch_alert(target, 'Scheduled check drift detected', f"Baseline drift detected for {target}.")
    save_runtime_state('scheduled-check-run')
    return dict(plan)


def run_due_scheduled_client_checks(now=None):
    """Run every scheduled client check whose interval has elapsed."""
    now = now or time.time()
    due = []
    for target, plan in list(scheduled_client_checks.items()):
        last_run = plan.get('last_run')
        interval_seconds = int(plan.get('interval_minutes') or 60) * 60
        if last_run is None or now - float(last_run or 0) >= interval_seconds:
            due.append(target)
    results = []
    for target in due[:25]:
        try:
            results.append(run_scheduled_client_check(target, now=now))
        except ValueError:
            continue
    return results

def is_client_watched(identifier):
    key = str(identifier or '').strip()
    return key in watched_clients


def create_client_watch_alert(identifier, title, message):
    alert = {
        'id': str(uuid.uuid4()),
        'alert_type': 'watched-client',
        'title': title,
        'message': message,
        'ip': identifier,
        'device_url': f"/clients/{quote(str(identifier))}",
        'read': False,
        'timestamp': time.time(),
        'time_label': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
    }
    with new_device_alerts_lock:
        new_device_alerts.insert(0, alert)
        del new_device_alerts[200:]
    return alert


def capture_http_preview_thumbnail(url):
    """Capture a small web preview when a local browser/screenshot utility exists."""
    tool = shutil.which('wkhtmltoimage') or shutil.which('chromium') or shutil.which('chromium-browser') or shutil.which('google-chrome')
    if not tool:
        return None
    os.makedirs(HTTP_PREVIEW_DIR, exist_ok=True)
    filename = secure_filename(re.sub(r'[^A-Za-z0-9_.-]+', '_', url))[:120] + '.png'
    output_path = os.path.join(HTTP_PREVIEW_DIR, filename)
    try:
        if os.path.exists(output_path) and time.time() - os.path.getmtime(output_path) < 3600:
            return f'/http-previews/{filename}'
        if os.path.basename(tool) == 'wkhtmltoimage':
            command = [tool, '--width', '480', '--height', '320', url, output_path]
        else:
            command = [tool, '--headless', '--disable-gpu', '--no-sandbox', f'--screenshot={output_path}', '--window-size=480,320', url]
        result = subprocess.run(command, capture_output=True, text=True, timeout=8, check=False)
        if result.returncode == 0 and os.path.exists(output_path):
            return f'/http-previews/{filename}'
    except (OSError, subprocess.TimeoutExpired):
        return None
    return None


def inspect_http_services(host, ports):
    """Safely inspect likely HTTP services for titles and headers."""
    results = []
    for port in ports:
        scheme = 'https' if int(port) in (443, 8443, 9443) else 'http'
        url = f"{scheme}://{host}:{port}/"
        result = {'port': int(port), 'url': url, 'status': None, 'title': None, 'server': None, 'error': None, 'favicon': None}
        try:
            req = Request(url, headers={'User-Agent': 'MobileRouterLab/1.0'})
            with urlopen(req, timeout=3) as resp:
                body = resp.read(65536).decode('utf-8', errors='ignore')
                result['status'] = getattr(resp, 'status', None)
                result['server'] = resp.headers.get('Server')
                match = re.search(r'<title[^>]*>(.*?)</title>', body, re.I | re.S)
                if match:
                    result['title'] = re.sub(r'\s+', ' ', match.group(1)).strip()[:120]
                result['favicon'] = device_intel.favicon_metadata(url, urlopen)
                result['thumbnail_url'] = capture_http_preview_thumbnail(url)
        except HTTPError as e:
            result['status'] = e.code
            result['server'] = e.headers.get('Server')
            result['error'] = e.reason
        except (URLError, TimeoutError, socket.timeout, ValueError) as e:
            result['error'] = str(e)
        results.append(result)
    return results


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
        item['manufacturer'] = item.get('manufacturer') or 'Unknown'
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
        inventory_records,
    )


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


def _ping_command(host, count=4, timeout=2):
    return diagnostics_service.ping_command(host, count=count, timeout=timeout, os_name=os.name)


def _parse_ping_output(output):
    return diagnostics_service.parse_ping_output(output)


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


def _parse_route_lines(output):
    return diagnostics_service.parse_route_lines(output)


def build_route_diagnostics(target=None):
    return diagnostics_service.build_route_diagnostics(target, _run_text_command, os_name=os.name)


def classify_service_role(service_type, text=''):
    value = f"{service_type or ''} {text or ''}".lower()
    if any(term in value for term in ['printer', 'ipp', 'pdl-datastream']):
        return 'Printer'
    if any(term in value for term in ['airplay', 'media', 'spotify', 'raop', 'dlna', 'mediarenderer']):
        return 'Media device'
    if any(term in value for term in ['router', 'gateway', 'internetgatewaydevice', 'wanipconnection']):
        return 'Gateway/router'
    if any(term in value for term in ['workstation', 'smb', 'ssh', 'http']):
        return 'Host service'
    return 'Service endpoint'


def _parse_mdns_output(output):
    services = []
    for line in (output or '').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = [part.strip() for part in line.split(';')]
        if len(parts) >= 9 and parts[0] == '=':
            txt = ';'.join(parts[9:]) if len(parts) > 9 else ''
            services.append({
                'interface': parts[1],
                'protocol': parts[2],
                'name': parts[3],
                'service_type': parts[4],
                'domain': parts[5],
                'hostname': parts[6],
                'ip': parts[7],
                'port': parts[8],
                'txt': txt,
                'role': classify_service_role(parts[4], txt),
            })
    return services


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


def _parse_ssdp_response(response):
    headers = {}
    for line in response.split('\r\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            headers[key.strip().lower()] = value.strip()
    location = headers.get('location') or ''
    host = ''
    try:
        from urllib.parse import urlparse
        host = urlparse(location).hostname or ''
    except Exception:
        host = ''
    service_type = headers.get('st') or headers.get('nt') or ''
    return {
        'ip': host,
        'friendly_name': headers.get('server') or headers.get('usn') or 'UPnP device',
        'manufacturer': headers.get('manufacturer') or headers.get('server') or 'Unknown',
        'model': headers.get('modelname') or headers.get('server') or '',
        'service_type': service_type,
        'control_url': location,
        'usn': headers.get('usn'),
        'role': classify_service_role(service_type, headers.get('server')),
        'headers': headers,
    }


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


def _parse_lldpctl_keyvalue(output):
    neighbors = []
    current = {}
    for line in (output or '').splitlines():
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"')
        if key.endswith('.chassis.name'):
            if current:
                neighbors.append(current)
            current = {'name': value, 'protocol': 'LLDP/CDP'}
        elif key.endswith('.port.ifname') or key.endswith('.port.descr'):
            current['port_id'] = value
        elif key.endswith('.mgmt-ip'):
            current['management_address'] = value
        elif '.vlan.' in key and key.endswith('.vid'):
            current.setdefault('vlans', []).append(value)
        elif key.endswith('.chassis.descr'):
            current['description'] = value
    if current:
        neighbors.append(current)
    for neighbor in neighbors:
        neighbor['role'] = 'Switch/router neighbor'
    return neighbors


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


def parse_neighbor_table(output):
    """Parse Linux ip neigh/ARP-like output into device dictionaries."""
    devices = []
    for line in (output or '').splitlines():
        tokens = line.split()
        if not tokens:
            continue
        ip = tokens[0].strip('()')
        mac = None
        iface = None
        arp_match = re.search(r'\(([^)]+)\)\s+at\s+([0-9a-fA-F:.-]+).*\s+on\s+(\S+)', line)
        if arp_match:
            ip, mac, iface = arp_match.groups()
        if 'lladdr' in tokens:
            mac = tokens[tokens.index('lladdr') + 1]
        if 'dev' in tokens:
            iface = tokens[tokens.index('dev') + 1]
        if mac or ip:
            devices.append({'ip': ip, 'mac': mac, 'interface': iface, 'discovery_methods': ['neighbor-table'], 'scan_note': 'Observed in local ARP/neighbor table.'})
    return devices


def merge_discovered_devices(groups):
    """Merge device records from multiple discovery methods by MAC, IP, or name."""
    merged = {}
    for method, devices in groups:
        for raw in devices or []:
            device = dict(raw)
            mac = normalize_mac(device.get('mac') or device.get('address') or device.get('bssid'))
            if mac:
                device['mac'] = mac
            key = mac or device.get('ip') or device.get('hostname') or device.get('name') or uuid.uuid4().hex
            current = merged.setdefault(key, {})
            methods = set(current.get('discovery_methods') or []) | set(device.get('discovery_methods') or []) | {method}
            service_metadata = list(current.get('service_metadata_list') or [])
            if device.get('service_metadata'):
                service_metadata.append(device.get('service_metadata'))
            current.update({k: v for k, v in device.items() if v not in (None, '', [])})
            current['discovery_methods'] = sorted(methods)
            if service_metadata:
                current['service_metadata_list'] = service_metadata[-10:]
    return list(merged.values())



def passive_monitor_snapshot(interface=None):
    """Return passive ARP-cache monitor state for one interface or all interfaces."""
    with passive_monitor_lock:
        if interface:
            job = passive_monitor_jobs.get(interface)
            return dict(job) if job else {'interface': interface, 'enabled': False}
        return {name: dict(job) for name, job in passive_monitor_jobs.items()}


def _passive_monitor_worker(interface):
    """Continuously refresh passive inventory from observed ARP-cache entries."""
    while True:
        with passive_monitor_lock:
            job = passive_monitor_jobs.get(interface)
            if not job or not job.get('enabled'):
                return
            interval = job.get('interval', 10)
        try:
            devices = classify_scan_results(passive_scan(interface), interface)
            enriched = record_inventory_devices(devices, 'passive-monitor', interface)
            with passive_monitor_lock:
                current = passive_monitor_jobs.get(interface)
                if current:
                    current.update({
                        'last_update': time.time(),
                        'last_count': len(enriched),
                        'error': None,
                    })
        except Exception as exc:
            with passive_monitor_lock:
                current = passive_monitor_jobs.get(interface)
                if current:
                    current.update({'last_update': time.time(), 'error': str(exc)})
        time.sleep(interval)


def set_passive_monitor(interface, enabled, interval=10):
    """Start or stop a background passive monitor for an interface."""
    interface = (interface or '').strip()
    if not interface:
        raise ValueError('Missing interface')
    interval = max(5, min(parse_int(interval, 'Interval must be an integer'), 300))
    with passive_monitor_lock:
        job = passive_monitor_jobs.get(interface, {'interface': interface})
        job.update({
            'enabled': bool(enabled),
            'interval': interval,
            'updated_at': time.time(),
        })
        if enabled and not job.get('started_at'):
            job['started_at'] = time.time()
        passive_monitor_jobs[interface] = job
        should_start = enabled and not job.get('thread_alive')
        if should_start:
            job['thread_alive'] = True
    if should_start:
        def runner():
            try:
                _passive_monitor_worker(interface)
            finally:
                with passive_monitor_lock:
                    current = passive_monitor_jobs.get(interface)
                    if current:
                        current['thread_alive'] = False
        threading.Thread(target=runner, daemon=True).start()
    return passive_monitor_snapshot(interface)


def comprehensive_network_device_scan(selected_interface, include_passive=True, include_services=True, sweep_cidr=None):
    """Combine active, passive, ARP/neighbor, service, and optional ping-sweep discovery."""
    if not selected_interface:
        raise ValueError('Missing interface')
    groups = []
    errors = []
    try:
        groups.append(('active-arp', classify_scan_results(active_scan(selected_interface), selected_interface)))
    except Exception as exc:
        errors.append(f'active scan: {exc}')
    if include_passive:
        try:
            groups.append(('passive-observation', classify_scan_results(passive_scan(selected_interface), selected_interface)))
        except Exception as exc:
            errors.append(f'passive scan: {exc}')
    if os.name != 'nt':
        neigh = _run_text_command(['ip', 'neigh', 'show', 'dev', selected_interface], timeout=5)
        groups.append(('neighbor-table', parse_neighbor_table(neigh.get('output'))))
        arp = _run_text_command(['arp', '-an'], timeout=5)
        groups.append(('arp-cache', parse_neighbor_table(arp.get('output'))))
    if sweep_cidr:
        try:
            sweep = run_ping_sweep(sweep_cidr, count=1, timeout=1)
            groups.append(('ping-sweep', [{'ip': item.get('host'), 'discovery_methods': ['ping-sweep'], 'reachable': item.get('reachable')} for item in sweep.get('results', []) if item.get('reachable')]))
        except Exception as exc:
            errors.append(f'ping sweep: {exc}')
    if include_services:
        mdns = discover_mdns_services(selected_interface)
        groups.append(('mdns', [{'ip': service.get('ip'), 'hostname': service.get('hostname'), 'name': service.get('name'), 'device_type': service.get('role'), 'service_metadata': service, 'discovery_methods': ['mdns']} for service in mdns.get('services', [])]))
        upnp = discover_upnp_devices(timeout=2)
        groups.append(('upnp-ssdp', [{'ip': device.get('ip'), 'name': device.get('friendly_name'), 'manufacturer': device.get('manufacturer'), 'device_type': device.get('role'), 'service_metadata': device, 'discovery_methods': ['upnp-ssdp']} for device in upnp.get('devices', [])]))
        lldp = discover_lldp_neighbors(selected_interface)
        groups.append(('lldp-cdp', [{'ip': neighbor.get('management_address'), 'name': neighbor.get('name'), 'device_type': neighbor.get('role'), 'service_metadata': neighbor, 'discovery_methods': ['lldp-cdp']} for neighbor in lldp.get('neighbors', [])]))
    merged = merge_discovered_devices(groups)
    enriched = record_inventory_devices(merged, 'comprehensive-network-scan', selected_interface)
    return {
        'devices': enriched,
        'methods': [method for method, _devices in groups],
        'errors': errors,
        'summary': {
            'total_devices': len(enriched),
            'host_like': len([item for item in enriched if not item.get('is_control_traffic')]),
            'with_services': len([item for item in enriched if item.get('service_metadata') or item.get('service_metadata_list')]),
        },
    }


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

    if not is_bluetooth and ip:
        inventory_device = enrich_ip_client_display_name(ip, inventory_device)
        mac = (inventory_device or {}).get('mac') or mac

    manufacturer = (inventory_device or {}).get('manufacturer') or (lookup_manufacturer(mac) if mac else 'Unknown')
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
        display_name_source=(inventory_device or {}).get('display_name_source'),
        inventory_device=inventory_device or {},
        is_bluetooth=is_bluetooth,
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
    return jsonify({'hosts': enriched_hosts})


@app.route('/passive-scan', methods=['POST'])
def passive_scan_route():
    iface = request.form.get('selectedInterface')
    if not iface:
        return json_error('Missing interface')
    devices = classify_scan_results(passive_scan(iface), iface)
    enriched_devices = record_inventory_devices(devices, 'passive-scan', iface)
    return jsonify({'devices': enriched_devices})



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
        status = set_passive_monitor(interface, enabled, data.get('interval') or 10)
    except ValueError as exc:
        return json_error(str(exc))
    message = 'Continuous passive capture enabled.' if enabled else 'Continuous passive capture disabled.'
    return json_success(message=message, status=status)


@app.route('/comprehensive-scan', methods=['POST'])
def comprehensive_scan_route():
    try:
        result = comprehensive_network_device_scan(
            request.form.get('selectedInterface'),
            include_passive=request.form.get('includePassive', 'on') == 'on',
            include_services=request.form.get('includeServices', 'on') == 'on',
            sweep_cidr=(request.form.get('sweepCidr') or '').strip() or None,
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
        ap_mac, target_mac, frames = validate_lab_deauth_request(data)
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
        lab = validate_evil_twin_lab_request(data)
        run = record_evil_twin_lab_run(selected_interface, lab)
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
        lab = validate_pineap_lab_request(data)
        run = build_pineap_lab_result(selected_interface, lab)
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
        lab = validate_handshake_lab_request(data)
        record = record_handshake_lab_evidence(selected_interface, lab, request.files.get('capture'))
    except ValueError as e:
        return json_error(str(e))
    return json_success(message='Cataloged WPA handshake/PMKID lab evidence for validation and export.', record=record)


@app.route('/handshake-lab.<fmt>')
def export_handshake_lab(fmt):
    records = handshake_lab_export_records()
    if fmt == 'json':
        return jsonify({'handshakes': records, 'exported_at': time.time()})
    if fmt == 'csv':
        return Response(handshake_records_as_csv(records), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=handshake-lab.csv'})
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
