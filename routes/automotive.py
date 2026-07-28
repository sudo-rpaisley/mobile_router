"""Offline automotive lookup and workshop routes."""

import csv
import io
import json
import sqlite3
import socket
import ipaddress
import importlib
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.error import HTTPError, URLError

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, url_for

from services.automotive import AutomotiveStore, simple_pdf


MAX_DATABASE_BYTES = 25 * 1024 * 1024


def _validate_download_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
        raise ValueError('Enter a direct HTTP or HTTPS database URL.')
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80))
    except socket.gaierror as exc:
        raise ValueError('The database host could not be resolved.') from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError('Database links cannot target local, private, or reserved network addresses.')
    return url


class SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_download_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _download(url):
    _validate_download_url(url)
    try:
        response = build_opener(SafeRedirectHandler()).open(
            Request(url, headers={'User-Agent': 'MobileRouter/automotive-database'}), timeout=20,
        )
    except (HTTPError, URLError, TimeoutError) as exc:
        raise ValueError(f'Database download failed: {exc}') from exc
    with response:
        length = int(response.headers.get('Content-Length') or 0)
        if length > MAX_DATABASE_BYTES:
            raise ValueError('The database is larger than the 25 MB import limit.')
        data = response.read(MAX_DATABASE_BYTES + 1)
    if len(data) > MAX_DATABASE_BYTES:
        raise ValueError('The database is larger than the 25 MB import limit.')
    return data


def _pdf_text(content):
    PdfReader = importlib.import_module('pypdf').PdfReader
    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            raise ValueError('Encrypted PDFs are not supported.')
        text = '\n'.join(page.extract_text() or '' for page in reader.pages)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError('The PDF could not be read. Scanned PDFs must be OCRed first.') from exc
    if not text.strip():
        raise ValueError('No searchable text was found. OCR this PDF before importing it.')
    return text


def _uploaded_content(upload):
    content = upload.read(MAX_DATABASE_BYTES + 1)
    if len(content) > MAX_DATABASE_BYTES:
        raise ValueError('The uploaded database is larger than the 25 MB import limit.')
    return content


def create_automotive_blueprint(context_provider):
    blueprint = Blueprint('automotive', __name__)

    def store():
        return AutomotiveStore()

    @blueprint.route('/automotive')
    def index():
        database = store()
        return render_template('automotive.html', title='Automotive', vehicles=database.vehicles(), reports=database.reports(), imports=database.imports(), pending_imports=database.pending_imports(), **context_provider())

    @blueprint.route('/automotive/vin', methods=['GET', 'POST'])
    def vin_lookup():
        result = error = None
        vin = request.values.get('vin', '')
        if vin:
            try:
                result = store().lookup_vin(vin)
            except ValueError as exc:
                error = str(exc)
        return render_template('vin_lookup.html', title='VIN Lookup', vin=vin, result=result, error=error, **context_provider())

    @blueprint.post('/automotive/vehicles')
    def save_vehicle():
        try:
            store().save_vehicle(request.form)
        except (ValueError, sqlite3.IntegrityError) as exc:
            return Response(str(exc), status=400)
        return redirect(url_for('automotive.index'))

    @blueprint.post('/automotive/databases/vin')
    def import_vin():
        upload = request.files.get('database')
        try:
            content = _uploaded_content(upload) if upload and upload.filename else _download(request.form.get('url', ''))
            database = store(); records = database.parse_vin_csv(content)
            pending_id = database.stage_import('vin', upload.filename if upload and upload.filename else request.form.get('url', ''), content, records)
        except (ValueError, OSError) as exc:
            return Response(str(exc), status=400)
        return redirect(url_for('automotive.review_import', pending_id=pending_id))

    @blueprint.post('/automotive/databases/dtc')
    def import_dtc():
        upload = request.files.get('database')
        filename = upload.filename if upload and upload.filename else request.form.get('url', '')
        try:
            content = _uploaded_content(upload) if upload and upload.filename else _download(request.form.get('url', ''))
            database = store()
            if filename.lower().endswith('.pdf') or content.startswith(b'%PDF'):
                records = database.parse_dtc_text(_pdf_text(content), request.form.get('make', ''))
            elif filename.lower().endswith('.csv'):
                records = database.parse_dtc_csv(content, request.form.get('make', ''))
            else:
                records = database.parse_dtc_text(content.decode('utf-8-sig', errors='replace'), request.form.get('make', ''))
            pending_id = database.stage_import('dtc', filename, content, records)
        except (ValueError, OSError) as exc:
            return Response(str(exc), status=400)
        return redirect(url_for('automotive.review_import', pending_id=pending_id))

    @blueprint.get('/automotive/imports/<int:pending_id>')
    def review_import(pending_id):
        pending = store().pending_import(pending_id)
        if not pending:
            abort(404)
        return render_template('automotive_import_review.html', title='Review Import', pending=pending, **context_provider())

    @blueprint.post('/automotive/imports/<int:pending_id>/apply')
    def apply_import(pending_id):
        try:
            _, count = store().apply_pending_import(pending_id, request.form.getlist('selected'))
        except ValueError as exc:
            return Response(str(exc), status=400)
        return redirect(url_for('automotive.index', imported=count, kind='database'))

    @blueprint.post('/automotive/imports/<int:pending_id>/discard')
    def discard_import(pending_id):
        try:
            store().discard_pending_import(pending_id)
        except ValueError:
            abort(404)
        return redirect(url_for('automotive.index'))

    @blueprint.get('/automotive/codes')
    def code_lookup():
        code = request.args.get('code', '')
        matches = store().lookup_code(code, request.args.get('make', '')) if code else []
        return render_template('dtc_lookup.html', title='Code Lookup', code=code, matches=matches, **context_provider())

    @blueprint.post('/automotive/reports')
    def save_report():
        try:
            report_id = store().save_report(request.form)
        except ValueError as exc:
            return Response(str(exc), status=400)
        return redirect(url_for('automotive.report_view', report_id=report_id))

    @blueprint.route('/automotive/vehicles/<int:vehicle_id>', methods=['GET', 'POST'])
    def vehicle_detail(vehicle_id):
        database = store(); vehicle = database.vehicle(vehicle_id)
        if not vehicle:
            abort(404)
        error = None
        if request.method == 'POST':
            try:
                database.update_vehicle(vehicle_id, request.form)
                return redirect(url_for('automotive.vehicle_detail', vehicle_id=vehicle_id))
            except (ValueError, sqlite3.IntegrityError) as exc:
                error = str(exc)
        return render_template('automotive_vehicle.html', title='Vehicle', vehicle=database.vehicle(vehicle_id),
                               identifiers=database.vehicle_identifiers(vehicle_id), modules=database.vehicle_modules(vehicle_id),
                               reports=database.reports(), error=error, **context_provider())

    @blueprint.post('/automotive/vehicles/<int:vehicle_id>/archive')
    def archive_vehicle(vehicle_id):
        try:
            store().archive_vehicle(vehicle_id)
        except ValueError:
            abort(404)
        return redirect(url_for('automotive.index'))

    @blueprint.post('/automotive/vehicles/<int:vehicle_id>/identifiers')
    def add_vehicle_identifier(vehicle_id):
        try:
            store().add_vehicle_identifier(vehicle_id, request.form)
        except ValueError as exc:
            return Response(str(exc), status=400)
        return redirect(url_for('automotive.vehicle_detail', vehicle_id=vehicle_id))

    @blueprint.post('/automotive/vehicles/<int:vehicle_id>/identifiers/<int:identifier_id>/delete')
    def delete_vehicle_identifier(vehicle_id, identifier_id):
        try:
            store().delete_vehicle_identifier(vehicle_id, identifier_id)
        except ValueError:
            abort(404)
        return redirect(url_for('automotive.vehicle_detail', vehicle_id=vehicle_id))

    @blueprint.post('/automotive/vehicles/<int:vehicle_id>/modules')
    def add_vehicle_module(vehicle_id):
        try:
            store().add_vehicle_module(vehicle_id, request.form)
        except ValueError as exc:
            return Response(str(exc), status=400)
        return redirect(url_for('automotive.vehicle_detail', vehicle_id=vehicle_id))

    @blueprint.post('/automotive/vehicles/<int:vehicle_id>/modules/<int:module_id>/delete')
    def delete_vehicle_module(vehicle_id, module_id):
        try:
            store().delete_vehicle_module(vehicle_id, module_id)
        except ValueError:
            abort(404)
        return redirect(url_for('automotive.vehicle_detail', vehicle_id=vehicle_id))

    @blueprint.get('/automotive/reports/<int:report_id>')
    def report_view(report_id):
        report = store().report(report_id)
        if not report:
            abort(404)
        return render_template('automotive_report.html', title='Workshop Report', report=report, **context_provider())

    @blueprint.get('/automotive/reports/<int:report_id>.<fmt>')
    def report_export(report_id, fmt):
        report = store().report(report_id)
        if not report:
            abort(404)
        if fmt == 'json':
            return jsonify(report)
        if fmt == 'csv':
            output = io.StringIO(); writer = csv.writer(output)
            writer.writerow(['Title', report['title']]); writer.writerow(['VIN', report.get('vin') or ''])
            writer.writerow(['Codes', ', '.join(report['codes'])]); writer.writerow(['Work done', report.get('work_done') or ''])
            return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename=workshop-report-{report_id}.csv'})
        if fmt == 'pdf':
            lines = [f"VIN: {report.get('vin') or 'Not assigned'}", f"Vehicle: {report.get('make') or ''} {report.get('model') or ''}",
                     f"Odometer: {report.get('odometer') or ''}", f"Technician: {report.get('technician') or ''}",
                     f"Codes: {', '.join(report['codes'])}"]
            for code in report['codes']:
                definitions = report['code_details'].get(code) or []
                lines.append(f"{code}: {definitions[0]['description'] if definitions else 'No local definition'}")
            lines.extend([f"Work done: {report.get('work_done') or ''}", f"Notes: {report.get('notes') or ''}"])
            return Response(simple_pdf(report['title'], lines), mimetype='application/pdf', headers={'Content-Disposition': f'attachment; filename=workshop-report-{report_id}.pdf'})
        abort(404)

    return blueprint
