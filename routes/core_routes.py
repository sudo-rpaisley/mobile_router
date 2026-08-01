"""Core pages, adapter exports, evidence, reports, and contact routes."""

import json
import os
import time

from flask import (
    Response,
    jsonify,
    render_template,
    request,
    send_file,
    send_from_directory,
)

from app_support.context import dependency_proxy


CORE_ROUTE_DEPENDENCIES = {
    'EVIDENCE_DIR',
    'ROADMAP_SECTIONS',
    'adapter_snapshot',
    'adapter_update_fragments',
    'build_report_data',
    'create_evidence_record',
    'current_context',
    'evidence_as_csv',
    'evidence_as_markdown',
    'evidence_records',
    'evidence_vault',
    'evidence_vault_lock',
    'json_error',
    'json_success',
    'network_interfaces',
    'remaining_roadmap_items',
    'report_as_csv',
    'report_as_markdown',
}


def register_core_routes(app, context_provider):
    deps = dependency_proxy(
        context_provider,
        CORE_ROUTE_DEPENDENCIES,
        label='core route',
    )

    @app.route('/')
    def index():
        return render_template('index.html', title='Home', **deps.current_context())

    @app.route('/about')
    def about():
        return render_template('about.html', title='About', **deps.current_context())

    @app.route('/contact')
    def contact_page():
        return render_template('contact.html', title='Contact', **deps.current_context())

    @app.route('/submit-contact', methods=['POST'])
    def submit_contact():
        data = request.get_json() or {}
        name = data.get('name')
        email = data.get('email')
        message = data.get('message')
        if not name or not email or not message:
            return deps.json_error('Missing information')
        try:
            with open('contact_messages.txt', 'a', encoding='utf-8') as handle:
                json.dump(
                    {
                        'name': name,
                        'email': email,
                        'message': message,
                        'timestamp': time.time(),
                    },
                    handle,
                )
                handle.write('\n')
            return deps.json_success()
        except (OSError, TypeError, ValueError) as exc:
            return deps.json_error(str(exc), 500)

    @app.route('/favicon.ico')
    def favicon():
        return send_from_directory(
            os.path.join(app.root_path, 'static'),
            'favicon.ico',
        )

    @app.route('/red-team')
    def red_team():
        return render_template(
            'red-team.html',
            title='Red Team',
            **deps.current_context(),
        )

    @app.route('/roadmap')
    def roadmap_page():
        return render_template(
            'roadmap.html',
            title='Roadmap',
            roadmap_sections=deps.ROADMAP_SECTIONS,
            remaining_roadmap_items=deps.remaining_roadmap_items(),
            **deps.current_context(),
        )

    @app.route('/adapters', methods=['POST'])
    def adapters():
        """Return the available network interfaces as JSON."""
        return jsonify(
            {
                'interfaces': [
                    iface.to_dict() for iface in deps.network_interfaces
                ]
            }
        )

    @app.route('/adapters/updates', methods=['POST'])
    def adapter_updates():
        """Return adapter data and replaceable fragments when adapters changed."""
        data = request.get_json(silent=True) or {}
        current_snapshot = deps.adapter_snapshot()
        changed = data.get('snapshot') != current_snapshot
        return jsonify(
            {
                'changed': changed,
                'snapshot': current_snapshot,
                'interfaces': [
                    iface.to_dict() for iface in deps.network_interfaces
                ],
                'fragments': (
                    deps.adapter_update_fragments(data.get('title') or 'Home')
                    if changed
                    else {}
                ),
            }
        )

    @app.route('/export/interfaces.json')
    def export_interfaces_json():
        return jsonify(
            {
                'interfaces': [
                    iface.to_dict() for iface in deps.network_interfaces
                ],
                'exported_at': time.time(),
            }
        )

    @app.route('/export/capabilities.json')
    def export_capabilities_json():
        from scripts.capabilities import build_capabilities

        return jsonify(
            {
                'capabilities': build_capabilities(),
                'exported_at': time.time(),
            }
        )

    @app.route('/evidence')
    def evidence_page():
        return render_template(
            'evidence.html',
            title='Evidence Vault',
            evidence=deps.evidence_records(),
            **deps.current_context(),
        )

    @app.route('/evidence', methods=['POST'])
    def create_evidence_route():
        try:
            record = deps.create_evidence_record(
                request.form.get('title'),
                request.form.get('category'),
                request.form.get('source'),
                request.form.get('device'),
                request.form.get('notes'),
                request.form.get('content'),
                request.files.get('artifact'),
            )
        except ValueError as exc:
            return deps.json_error(str(exc))
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return deps.json_success(evidence=record)
        return render_template(
            'evidence.html',
            title='Evidence Vault',
            evidence=deps.evidence_records(),
            created=record,
            **deps.current_context(),
        )

    @app.route('/evidence.<fmt>')
    def export_evidence(fmt):
        records = deps.evidence_records()
        if fmt == 'json':
            return jsonify({'evidence': records, 'exported_at': time.time()})
        if fmt == 'csv':
            return Response(
                deps.evidence_as_csv(records),
                mimetype='text/csv',
                headers={
                    'Content-Disposition': 'attachment; filename=evidence-vault.csv'
                },
            )
        if fmt in {'md', 'markdown'}:
            return Response(
                deps.evidence_as_markdown(records),
                mimetype='text/markdown',
                headers={
                    'Content-Disposition': 'attachment; filename=evidence-vault.md'
                },
            )
        return deps.json_error('Unsupported evidence export format', 404)

    @app.route('/evidence/<evidence_id>/download')
    def download_evidence_file(evidence_id):
        with deps.evidence_vault_lock:
            record = next(
                (
                    item
                    for item in deps.evidence_vault
                    if item.get('id') == evidence_id
                ),
                None,
            )
        if not record or not record.get('stored_name'):
            return deps.json_error('Evidence file not found', 404)
        path = os.path.join(deps.EVIDENCE_DIR, record['stored_name'])
        if not os.path.isfile(path):
            return deps.json_error('Evidence file not found', 404)
        return send_file(
            path,
            as_attachment=True,
            download_name=record.get('file_name') or record['stored_name'],
        )

    @app.route('/reports')
    def reports_page():
        return render_template(
            'reports.html',
            title='Reports',
            report=deps.build_report_data(),
            **deps.current_context(),
        )

    @app.route('/reports.<fmt>')
    def export_report(fmt):
        report = deps.build_report_data()
        if fmt == 'json':
            return jsonify(report)
        if fmt == 'csv':
            return Response(
                deps.report_as_csv(report),
                mimetype='text/csv',
                headers={
                    'Content-Disposition': 'attachment; filename=mobile-router-report.csv'
                },
            )
        if fmt in {'md', 'markdown'}:
            return Response(
                deps.report_as_markdown(report),
                mimetype='text/markdown',
                headers={
                    'Content-Disposition': 'attachment; filename=mobile-router-report.md'
                },
            )
        if fmt == 'html':
            return render_template(
                'report_export.html',
                title='Report Export',
                report=report,
            )
        return deps.json_error('Unsupported report format', 404)

    @app.route('/network-scan')
    def network_scan():
        return render_template(
            'network_scan.html',
            title='Network Scan',
            **deps.current_context(),
        )

    @app.route('/diagnostics')
    def diagnostics_page():
        return render_template(
            'diagnostics.html',
            title='Diagnostics',
            **deps.current_context(),
        )

    @app.route('/service-discovery')
    def service_discovery_page():
        return render_template(
            'service_discovery.html',
            title='Service Discovery',
            **deps.current_context(),
        )

    @app.route('/advanced-diagnostics')
    def advanced_diagnostics_page():
        return render_template(
            'advanced_diagnostics.html',
            title='Advanced Diagnostics',
            **deps.current_context(),
        )

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
        'advanced_diagnostics_page': advanced_diagnostics_page,
    }
