"""Client service fingerprinting and bounded HTTP inspection."""

import os
import re
import shutil
import socket
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from services import device_intel
from werkzeug.utils import secure_filename

from .client_service_dependencies import client_service_dependencies


def fingerprint_client_services(identifier):
    """Run safe, lightweight service fingerprint checks against saved open ports."""
    deps = client_service_dependencies()
    device = deps.find_inventory_device(identifier) or {}
    host = device.get('ip') or identifier
    fingerprints = []
    http_ports = []
    for detail in device.get('open_port_details', []):
        port = detail.get('port')
        service = str(detail.get('service') or '').lower()
        finding = {
            'port': port,
            'service': detail.get('service') or 'Unknown',
            'confidence': 'low',
            'banner': None,
            'notes': [],
        }
        if port in (80, 443, 8080, 8443, 8000, 9443) or any(
            name in service for name in ('http', 'https', 'web')
        ):
            http_ports.append(port)
            finding['confidence'] = 'medium'
            finding['notes'].append('HTTP-like port selected for web inspection.')
        elif port in (21, 22, 25, 110, 143, 587, 993, 995):
            try:
                with socket.create_connection((host, int(port)), timeout=2) as sock:
                    sock.settimeout(2)
                    try:
                        banner = sock.recv(256).decode(
                            'utf-8', errors='ignore'
                        ).strip()
                    except socket.timeout:
                        banner = ''
                if banner:
                    finding['banner'] = banner[:160]
                    finding['confidence'] = 'high'
                else:
                    finding['notes'].append(
                        'Port accepted TCP connection but did not send a banner quickly.'
                    )
                    finding['confidence'] = 'medium'
            except OSError as exc:
                finding['notes'].append(f'Banner probe unavailable: {exc}')
        else:
            finding['notes'].append(
                'Service inferred from port number; no active banner probe selected.'
            )
        fingerprints.append(finding)
    if http_ports:
        web_results = deps.inspect_http_services(host, sorted(set(http_ports))[:8])
        by_port = {item['port']: item for item in web_results}
        for finding in fingerprints:
            web = by_port.get(finding.get('port'))
            if web:
                finding['http'] = web
                if web.get('title') or web.get('server') or web.get('status'):
                    finding['confidence'] = 'high'
    deps.append_client_timeline_event(
        host,
        'Services fingerprinted',
        f"Checked {len(fingerprints)} saved service(s).",
        'service-fingerprint',
    )
    return fingerprints


def capture_http_preview_thumbnail(url):
    """Capture a small web preview when a local screenshot utility exists."""
    deps = client_service_dependencies()
    tool = (
        shutil.which('wkhtmltoimage')
        or shutil.which('chromium')
        or shutil.which('chromium-browser')
        or shutil.which('google-chrome')
    )
    if not tool:
        return None
    os.makedirs(deps.HTTP_PREVIEW_DIR, exist_ok=True)
    filename = secure_filename(re.sub(r'[^A-Za-z0-9_.-]+', '_', url))[:120] + '.png'
    output_path = os.path.join(deps.HTTP_PREVIEW_DIR, filename)
    try:
        if (
            os.path.exists(output_path)
            and time.time() - os.path.getmtime(output_path) < 3600
        ):
            return f'/http-previews/{filename}'
        if os.path.basename(tool) == 'wkhtmltoimage':
            command = [tool, '--width', '480', '--height', '320', url, output_path]
        else:
            command = [
                tool,
                '--headless',
                '--disable-gpu',
                '--no-sandbox',
                f'--screenshot={output_path}',
                '--window-size=480,320',
                url,
            ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if result.returncode == 0 and os.path.exists(output_path):
            return f'/http-previews/{filename}'
    except (OSError, subprocess.TimeoutExpired):
        return None
    return None


def inspect_http_services(host, ports):
    """Safely inspect likely HTTP services for titles and headers."""
    deps = client_service_dependencies()
    results = []
    for port in ports:
        scheme = 'https' if int(port) in (443, 8443, 9443) else 'http'
        url = f'{scheme}://{host}:{port}/'
        result = {
            'port': int(port),
            'url': url,
            'status': None,
            'title': None,
            'server': None,
            'error': None,
            'favicon': None,
        }
        try:
            req = Request(url, headers={'User-Agent': 'MobileRouterLab/1.0'})
            with urlopen(req, timeout=3) as resp:
                body = resp.read(65536).decode('utf-8', errors='ignore')
                result['status'] = getattr(resp, 'status', None)
                result['server'] = resp.headers.get('Server')
                match = re.search(r'<title[^>]*>(.*?)</title>', body, re.I | re.S)
                if match:
                    result['title'] = re.sub(
                        r'\s+', ' ', match.group(1)
                    ).strip()[:120]
                result['favicon'] = device_intel.favicon_metadata(url, urlopen)
                result['thumbnail_url'] = deps.capture_http_preview_thumbnail(url)
        except HTTPError as exc:
            result['status'] = exc.code
            result['server'] = exc.headers.get('Server')
            result['error'] = exc.reason
        except (URLError, TimeoutError, socket.timeout, ValueError) as exc:
            result['error'] = str(exc)
        results.append(result)
    return results
