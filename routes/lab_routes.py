"""Authorised network and wireless laboratory action routes."""

from functools import wraps


def register_lab_routes(app, context_provider):
    globals().update(context_provider())

    def _refresh_context(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            globals().update(context_provider())
            return view(*args, **kwargs)
        return wrapped

    @app.route('/syn-flood', methods=['POST'])
    @_refresh_context
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
    @_refresh_context
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

    @app.route('/spoof-mac', methods=['POST'])
    @_refresh_context
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
    @_refresh_context
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
    @_refresh_context
    def deauth_route():
        data = request.form
        selected_interface = data.get('selectedInterface')

        if missing_fields(data, 'selectedInterface', 'ap', 'frames'):
            return json_error('Missing required parameters')

        try:
            ap_mac, target_mac, frames = labs_service.validate_deauth_request(data, normalize_mac, parse_int)
        except ValueError as e:
            return json_error(str(e))

        try:
            from scripts.wifi.deauth import deauth
            deauth(ap_mac, target_mac, selected_interface, frames)
            return json_success(message=f'Sent {frames} authorized lab deauth frames on {selected_interface}')
        except Exception as e:
            return json_error(f'Deauth error: {str(e)}', 500)

    @app.route('/evil-twin-lab', methods=['POST'])
    @_refresh_context
    def evil_twin_lab_route():
        data = request.form
        selected_interface = data.get('selectedInterface')

        if missing_fields(data, 'selectedInterface', 'ssid', 'bssid', 'channel'):
            return json_error('Missing required parameters')

        try:
            lab = labs_service.validate_evil_twin_request(data, normalize_mac, parse_int)
            run = labs_service.record_evil_twin_run(selected_interface, lab, evil_twin_lab_runs, evil_twin_lab_lock, save_runtime_state, app.logger)
        except ValueError as e:
            return json_error(str(e))

        action_messages = {
            'plan': 'Prepared evil twin and captive portal lab plan; no radio services were started by Mobile Router.',
            'start': 'Logged authorized evil twin lab start checklist; run AP services only in your isolated lab environment.',
            'cleanup': 'Logged evil twin lab cleanup checklist; verify rogue AP, DHCP, DNS, and portal services are stopped.',
        }
        return json_success(message=action_messages[run['action']], run=run)

    @app.route('/pineap-lab', methods=['POST'])
    @_refresh_context
    def pineap_lab_route():
        data = request.form
        selected_interface = data.get('selectedInterface')
        if missing_fields(data, 'selectedInterface'):
            return json_error('Missing required parameters')
        try:
            lab = labs_service.validate_pineap_request(data, normalize_mac, parse_int)
            from scripts.wifi import utils as wifi_utils
            run = labs_service.build_pineap_result(selected_interface, lab, pineap_lab_runs, pineap_lab_lock, save_runtime_state, app.logger, wifi_utils)
        except ValueError as e:
            return json_error(str(e))
        except Exception as e:
            return json_error(f'PineAP-style lab error: {str(e)}', 500)
        return json_success(message=f"Recorded {run['action']} workflow with {len(run['module_status'])} module(s).", run=run)

    @app.route('/handshake-lab', methods=['POST'])
    @_refresh_context
    def handshake_lab_route():
        data = request.form
        selected_interface = data.get('selectedInterface')
        if missing_fields(data, 'selectedInterface', 'ssid', 'bssid', 'channel'):
            return json_error('Missing required parameters')
        try:
            lab = labs_service.validate_handshake_request(data, normalize_mac, parse_int)
            record = labs_service.record_handshake_evidence(selected_interface, lab, request.files.get('capture'), create_evidence_record, handshake_lab_records, handshake_lab_lock, save_runtime_state, app.logger)
        except ValueError as e:
            return json_error(str(e))
        return json_success(message='Cataloged WPA handshake/PMKID lab evidence for validation and export.', record=record)

    @app.route('/handshake-lab.<fmt>')
    @_refresh_context
    def export_handshake_lab(fmt):
        records = labs_service.export_handshake_records(handshake_lab_records, handshake_lab_lock)
        if fmt == 'json':
            return jsonify({'handshakes': records, 'exported_at': time.time()})
        if fmt == 'csv':
            return Response(labs_service.handshake_records_csv(records), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=handshake-lab.csv'})
        return json_error('Unsupported handshake export format', 404)

    @app.route('/aireplay-deauth', methods=['POST'])
    @_refresh_context
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

    return {
        'syn_flood': syn_flood,
        'syn_flood_broadcast': syn_flood_broadcast,
        'spoof_mac_route': spoof_mac_route,
        'beacon_advertise': beacon_advertise,
        'deauth_route': deauth_route,
        'evil_twin_lab_route': evil_twin_lab_route,
        'pineap_lab_route': pineap_lab_route,
        'handshake_lab_route': handshake_lab_route,
        'export_handshake_lab': export_handshake_lab,
        'aireplay_deauth_route': aireplay_deauth_route
    }
