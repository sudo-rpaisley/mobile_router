"""Scheduled client checks and watched-client alerts."""

import socket
import time
import uuid
from urllib.parse import quote

from .client_service_dependencies import client_service_dependencies


def save_scheduled_client_check(identifier, data):
    """Store a recurring-check plan for a watched or important client."""
    deps = client_service_dependencies()
    target = str(identifier or '').strip()
    if not target:
        raise ValueError('Missing client identifier')
    interval = max(
        5,
        min(
            deps.parse_int(
                data.get('intervalMinutes') or 60,
                'Interval must be an integer',
            ),
            10080,
        ),
    )
    checks = sorted(
        {
            check
            for check in (
                data.get('checks') or 'ping,common-ports,baseline-drift'
            ).split(',')
            if check
            in {
                'ping',
                'common-ports',
                'http-inspect',
                'service-fingerprint',
                'baseline-drift',
            }
        }
    )
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
    deps.scheduled_client_checks[target] = plan
    deps.append_client_timeline_event(
        target,
        'Scheduled checks updated',
        f"Scheduled {', '.join(checks)} every {interval} minute(s).",
        'scheduled-checks',
    )
    deps.save_runtime_state('scheduled-check')
    return dict(plan)


def scan_common_client_ports(host, timeout=0.35):
    """Run a bounded common-port refresh for scheduled checks."""
    from scripts.portScanner import COMMON_SERVICE_HINTS, identify_port_service

    deps = client_service_dependencies()
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
            open_details.append(
                deps.enrich_web_port_metadata(
                    target, identify_port_service(int(port))
                )
            )
    if open_details:
        deps.record_device_open_ports(
            target, open_details, source='scheduled-common-ports'
        )
    return open_details


def run_scheduled_client_check(identifier, now=None):
    """Execute one saved scheduled-check plan and persist its summary."""
    deps = client_service_dependencies()
    target = str(identifier or '').strip()
    plan = deps.scheduled_client_checks.get(target)
    if not plan:
        raise ValueError('No scheduled check plan found for this client')
    now = now or time.time()
    results = {}
    checks = plan.get('checks') or []
    if 'ping' in checks:
        results['ping'] = deps.run_ping_check(target, count=2, timeout=2)
    if 'common-ports' in checks:
        results['common_ports'] = deps.scan_common_client_ports(target)
    if 'http-inspect' in checks:
        device = deps.find_inventory_device(target) or {}
        ports = [
            item.get('port')
            for item in device.get('open_port_details', [])
            if item.get('web_url')
            or str(item.get('service') or '').lower().startswith('http')
        ]
        results['http_inspect'] = deps.inspect_http_services(
            target,
            sorted({int(port) for port in ports if port})[:8],
        )
    if 'service-fingerprint' in checks:
        results['service_fingerprint'] = deps.fingerprint_client_services(target)
    if 'baseline-drift' in checks:
        results['baseline_drift'] = deps.client_baseline_diff(
            deps.find_inventory_device(target) or {}
        )
    plan.update(
        {
            'last_run': now,
            'next_run': now + (int(plan.get('interval_minutes') or 60) * 60),
            'last_result': results,
            'status': 'completed',
        }
    )
    deps.append_client_timeline_event(
        target,
        'Scheduled check run',
        f"Completed scheduled checks: {', '.join(checks)}.",
        'scheduled-checks',
    )
    drift = results.get('baseline_drift') or {}
    if deps.is_client_watched(target) and drift.get('status') == 'Drift detected':
        deps.create_client_watch_alert(
            target,
            'Scheduled check drift detected',
            f'Baseline drift detected for {target}.',
        )
    deps.save_runtime_state('scheduled-check-run')
    return dict(plan)


def run_due_scheduled_client_checks(now=None):
    """Run every scheduled client check whose interval has elapsed."""
    deps = client_service_dependencies()
    now = now or time.time()
    due = []
    for target, plan in list(deps.scheduled_client_checks.items()):
        last_run = plan.get('last_run')
        interval_seconds = int(plan.get('interval_minutes') or 60) * 60
        if last_run is None or now - float(last_run or 0) >= interval_seconds:
            due.append(target)
    results = []
    for target in due[:25]:
        try:
            results.append(deps.run_scheduled_client_check(target, now=now))
        except ValueError:
            continue
    return results


def create_client_watch_alert(identifier, title, message):
    deps = client_service_dependencies()
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
    with deps.new_device_alerts_lock:
        deps.new_device_alerts.insert(0, alert)
        del deps.new_device_alerts[200:]
    return alert
