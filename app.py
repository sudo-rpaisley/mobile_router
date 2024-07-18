from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
import os
import json

from scripts.interfaceTools import *

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

@app.route('/')
def index():
    return render_template('index.html', title='Home', networkTechnologies=networkTechnologies, interfaces=network_interfaces)

@app.route('/about')
def about():
    return render_template('about.html', title='About')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico')

@app.route('/red-team')
def red_team():
    return render_template('red-team.html', title='Red Team', networkTechnologies=networkTechnologies, interfaces=network_interfaces)

@app.route('/<interface_type>')
def interfaces_by_type(interface_type):
    interface_type = interface_type.capitalize()
    filtered_interfaces = [iface for iface in network_interfaces if iface.interface_type.lower() == interface_type.lower()]
    if filtered_interfaces:
        return render_template('interface_type.html', title=f'{interface_type}', interfaces=filtered_interfaces, networkTechnologies=networkTechnologies, technology=interface_type)
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


# @app.route('/syn-flood', methods=['POST'])
# def syn_flood():
#     data = request.form
#     destination_address = data.get('destinationAddress')
#     destination_port = data.get('destinationPort')
#     frames = data.get('frames')
#     selected_interface = data.get('selectedInterface')
#     try:
#         # Implement your DoS attack logic here
#         return jsonify({'status': 'success', 'message': f'DoS successfully on {selected_interface}'})
#     except Exception as e:
#         return jsonify({'status': 'error', 'message': f'DoS error: {str(e)}'})

# @app.route('/syn-flood-broadcast', methods=['POST'])
# def syn_flood_broadcast():
#     data = request.form
#     frames = data.get('frames')
#     selected_interface = data.get('selectedInterface')
#     try:
#         # Implement your DoS broadcast logic here
#         return jsonify({'status': 'success', 'message': f'DoS successfully on {selected_interface}'})
#     except Exception as e:
#         return jsonify({'status': 'error', 'message': f'Broadcast DoS error: {str(e)}'})

# @app.route('/wlan-scan', methods=['POST'])
# def wlan_scan():
#     data = request.form
#     selected_interface = data.get('selectedInterface')
#     try:
#         # Implement your WLAN scan logic here
#         wlans = [{'ssid': 'example_ssid', 'bssid': '00:1A:2B:3C:4D:5E'}]
#         return jsonify({'status': 'success', 'message': f'Got wlans for {selected_interface}', 'wlans': wlans})
#     except Exception as e:
#         return jsonify({'status': 'error', 'message': f'WLAN scan error: {str(e)}'})

# @app.route('/wlan-connect', methods=['POST'])
# def wlan_connect():
#     data = request.form
#     selected_interface = data.get('selectedInterface')
#     ssid = data.get('ssid')
#     password = data.get('password')
#     try:
#         # Implement your WLAN connect logic here
#         return jsonify({'status': 'success', 'message': f'Connected to {ssid} on {selected_interface}'})
#     except Exception as e:
#         return jsonify({'status': 'error', 'message': f'WLAN connect error: {str(e)}'})


if __name__ == '__main__':
    host='127.0.0.1'
    port=8080
    app.run(host=host, port=port, debug=True)
