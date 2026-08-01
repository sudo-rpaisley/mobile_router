"""Inventory, client intelligence, alerts, and scan-result routes."""

from app_support.context import bind_context


def register_client_routes(app, context_provider):
    _refresh_context = bind_context(globals(), context_provider)

    @app.route('/inventory')
    @_refresh_context
    def inventory_page(import_result=None):
        records = inventory_records()
        return render_template(
            'inventory.html',
            title='Device Inventory',
            devices=records,
            insights=manufacturer_insights(records),
            import_result=import_result,
            **current_context(),
        )

    @app.route('/inventory/export.json')
    @_refresh_context
    def inventory_export_json():
        return jsonify(inventory_export_payload())

    @app.route('/inventory/import', methods=['POST'])
    @_refresh_context
    def inventory_import_route():
        artifact = request.files.get('inventoryFile')
        try:
            if artifact and artifact.filename:
                payload = json.load(artifact.stream)
            else:
                payload = request.get_json(silent=True) or json.loads(request.form.get('inventoryJson') or '{}')
            result = import_inventory_payload(payload)
        except (ValueError, json.JSONDecodeError) as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return json_error(str(e))
            return inventory_page(import_result={'status': 'error', 'message': str(e)})
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return json_success(**result)
        return inventory_page(import_result={'status': 'success', **result})

    @app.route('/alerts')
    @_refresh_context
    def alerts_page():
        return render_template('alerts.html', title='Alerts', alerts=alert_records(), **current_context())

    @app.route('/alerts/status')
    @_refresh_context
    def alerts_status():
        alerts = alert_records()
        return json_success(alerts=alerts, unread_count=len([alert for alert in alerts if not alert.get('read')]))

    @app.route('/alerts/<alert_id>/read', methods=['POST'])
    @_refresh_context
    def mark_alert_read(alert_id):
        alert, unread_count = alerts_service.mark_alert_read(alert_id, new_device_alerts, new_device_alerts_lock)
        if alert:
            return json_success(alert=alert, unread_count=unread_count)
        return json_error('Alert not found', 404)

    @app.route('/alerts/read-all', methods=['POST'])
    @_refresh_context
    def mark_all_alerts_read():
        return json_success(unread_count=alerts_service.mark_all_alerts_read(new_device_alerts, new_device_alerts_lock))

    @app.route('/http-previews/<path:filename>')
    @_refresh_context
    def http_preview_file(filename):
        """Serve locally captured HTTP preview thumbnails."""
        return send_from_directory(HTTP_PREVIEW_DIR, filename)

    @app.route('/clients/<identifier>/services/<int:port>')
    @_refresh_context
    def client_service_detail(identifier, port):
        """Show a focused saved-service detail page for an IP client port."""
        device = enrich_ip_client_display_name(identifier, find_inventory_device(identifier) or {})
        host = device.get('ip') or identifier
        service = next((dict(item) for item in device.get('open_port_details', []) if int(item.get('port') or 0) == int(port)), None)
        if not service:
            return render_template('service_detail.html', title='Service not found', host=host, port=port, service=None, device=device, **current_context()), 404
        return render_template('service_detail.html', title=f"{host}:{port} Service", host=host, port=port, service=service, device=device, **current_context())

    @app.route('/clients/<identifier>')
    @_refresh_context
    def client_detail(identifier):
        """Display details for a client identified by MAC or IP address."""
        mac_re = re.compile(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$')
        inventory_device = find_inventory_device(identifier)

        mac = None
        ip = None

        if mac_re.match(identifier):
            mac = normalize_mac(identifier)
            ip = (inventory_device or {}).get('ip') or get_ip_by_mac(mac)
        else:
            ip = identifier
            mac = (inventory_device or {}).get('mac') or get_mac_by_ip(ip)

        sources = set((inventory_device or {}).get('sources', []))
        device_type = str((inventory_device or {}).get('device_type') or '').casefold()
        is_bluetooth = 'bluetooth-scan' in sources or 'bluetooth' in device_type
        if is_bluetooth:
            ip = None

        display_name = (
            (inventory_device or {}).get('name')
            or (inventory_device or {}).get('display_name')
            or mac
            or ip
            or identifier
        )
        if not is_bluetooth and ip:
            inventory_device = enrich_ip_client_display_name(ip, inventory_device)
            mac = (inventory_device or {}).get('mac') or mac

        manufacturer = (inventory_device or {}).get('manufacturer')
        if not manufacturer or str(manufacturer).casefold() == 'unknown':
            manufacturer = lookup_manufacturer(mac)
        display_name = display_name_for_inventory_device(inventory_device or {}, mac or ip or identifier)

        last_port_scan = None if is_bluetooth else (inventory_device or {}).get('last_port_scan')
        health_summary = None if is_bluetooth else client_health_summary(inventory_device or {}, ip)
        timeline = [] if is_bluetooth else client_timeline(ip or mac or identifier, inventory_device)
        watched = False if is_bluetooth else is_client_watched(ip or identifier)
        reachability = [] if is_bluetooth else client_reachability_history(ip or identifier)
        baseline_diff = None if is_bluetooth else client_baseline_diff(inventory_device or {})
        relationship_map = None if is_bluetooth else client_relationship_map(ip or identifier)
        scheduled_check = None if is_bluetooth else scheduled_client_checks.get(ip or identifier)

        return render_template(
            'client_detail.html',
            title=f'Client {display_name}',
            ip=ip,
            mac=mac,
            manufacturer=manufacturer,
            display_name=display_name,
            is_bluetooth=is_bluetooth,
            display_name_source=(inventory_device or {}).get('display_name_source'),
            inventory_device=inventory_device or {},
            open_port_details=[] if is_bluetooth else (inventory_device or {}).get('open_port_details', []),
            open_ports=[] if is_bluetooth else (inventory_device or {}).get('open_ports', []),
            last_port_scan_label=(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_port_scan))
                if last_port_scan
                else None
            ),
            health_summary=health_summary,
            client_timeline=timeline,
            watched_client=watched,
            reachability_history=reachability,
            baseline_diff=baseline_diff,
            relationship_map=relationship_map,
            scheduled_check=scheduled_check,
            bluetooth_fields=bluetooth_detail_fields(inventory_device) if is_bluetooth else [],
            bluetooth_action_capability=bluetooth_action_capability() if is_bluetooth else None,
            bluetooth_actions=bluetooth_contextual_actions(inventory_device) if is_bluetooth else [],
            bluetooth_adapters=bluetooth_adapter_choices() if is_bluetooth else [],
            bluetooth_action_history=bluetooth_action_history(mac) if is_bluetooth else [],
            **current_context(),
        )

    @app.route('/clients/<identifier>/watch', methods=['POST'])
    @_refresh_context
    def watch_client(identifier):
        """Toggle watch notifications for an IP client."""
        watch = request.form.get('watch', 'on') == 'on'
        target = str(identifier or '').strip()
        if not target:
            return json_error('Missing client identifier')
        if watch:
            watched_clients.add(target)
            append_client_timeline_event(target, 'Watch enabled', 'This client will create alerts for notable profile changes.', 'client-watch')
            save_runtime_state('client-watch')
            return json_success(watched=True, message='Client watch enabled.')
        watched_clients.discard(target)
        append_client_timeline_event(target, 'Watch disabled', 'Client watch notifications were disabled.', 'client-watch')
        save_runtime_state('client-watch')
        return json_success(watched=False, message='Client watch disabled.')

    @app.route('/clients/<identifier>/http-inspect', methods=['POST'])
    @_refresh_context
    def client_http_inspect(identifier):
        """Inspect saved or supplied HTTP-like services for an IP client."""
        inventory_device = find_inventory_device(identifier) or {}
        host = inventory_device.get('ip') or identifier
        raw_ports = request.form.get('ports')
        try:
            if raw_ports:
                candidates = [parse_int(item.strip(), 'Ports must be integers') for item in raw_ports.split(',') if item.strip()]
            else:
                http_names = ('http', 'https', 'web', 'proxy')
                candidates = [
                    item['port'] for item in inventory_device.get('open_port_details', [])
                    if any(name in str(item.get('service', '')).lower() for name in http_names) or item.get('port') in (80, 443, 8080, 8443, 8000, 9443)
                ]
        except ValueError as e:
            return json_error(str(e))
        candidates = sorted(set(port for port in candidates if 1 <= port <= 65535))[:8]
        if not candidates:
            return json_error('No HTTP-like saved ports are available for this client. Run a port scan first or supply ports.', 400)
        results = inspect_http_services(host, candidates)
        append_client_timeline_event(host, 'HTTP inspected', f"Inspected {len(results)} web service candidate(s).", 'http-inspector')
        return json_success(results=results)

    @app.route('/clients/<identifier>/summary')
    @_refresh_context
    def client_summary_route(identifier):
        """Return the latest saved profile fields needed by inline device cards."""
        device = enrich_ip_client_display_name(identifier, find_inventory_device(identifier) or {})
        host = device.get('ip') or identifier
        return json_success(device={
            'ip': host,
            'mac': device.get('mac'),
            'display_name': display_name_for_inventory_device(device, host),
            'manufacturer': device.get('manufacturer') or 'Unknown',
            'open_port_details': device.get('open_port_details', []),
            'open_ports': device.get('open_ports', []),
            'client_tags': device.get('client_tags', []),
            'client_notes': device.get('client_notes'),
            'last_port_scan': device.get('last_port_scan'),
        })

    @app.route('/clients/<identifier>/metadata', methods=['POST'])
    @_refresh_context
    def client_metadata_route(identifier):
        """Save user-maintained IP client profile metadata."""
        try:
            device = update_client_metadata(identifier, request.form)
        except ValueError as e:
            return json_error(str(e))
        return json_success(device=device, message='Client profile metadata saved.')

    @app.route('/clients/<identifier>/baseline', methods=['POST'])
    @_refresh_context
    def client_baseline_route(identifier):
        """Save current device observations as the expected baseline."""
        device = save_client_baseline(identifier)
        return json_success(device=device, baseline=client_baseline_diff(device), message='Client baseline saved.')

    @app.route('/clients/<identifier>/export.<fmt>')
    @_refresh_context
    def client_export_route(identifier, fmt):
        """Export an individual IP client profile."""
        profile = client_profile_export(identifier)
        if fmt == 'json':
            return jsonify(profile)
        if fmt == 'md':
            device = profile['device']
            lines = [
                f"# Client profile: {profile['host']}",
                '',
                f"- Manufacturer: {device.get('manufacturer') or 'Unknown'}",
                f"- MAC: {device.get('mac') or 'Unknown'}",
                f"- Tags: {', '.join(device.get('client_tags', [])) or 'None'}",
                f"- Owner: {device.get('client_owner') or 'Unknown'}",
                f"- Location: {device.get('client_location') or 'Unknown'}",
                f"- Health: {profile['health']['level']} ({profile['health']['score']}/100)",
                f"- Baseline: {profile['baseline']['status']}",
                '',
                '## Open ports',
            ]
            for item in device.get('open_port_details', []):
                lines.append(f"- {item.get('port')}/tcp {item.get('service') or 'Unknown'} — {item.get('description') or ''}")
            if not device.get('open_port_details'):
                lines.append('- No open ports saved.')
            lines.extend(['', '## Timeline'])
            for event in profile['timeline']:
                lines.append(f"- {event.get('time_label')}: {event.get('type')} — {event.get('message')}")
            return Response('\n'.join(lines), mimetype='text/markdown', headers={'Content-Disposition': f'attachment; filename=client-{profile["host"]}.md'})
        return json_error('Unsupported client export format', 404)

    @app.route('/clients/<identifier>/relationship-map')
    @_refresh_context
    def client_relationship_map_route(identifier):
        return json_success(map=client_relationship_map(identifier))

    @app.route('/clients/<identifier>/intelligence', methods=['POST'])
    @_refresh_context
    def client_intelligence_route(identifier):
        active_probe = request.form.get('activeProbe') in {'on', 'true', '1'}
        return json_success(intelligence=client_intelligence_profile(identifier, active_probe=active_probe))

    @app.route('/clients/<identifier>/fingerprint', methods=['POST'])
    @_refresh_context
    def client_fingerprint_route(identifier):
        return json_success(fingerprints=fingerprint_client_services(identifier))

    @app.route('/clients/<identifier>/scheduled-check', methods=['POST'])
    @_refresh_context
    def client_scheduled_check_route(identifier):
        try:
            plan = save_scheduled_client_check(identifier, request.form)
        except ValueError as e:
            return json_error(str(e))
        return json_success(plan=plan, message='Scheduled client check saved.')

    @app.route('/clients/<identifier>/scheduled-check/run', methods=['POST'])
    @_refresh_context
    def client_scheduled_check_run_route(identifier):
        try:
            plan = run_scheduled_client_check(identifier)
        except ValueError as e:
            return json_error(str(e), 404)
        return json_success(plan=plan, message='Scheduled client check ran.')

    @app.route('/scheduled-checks/run-due', methods=['POST'])
    @_refresh_context
    def scheduled_checks_run_due_route():
        results = run_due_scheduled_client_checks()
        return json_success(results=results, count=len(results), message=f'Ran {len(results)} due scheduled check(s).')

    @app.route('/active-scan', methods=['POST'])
    @_refresh_context
    def active_scan_route():
        iface = request.form.get('selectedInterface')
        if not iface:
            return json_error('Missing interface')
        hosts = classify_scan_results(active_scan(iface), iface)
        enriched_hosts = record_inventory_devices(hosts, 'active-scan', iface)
        network_clients = record_scan_devices_for_wireless_network(
            iface, request.form.get('ssid'), request.form.get('bssid'), enriched_hosts,
        )
        return jsonify({'hosts': enriched_hosts, 'network_clients': network_clients})

    @app.route('/passive-scan', methods=['POST'])
    @_refresh_context
    def passive_scan_route():
        iface = request.form.get('selectedInterface')
        if not iface:
            return json_error('Missing interface')
        devices = classify_scan_results(passive_scan(iface), iface)
        enriched_devices = record_inventory_devices(devices, 'passive-scan', iface)
        analytics = record_passive_observation_analytics(iface, enriched_devices, 'passive-scan')
        network_clients = record_scan_devices_for_wireless_network(
            iface, request.form.get('ssid'), request.form.get('bssid'), enriched_devices,
        )
        return jsonify({'devices': enriched_devices, 'analytics': analytics, 'network_clients': network_clients})

    @app.route('/passive-analytics.json')
    @_refresh_context
    def passive_analytics_route():
        interface = request.args.get('selectedInterface') or request.args.get('interface')
        return json_success(analytics=passive_observation_summary(interface))

    @app.route('/passive-monitor/status')
    @_refresh_context
    def passive_monitor_status_route():
        interface = request.args.get('selectedInterface') or request.args.get('interface')
        status = passive_monitor_snapshot(interface)
        return jsonify({'status': status})

    @app.route('/passive-monitor/toggle', methods=['POST'])
    @_refresh_context
    def passive_monitor_toggle_route():
        data = request.form
        interface = data.get('selectedInterface') or data.get('interface')
        enabled = str(data.get('enabled') or '').strip().lower() in {'1', 'true', 'yes', 'on'}
        try:
            status = set_passive_monitor(interface, enabled, data.get('interval') or 10, data.get('mode') or 'cache')
        except ValueError as exc:
            return json_error(str(exc))
        message = 'Continuous passive capture enabled.' if enabled else 'Continuous passive capture disabled.'
        return json_success(message=message, status=status)

    @app.route('/comprehensive-scan', methods=['POST'])
    @_refresh_context
    def comprehensive_scan_route():
        try:
            selected_interface = request.form.get('selectedInterface')
            result = comprehensive_network_device_scan(
                selected_interface,
                include_passive=request.form.get('includePassive', 'on') == 'on',
                include_services=request.form.get('includeServices', 'on') == 'on',
                sweep_cidr=(request.form.get('sweepCidr') or '').strip() or None,
            )
            result['network_clients'] = record_scan_devices_for_wireless_network(
                selected_interface, request.form.get('ssid'), request.form.get('bssid'), result.get('devices', []),
            )
        except ValueError as e:
            return json_error(str(e))
        return json_success(result=result)

    @app.route('/inventory/<identifier>/forget', methods=['POST'])
    @_refresh_context
    def forget_inventory_route(identifier):
        removed = forget_inventory_device(identifier)
        if not removed:
            return json_error('Device was not found in inventory', 404)
        return json_success(message='Device forgotten from Mobile Router inventory')

    return {
        'inventory_page': inventory_page,
        'inventory_export_json': inventory_export_json,
        'inventory_import_route': inventory_import_route,
        'alerts_page': alerts_page,
        'alerts_status': alerts_status,
        'mark_alert_read': mark_alert_read,
        'mark_all_alerts_read': mark_all_alerts_read,
        'http_preview_file': http_preview_file,
        'client_service_detail': client_service_detail,
        'client_detail': client_detail,
        'watch_client': watch_client,
        'client_http_inspect': client_http_inspect,
        'client_summary_route': client_summary_route,
        'client_metadata_route': client_metadata_route,
        'client_baseline_route': client_baseline_route,
        'client_export_route': client_export_route,
        'client_relationship_map_route': client_relationship_map_route,
        'client_intelligence_route': client_intelligence_route,
        'client_fingerprint_route': client_fingerprint_route,
        'client_scheduled_check_route': client_scheduled_check_route,
        'client_scheduled_check_run_route': client_scheduled_check_run_route,
        'scheduled_checks_run_due_route': scheduled_checks_run_due_route,
        'active_scan_route': active_scan_route,
        'passive_scan_route': passive_scan_route,
        'passive_analytics_route': passive_analytics_route,
        'passive_monitor_status_route': passive_monitor_status_route,
        'passive_monitor_toggle_route': passive_monitor_toggle_route,
        'comprehensive_scan_route': comprehensive_scan_route,
        'forget_inventory_route': forget_inventory_route
    }
