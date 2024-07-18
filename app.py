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
    return render_template('index.html', title='Home') #, interfaces=interfaces, network_technologies=network_technologies, technology_map=technology_map)

@app.route('/about')
def about():
    return render_template('about.html', title='About')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico')


@app.route('/red-team')
def red_team():
    # interfaces, _ = get_adapters()
    return render_template('red-team.html', title='Red Team') #, interfaces=interfaces)

@app.route('/<interface_type>/<interface_name>')
def interface_detail(interface_type, interface_name):
    interface = next((iface for iface in network_interfaces if iface.name == interface_name and iface.interface_type == interface_type), None)
    if interface:
        return render_template('interface_detail.html', title=f'{interface_type} - {interface_name}', interface=interface)
    else:
        return "Interface not found", 404

# @app.route('/<network_technology>')
# def technology(network_technology):
#     interfaces, _ = get_adapters()
#     technology_key = next((key for key, value in technology_map.items() if value == network_technology), None)
#     if not technology_key:
#         return render_template('404-Error.html', title='404: Technology not found', interfaces=interfaces, message=f'Technology ({network_technology}) not found')

#     specific_interfaces = [intf for intf in interfaces if intf['networkTechnology'] == technology_key]
#     if specific_interfaces:
#         return render_template('technology.html', title=network_technology, filtered_interfaces=specific_interfaces, technology=technology_key)
#     else:
#         return render_template('404-Error.html', title='404: Technology not found', interfaces=interfaces, message=f'Technology ({network_technology}) not found')

# @app.route('/<network_technology>/<name>')
# def interface(network_technology, name):
#     interfaces, _ = get_adapters()
#     technology_key = next((key for key, value in technology_map.items() if value == network_technology), None)
#     specific_interface = next((intf for intf in interfaces if intf['ifname'] == name and intf['networkTechnology'] == technology_key), None)

#     if specific_interface:
#         return render_template('interface.html', title=specific_interface['ifname'], interface=specific_interface)
#     else:
#         return render_template('404-Error.html', title='404: Interface not found', interfaces=interfaces, message=f'Interface {name} not found')

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
    
    get_network_interfaces()
    app.run(host=host, port=port)


