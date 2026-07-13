from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO
import os
import json
import time
import threading
import asyncio
import re

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
    get_mac_by_ip,
    get_ip_by_mac,
)


app = Flask(__name__)
log_path = configure_logging(app)
socketio = SocketIO(app)

# Fetch network interfaces at the start
network_interfaces = get_network_interfaces()
networkTechnologies = {iface.interface_type for iface in network_interfaces}


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


register_blueprints(app, current_context)


# Endpoint to fetch the current list of network adapters
@app.route('/adapters', methods=['POST'])
def adapters():
    """Return the available network interfaces as JSON."""
    return jsonify({'interfaces': [iface.to_dict() for iface in network_interfaces]})


@app.route('/network-scan')
def network_scan():
    return render_template('network_scan.html', title='Network Scan', **current_context())


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
    hosts = active_scan(iface)
    return jsonify({'hosts': hosts})


@app.route('/passive-scan', methods=['POST'])
def passive_scan_route():
    iface = request.form.get('selectedInterface')
    if not iface:
        return json_error('Missing interface')
    devices = passive_scan(iface)
    return jsonify({'devices': devices})


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


@app.route('/traceroute', methods=['POST'])
def traceroute_route():
    host = request.form.get('host')
    if not host:
        return json_error('Missing host')
    from scripts.traceroute import traceroute
    hops = traceroute(host)
    return jsonify({'hops': hops})


@app.route('/<interface_type>')
def interfaces_by_type(interface_type):
    interface_type = interface_type.capitalize()
    filtered_interfaces = [iface for iface in network_interfaces if iface.interface_type.lower() == interface_type.lower()]
    if filtered_interfaces:
        return render_template('interface_type.html', title=f'{interface_type}', filtered_interfaces=filtered_interfaces, technology=interface_type, **current_context())
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


@app.route('/wlan-scan', methods=['POST'])
def wlan_scan():
    data = request.form
    selected_interface = data.get('selectedInterface')

    if not selected_interface:
        return json_error('Missing selected interface')

    try:
        from scripts.wifi import utils as wifi_utils
        wifi_utils.scan_networks()
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
        devices_summary = [{'address': dev.address, 'name': dev.name} for dev in devices]
        return json_success(devices=devices_summary)
    except Exception as e:
        return json_error(f'Bluetooth scan error: {str(e)}', 500)


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
    ap_mac = data.get('ap')
    target_mac = data.get('target') or 'ff:ff:ff:ff:ff:ff'

    if missing_fields(data, 'selectedInterface', 'ap', 'frames'):
        return json_error('Missing required parameters')

    try:
        frames = parse_int(data.get('frames'), 'Frames must be an integer')
    except ValueError as e:
        return json_error(str(e))

    try:
        from scripts.wifi.deauth import deauth
        deauth(ap_mac, target_mac, selected_interface, frames)
        return json_success(message=f'Sent {frames} deauth frames on {selected_interface}')
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
