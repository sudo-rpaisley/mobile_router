"""Wireless, Bluetooth, adapter state, and interface-detail routes."""

from functools import wraps


def register_interface_routes(app, context_provider):
    globals().update(context_provider())

    def _refresh_context(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            globals().update(context_provider())
            return view(*args, **kwargs)
        return wrapped

    @app.route('/wireless/network/label', methods=['POST'])
    @_refresh_context
    def wireless_network_client_label_route():
        """Save an SSID-scoped custom label for a network client card."""
        interface = request.form.get('interface')
        ssid = request.form.get('ssid')
        bssid = request.form.get('bssid')
        identity = request.form.get('identity') or request.form.get('ip') or request.form.get('mac')
        label = (request.form.get('label') or '').strip()[:80]
        if not interface or not ssid or not identity:
            return json_error('Interface, SSID, and client identity are required')
        key = wireless_network_client_label_key(interface, ssid, bssid, identity)
        if label:
            wireless_network_labels[key] = label
        else:
            wireless_network_labels.pop(key, None)
        save_runtime_state('wireless-label')
        return json_success(label=label, message='Network client label saved.')

    @app.route('/wireless/network/clients.json')
    @_refresh_context
    def wireless_network_clients_json():
        """Return the persisted Wi-Fi network device list for in-page refreshes."""
        from scripts.wifi import utils as wifi_utils
        network = wifi_utils.get_network_detail(ssid=request.args.get('ssid'), bssid=request.args.get('bssid'), interface_name=request.args.get('interface'))
        network = merge_wireless_network_clients(network)
        return json_success(
            clients=network.get('clients', []),
            disappeared_clients=network.get('disappeared_clients', []),
            client_count=network.get('client_count', 0),
        )

    @app.route('/wireless/network/clients.csv')
    @_refresh_context
    def wireless_network_clients_export():
        """Export the persisted Wi-Fi network device list as CSV."""
        from scripts.wifi import utils as wifi_utils
        network = wifi_utils.get_network_detail(ssid=request.args.get('ssid'), bssid=request.args.get('bssid'), interface_name=request.args.get('interface'))
        network = merge_wireless_network_clients(network)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=['display_name', 'ip', 'mac', 'manufacturer', 'tags', 'notes', 'open_ports', 'open_port_details_json', 'first_seen', 'last_seen', 'state'])
        writer.writeheader()
        for client in network.get('clients', []) + network.get('disappeared_clients', []):
            writer.writerow({
                'display_name': client.get('display_name'),
                'ip': client.get('ip'),
                'mac': client.get('mac'),
                'manufacturer': client.get('manufacturer'),
                'tags': ', '.join(client.get('client_tags') or []),
                'notes': client.get('client_notes') or '',
                'open_ports': ', '.join(str(item.get('port')) for item in client.get('open_port_details') or []),
                'open_port_details_json': json.dumps(client.get('open_port_details') or []),
                'first_seen': client.get('network_first_seen'),
                'last_seen': client.get('network_last_seen'),
                'state': 'disappeared' if client in network.get('disappeared_clients', []) else 'visible',
            })
        filename = secure_filename(f"{network.get('ssid') or 'wireless-network'}-clients.csv")
        return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename="{filename}"'})

    @app.route('/wireless/network')
    @_refresh_context
    def wireless_network_detail():
        ssid = request.args.get('ssid')
        bssid = request.args.get('bssid')
        selected_interface = request.args.get('interface')

        if not ssid and not bssid:
            return "Wireless network not specified", 400

        from scripts.wifi import utils as wifi_utils
        network = wifi_utils.get_network_detail(ssid=ssid, bssid=bssid, interface_name=selected_interface)
        network = merge_wireless_network_clients(network)
        back_url = f"/wireless/{selected_interface}" if selected_interface else "/wireless"
        return render_template(
            'wireless_network_detail.html',
            title=f"{network['ssid']} Details",
            network=network,
            back_url=back_url,
            **current_context(),
        )

    @app.route('/interfaces/<interface_name>/state', methods=['POST'])
    @_refresh_context
    def interface_power_state(interface_name):
        desired_state = request.form.get('state')
        interface = next((iface for iface in network_interfaces if iface.name == interface_name), None)
        try:
            message = set_interface_power_state(
                interface_name,
                desired_state,
                getattr(interface, 'interface_type', None),
            )
            return json_success(message=message)
        except ValueError as exc:
            return json_error(str(exc), 400)
        except Exception as exc:
            return json_error(f'Interface power error: {exc}', 500)

    @app.route('/<interface_type>')
    @_refresh_context
    def interfaces_by_type(interface_type):
        requested_type = interface_type.lower()
        filtered_interfaces = [iface for iface in network_interfaces if iface.interface_type.lower() == requested_type]
        if filtered_interfaces:
            display_type = filtered_interfaces[0].interface_type
            return render_template('interface_type.html', title=display_type, filtered_interfaces=filtered_interfaces, technology=display_type, **current_context())
        else:
            return "No interfaces found for this type", 404

    @app.route('/<interface_type>/<interface_name>')
    @_refresh_context
    def interface_detail(interface_type, interface_name):
        interface_type = interface_type.lower()
        interface = next((iface for iface in network_interfaces if iface.name == interface_name and iface.interface_type.lower() == interface_type), None)
        if interface:
            return render_template(
                'interface_detail.html',
                title=interface.name,
                interface=interface,
                **current_context(),
                **(bluetooth_phone_card_context() if interface.interface_type == 'Bluetooth' else {}),
            )
        else:
            return "Interface not found", 404

    @app.route('/wlan-modes', methods=['GET'])
    @_refresh_context
    def wlan_modes():
        selected_interface = request.args.get('selectedInterface')

        if not selected_interface:
            return json_error('Missing selected interface')

        try:
            from scripts.wifi import utils as wifi_utils
            return json_success(**wifi_utils.get_adapter_modes(selected_interface))
        except Exception as e:
            return json_error(f'WLAN mode error: {str(e)}', 500)

    @app.route('/wlan-mode', methods=['POST'])
    @_refresh_context
    def wlan_mode():
        data = request.form
        selected_interface = data.get('selectedInterface')
        mode = data.get('mode')

        if not selected_interface or not mode:
            return json_error('Missing required parameters')

        try:
            from scripts.wifi import utils as wifi_utils
            return json_success(**wifi_utils.set_adapter_mode(selected_interface, mode))
        except ValueError as e:
            return json_error(str(e))
        except Exception as e:
            return json_error(f'WLAN mode error: {str(e)}', 500)

    @app.route('/scan-jobs', methods=['POST'])
    @_refresh_context
    def start_scan_job():
        data = request.form
        try:
            job = create_scan_job(data.get('scanType'), data.get('selectedInterface'))
            return json_success(job=job)
        except ValueError as e:
            return json_error(str(e))

    @app.route('/scan-jobs/<job_id>')
    @_refresh_context
    def scan_job_status(job_id):
        with scan_jobs_lock:
            job = scan_jobs.get(job_id)
            if not job:
                return json_error('Scan job not found', 404)
            return json_success(job=_scan_job_snapshot(job))

    @app.route('/wlan-scan', methods=['POST'])
    @_refresh_context
    def wlan_scan():
        data = request.form
        selected_interface = data.get('selectedInterface')

        if not selected_interface:
            return json_error('Missing selected interface')

        try:
            from scripts.wifi import utils as wifi_utils
            wifi_utils.scan_networks(selected_interface)
            wlans = wifi_utils.get_networks_summary()
            return json_success(message=f'Got wlans for {selected_interface}', wlans=wlans)
        except Exception as e:
            return json_error(f'WLAN scan error: {str(e)}', 500)

    @app.route('/wlan-connect', methods=['POST'])
    @_refresh_context
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
    @_refresh_context
    def bluetooth_scan():
        data = request.form
        selected_interface = data.get('selectedInterface')

        if not selected_interface:
            return json_error('Missing selected interface')

        try:
            devices = asyncio.run(get_bluetooth_devices())
            devices_summary = [bluetooth_device_summary(dev) for dev in devices]
            return json_success(devices=devices_summary, action_capability=bluetooth_action_capability())
        except Exception as e:
            return json_error(f'Bluetooth scan error: {str(e)}', 500)

    @app.route('/bluetooth-action', methods=['POST'])
    @_refresh_context
    def bluetooth_action():
        data = request.form
        action = data.get('action')
        address = data.get('address')
        adapter = data.get('adapter')

        try:
            output = run_bluetoothctl_action(action, address, adapter=adapter)
            updates = _bluetooth_state_updates_for_action(action)
            if action == 'info':
                updates.update(_parse_bluetooth_info_output(output))
            device = _merge_inventory_device_state(address, updates) if updates else find_inventory_device(address)
            history = record_bluetooth_action_history(address, action, 'success', output or 'Action completed.', adapter=adapter)
            return json_success(message='Bluetooth action completed', output=output, history=history, actions=bluetooth_contextual_actions(device), device_state=bluetooth_device_state(device))
        except ValueError as e:
            history = record_bluetooth_action_history(address, action, 'error', str(e), adapter=adapter)
            return json_error(str(e), history=history)
        except BluetoothToolUnavailable as e:
            history = record_bluetooth_action_history(address, action, 'error', str(e), adapter=adapter)
            return json_error(str(e), 501, history=history)
        except Exception as e:
            message = f'Bluetooth action error: {str(e)}'
            history = record_bluetooth_action_history(address, action, 'error', message, adapter=adapter)
            return json_error(message, 500, history=history)

    @app.route('/bluetooth-device/<address>/refresh', methods=['POST'])
    @_refresh_context
    def bluetooth_device_refresh(address):
        try:
            output = run_bluetoothctl_action('info', address, adapter=request.form.get('adapter'))
            device = _merge_inventory_device_state(address, _parse_bluetooth_info_output(output))
            history = record_bluetooth_action_history(address, 'refresh', 'success', output or 'Device info refreshed.', adapter=request.form.get('adapter'))
            return json_success(message='Bluetooth device refreshed', output=output, device=device, history=history, actions=bluetooth_contextual_actions(device), device_state=bluetooth_device_state(device))
        except ValueError as e:
            history = record_bluetooth_action_history(address, 'refresh', 'error', str(e), adapter=request.form.get('adapter'))
            return json_error(str(e), history=history)
        except BluetoothToolUnavailable as e:
            history = record_bluetooth_action_history(address, 'refresh', 'error', str(e), adapter=request.form.get('adapter'))
            return json_error(str(e), 501, history=history)
        except Exception as e:
            message = f'Bluetooth refresh error: {str(e)}'
            history = record_bluetooth_action_history(address, 'refresh', 'error', message, adapter=request.form.get('adapter'))
            return json_error(message, 500, history=history)

    return {
        'wireless_network_client_label_route': wireless_network_client_label_route,
        'wireless_network_clients_json': wireless_network_clients_json,
        'wireless_network_clients_export': wireless_network_clients_export,
        'wireless_network_detail': wireless_network_detail,
        'interface_power_state': interface_power_state,
        'interfaces_by_type': interfaces_by_type,
        'interface_detail': interface_detail,
        'wlan_modes': wlan_modes,
        'wlan_mode': wlan_mode,
        'start_scan_job': start_scan_job,
        'scan_job_status': scan_job_status,
        'wlan_scan': wlan_scan,
        'wlan_connect': wlan_connect,
        'bluetooth_scan': bluetooth_scan,
        'bluetooth_action': bluetooth_action,
        'bluetooth_device_refresh': bluetooth_device_refresh
    }
