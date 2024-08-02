from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
import os
import json
import time
import threading

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

# Start polling in a separate thread
polling_thread = threading.Thread(target=poll_interfaces, daemon=True)
polling_thread.start()

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
    print(f"Looking for interfaces of type: {interface_type}")
    filtered_interfaces = [iface for iface in network_interfaces if iface.interface_type.lower() == interface_type.lower()]
    print(f"Filtered interfaces: {filtered_interfaces}")
    if filtered_interfaces:
        return render_template('interface_type.html', title=f'{interface_type}', interfaces=filtered_interfaces, networkTechnologies=networkTechnologies, technology=interface_type)
    else:
        return "No interfaces found for this type", 404

@app.route('/<interface_type>/<interface_name>')
def interface_detail(interface_type, interface_name):
    interface_type = interface_type.lower()
    print(f"Looking for interface of type: {interface_type} with name: {interface_name}")
    interface = next((iface for iface in network_interfaces if iface.name == interface_name and iface.interface_type.lower() == interface_type), None)
    if interface:
        return render_template('interface_detail.html', title=interface.name, interface=interface, networkTechnologies=networkTechnologies, interfaces=network_interfaces)
    else:
        print(f"Interface not found: {interface_type}/{interface_name}")
        return render_template('error.html', error_code=404, error_name="Interface Not Found", error_description=f"The interface '{interface_name}' of type '{interface_type}' was not found."), 404

# Custom error handler for 404
@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', error_code=404, error_name="Page Not Found", error_description="Sorry, but the page you were trying to view does not exist."), 404

# Custom error handler for 500
@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error.html', error_code=500, error_name="Internal Server Error", error_description="Sorry, but something went wrong on our end. Please try again later."), 500

@app.errorhandler(Exception)
def handle_exception(e):
    # Generic error handler for all other exceptions
    return render_template('error.html', error_code=500, error_name="Internal Server Error", error_description=str(e)), 500

if __name__ == '__main__':
    host='0.0.0.0'
    port=8080
    socketio.run(app, host=host, port=port, debug=True)

