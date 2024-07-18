from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import json

from scripts.interfaceTools import *

app = Flask(__name__)

# # Define your technologyMap here:
# technology_map = {
#     'Wi-Fi': 'Wireless',
#     'Ethernet': 'Wired',
#     'Bluetooth': 'Bluetooth',
#     'Loopback': 'Loopback',
#     # Other mappings as necessary
# }

# def get_adapters():
#     interfaces = [
#         {'ifname': 'eth0', 'networkTechnology': 'Ethernet', 'address': '00:1A:2B:3C:4D:5E'},
#         {'ifname': 'wlan0', 'networkTechnology': 'Wi-Fi', 'address': '00:1A:2B:3C:4D:5F'},
#         # Add more interfaces as needed
#     ]
#     network_technologies = list({iface['networkTechnology'] for iface in interfaces})
#     return interfaces, network_technologies

@app.route('/')
def index():
    # interfaces, network_technologies = get_adapters()
    return render_template('index.html', title='Home') #, interfaces=interfaces, network_technologies=network_technologies, technology_map=technology_map

@app.route('/about')
def about():
    return render_template('about.html', title='About')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico')



@app.route('/red-team')
def red_team():
    return render_template('red-team.html', title='Red Team') 



@app.route('/<interface_type>/<interface_name>')
def interface_detail(interface_type, interface_name):
    interface_type = interface_type.lower()
    interface = next((iface for iface in network_interfaces if iface.name == interface_name and iface.interface_type.lower() == interface_type), None)
    if interface:
        return render_template('interface_detail.html', title=f'{interface_type.capitalize()} - {interface_name}', interface=interface)
    else:
        return "Interface not found", 404

@app.route('/<interface_type>')
def interfaces_by_type(interface_type):
    interface_type = interface_type.lower()
    filtered_interfaces = [iface for iface in network_interfaces if iface.interface_type.lower() == interface_type]
    if filtered_interfaces:
        return render_template('interface_type.html', title=f'{interface_type.capitalize()} Interfaces', interfaces=filtered_interfaces)
    else:
        return "No interfaces found for this type", 404


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
    
    network_interfaces = get_network_interfaces()
    app.run(host=host, port=port, debug=True)


