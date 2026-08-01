"""Port scans, jobs, diagnostics, and service-discovery routes."""

from app_support.context import bind_context


def register_diagnostic_routes(app, context_provider):
    _refresh_context = bind_context(globals(), context_provider)

    @app.route('/port-scan')
    @_refresh_context
    def port_scan_page():
        return render_template('port_scan.html', title='Port Scan', **current_context())

    @app.route('/jobs')
    @_refresh_context
    def jobs_page():
        return render_template('jobs.html', title='Jobs', **current_context())

    @app.route('/traceroute')
    @_refresh_context
    def traceroute_page():
        return render_template('traceroute.html', title='Traceroute', **current_context())

    @app.route('/port-scan', methods=['POST'])
    @_refresh_context
    def port_scan_route():
        data = request.form
        if missing_fields(data, 'host', 'start', 'end'):
            return json_error('Missing parameters')

        try:
            start_port = parse_int(data.get('start'), 'Ports must be integers')
            end_port = parse_int(data.get('end'), 'Ports must be integers')
        except ValueError as e:
            return json_error(str(e))

        from scripts.portScanner import PortScanError, describe_open_ports, scan_ports

        try:
            ports = scan_ports(data.get('host'), start_port, end_port)
        except PortScanError as e:
            return json_error(str(e))

        port_details = [enrich_web_port_metadata(data.get('host'), detail) for detail in describe_open_ports(ports)]
        record_device_open_ports(data.get('host'), port_details, source='port-scan')
        return jsonify({'ports': ports, 'port_details': port_details})

    @app.route('/port-scan-jobs', methods=['POST'])
    @_refresh_context
    def start_port_scan_job():
        data = request.form
        if missing_fields(data, 'host', 'start', 'end'):
            return json_error('Missing parameters')
        try:
            start_port = parse_int(data.get('start'), 'Ports must be integers')
            end_port = parse_int(data.get('end'), 'Ports must be integers')
            job = create_port_scan_job(data.get('host'), start_port, end_port, data.get('label'))
            return json_success(job=job)
        except ValueError as e:
            return json_error(str(e))

    @app.route('/port-scan-jobs/<job_id>')
    @_refresh_context
    def port_scan_job_status(job_id):
        with port_scan_jobs_lock:
            job = port_scan_jobs.get(job_id)
            if not job:
                return json_error('Port scan job not found', 404)
            return json_success(job=_port_scan_job_snapshot(job))

    @app.route('/jobs/status')
    @_refresh_context
    def jobs_status():
        jobs = all_job_snapshots()
        return json_success(jobs=jobs, running_count=len([job for job in jobs if job.get('status') in {'queued', 'running'}]))

    @app.route('/jobs/<job_id>/cancel', methods=['POST'])
    @_refresh_context
    def cancel_job(job_id):
        with port_scan_jobs_lock:
            port_job = port_scan_jobs.get(job_id)
            if port_job:
                if port_job.get('status') in {'queued', 'running'}:
                    port_job['cancel_requested'] = True
                    port_job['status'] = 'cancelled' if port_job.get('status') == 'queued' else port_job.get('status')
                    port_job['message'] = 'Cancellation requested.'
                    port_job['updated_at'] = time.time()
                return json_success(job=_port_scan_job_snapshot(port_job))
        with scan_jobs_lock:
            scan_job = scan_jobs.get(job_id)
            if scan_job:
                scan_job['cancel_requested'] = True
                if scan_job.get('status') in {'queued', 'running'}:
                    scan_job['status'] = 'cancelled'
                    scan_job['message'] = 'Cancellation requested.'
                    scan_job['updated_at'] = time.time()
                return json_success(job=_scan_job_snapshot(scan_job))
        return json_error('Job not found', 404)

    @app.route('/traceroute', methods=['POST'])
    @_refresh_context
    def traceroute_route():
        host = request.form.get('host')
        if not host:
            return json_error('Missing host')
        from scripts.traceroute import traceroute
        hops = traceroute(host)
        return jsonify({'hops': hops})

    @app.route('/ping', methods=['POST'])
    @_refresh_context
    def ping_route():
        try:
            result = run_ping_check(request.form.get('host'), request.form.get('count') or 4, request.form.get('timeout') or 2)
        except ValueError as e:
            return json_error(str(e))
        except subprocess.TimeoutExpired:
            return json_error('Ping timed out', 504)
        return json_success(result=result, history=ping_history[-10:])

    @app.route('/ping-sweep', methods=['POST'])
    @_refresh_context
    def ping_sweep_route():
        try:
            sweep = run_ping_sweep(request.form.get('cidr'), request.form.get('count') or 1, request.form.get('timeout') or 1)
        except ValueError as e:
            return json_error(str(e))
        return json_success(sweep=sweep, history=ping_history[-10:])

    @app.route('/route-diagnostics', methods=['POST'])
    @_refresh_context
    def route_diagnostics_route():
        diagnostics = build_route_diagnostics(request.form.get('target'))
        return json_success(diagnostics=diagnostics)

    @app.route('/mdns-discovery', methods=['POST'])
    @_refresh_context
    def mdns_discovery_route():
        result = discover_mdns_services(request.form.get('selectedInterface'))
        return json_success(result=result)

    @app.route('/upnp-discovery', methods=['POST'])
    @_refresh_context
    def upnp_discovery_route():
        try:
            timeout = parse_int(request.form.get('timeout') or 2, 'Timeout must be an integer')
        except ValueError as e:
            return json_error(str(e))
        result = discover_upnp_devices(timeout=max(1, min(timeout, 5)))
        return json_success(result=result)

    @app.route('/neighbor-discovery', methods=['POST'])
    @_refresh_context
    def neighbor_discovery_route():
        result = discover_lldp_neighbors(request.form.get('selectedInterface'))
        return json_success(result=result)

    @app.route('/vlan-discovery', methods=['POST'])
    @_refresh_context
    def vlan_discovery_route():
        result = discover_vlan_context(request.form.get('ssid'), request.form.get('vlanId'), request.form.get('notes'))
        return json_success(result=result)

    @app.route('/egress-diagnostics', methods=['POST'])
    @_refresh_context
    def egress_diagnostics_route():
        return json_success(result=build_egress_diagnostics(request.form.get('selectedInterface')))

    @app.route('/iperf3-test', methods=['POST'])
    @_refresh_context
    def iperf3_test_route():
        try:
            result = run_iperf3_test(request.form.get('mode'), request.form.get('host'), request.form.get('port') or 5201, request.form.get('seconds') or 5)
        except (ValueError, subprocess.TimeoutExpired) as e:
            return json_error(str(e))
        return json_success(result=result)

    @app.route('/snmp-discovery', methods=['POST'])
    @_refresh_context
    def snmp_discovery_route():
        if request.form.get('authorized') != 'on':
            return json_error('Confirm this is an authorized SNMP inventory check')
        try:
            result = run_snmp_inventory(request.form.get('host'), request.form.get('community'), request.form.get('version') or '2c', request.form.get('oid') or 'system')
        except ValueError as e:
            return json_error(str(e))
        return json_success(result=result)

    @app.route('/ipv6-assessment', methods=['POST'])
    @_refresh_context
    def ipv6_assessment_route():
        result = run_ipv6_assessment(request.form.get('host'), request.form.get('ports'))
        return json_success(result=result)

    return {
        'port_scan_page': port_scan_page,
        'jobs_page': jobs_page,
        'traceroute_page': traceroute_page,
        'port_scan_route': port_scan_route,
        'start_port_scan_job': start_port_scan_job,
        'port_scan_job_status': port_scan_job_status,
        'jobs_status': jobs_status,
        'cancel_job': cancel_job,
        'traceroute_route': traceroute_route,
        'ping_route': ping_route,
        'ping_sweep_route': ping_sweep_route,
        'route_diagnostics_route': route_diagnostics_route,
        'mdns_discovery_route': mdns_discovery_route,
        'upnp_discovery_route': upnp_discovery_route,
        'neighbor_discovery_route': neighbor_discovery_route,
        'vlan_discovery_route': vlan_discovery_route,
        'egress_diagnostics_route': egress_diagnostics_route,
        'iperf3_test_route': iperf3_test_route,
        'snmp_discovery_route': snmp_discovery_route,
        'ipv6_assessment_route': ipv6_assessment_route
    }
