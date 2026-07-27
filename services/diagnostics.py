"""Network diagnostics, reachability, and advanced assessment helpers."""

import ipaddress
import json
import os
import re
import time


def ping_command(host, count=4, timeout=2, os_name=os.name):
    """Build a platform-appropriate ping command."""
    if os_name == 'nt':
        return ['ping', '-n', str(count), '-w', str(timeout * 1000), host]
    return ['ping', '-c', str(count), '-W', str(timeout), host]


def parse_ping_output(output):
    """Return packet-loss and latency details from common ping output."""
    loss = None
    transmitted = received = None
    packet_match = re.search(
        r'(\d+)\s+packets transmitted,\s+(\d+)\s+(?:packets )?received,\s+([\d.]+)% packet loss',
        output,
    )
    if packet_match:
        transmitted = int(packet_match.group(1))
        received = int(packet_match.group(2))
        loss = float(packet_match.group(3))
    windows_match = re.search(
        r'Packets: Sent = (\d+), Received = (\d+), Lost = (\d+) \((\d+)% loss\)',
        output,
    )
    if windows_match:
        transmitted = int(windows_match.group(1))
        received = int(windows_match.group(2))
        loss = float(windows_match.group(4))
    stats_match = re.search(r'(?:rtt|round-trip).*?=\s*([\d.]+)/([\d.]+)/([\d.]+)/(?:[\d.]+)', output)
    windows_stats = re.search(r'Minimum = (\d+)ms, Maximum = (\d+)ms, Average = (\d+)ms', output)
    latency = {}
    if stats_match:
        latency = {
            'min_ms': float(stats_match.group(1)),
            'avg_ms': float(stats_match.group(2)),
            'max_ms': float(stats_match.group(3)),
        }
    elif windows_stats:
        latency = {
            'min_ms': float(windows_stats.group(1)),
            'avg_ms': float(windows_stats.group(3)),
            'max_ms': float(windows_stats.group(2)),
        }
    return {'transmitted': transmitted, 'received': received, 'packet_loss_percent': loss, 'latency': latency}


def run_ping_check(host, count, timeout, parse_int, subprocess_module, ping_history):
    """Run a bounded ping and append the result to reachability history."""
    host = (host or '').strip()
    if not host:
        raise ValueError('Host is required')
    count = max(1, min(parse_int(count, 'Count must be an integer'), 10))
    timeout = max(1, min(parse_int(timeout, 'Timeout must be an integer'), 10))
    started = time.time()
    result = subprocess_module.run(
        ping_command(host, count=count, timeout=timeout, os_name=os.name),
        capture_output=True,
        text=True,
        timeout=(count * timeout) + 5,
        check=False,
    )
    output = (result.stdout or result.stderr or '').strip()
    history = {
        'host': host,
        'reachable': result.returncode == 0,
        'returncode': result.returncode,
        'duration_ms': round((time.time() - started) * 1000, 2),
        'output': output,
        **parse_ping_output(output),
        'checked_at': time.time(),
    }
    ping_history.append(history)
    del ping_history[:-100]
    return history


def run_ping_sweep(cidr, count, timeout, run_ping_check, timeout_error):
    """Run a bounded ping sweep over small IPv4/IPv6 subnets."""
    network = ipaddress.ip_network((cidr or '').strip(), strict=False)
    hosts = list(network.hosts())
    if network.version == 6 and network.prefixlen < 120:
        raise ValueError('IPv6 sweeps are limited to /120 or smaller ranges')
    if len(hosts) > 64:
        raise ValueError('Subnet sweeps are limited to 64 hosts')
    results = []
    for host in hosts:
        try:
            results.append(run_ping_check(str(host), count=count, timeout=timeout))
        except timeout_error:
            results.append({
                'host': str(host),
                'reachable': False,
                'packet_loss_percent': 100.0,
                'latency': {},
                'output': 'Timed out',
                'checked_at': time.time(),
            })
    return {
        'cidr': str(network),
        'total_hosts': len(results),
        'reachable_hosts': len([item for item in results if item.get('reachable')]),
        'results': results,
    }


def parse_route_lines(output):
    """Parse Linux route output into dictionaries."""
    routes = []
    for line in (output or '').splitlines():
        line = line.strip()
        if not line:
            continue
        tokens = line.split()
        route = {
            'raw': line,
            'destination': tokens[0] if tokens else None,
            'gateway': None,
            'interface': None,
            'metric': None,
            'family': 'IPv6' if ':' in tokens[0] else 'IPv4',
        }
        if 'via' in tokens:
            route['gateway'] = tokens[tokens.index('via') + 1]
        if 'dev' in tokens:
            route['interface'] = tokens[tokens.index('dev') + 1]
        if 'metric' in tokens:
            route['metric'] = tokens[tokens.index('metric') + 1]
        routes.append(route)
    return routes


def build_route_diagnostics(target, run_text_command, os_name=os.name):
    """Display default gateways, routes, VPN hints, and target path context."""
    commands = []
    if os_name == 'nt':
        commands.append(['route', 'print'])
        if target:
            commands.append(['tracert', '-d', '-h', '1', target])
    else:
        commands.extend([['ip', '-4', 'route', 'show'], ['ip', '-6', 'route', 'show']])
        if target:
            commands.append(['ip', 'route', 'get', target])
    command_results = [run_text_command(command) for command in commands]
    routes = []
    for result in command_results:
        if result['command'][:2] in (['ip', '-4'], ['ip', '-6']) or result['command'][:1] == ['ip']:
            routes.extend(parse_route_lines(result['output']))
    return {
        'default_gateways': [route for route in routes if route.get('destination') == 'default'],
        'routes': routes,
        'vpn_hints': [
            route for route in routes
            if re.search(r'\b(tun|tap|wg|vpn|ppp|utun)\w*\b', route.get('interface') or '', re.I)
        ],
        'scan_path_context': next(
            (result['output'] for result in command_results if result['command'][:3] == ['ip', 'route', 'get']),
            '',
        ),
        'commands': command_results,
        'checked_at': time.time(),
    }


def discover_vlan_context(ssid, vlan_id, notes, run_text_command, note_store, uuid_factory, os_name=os.name):
    """Inventory VLAN-like interfaces and store optional SSID-to-VLAN notes."""
    command_result = (
        run_text_command(['ip', '-d', 'link', 'show'], timeout=5)
        if os_name != 'nt'
        else {'output': '', 'returncode': 1}
    )
    vlans = []
    current = None
    for line in command_result.get('output', '').splitlines():
        header = re.match(r'\d+:\s+([^:@]+(?:\.\d+)?)(?:@([^:]+))?:', line.strip())
        if header:
            name = header.group(1)
            parent = header.group(2)
            current = {'interface': name, 'parent': parent, 'vlan_id': None, 'raw': line.strip()}
            if '.' in name and name.rsplit('.', 1)[-1].isdigit():
                current['vlan_id'] = name.rsplit('.', 1)[-1]
                vlans.append(current)
            continue
        if current and 'vlan id' in line:
            match = re.search(r'vlan id\s+(\d+)', line)
            if match:
                current['vlan_id'] = match.group(1)
                if current not in vlans:
                    vlans.append(current)
    note_record = None
    if ssid or vlan_id or notes:
        note_record = {
            'id': uuid_factory().hex,
            'ssid': (ssid or '').strip(),
            'vlan_id': str(vlan_id or '').strip(),
            'notes': (notes or '').strip()[:500],
            'created_at': time.time(),
            'validation_context': 'Confirm client isolation, gateway ACLs, DHCP scope, DNS policy, and inter-VLAN firewall rules.',
        }
        note_store.insert(0, note_record)
        del note_store[100:]
    return {'vlans': vlans, 'notes': list(note_store), 'created_note': note_record, 'command': command_result}


def build_egress_diagnostics(selected_interface, run_text_command, build_route_diagnostics, network_interfaces, environ, urlopen, open_file, os_name=os.name):
    """Collect public egress, DNS, NAT, VPN/proxy, and route context."""
    public_ip = None
    try:
        with urlopen('https://api.ipify.org', timeout=4) as response:
            public_ip = response.read().decode('utf-8').strip()
    except Exception as exc:
        public_error = str(exc)
    else:
        public_error = None
    try:
        with open_file('/etc/resolv.conf', encoding='utf-8') as handle:
            resolvers = [line.split()[1] for line in handle if line.startswith('nameserver') and len(line.split()) > 1]
    except OSError:
        resolvers = []
    ipv6_default = run_text_command(['ip', '-6', 'route', 'show', 'default'], timeout=5) if os_name != 'nt' else {'output': ''}
    interface_route = (
        run_text_command(['ip', 'route', 'show', 'dev', selected_interface], timeout=5)
        if selected_interface and os_name != 'nt'
        else {'output': ''}
    )
    proxy_hints = {key: value for key, value in environ.items() if key.lower() in {'http_proxy', 'https_proxy', 'all_proxy', 'no_proxy'}}
    route_diag = build_route_diagnostics(public_ip) if public_ip else build_route_diagnostics()
    private_addresses = [iface.to_dict().get('ip_address') for iface in network_interfaces if getattr(iface, 'ip_address', None)]
    private_prefixes = ('10.', '172.16.', '172.17.', '172.18.', '172.19.', '172.2', '172.30.', '172.31.', '192.168.')
    nat_context = 'Likely NAT/private egress' if any(str(ip).startswith(private_prefixes) for ip in private_addresses) else 'No RFC1918 interface address detected'
    return {
        'public_ip': public_ip,
        'public_ip_error': public_error,
        'nat_context': nat_context,
        'dns_resolvers': resolvers,
        'ipv6_egress': ipv6_default.get('output'),
        'vpn_hints': route_diag.get('vpn_hints', []),
        'proxy_hints': proxy_hints,
        'interface_route_context': interface_route.get('output'),
        'per_interface': [
            {'name': iface.name, 'type': iface.interface_type, 'ip_address': getattr(iface, 'ip_address', None)}
            for iface in network_interfaces
        ],
    }


def run_iperf3_test(mode, host, port, seconds, parse_int, shutil_module, subprocess_module):
    """Run a bounded iperf3 client or one-shot server check."""
    iperf3 = shutil_module.which('iperf3')
    if not iperf3:
        raise ValueError('iperf3 is not installed')
    mode = (mode or 'client').strip().lower()
    port = max(1, min(parse_int(port, 'Port must be an integer'), 65535))
    seconds = max(1, min(parse_int(seconds, 'Seconds must be an integer'), 30))
    if mode == 'client':
        if not host:
            raise ValueError('Host is required for iperf3 client tests')
        command = [iperf3, '-c', host, '-p', str(port), '-t', str(seconds), '-J']
    elif mode == 'server':
        command = [iperf3, '-s', '-1', '-p', str(port), '-J']
    else:
        raise ValueError('Mode must be client or server')
    result = subprocess_module.run(command, capture_output=True, text=True, timeout=seconds + 10, check=False)
    output = (result.stdout or result.stderr or '').strip()
    try:
        parsed = json.loads(output) if output.startswith('{') else {}
    except json.JSONDecodeError:
        parsed = {}
    summary = parsed.get('end', {}).get('sum_received') or parsed.get('end', {}).get('sum_sent') or {}
    return {'command': command, 'returncode': result.returncode, 'summary': summary, 'json': parsed, 'output': output[-2000:]}


def run_snmp_inventory(host, community, version, oid, shutil_module, subprocess_module, record_inventory_devices):
    """Collect authorized SNMP identity/interface metadata using supplied credentials."""
    if not host:
        raise ValueError('SNMP host is required')
    if not community:
        raise ValueError('SNMP community or credential is required')
    snmpwalk = shutil_module.which('snmpwalk')
    if not snmpwalk:
        raise ValueError('snmpwalk is not installed')
    oid_map = {'system': '1.3.6.1.2.1.1', 'interfaces': '1.3.6.1.2.1.2.2.1.2'}
    selected_oid = oid_map.get((oid or 'system').strip().lower(), oid_map['system'])
    command = [snmpwalk, '-v', version or '2c', '-c', community, '-Oqv', host, selected_oid]
    result = subprocess_module.run(command, capture_output=True, text=True, timeout=10, check=False)
    lines = [line.strip().strip('"') for line in (result.stdout or '').splitlines() if line.strip()]
    metadata = {
        'host': host,
        'version': version,
        'oid': selected_oid,
        'values': lines[:50],
        'returncode': result.returncode,
        'error': (result.stderr or '').strip(),
    }
    record_inventory_devices([
        {'ip': host, 'name': lines[0] if lines else host, 'device_type': 'SNMP device', 'service_metadata': metadata}
    ], 'snmp-discovery')
    return metadata


def run_ipv6_assessment(host, ports, run_text_command, shutil_module, socket_module, os_name=os.name):
    """Run bounded IPv6 reachability, route, neighbor, DNS, and TCP checks."""
    host = (host or '').strip()
    ports = [int(port) for port in re.split(r'[,\s]+', ports or '') if port.strip().isdigit()][:10]
    ping = None
    trace = None
    if host:
        ping = run_text_command(['ping', '-6', '-c', '3', host], timeout=8)
        traceroute_tool = shutil_module.which('traceroute6') or shutil_module.which('traceroute')
        if traceroute_tool:
            trace = run_text_command([traceroute_tool, '-6', '-n', '-m', '12', host], timeout=15)
    neighbors = run_text_command(['ip', '-6', 'neigh', 'show'], timeout=5) if os_name != 'nt' else {'output': ''}
    routes = run_text_command(['ip', '-6', 'route', 'show'], timeout=5) if os_name != 'nt' else {'output': ''}
    dns_records = []
    if host:
        try:
            dns_records = sorted({item[4][0] for item in socket_module.getaddrinfo(host, None, socket_module.AF_INET6)})
        except socket_module.gaierror:
            dns_records = []
    port_results = []
    for port in ports:
        status = 'closed'
        try:
            with socket_module.create_connection((host, port, 0, 0), timeout=1):
                status = 'open'
        except OSError:
            status = 'closed'
        port_results.append({'port': port, 'status': status})
    return {
        'host': host,
        'ping': ping,
        'traceroute': trace,
        'neighbors': neighbors.get('output'),
        'router_advertisement_visibility': routes.get('output'),
        'dns_aaaa': dns_records,
        'ports': port_results,
    }
