from flask import Flask, Response, current_app, render_template, request, jsonify, send_from_directory, send_file, redirect, url_for, session
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
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException

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
SOCIAL_PROFILE_ID_DIR = os.path.join(app.instance_path, 'social_profile_ids')
SOCIAL_PROFILE_SIGNATURE_DIR = os.path.join(app.instance_path, 'social_profile_signatures')
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
            {'title': 'Guided connectivity diagnostics module', 'priority': 'High', 'priority_class': 'danger', 'description': 'Teach learners to select a host, test reachability, interpret latency and loss, trace its route, run a bounded service scan, and save the results as evidence.'},
            {'title': 'Training trophies and milestones', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Award trophies for milestones such as 20 completed scans, first Bluetooth refresh, first OUI lookup, first export, and completion of each guided module.'},
        ],
    },
    {
        'title': 'Training trophies',
        'items': [
            {'title': 'Scan milestone trophies', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Award first Wi-Fi scan, first Bluetooth scan, 10 scans, 20 scans, first scan with more than five networks, first multi-BSSID SSID, and first hidden network discovered.'},
            {'title': 'Wireless analysis trophies', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Award channel congestion review, 2.4/5 GHz comparison, occupancy export, BSSID drill-down, OUI/vendor lookup, WPS exposure finding, and best-channel recommendation review.'},
            {'title': 'Bluetooth workflow trophies', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Award first Bluetooth device discovery, metadata refresh, state interpretation, vendor identification, action history entry, and inventory-only forget action.'},
            {'title': 'Connectivity diagnostics trophies', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Award First Contact, Name Resolver, Dual Stack, Latency Analyst, Pathfinder, and Network Medic milestones for completing increasingly detailed reachability and route diagnostics.'},
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
            {'title': 'Tabbed connectivity diagnostics workspace', 'priority': 'High', 'priority_class': 'danger', 'description': 'Create an option-A diagnostics workspace with Overview, Reachability, DNS, Routes, Neighbors, Services, Traffic, and History tabs rather than adding more controls to a single long page.'},
            {'title': 'Device-page reachability actions', 'priority': 'High', 'priority_class': 'danger', 'description': 'Add contextual Ping, Traceroute, and bounded Port Scan actions to IP device pages with live reachability state, last-checked time, latency, and packet-loss summaries.'},
            {'title': 'Reachability history and comparisons', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Store recent reachability checks so users can compare latency and loss across hosts, interfaces, IPv4/IPv6, and repeated assessments.'},
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
        'title': 'Automotive diagnostics',
        'items': [
            {'title': 'Offline VIN, DTC, vehicle, and workshop records', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Automotive pages now provide local WMI/VIN and DTC lookups, saved vehicles, translation snapshots, report exports, and SQLite persistence.', 'description': 'Provide the local automotive data and reporting foundation without online lookups.'},
            {'title': 'Staged automotive database imports', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'VIN and DTC uploads are checksum-tracked, staged for row review, selectively approved in one transaction, or discarded.', 'description': 'Review parsed VIN and DTC records before they affect live lookup results.'},
            {'title': 'Vehicle and module identity inventory', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Vehicle pages retain chassis, frame, body, engine, transmission, registration, fleet, and legacy identifiers plus ECU/module identities, calibration data, and module-reported VIN match warnings.', 'description': 'Keep one canonical vehicle VIN while tracking physical identifiers and every control-module identity observation.'},
            {'title': 'Simulated OBD-II reader', 'priority': 'High', 'priority_class': 'danger', 'description': 'Build an ELM327-style simulator for connection, VIN, current/pending/permanent DTC, freeze-frame, readiness, live-PID, timeout, malformed-response, and clear-code scenarios before hardware arrives.'},
            {'title': 'Transport-neutral OBD architecture', 'priority': 'High', 'priority_class': 'danger', 'description': 'Define shared discovery, connect, command, timeout, cancellation, and disconnect contracts for simulated, USB serial, Bluetooth Classic, BLE, and Wi-Fi readers.'},
            {'title': 'Immutable diagnostic sessions', 'priority': 'High', 'priority_class': 'danger', 'description': 'Persist adapter identity, protocol, vehicle VIN, raw responses, categorized DTCs, freeze-frame values, readiness monitors, PID samples, warnings, and before/after state.'},
            {'title': 'Automotive diagnostics workspace', 'priority': 'High', 'priority_class': 'danger', 'description': 'Add reader and vehicle selection, connection state, quick/full scans, readiness, freeze-frame, live data, saved sessions, and create-report actions.'},
            {'title': 'USB serial ELM327 and STN support', 'priority': 'High', 'priority_class': 'danger', 'description': 'Discover ports, probe baud rates, initialize supported adapters, detect protocols, enforce bounded commands, cancel work, and retain raw exchanges.'},
            {'title': 'Bluetooth Classic and Wi-Fi OBD transports', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Support paired RFCOMM/SPP readers and configured TCP readers through the same diagnostic-session service.'},
            {'title': 'Adapter-specific Bluetooth LE plugins', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Add BLE GATT transports as explicit adapter plugins rather than treating every BLE reader as a generic serial device.'},
            {'title': 'Safe DTC clearing workflow', 'priority': 'High', 'priority_class': 'danger', 'description': 'Require a saved pre-clear scan and explicit warning, record the action, explain readiness reset, and automatically capture a post-clear scan.'},
            {'title': 'Full downloadable VIN decoder dataset', 'priority': 'High', 'priority_class': 'danger', 'description': 'Add a versioned authoritative dataset adapter for make, model, year, body, engine, plant, restraint, and manufacturer-specific VDS decoding while keeping runtime lookup offline.'},
            {'title': 'Versioned DTC definition library', 'priority': 'High', 'priority_class': 'danger', 'description': 'Preserve multiple sourced definitions and translations by make, model, year, engine, module, language, source page, confidence, and superseded state instead of replacing code/make pairs.'},
            {'title': 'PDF provenance and OCR review', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Retain original documents, page numbers, extracted context, confidence, and corrections, with optional OCR staging for image-only diagnostic manuals.'},
            {'title': 'Professional workshop PDF reports', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Add Unicode, wrapping, pagination, DTC tables, branding, dates, diagnostic sessions, before/after results, parts, labor, recommendations, attachments, and signatures.'},
            {'title': 'Report revisions and finalization', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Support draft, final, amended, and void states with revision history, finalized-by identity, and immutable finalized records.'},
            {'title': 'Automotive backup and restore', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Export, validate, and restore the complete automotive database, source documents, vehicle histories, sessions, reports, and import provenance.'},
            {'title': 'Automotive route, browser, and hardware tests', 'priority': 'High', 'priority_class': 'danger', 'description': 'Cover authentication, CSRF, uploads, redirects, corrupt PDFs, migrations, rollback, reader simulation, diagnostic sessions, report downloads, accessibility, and mobile layouts.'},
        ],
    },
    {
        'title': 'Train Controller integration',
        'source_url': 'https://github.com/sudo-rpaisley/Train-Controller',
        'items': [
            {'title': 'Train Controller repository compatibility review', 'priority': 'High', 'priority_class': 'danger', 'description': 'Review sudo-rpaisley/Train-Controller features, dependencies, entry points, data model, platform requirements, tests, and license, then map reusable functionality to Mobile Router capabilities and pages.'},
            {'title': 'Train Controller feature inventory and import plan', 'priority': 'High', 'priority_class': 'danger', 'description': 'Catalog the linked repository\'s user-facing controls and supporting services, identify code that can be reused versus adapted, and split the integration into independently testable phases before implementation.'},
            {'title': 'Train Controller integration boundary', 'priority': 'High', 'priority_class': 'danger', 'description': 'Define a capability-backed adapter or plugin boundary so selected Train Controller functionality can be added without tightly coupling either application or duplicating platform-specific logic.'},
            {'title': 'Train Controller workflow and progress bridge', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Expose approved Train Controller workflows through Full and Training modes while sharing guided steps, progress, trophies, action history, and evidence exports where appropriate.'},
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


from routes.core_routes import register_core_routes
from routes.client_routes import register_client_routes
from routes.diagnostic_routes import register_diagnostic_routes
from routes.interface_routes import register_interface_routes
from routes.lab_routes import register_lab_routes

globals().update(register_core_routes(app, lambda: globals()))
globals().update(register_client_routes(app, lambda: globals()))
globals().update(register_diagnostic_routes(app, lambda: globals()))
globals().update(register_interface_routes(app, lambda: globals()))
globals().update(register_lab_routes(app, lambda: globals()))


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
                return redirect(url_for('social_auth_login', next=request.full_path.rstrip('?')))
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


def save_profile_image(upload, directory, prefix):
    """Persist a bounded identity/signature image and return storage metadata."""
    if not upload or not upload.filename:
        raise ValueError('Choose an image to upload.')
    safe_name = secure_filename(upload.filename) or 'image'
    extension = os.path.splitext(safe_name)[1].casefold()
    if extension not in {'.jpg', '.jpeg', '.png', '.webp'}:
        raise ValueError('Use a JPG, PNG, or WebP image.')
    content = upload.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        raise ValueError('Images must be 10 MB or smaller.')
    filename = f'{prefix}-{uuid.uuid4()}{extension}'
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, filename), 'wb') as handle:
        handle.write(content)
    return {'filename': filename, 'original_name': safe_name, 'size': len(content),
            'sha256': hashlib.sha256(content).hexdigest()}


def identity_image_ocr(path):
    """Run local Tesseract when available; OCR never uses an online service."""
    executable = shutil.which('tesseract')
    if not executable:
        return '', 'unavailable'
    try:
        result = subprocess.run([executable, path, 'stdout'], capture_output=True, text=True, timeout=45, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return '', 'failed'
    text = result.stdout.strip()
    return text, 'complete' if text else 'no_text'


def identity_ocr_fields(text):
    """Extract conservative labeled values while retaining the full OCR text for review."""
    def labeled(pattern):
        match = re.search(pattern, text, re.I | re.M)
        return match.group(1).strip() if match else ''
    dates = re.findall(r'\b(?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})\b', text)
    return {
        'document_number': labeled(r'(?:document|licen[cs]e|passport|id)\s*(?:no\.?|number|#)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9 -]{3,})'),
        'date_of_birth': labeled(r'(?:date of birth|birth|dob)\s*[:\-]?\s*([^\n]+)'),
        'expiry_date': labeled(r'(?:expiry|expires|expiration|exp)\s*[:\-]?\s*([^\n]+)'),
        'detected_dates': dates[:10],
    }


def login_destination(value):
    """Return a safe, existing local GET destination or the application home page."""
    candidate = str(value or '').strip()
    parsed = urlsplit(candidate)
    if (not candidate.startswith('/') or candidate.startswith('//') or '\\' in candidate
            or parsed.scheme or parsed.netloc):
        return url_for('index')
    try:
        endpoint, route_values = current_app.url_map.bind_to_environ(request.environ).match(parsed.path, method='GET')
    except HTTPException:
        return url_for('index')
    if endpoint in {'social_auth_login', 'social_auth_setup', 'social_auth_logout'}:
        return url_for('index')
    if endpoint == 'interfaces_by_type' and not any(
        iface.interface_type.casefold() == route_values['interface_type'].casefold() for iface in network_interfaces
    ):
        return url_for('index')
    if endpoint == 'interface_detail' and not any(
        iface.interface_type.casefold() == route_values['interface_type'].casefold()
        and iface.name == route_values['interface_name'] for iface in network_interfaces
    ):
        return url_for('index')
    return parsed.path + (f'?{parsed.query}' if parsed.query else '')


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
        return redirect(url_for('social_auth_setup', next=request.full_path.rstrip('?')))
    session_user = current_app_user()
    if not session_user:
        return redirect(url_for('social_auth_login', next=request.full_path.rstrip('?')))
    with social_users_lock:
        stored_user = social_users.get(session_user.get('username'))
    if not stored_user:
        session.pop('social_user', None)
        return redirect(url_for('social_auth_login', next=request.full_path.rstrip('?')))
    session['social_user'] = {'username': stored_user['username'], 'role': stored_user['role']}
    return None


@app.context_processor
def inject_application_auth():
    return {'app_user': current_app_user(), 'app_csrf_token': social_csrf_token()}


@app.route('/setup', methods=['GET', 'POST'])
def social_auth_setup():
    if social_users:
        return redirect(url_for('social_auth_login', next=request.form.get('next') or request.args.get('next', '')))
    if request.method == 'POST':
        if not secrets.compare_digest(str(request.form.get('csrf_token') or ''), social_csrf_token()):
            return json_error('Invalid or expired form token.', 400)
        try:
            user = social_auth_service.create_user(
                request.form.get('username'), request.form.get('password'), 'admin',
                social_users, social_users_lock,
            )
        except ValueError as exc:
            return render_template('social_auth.html', title='Social Profile Setup', mode='setup', error=str(exc), next_url=request.form.get('next') or request.args.get('next', ''), csrf_token=social_csrf_token(), **current_context()), 400
        session['social_user'] = {'username': user['username'], 'role': user['role']}
        with social_profiles_lock:
            for profile in social_profiles.values():
                profile.setdefault('owner', user['username'])
        record_social_audit('auth.setup')
        save_runtime_state('social-auth-setup')
        return redirect(login_destination(request.form.get('next') or request.args.get('next')))
    return render_template('social_auth.html', title='Social Profile Setup', mode='setup', next_url=request.args.get('next', ''), csrf_token=social_csrf_token(), **current_context())


@app.route('/login', methods=['GET', 'POST'])
def social_auth_login():
    if not social_users:
        return redirect(url_for('social_auth_setup', next=request.form.get('next') or request.args.get('next', '')))
    if request.method == 'POST':
        if not secrets.compare_digest(str(request.form.get('csrf_token') or ''), social_csrf_token()):
            return json_error('Invalid or expired form token.', 400)
        user = social_auth_service.authenticate(
            request.form.get('username'), request.form.get('password'), social_users, social_users_lock,
        )
        if not user:
            return render_template('social_auth.html', title='Social Profile Login', mode='login', error='Invalid username or password.', next_url=request.form.get('next') or request.args.get('next', ''), csrf_token=social_csrf_token(), **current_context()), 401
        session['social_user'] = {'username': user['username'], 'role': user['role']}
        record_social_audit('auth.login')
        save_runtime_state('social-auth-login')
        return redirect(login_destination(request.form.get('next') or request.args.get('next')))
    return render_template('social_auth.html', title='Social Profile Login', mode='login', next_url=request.args.get('next', ''), csrf_token=social_csrf_token(), **current_context())


@app.route('/logout', methods=['POST'])
@social_login_required()
def social_auth_logout():
    record_social_audit('auth.logout')
    save_runtime_state('social-auth-logout')
    session.pop('social_user', None)
    return redirect(url_for('social_auth_login'))


@app.route('/social-engineering/setup')
def legacy_social_auth_setup():
    return redirect(url_for('social_auth_setup', next=request.args.get('next', '')))


@app.route('/social-engineering/login')
def legacy_social_auth_login():
    return redirect(url_for('social_auth_login', next=request.args.get('next', '')))


@app.route('/users')
@social_login_required({'admin'})
def application_users_page():
    with social_users_lock:
        users = [dict(user) for user in social_users.values()]
    return render_template('application_users.html', title='User Management', users=users, csrf_token=social_csrf_token(), **current_context())


@app.route('/users', methods=['POST'])
@social_login_required({'admin'})
def create_application_user():
    try:
        user = social_auth_service.create_user(
            request.form.get('username'), request.form.get('password'), request.form.get('role'),
            social_users, social_users_lock,
        )
    except ValueError as exc:
        with social_users_lock:
            users = [dict(item) for item in social_users.values()]
        return render_template('application_users.html', title='User Management', users=users, error=str(exc), csrf_token=social_csrf_token(), **current_context()), 400
    record_social_audit('user.create', detail=f"{user['username']}:{user['role']}")
    save_runtime_state('application-user-create')
    return redirect(url_for('application_users_page'))


@app.route('/social-engineering')
@social_login_required()
def social_engineering_page():
    profiles = owned_social_profiles()
    query = request.args.get('q', '')
    status = request.args.get('status', '')
    tag = request.args.get('tag', '')
    filtered_profiles = social_profile_service.search_profiles(profiles, query, status, tag)
    available_tags = sorted({item for profile in profiles for item in profile.get('tags', [])}, key=str.casefold)
    summary = social_profile_service.dashboard_summary(profiles)
    duplicates = social_profile_service.duplicate_candidates(profiles)
    return render_template(
        'social_engineering.html',
        title='Social Engineering',
        profiles=filtered_profiles, total_profiles=len(profiles), available_tags=available_tags,
        search_query=query, selected_status=status, selected_tag=tag,
        social_user=session.get('social_user'), csrf_token=social_csrf_token(),
        social_audit=recent_social_audit(), summary=summary, duplicates=duplicates,
        **current_context(),
    )


@app.route('/social-engineering/profiles', methods=['POST'])
@social_login_required({'editor', 'credential_manager', 'admin'})
def create_social_profile():
    try:
        profile = social_profile_service.create_profile(request.form, social_profiles, social_profiles_lock)
    except ValueError as exc:
        profiles = owned_social_profiles()
        return render_template(
            'social_engineering.html', title='Social Engineering',
            profiles=profiles, total_profiles=len(profiles), available_tags=[], search_query='', selected_status='', selected_tag='',
            summary=social_profile_service.dashboard_summary(profiles), duplicates=social_profile_service.duplicate_candidates(profiles), social_audit=recent_social_audit(),
            form_values=request.form, error=str(exc), social_user=session.get('social_user'),
            csrf_token=social_csrf_token(), **current_context(),
        ), 400
    with social_profiles_lock:
        social_profiles[profile['id']]['owner'] = current_app_user()['username']
        profile['owner'] = current_app_user()['username']
    try:
        save_social_profile_photo(profile['id'], request.files.get('profile_photo'))
    except ValueError as exc:
        social_profile_service.delete_profile(profile['id'], social_profiles, social_profiles_lock)
        profiles = owned_social_profiles()
        return render_template(
            'social_engineering.html', title='Social Engineering', profiles=profiles, total_profiles=len(profiles), available_tags=[], search_query='', selected_status='', selected_tag='',
            summary=social_profile_service.dashboard_summary(profiles), duplicates=social_profile_service.duplicate_candidates(profiles), social_audit=recent_social_audit(),
            form_values=request.form, error=str(exc), social_user=session.get('social_user'),
            csrf_token=social_csrf_token(), **current_context(),
        ), 400
    record_social_audit('profile.create', profile['id'])
    save_runtime_state('social-profile-create')
    return redirect(url_for('social_profile_detail', profile_id=profile['id']))


@app.route('/social-engineering/profiles/<profile_id>')
@social_login_required()
def social_profile_detail(profile_id):
    profile = owned_social_profile(profile_id)
    if not profile:
        return render_template('social_profile_detail.html', title='Profile not found', profile=None, **current_context()), 404
    for device in profile.get('devices', []):
        device['inventory_match'] = find_inventory_device(device.get('mac')) if device.get('mac') else None
    contact_refs = {
        **{f"email:{email['id']}": {'label': f"{email['label']} email", 'value': email['value'], 'status': email.get('status')} for email in profile.get('emails', [])},
        **({'phone': {'label': 'Phone', 'value': profile['phone'], 'status': profile.get('phone_status')}} if profile.get('phone') else {}),
    }
    for link in profile.get('social_links', []):
        link['recovery_contacts'] = [contact_refs[ref] for ref in link.get('recovery_refs', []) if ref in contact_refs]
    inventory_choices = [
        item for item in inventory_records()
        if (item.get('mac') or item.get('address')) and not item.get('is_control_traffic')
    ]
    user_record = current_user_record() or {}
    owned_profiles = owned_social_profiles()
    vault_credentials = [
        {'id': credential['id'], 'ciphertext': credential.get('secret_ciphertext', '')}
        for owned_profile in owned_profiles for credential in owned_profile.get('credentials', [])
        if credential.get('secret_ciphertext')
    ]
    profile_by_id = {item['id']: item for item in owned_profiles}
    for relationship in profile.get('relationships', []):
        relationship['target'] = profile_by_id.get(relationship.get('target_profile_id'))
    return render_template(
        'social_profile_detail.html', title=profile['full_name'], profile=profile,
        contact_refs=contact_refs, inventory_choices=inventory_choices,
        vault_verifier=user_record.get('vault_verifier', ''), vault_credentials=vault_credentials,
        relationship_choices=[item for item in owned_profiles if item['id'] != profile_id],
        social_user=session.get('social_user'), csrf_token=social_csrf_token(), **current_context(),
    )


@app.route('/social-engineering/profiles/<profile_id>/photo')
@social_login_required()
def social_profile_photo(profile_id):
    profile = owned_social_profile(profile_id)
    if not profile or not profile.get('photo_filename'):
        return '', 404
    return send_from_directory(SOCIAL_PROFILE_PHOTO_DIR, profile['photo_filename'])


@app.route('/social-engineering/profiles/<profile_id>/update', methods=['POST'])
@social_login_required({'editor', 'credential_manager', 'admin'})
def update_social_profile(profile_id):
    if not owned_social_profile(profile_id):
        return json_error('Profile not found', 404)
    try:
        profile = social_profile_service.update_profile(
            profile_id, request.form, social_profiles, social_profiles_lock,
        )
    except KeyError:
        return json_error('Profile not found', 404)
    except ValueError as exc:
        current = social_profile_service.get_profile(profile_id, social_profiles, social_profiles_lock)
        return render_template(
            'social_profile_detail.html', title=(current or {}).get('full_name', 'Profile'),
            profile={**(current or {}), **request.form}, error=str(exc), social_user=session.get('social_user'),
            csrf_token=social_csrf_token(), contact_refs={}, inventory_choices=[],
            vault_verifier=(current_user_record() or {}).get('vault_verifier', ''), **current_context(),
        ), 400
    try:
        save_social_profile_photo(profile_id, request.files.get('profile_photo'))
    except ValueError as exc:
        return json_error(str(exc))
    record_social_audit('profile.update', profile_id)
    save_runtime_state('social-profile-update')
    return redirect(url_for('social_profile_detail', profile_id=profile['id']))


@app.route('/social-engineering/profiles/<profile_id>/delete', methods=['POST'])
@social_login_required({'admin'})
def delete_social_profile(profile_id):
    profile = owned_social_profile(profile_id)
    if not profile:
        return json_error('Profile not found', 404)
    if not social_profile_service.delete_profile(profile_id, social_profiles, social_profiles_lock):
        return json_error('Profile not found', 404)
    if profile.get('photo_filename'):
        photo_path = os.path.join(SOCIAL_PROFILE_PHOTO_DIR, profile['photo_filename'])
        if os.path.exists(photo_path):
            os.unlink(photo_path)
    for attachment in profile.get('attachments', []):
        attachment_path = os.path.join(SOCIAL_PROFILE_ATTACHMENT_DIR, attachment.get('filename', ''))
        if os.path.isfile(attachment_path):
            os.unlink(attachment_path)
    for collection, directory in (
        (profile.get('identity_documents', []), SOCIAL_PROFILE_ID_DIR),
        (profile.get('signatures', []), SOCIAL_PROFILE_SIGNATURE_DIR),
    ):
        for item in collection:
            path = os.path.join(directory, item.get('filename', ''))
            if os.path.isfile(path):
                os.unlink(path)
    record_social_audit('profile.delete', profile_id)
    save_runtime_state('social-profile-delete')
    return redirect(url_for('social_engineering_page'))


@app.route('/social-engineering/profiles/<profile_id>/credentials', methods=['POST'])
@social_login_required({'credential_manager', 'admin'})
def add_social_profile_credential(profile_id):
    if not owned_social_profile(profile_id):
        return json_error('Profile not found', 404)
    try:
        social_profile_service.add_credential(profile_id, request.form, social_profiles, social_profiles_lock)
    except KeyError:
        return json_error('Profile not found', 404)
    except ValueError as exc:
        return json_error(str(exc))
    record_social_audit('credential.create', profile_id)
    save_runtime_state('social-profile-credential-create')
    return redirect(url_for('social_profile_detail', profile_id=profile_id))


@app.route('/social-engineering/profiles/<profile_id>/credentials/<credential_id>/delete', methods=['POST'])
@social_login_required({'credential_manager', 'admin'})
def delete_social_profile_credential(profile_id, credential_id):
    if not owned_social_profile(profile_id):
        return json_error('Profile not found', 404)
    try:
        removed = social_profile_service.delete_credential(profile_id, credential_id, social_profiles, social_profiles_lock)
    except KeyError:
        return json_error('Profile not found', 404)
    if not removed:
        return json_error('Credential not found', 404)
    record_social_audit('credential.delete', profile_id)
    save_runtime_state('social-profile-credential-delete')
    return redirect(url_for('social_profile_detail', profile_id=profile_id))


@app.route('/social-engineering/profiles/<profile_id>/credentials/<credential_id>/update', methods=['POST'])
@social_login_required({'credential_manager', 'admin'})
def update_social_profile_credential(profile_id, credential_id):
    if not owned_social_profile(profile_id):
        return json_error('Profile not found', 404)
    try:
        social_profile_service.update_credential(
            profile_id, credential_id, request.form, social_profiles, social_profiles_lock,
        )
    except KeyError:
        return json_error('Credential not found', 404)
    except ValueError as exc:
        return json_error(str(exc))
    record_social_audit('credential.rotate' if request.form.get('secret_ciphertext') else 'credential.update', profile_id)
    save_runtime_state('social-profile-credential-update')
    return redirect(url_for('social_profile_detail', profile_id=profile_id))


@app.route('/social-engineering/profiles/<profile_id>/devices', methods=['POST'])
@social_login_required({'editor', 'credential_manager', 'admin'})
def add_social_profile_device(profile_id):
    if not owned_social_profile(profile_id):
        return json_error('Profile not found', 404)
    try:
        social_profile_service.add_device(
            profile_id, request.form, social_profiles, social_profiles_lock, normalize_mac,
        )
    except KeyError:
        return json_error('Profile not found', 404)
    except ValueError as exc:
        return json_error(str(exc))
    record_social_audit('device.create', profile_id)
    save_runtime_state('social-profile-device-create')
    return redirect(url_for('social_profile_detail', profile_id=profile_id))


@app.route('/social-engineering/profiles/<profile_id>/devices/<device_id>/delete', methods=['POST'])
@social_login_required({'editor', 'credential_manager', 'admin'})
def delete_social_profile_device(profile_id, device_id):
    if not owned_social_profile(profile_id):
        return json_error('Profile not found', 404)
    try:
        removed = social_profile_service.delete_device(profile_id, device_id, social_profiles, social_profiles_lock)
    except KeyError:
        return json_error('Profile not found', 404)
    if not removed:
        return json_error('Device not found', 404)
    record_social_audit('device.delete', profile_id)
    save_runtime_state('social-profile-device-delete')
    return redirect(url_for('social_profile_detail', profile_id=profile_id))


@app.route('/social-engineering/profiles/<profile_id>/devices/<device_id>/update', methods=['POST'])
@social_login_required({'editor', 'credential_manager', 'admin'})
def update_social_profile_device(profile_id, device_id):
    if not owned_social_profile(profile_id):
        return json_error('Profile not found', 404)
    try:
        social_profile_service.update_device(
            profile_id, device_id, request.form, social_profiles, social_profiles_lock, normalize_mac,
        )
    except KeyError:
        return json_error('Device not found', 404)
    except ValueError as exc:
        return json_error(str(exc))
    record_social_audit('device.update', profile_id)
    save_runtime_state('social-profile-device-update')
    return redirect(url_for('social_profile_detail', profile_id=profile_id))


@app.route('/vault-verifier', methods=['POST'])
@social_login_required()
def save_vault_verifier():
    verifier = str(request.form.get('vault_verifier') or '')
    if not verifier.startswith('vault:v1:') or len(verifier) > 20000:
        return json_error('Invalid vault verifier.')
    username = current_app_user()['username']
    with social_users_lock:
        user = social_users.get(username)
        if not user:
            return json_error('User not found.', 404)
        if user.get('vault_verifier'):
            return json_error('Vault verifier is already configured.', 409)
        user['vault_verifier'] = verifier
    record_social_audit('vault.initialize')
    save_runtime_state('vault-verifier')
    return json_success()


@app.route('/vault-rotate', methods=['POST'])
@social_login_required({'credential_manager', 'admin'})
def rotate_vault():
    verifier = str(request.form.get('vault_verifier') or '')
    try:
        replacements = json.loads(request.form.get('credentials') or '{}')
    except json.JSONDecodeError:
        return json_error('Invalid credential rotation payload.')
    if not verifier.startswith('vault:v1:') or not isinstance(replacements, dict):
        return json_error('Invalid vault rotation payload.')
    username = current_app_user()['username']
    profiles = owned_social_profiles()
    expected = {item['id'] for profile in profiles for item in profile.get('credentials', []) if item.get('secret_ciphertext')}
    if set(replacements) != expected or any(not str(value).startswith('vault:v1:') for value in replacements.values()):
        return json_error('Every encrypted credential must be rotated together.')
    with social_profiles_lock:
        for profile in social_profiles.values():
            if profile.get('owner') != username:
                continue
            for credential in profile.get('credentials', []):
                if credential.get('id') in replacements:
                    credential['secret_ciphertext'] = replacements[credential['id']]
                    credential['rotated_at'] = time.time()
    with social_users_lock:
        social_users[username]['vault_verifier'] = verifier
    record_social_audit('vault.rotate')
    save_runtime_state('vault-rotate')
    return json_success()


@app.route('/social-engineering/profiles/<profile_id>/relationships', methods=['POST'])
@social_login_required({'editor', 'admin'})
def add_social_profile_relationship(profile_id):
    if not owned_social_profile(profile_id):
        return json_error('Profile not found', 404)
    try:
        social_profile_service.add_relationship(profile_id, request.form, social_profiles, social_profiles_lock)
    except (KeyError, ValueError) as exc:
        return json_error(str(exc))
    record_social_audit('relationship.create', profile_id)
    save_runtime_state('relationship-create')
    return redirect(url_for('social_profile_detail', profile_id=profile_id))


@app.route('/social-engineering/profiles/<profile_id>/relationships/<relationship_id>/delete', methods=['POST'])
@social_login_required({'editor', 'admin'})
def delete_social_profile_relationship(profile_id, relationship_id):
    if not owned_social_profile(profile_id):
        return json_error('Profile not found', 404)
    social_profile_service.delete_relationship(profile_id, relationship_id, social_profiles, social_profiles_lock)
    record_social_audit('relationship.delete', profile_id)
    save_runtime_state('relationship-delete')
    return redirect(url_for('social_profile_detail', profile_id=profile_id))


@app.route('/social-engineering/profiles/merge', methods=['POST'])
@social_login_required({'editor', 'admin'})
def merge_social_profiles():
    primary_id, duplicate_id = request.form.get('primary_id'), request.form.get('duplicate_id')
    if not owned_social_profile(primary_id) or not owned_social_profile(duplicate_id):
        return json_error('Profile not found', 404)
    try:
        social_profile_service.merge_profiles(primary_id, duplicate_id, social_profiles, social_profiles_lock)
    except (KeyError, ValueError) as exc:
        return json_error(str(exc))
    record_social_audit('profile.merge', primary_id, duplicate_id)
    save_runtime_state('profile-merge')
    return redirect(url_for('social_profile_detail', profile_id=primary_id))


@app.route('/social-engineering/profiles/<profile_id>/attachments', methods=['POST'])
@social_login_required({'editor', 'admin'})
def add_social_profile_attachment(profile_id):
    if not owned_social_profile(profile_id):
        return json_error('Profile not found', 404)
    upload = request.files.get('attachment')
    if not upload or not upload.filename:
        return json_error('Choose a file to attach.')
    content = upload.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        return json_error('Attachments must be 10 MB or smaller.')
    safe_name = secure_filename(upload.filename) or 'attachment'
    filename = f'{profile_id}-{uuid.uuid4()}-{safe_name}'
    os.makedirs(SOCIAL_PROFILE_ATTACHMENT_DIR, exist_ok=True)
    with open(os.path.join(SOCIAL_PROFILE_ATTACHMENT_DIR, filename), 'wb') as handle:
        handle.write(content)
    social_profile_service.add_attachment(profile_id, {
        'filename': filename, 'original_name': safe_name, 'description': request.form.get('description'),
        'sha256': hashlib.sha256(content).hexdigest(), 'size': len(content),
    }, social_profiles, social_profiles_lock)
    record_social_audit('attachment.create', profile_id, safe_name)
    save_runtime_state('attachment-create')
    return redirect(url_for('social_profile_detail', profile_id=profile_id))


@app.route('/social-engineering/profiles/<profile_id>/identity-documents', methods=['POST'])
@social_login_required({'editor', 'admin'})
def add_identity_document(profile_id):
    if not owned_social_profile(profile_id):
        return json_error('Profile not found', 404)
    try:
        image = save_profile_image(request.files.get('identity_image'), SOCIAL_PROFILE_ID_DIR, f'{profile_id}-id')
    except ValueError as exc:
        return json_error(str(exc))
    path = os.path.join(SOCIAL_PROFILE_ID_DIR, image['filename'])
    ocr_text, ocr_status = identity_image_ocr(path)
    detected = identity_ocr_fields(ocr_text)
    document = {
        'id': str(uuid.uuid4()), **image, 'document_type': str(request.form.get('document_type') or 'other')[:100],
        'document_number': str(request.form.get('document_number') or detected['document_number'])[:200],
        'issuing_country': str(request.form.get('issuing_country') or '')[:100],
        'date_of_birth': str(request.form.get('date_of_birth') or detected['date_of_birth'])[:100],
        'issue_date': str(request.form.get('issue_date') or '')[:100],
        'expiry_date': str(request.form.get('expiry_date') or detected['expiry_date'])[:100],
        'address': str(request.form.get('address') or '')[:1000], 'notes': str(request.form.get('notes') or '')[:2000],
        'ocr_text': ocr_text[:20000], 'ocr_status': ocr_status, 'detected_dates': detected['detected_dates'],
        'created_at': time.time(), 'updated_at': time.time(),
    }
    with social_profiles_lock:
        social_profiles[profile_id].setdefault('identity_documents', []).append(document)
    record_social_audit('identity-document.create', profile_id, document['document_type'])
    save_runtime_state('identity-document-create')
    return redirect(url_for('identity_document_detail', profile_id=profile_id, document_id=document['id']))


@app.route('/social-engineering/profiles/<profile_id>/identity-documents/<document_id>', methods=['GET', 'POST'])
@social_login_required()
def identity_document_detail(profile_id, document_id):
    profile = owned_social_profile(profile_id)
    document = next((item for item in (profile or {}).get('identity_documents', []) if item.get('id') == document_id), None)
    if not document:
        return render_template('identity_document.html', title='Identity document not found', profile=profile, document=None, **current_context()), 404
    if request.method == 'POST':
        if current_app_user().get('role') not in {'editor', 'admin'}:
            return json_error('You do not have permission for this action.', 403)
        fields = ('document_type', 'document_number', 'issuing_country', 'date_of_birth', 'issue_date', 'expiry_date', 'address', 'notes')
        with social_profiles_lock:
            stored = next(item for item in social_profiles[profile_id].setdefault('identity_documents', []) if item.get('id') == document_id)
            for field in fields:
                stored[field] = str(request.form.get(field) or '').strip()[:2000 if field in {'address', 'notes'} else 200]
            stored['updated_at'] = time.time()
        record_social_audit('identity-document.update', profile_id, document_id)
        save_runtime_state('identity-document-update')
        return redirect(url_for('identity_document_detail', profile_id=profile_id, document_id=document_id, saved=1))
    return render_template('identity_document.html', title=f"{profile['full_name']} identity document", profile=profile,
                           document=document, csrf_token=social_csrf_token(), **current_context())


@app.route('/social-engineering/profiles/<profile_id>/identity-documents/<document_id>/image')
@social_login_required()
def identity_document_image(profile_id, document_id):
    profile = owned_social_profile(profile_id)
    document = next((item for item in (profile or {}).get('identity_documents', []) if item.get('id') == document_id), None)
    if not document:
        return json_error('Identity document not found', 404)
    return send_from_directory(SOCIAL_PROFILE_ID_DIR, document['filename'])


@app.route('/social-engineering/profiles/<profile_id>/identity-documents/<document_id>/delete', methods=['POST'])
@social_login_required({'editor', 'admin'})
def delete_identity_document(profile_id, document_id):
    if not owned_social_profile(profile_id):
        return json_error('Profile not found', 404)
    with social_profiles_lock:
        items = social_profiles[profile_id].setdefault('identity_documents', [])
        document = next((item for item in items if item.get('id') == document_id), None)
        if document:
            social_profiles[profile_id]['identity_documents'] = [item for item in items if item.get('id') != document_id]
    if not document:
        return json_error('Identity document not found', 404)
    path = os.path.join(SOCIAL_PROFILE_ID_DIR, document['filename'])
    if os.path.isfile(path):
        os.unlink(path)
    record_social_audit('identity-document.delete', profile_id, document_id)
    save_runtime_state('identity-document-delete')
    return redirect(url_for('social_profile_detail', profile_id=profile_id))


@app.route('/social-engineering/profiles/<profile_id>/signatures', methods=['POST'])
@social_login_required({'editor', 'admin'})
def add_profile_signature(profile_id):
    if not owned_social_profile(profile_id):
        return json_error('Profile not found', 404)
    try:
        image = save_profile_image(request.files.get('signature_image'), SOCIAL_PROFILE_SIGNATURE_DIR, f'{profile_id}-signature')
    except ValueError as exc:
        return json_error(str(exc))
    signature = {'id': str(uuid.uuid4()), **image, 'label': str(request.form.get('label') or 'Signature')[:200],
                 'signed_at': str(request.form.get('signed_at') or '')[:100], 'notes': str(request.form.get('notes') or '')[:2000],
                 'created_at': time.time()}
    with social_profiles_lock:
        social_profiles[profile_id].setdefault('signatures', []).append(signature)
    record_social_audit('signature.create', profile_id, signature['label'])
    save_runtime_state('signature-create')
    return redirect(url_for('social_profile_detail', profile_id=profile_id))


@app.route('/social-engineering/profiles/<profile_id>/signatures/<signature_id>/image')
@social_login_required()
def profile_signature_image(profile_id, signature_id):
    profile = owned_social_profile(profile_id)
    signature = next((item for item in (profile or {}).get('signatures', []) if item.get('id') == signature_id), None)
    if not signature:
        return json_error('Signature not found', 404)
    return send_from_directory(SOCIAL_PROFILE_SIGNATURE_DIR, signature['filename'])


@app.route('/social-engineering/profiles/<profile_id>/signatures/<signature_id>/delete', methods=['POST'])
@social_login_required({'editor', 'admin'})
def delete_profile_signature(profile_id, signature_id):
    if not owned_social_profile(profile_id):
        return json_error('Profile not found', 404)
    with social_profiles_lock:
        items = social_profiles[profile_id].setdefault('signatures', [])
        signature = next((item for item in items if item.get('id') == signature_id), None)
        if signature:
            social_profiles[profile_id]['signatures'] = [item for item in items if item.get('id') != signature_id]
    if not signature:
        return json_error('Signature not found', 404)
    path = os.path.join(SOCIAL_PROFILE_SIGNATURE_DIR, signature['filename'])
    if os.path.isfile(path):
        os.unlink(path)
    record_social_audit('signature.delete', profile_id, signature_id)
    save_runtime_state('signature-delete')
    return redirect(url_for('social_profile_detail', profile_id=profile_id))


@app.route('/social-engineering/profiles/<profile_id>/attachments/<attachment_id>')
@social_login_required()
def download_social_profile_attachment(profile_id, attachment_id):
    profile = owned_social_profile(profile_id)
    item = next((entry for entry in (profile or {}).get('attachments', []) if entry.get('id') == attachment_id), None)
    if not item:
        return json_error('Attachment not found', 404)
    record_social_audit('attachment.download', profile_id, item['original_name'])
    return send_from_directory(SOCIAL_PROFILE_ATTACHMENT_DIR, item['filename'], as_attachment=True, download_name=item['original_name'])


@app.route('/social-engineering/profiles/<profile_id>/attachments/<attachment_id>/delete', methods=['POST'])
@social_login_required({'editor', 'admin'})
def delete_social_profile_attachment(profile_id, attachment_id):
    if not owned_social_profile(profile_id):
        return json_error('Profile not found', 404)
    item = social_profile_service.delete_attachment(profile_id, attachment_id, social_profiles, social_profiles_lock)
    if not item:
        return json_error('Attachment not found', 404)
    path = os.path.join(SOCIAL_PROFILE_ATTACHMENT_DIR, item['filename'])
    if os.path.isfile(path):
        os.unlink(path)
    record_social_audit('attachment.delete', profile_id, item['original_name'])
    save_runtime_state('attachment-delete')
    return redirect(url_for('social_profile_detail', profile_id=profile_id))


@app.route('/social-engineering/export')
@social_login_required()
def export_social_profiles():
    profiles = owned_social_profiles()
    if request.args.get('format') == 'csv':
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=['full_name', 'organization', 'job_title', 'phone', 'emails', 'tags', 'status'])
        writer.writeheader()
        for item in profiles:
            writer.writerow({'full_name': item['full_name'], 'organization': item.get('organization'), 'job_title': item.get('job_title'),
                             'phone': item.get('phone'), 'emails': ', '.join(email['value'] for email in item.get('emails', [])),
                             'tags': ', '.join(item.get('tags', [])), 'status': item.get('profile_status')})
        return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=contacts.csv'})
    safe_profiles = [{key: value for key, value in item.items() if key != 'credentials'} for item in profiles]
    return Response(json.dumps({'profiles': safe_profiles}, indent=2), mimetype='application/json', headers={'Content-Disposition': 'attachment; filename=contacts.json'})


@app.route('/social-engineering/import', methods=['POST'])
@social_login_required({'editor', 'admin'})
def import_social_profiles():
    upload = request.files.get('contacts_file')
    if not upload:
        return json_error('Choose a JSON contacts export.')
    try:
        payload = json.loads(upload.read(2 * 1024 * 1024).decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return json_error('The contacts file is not valid JSON.')
    records = payload.get('profiles', []) if isinstance(payload, dict) else []
    if not isinstance(records, list) or len(records) > 1000:
        return json_error('The contacts export is invalid or too large.')
    created = 0
    for record in records:
        if not isinstance(record, dict):
            continue
        values = {'full_name': record.get('full_name'), 'organization': record.get('organization'),
                  'job_title': record.get('job_title'), 'phone': record.get('phone'), 'notes': record.get('notes'),
                  'phone_status': record.get('phone_status'), 'phone_source': record.get('phone_source'),
                  'phone_confidence': record.get('phone_confidence'), 'phone_verified_date': record.get('phone_verified_date'),
                  'tags': ','.join(record.get('tags', [])), 'profile_status': record.get('profile_status'),
                  'authorization_basis': record.get('authorization_basis'), 'review_date': record.get('review_date'),
                  'retention_until': record.get('retention_until'),
                  'email_id': [item.get('id') for item in record.get('emails', [])],
                  'email_label': [item.get('label') for item in record.get('emails', [])],
                  'email_value': [item.get('value') for item in record.get('emails', [])],
                  'email_status': [item.get('status') for item in record.get('emails', [])],
                  'email_source': [item.get('source') for item in record.get('emails', [])],
                  'email_confidence': [item.get('confidence') for item in record.get('emails', [])],
                  'email_verified_date': [item.get('verified_date') for item in record.get('emails', [])],
                  'custom_field_name': [item.get('name') for item in record.get('custom_fields', [])],
                  'custom_field_value': [item.get('value') for item in record.get('custom_fields', [])],
                  'custom_field_type': [item.get('type') for item in record.get('custom_fields', [])]}
        try:
            profile = social_profile_service.create_profile(values, social_profiles, social_profiles_lock)
        except ValueError:
            continue
        with social_profiles_lock:
            social_profiles[profile['id']]['owner'] = current_app_user()['username']
        created += 1
    record_social_audit('profiles.import', detail=str(created))
    save_runtime_state('profiles-import')
    return redirect(url_for('social_engineering_page'))


@app.route('/social-engineering/profiles/<profile_id>/audit', methods=['POST'])
@social_login_required()
def social_profile_client_audit(profile_id):
    if not owned_social_profile(profile_id):
        return json_error('Profile not found', 404)
    action = str(request.form.get('action') or '')
    if action not in {'credential.reveal', 'vault.unlock'}:
        return json_error('Unsupported audit action.')
    record_social_audit(action, profile_id)
    save_runtime_state('social-profile-audit')
    return json_success()


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
app.config['AUTOMOTIVE_PEOPLE_PROVIDER'] = lambda: [
    {'id': profile.get('id'), 'full_name': profile.get('full_name') or 'Unnamed person'}
    for profile in owned_social_profiles()
]
register_blueprints(app, current_context)


# Endpoint to fetch the current list of network adapters


if __name__ == '__main__':
    host = '0.0.0.0'
    port = 8080
    app.logger.info("Server running at http://%s:%s (log file: %s)", host, port, log_path)
    socketio.run(app, host=host, port=port, debug=True)
