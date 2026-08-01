"""Core pages, adapter exports, evidence, reports, and contact routes."""

from functools import wraps


def register_core_routes(app, context_provider):
    globals().update(context_provider())

    def _refresh_context(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            globals().update(context_provider())
            return view(*args, **kwargs)
        return wrapped

    @app.route('/')
    @_refresh_context
    def index():
        return render_template('index.html', title='Home', **current_context())

    @app.route('/about')
    @_refresh_context
    def about():
        return render_template('about.html', title='About', **current_context())

    @app.route('/contact')
    @_refresh_context
    def contact_page():
        return render_template('contact.html', title='Contact', **current_context())

    @app.route('/submit-contact', methods=['POST'])
    @_refresh_context
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
    @_refresh_context
    def favicon():
        return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico')

    @app.route('/red-team')
    @_refresh_context
    def red_team():
        return render_template('red-team.html', title='Red Team', **current_context())

    @app.route('/roadmap')
    @_refresh_context
    def roadmap_page():
        return render_template(
            'roadmap.html',
            title='Roadmap',
            roadmap_sections=ROADMAP_SECTIONS,
            remaining_roadmap_items=remaining_roadmap_items(),
            **current_context(),
        )

    @app.route('/adapters', methods=['POST'])
    @_refresh_context
    def adapters():
        """Return the available network interfaces as JSON."""
        return jsonify({'interfaces': [iface.to_dict() for iface in network_interfaces]})

    @app.route('/adapters/updates', methods=['POST'])
    @_refresh_context
    def adapter_updates():
        """Return adapter data plus replaceable page fragments when adapters changed."""
        data = request.get_json(silent=True) or {}
        current_snapshot = adapter_snapshot()
        changed = data.get('snapshot') != current_snapshot
        return jsonify({
            'changed': changed,
            'snapshot': current_snapshot,
            'interfaces': [iface.to_dict() for iface in network_interfaces],
            'fragments': adapter_update_fragments(data.get('title') or 'Home') if changed else {},
        })

    @app.route('/export/interfaces.json')
    @_refresh_context
    def export_interfaces_json():
        return jsonify({
            'interfaces': [iface.to_dict() for iface in network_interfaces],
            'exported_at': time.time(),
        })

    @app.route('/export/capabilities.json')
    @_refresh_context
    def export_capabilities_json():
        from scripts.capabilities import build_capabilities
        return jsonify({
            'capabilities': build_capabilities(),
            'exported_at': time.time(),
        })

    @app.route('/evidence')
    @_refresh_context
    def evidence_page():
        return render_template('evidence.html', title='Evidence Vault', evidence=evidence_records(), **current_context())

    @app.route('/evidence', methods=['POST'])
    @_refresh_context
    def create_evidence_route():
        try:
            record = create_evidence_record(
                request.form.get('title'),
                request.form.get('category'),
                request.form.get('source'),
                request.form.get('device'),
                request.form.get('notes'),
                request.form.get('content'),
                request.files.get('artifact'),
            )
        except ValueError as e:
            return json_error(str(e))
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return json_success(evidence=record)
        return render_template('evidence.html', title='Evidence Vault', evidence=evidence_records(), created=record, **current_context())

    @app.route('/evidence.<fmt>')
    @_refresh_context
    def export_evidence(fmt):
        records = evidence_records()
        if fmt == 'json':
            return jsonify({'evidence': records, 'exported_at': time.time()})
        if fmt == 'csv':
            return Response(evidence_as_csv(records), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=evidence-vault.csv'})
        if fmt in {'md', 'markdown'}:
            return Response(evidence_as_markdown(records), mimetype='text/markdown', headers={'Content-Disposition': 'attachment; filename=evidence-vault.md'})
        return json_error('Unsupported evidence export format', 404)

    @app.route('/evidence/<evidence_id>/download')
    @_refresh_context
    def download_evidence_file(evidence_id):
        with evidence_vault_lock:
            record = next((item for item in evidence_vault if item.get('id') == evidence_id), None)
        if not record or not record.get('stored_name'):
            return json_error('Evidence file not found', 404)
        path = os.path.join(EVIDENCE_DIR, record['stored_name'])
        if not os.path.isfile(path):
            return json_error('Evidence file not found', 404)
        return send_file(path, as_attachment=True, download_name=record.get('file_name') or record['stored_name'])

    @app.route('/reports')
    @_refresh_context
    def reports_page():
        return render_template('reports.html', title='Reports', report=build_report_data(), **current_context())

    @app.route('/reports.<fmt>')
    @_refresh_context
    def export_report(fmt):
        report = build_report_data()
        if fmt == 'json':
            return jsonify(report)
        if fmt == 'csv':
            return Response(report_as_csv(report), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=mobile-router-report.csv'})
        if fmt in {'md', 'markdown'}:
            return Response(report_as_markdown(report), mimetype='text/markdown', headers={'Content-Disposition': 'attachment; filename=mobile-router-report.md'})
        if fmt == 'html':
            return render_template('report_export.html', title='Report Export', report=report)
        return json_error('Unsupported report format', 404)

    @app.route('/network-scan')
    @_refresh_context
    def network_scan():
        return render_template('network_scan.html', title='Network Scan', **current_context())

    @app.route('/diagnostics')
    @_refresh_context
    def diagnostics_page():
        return render_template('diagnostics.html', title='Diagnostics', **current_context())

    @app.route('/service-discovery')
    @_refresh_context
    def service_discovery_page():
        return render_template('service_discovery.html', title='Service Discovery', **current_context())

    @app.route('/advanced-diagnostics')
    @_refresh_context
    def advanced_diagnostics_page():
        return render_template('advanced_diagnostics.html', title='Advanced Diagnostics', **current_context())

    return {
        'index': index,
        'about': about,
        'contact_page': contact_page,
        'submit_contact': submit_contact,
        'favicon': favicon,
        'red_team': red_team,
        'roadmap_page': roadmap_page,
        'adapters': adapters,
        'adapter_updates': adapter_updates,
        'export_interfaces_json': export_interfaces_json,
        'export_capabilities_json': export_capabilities_json,
        'evidence_page': evidence_page,
        'create_evidence_route': create_evidence_route,
        'export_evidence': export_evidence,
        'download_evidence_file': download_evidence_file,
        'reports_page': reports_page,
        'export_report': export_report,
        'network_scan': network_scan,
        'diagnostics_page': diagnostics_page,
        'service_discovery_page': service_discovery_page,
        'advanced_diagnostics_page': advanced_diagnostics_page
    }
