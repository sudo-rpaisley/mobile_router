"""Helpers for safe, auditable wireless lab workflows."""

import csv
import io
import os
import re
import time
import uuid

DEAUTH_FRAME_LIMIT = 5
BROADCAST_MAC = 'ff:ff:ff:ff:ff:ff'
EVIL_TWIN_MAX_DURATION_MINUTES = 30
EVIL_TWIN_ACTIONS = {'plan', 'start', 'cleanup'}
PINEAP_ACTIONS = {'recon', 'campaign', 'handshake', 'module'}
PINEAP_MODULES = {'recon', 'evil-twin-lab', 'handshake-capture', 'portal-awareness', 'detection-report'}
HANDSHAKE_CAPTURE_TYPES = {'wpa-handshake', 'pmkid'}


def require_normalized_mac(value, normalize_mac):
    """Return a normalized MAC address or raise ValueError for required lab inputs."""
    mac = normalize_mac(value)
    if not mac:
        raise ValueError('Enter a valid MAC address in the form aa:bb:cc:dd:ee:ff')
    return mac


def validate_deauth_request(data, normalize_mac, parse_int):
    """Validate bounded deauth lab inputs for an authorized classroom exercise."""
    ap_mac = require_normalized_mac(data.get('ap'), normalize_mac)
    target_mac = require_normalized_mac(data.get('target') or BROADCAST_MAC, normalize_mac)
    if ap_mac == BROADCAST_MAC:
        raise ValueError('AP MAC must be a specific lab access point, not broadcast')
    if data.get('authorized') != 'on':
        raise ValueError('Confirm this is an authorized isolated lab network before running deauth')
    frames = parse_int(data.get('frames'), 'Frames must be an integer')
    if frames < 1 or frames > DEAUTH_FRAME_LIMIT:
        raise ValueError(f'Frames must be between 1 and {DEAUTH_FRAME_LIMIT} for first-year labs')
    return ap_mac, target_mac, frames


def validate_evil_twin_request(data, normalize_mac, parse_int):
    """Validate a controlled rogue-AP/captive-portal lab workflow request."""
    action = (data.get('action') or 'plan').strip().lower()
    if action not in EVIL_TWIN_ACTIONS:
        raise ValueError('Choose plan, start, or cleanup for the lab workflow')
    if data.get('authorized') != 'on':
        raise ValueError('Confirm this is an authorized isolated lab before preparing an evil twin lab workflow')
    ssid = (data.get('ssid') or '').strip()
    if not ssid or len(ssid) > 32:
        raise ValueError('Enter the exact lab SSID, up to 32 characters')
    bssid = require_normalized_mac(data.get('bssid'), normalize_mac)
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


def evil_twin_guidance(run):
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


def record_evil_twin_run(selected_interface, lab, runs, lock, save_state, logger):
    """Record a non-credential evil-twin/captive-portal lab workflow event."""
    run = {'id': uuid.uuid4().hex, 'created_at': time.time(), 'interface': selected_interface, **lab}
    run.update(evil_twin_guidance(run))
    with lock:
        runs.append(run)
        del runs[:-25]
    save_state('evil-twin-lab')
    logger.info(
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


def validate_pineap_request(data, normalize_mac, parse_int):
    """Validate a WiFi Pineapple-style lab controller request."""
    if data.get('authorized') != 'on':
        raise ValueError('Confirm this is an authorized isolated lab before running a campaign workflow')
    action = (data.get('action') or 'recon').strip().lower()
    if action not in PINEAP_ACTIONS:
        raise ValueError('Choose recon, campaign, handshake, or module')
    ssid = (data.get('ssid') or '').strip()
    if ssid and len(ssid) > 32:
        raise ValueError('SSID must be 32 characters or fewer')
    bssid = require_normalized_mac(data.get('bssid'), normalize_mac) if data.get('bssid') else None
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


def build_pineap_result(selected_interface, lab, runs, lock, save_state, logger, wifi_utils):
    """Build an auditable, non-destructive PineAP-style lab result."""
    recon = []
    if lab['action'] == 'recon':
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
    with lock:
        runs.insert(0, run)
        del runs[100:]
    save_state('pineap-lab')
    logger.info('PineAP-style lab %s recorded for SSID %r on %s', run['action'], run['ssid'], selected_interface)
    return run


def validate_handshake_request(data, normalize_mac, parse_int):
    """Validate handshake/PMKID evidence catalog inputs."""
    if data.get('authorized') != 'on':
        raise ValueError('Confirm this is an authorized isolated lab before cataloging handshake evidence')
    ssid = (data.get('ssid') or '').strip()
    if not ssid or len(ssid) > 32:
        raise ValueError('Enter the exact lab SSID, up to 32 characters')
    bssid = require_normalized_mac(data.get('bssid'), normalize_mac)
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


def record_handshake_evidence(selected_interface, lab, uploaded_file, create_evidence_record, records, lock, save_state, logger):
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
    with lock:
        records.insert(0, record)
        del records[200:]
    save_state('handshake-lab')
    logger.info('Handshake lab evidence %s cataloged for SSID %r BSSID %s', record['capture_type'], record['ssid'], record['bssid'])
    return record


def export_handshake_records(records, lock):
    with lock:
        exported = [dict(item) for item in records]
    for item in exported:
        item['created_at_label'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(item.get('created_at', 0)))
    return exported


def handshake_records_csv(records):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['SSID', 'BSSID', 'Channel', 'Type', 'Client', 'Status', 'File', 'Created'])
    for item in records:
        writer.writerow([item.get('ssid'), item.get('bssid'), item.get('channel'), item.get('capture_type'), item.get('client'), item.get('validation_status'), item.get('file_name'), item.get('created_at_label')])
    return output.getvalue()
