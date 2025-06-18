from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
import os
import json
import time
import threading
import asyncio

from scripts.interfaceTools import *
from scripts.networkScan import active_scan, passive_scan

app = Flask(__name__)
socketio = SocketIO(app)

# Fetch network interfaces at the start
network_interfaces = get_network_interfaces()
networkTechnologies = {iface.interface_type for iface in network_interfaces}

def poll_interfaces():
    global network_interfaces, networkTechnologies
    while True:
        updated_interfaces = get_network_interfaces()
        if updated_interfaces != network_interfaces:
            network_interfaces = updated_interfaces
            networkTechnologies = {iface.interface_type for iface in network_interfaces}
            socketio.emit('update_interfaces', {'interfaces': [iface.__dict__ for iface in network_interfaces]})
        time.sleep(5)  # Poll every 5 seconds

# Start polling in a separate thread
polling_thread = threading.Thread(target=poll_interfaces, daemon=True)
polling_thread.start()

@app.route('/')
def index():
    return render_template('index.html', title='Home', networkTechnologies=networkTechnologies, interfaces=network_interfaces)

@app.route('/about')
def about():
    return render_template('about.html', title='About', networkTechnologies=networkTechnologies, interfaces=network_interfaces)

@app.route('/contact')
def contact_page():
    return render_template('contact.html', title='Contact', networkTechnologies=networkTechnologies, interfaces=network_interfaces)

@app.route('/submit-contact', methods=['POST'])
def submit_contact():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    message = data.get('message')
    if not name or not email or not message:
        return jsonify({'status': 'error', 'message': 'Missing information'}), 400
    try:
        with open('contact_messages.txt', 'a') as f:
            json.dump({'name': name, 'email': email, 'message': message, 'timestamp': time.time()}, f)
            f.write('\n')
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico')

@app.route('/red-team')
def red_team():
    return render_template('red-team.html', title='Red Team', networkTechnologies=networkTechnologies, interfaces=network_interfaces)

# Endpoint to fetch the current list of network adapters
@app.route('/adapters', methods=['POST'])
def adapters():
    """Return the available network interfaces as JSON."""
    return jsonify({'interfaces': [iface.__dict__ for iface in network_interfaces]})

@app.route('/network-scan')
def network_scan():
    return render_template('network_scan.html', title='Network Scan',
                           networkTechnologies=networkTechnologies,
                           interfaces=network_interfaces)

@app.route('/active-scan', methods=['POST'])
def active_scan_route():
    iface = request.form.get('selectedInterface')
    if not iface:
        return jsonify({'status': 'error', 'message': 'Missing interface'}), 400
    hosts = active_scan(iface)
    return jsonify({'hosts': hosts})

@app.route('/passive-scan', methods=['POST'])
def passive_scan_route():
    iface = request.form.get('selectedInterface')
    if not iface:
        return jsonify({'status': 'error', 'message': 'Missing interface'}), 400
    devices = passive_scan(iface)
    return jsonify({'devices': devices})

@app.route('/<interface_type>')
def interfaces_by_type(interface_type):
    interface_type = interface_type.capitalize()
    filtered_interfaces = [iface for iface in network_interfaces if iface.interface_type.lower() == interface_type.lower()]
    if filtered_interfaces:
        return render_template('interface_type.html', title=f'{interface_type}', interfaces=network_interfaces, filtered_interfaces=filtered_interfaces, networkTechnologies=networkTechnologies, technology=interface_type)
    else:
        return "No interfaces found for this type", 404

@app.route('/<interface_type>/<interface_name>')
def interface_detail(interface_type, interface_name):
    interface_type = interface_type.lower()
    interface = next((iface for iface in network_interfaces if iface.name == interface_name and iface.interface_type.lower() == interface_type), None)
    if interface:
        return render_template('interface_detail.html', title=interface.name, interface=interface, networkTechnologies=networkTechnologies, interfaces=network_interfaces)
    else:
        return "Interface not found", 404


@app.route('/syn-flood', methods=['POST'])
def syn_flood():
    data = request.form
    destination_address = data.get('destinationAddress')
    destination_port = data.get('destinationPort')
    frames = data.get('frames')
    selected_interface = data.get('selectedInterface')

    if not all([destination_address, destination_port, frames, selected_interface]):
        return jsonify({'status': 'error', 'message': 'Missing required parameters'}), 400

    try:
        from scripts.network import networkAttacks
        networkAttacks.synFlood('0.0.0.0', destination_address,
                                1234, int(destination_port),
                                int(frames), selected_interface)
        return jsonify({'status': 'success', 'message': f'DoS successfully on {selected_interface}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'DoS error: {str(e)}'}), 500

@app.route('/syn-flood-broadcast', methods=['POST'])
def syn_flood_broadcast():
    data = request.form
    frames = data.get('frames')
    selected_interface = data.get('selectedInterface')

    if not frames or not selected_interface:
        return jsonify({'status': 'error', 'message': 'Missing required parameters'}), 400

    try:
        from scripts.network import networkAttacks
        networkAttacks.broadcastFlood(int(frames), selected_interface)
        return jsonify({'status': 'success', 'message': f'DoS successfully on {selected_interface}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Broadcast DoS error: {str(e)}'}), 500

@app.route('/wlan-scan', methods=['POST'])
def wlan_scan():
    data = request.form
    selected_interface = data.get('selectedInterface')

    if not selected_interface:
        return jsonify({'status': 'error', 'message': 'Missing selected interface'}), 400

    try:
        from scripts.wifi import utils as wifi_utils
        wifi_utils.scan_networks()
        wlans = wifi_utils.get_networks_summary()
        return jsonify({'status': 'success', 'message': f'Got wlans for {selected_interface}', 'wlans': wlans})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'WLAN scan error: {str(e)}'}), 500

@app.route('/wlan-connect', methods=['POST'])
def wlan_connect():
    data = request.form
    selected_interface = data.get('selectedInterface')
    ssid = data.get('ssid')
    password = data.get('password')

    if not selected_interface or not ssid:
        return jsonify({'status': 'error', 'message': 'Missing required parameters'}), 400

    try:
        from scripts.wifi import utils as wifi_utils
        success = wifi_utils.connect_to_network(ssid, password, selected_interface)
        if success:
            return jsonify({'status': 'success', 'message': f'Connected to {ssid} on {selected_interface}'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to connect'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'WLAN connect error: {str(e)}'}), 500


@app.route('/bluetooth-scan', methods=['POST'])
def bluetooth_scan():
    data = request.form
    selected_interface = data.get('selectedInterface')

    if not selected_interface:
        return jsonify({'status': 'error', 'message': 'Missing selected interface'}), 400

    try:
        devices = asyncio.run(get_bluetooth_devices())
        devices_summary = [{'address': dev.address, 'name': dev.name} for dev in devices]
        return jsonify({'status': 'success', 'devices': devices_summary})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Bluetooth scan error: {str(e)}'}), 500

@app.route('/spoof-mac', methods=['POST'])
def spoof_mac_route():
    data = request.form
    interface = data.get("interface")
    new_mac = data.get("mac")
    if not interface or not new_mac:
        return jsonify({"status": "error", "message": "Missing parameters"}), 400
    success = spoof_mac(interface, new_mac)
    if success:
        return jsonify({"status": "success", "message": "MAC updated"})
    else:
        return jsonify({"status": "error", "message": "Failed to update MAC"}), 500


@app.route('/beacon-advertise', methods=['POST'])
def beacon_advertise():
    data = request.form
    selected_interface = data.get('selectedInterface')
    ssid = data.get('ssid')
    frames = data.get('frames')
    src_mac = data.get('srcMac') or '22:22:22:22:22:22'
    bssid = data.get('bssid') or '33:33:33:33:33:33'

    if not selected_interface or not ssid or not frames:
        return jsonify({'status': 'error', 'message': 'Missing required parameters'}), 400

    try:
        frames = int(frames)
    except ValueError:
        return jsonify({'status': 'error', 'message': 'Frames must be an integer'}), 400

    try:
        from scripts.wifi.beaconspoof import beaconSpoof
        beaconSpoof(ssid, selected_interface, frames, src=src_mac, bssid=bssid)
        return jsonify({'status': 'success', 'message': f'Advertising {ssid} via {selected_interface}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Beacon advertise error: {str(e)}'}), 500


if __name__ == '__main__':
    host = '0.0.0.0'
    port = 8080
    print(f"Server running at http://{host}:{port}")
    socketio.run(app, host=host, port=port, debug=True)
