"""Client service fingerprinting, scheduled checks, alerts, and HTTP inspection."""

from functools import wraps


_CONTEXT_PROVIDER = None


def configure_client_services_context(provider):
    global _CONTEXT_PROVIDER
    _CONTEXT_PROVIDER = provider


def _refresh_context(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if _CONTEXT_PROVIDER is not None:
            globals().update(_CONTEXT_PROVIDER())
        return view(*args, **kwargs)
    return wrapped


@_refresh_context
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


@_refresh_context
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


@_refresh_context
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


@_refresh_context
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


@_refresh_context
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


@_refresh_context
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


@_refresh_context
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


@_refresh_context
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


__all__ = [
    'fingerprint_client_services',
    'save_scheduled_client_check',
    'scan_common_client_ports',
    'run_scheduled_client_check',
    'run_due_scheduled_client_checks',
    'create_client_watch_alert',
    'capture_http_preview_thumbnail',
    'inspect_http_services'
]
