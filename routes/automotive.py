"""Offline automotive lookup and workshop routes."""

import csv
import io
import json
import os
import sqlite3
import socket
import ipaddress
import importlib
import zipfile
import math
import secrets
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.error import HTTPError, URLError

from flask import Blueprint, Response, abort, current_app, jsonify, redirect, render_template, request, session, url_for

from services.automotive import AutomotiveStore, simple_pdf


MAX_DATABASE_BYTES = 25 * 1024 * 1024
MAX_ARCHIVE_FILES = 250
MAX_ARCHIVE_UNCOMPRESSED_BYTES = int(os.environ.get('MOBILE_ROUTER_AUTOMOTIVE_ZIP_LIMIT_MB', '250')) * 1024 * 1024


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


def _collapse_dtc_matches(matches):
    """Collapse repeated imports without hiding distinct applicability or wording."""
    collapsed = {}
    fields = ('make', 'model', 'description', 'scope', 'year_start', 'year_end', 'module', 'engine')
    for match in matches:
        key = tuple(str(match.get(field) or '').strip().casefold() for field in fields)
        if key not in collapsed:
            collapsed[key] = dict(match, duplicate_count=1, sources=[])
        else:
            collapsed[key]['duplicate_count'] += 1
        source = match.get('source_name') or match.get('source')
        if source and source not in collapsed[key]['sources']:
            collapsed[key]['sources'].append(source)
    return list(collapsed.values())


def _stack_dtc_matches(matches):
    """Stack equal code functions while retaining every manufacturer variant."""
    stacks = {}
    for match in _collapse_dtc_matches(matches):
        key = (str(match.get('description') or '').strip().casefold(),
               str(match.get('category') or '').strip().casefold())
        stack = stacks.setdefault(key, {
            'description': match.get('description') or '', 'category': match.get('category') or '', 'variants': [],
            'manufacturers': [], 'models': [],
        })
        stack['variants'].append(match)
        make = str(match.get('make') or 'Generic OBD-II').strip()
        model = str(match.get('model') or '').strip()
        if make not in stack['manufacturers']:
            stack['manufacturers'].append(make)
        if model and model not in stack['models']:
            stack['models'].append(model)
    for stack in stacks.values():
        stack['variants'].sort(key=lambda item: (
            0 if not item.get('make') else 1, str(item.get('make') or '').casefold(),
            str(item.get('model') or '').casefold(), -int(item.get('lookup_priority') or 0),
        ))
    return list(stacks.values())


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


def _dtc_records_from_file(database, content, filename, default_make=''):
    """Parse one DTC source or a bounded ZIP containing CSV, text, and PDFs."""
    lower_name = filename.lower()
    if lower_name.endswith('.zip') or content.startswith(b'PK\x03\x04'):
        records, total_size, file_count = [], 0, 0
        try:
            archive = zipfile.ZipFile(io.BytesIO(content))
            for member in archive.infolist():
                if member.is_dir() or member.filename.startswith('__MACOSX/'):
                    continue
                file_count += 1
                if file_count > MAX_ARCHIVE_FILES:
                    raise ValueError(f'ZIP archives may contain at most {MAX_ARCHIVE_FILES} files.')
                if member.flag_bits & 0x1:
                    raise ValueError(f'Encrypted ZIP entry is not supported: {member.filename}')
                total_size += member.file_size
                if total_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                    limit_mb = MAX_ARCHIVE_UNCOMPRESSED_BYTES // (1024 * 1024)
                    raise ValueError(f'The uncompressed ZIP contents exceed the {limit_mb} MB import limit.')
                if member.compress_size and member.file_size > member.compress_size * 500:
                    raise ValueError(f'ZIP entry has an unsafe compression ratio: {member.filename}')
                suffix = member.filename.lower()
                if not suffix.endswith(('.csv', '.txt', '.pdf')):
                    continue
                child = archive.read(member)
                child_records = _dtc_records_from_file(database, child, member.filename, default_make)
                for record in child_records:
                    record['source_name'] = record.get('source_name') or member.filename
                records.extend(child_records)
        except zipfile.BadZipFile as exc:
            raise ValueError('The ZIP file is damaged or invalid.') from exc
        if not records:
            raise ValueError('The ZIP contains no valid DTC records in CSV, text, or searchable PDF files.')
        return records
    if lower_name.endswith('.pdf') or content.startswith(b'%PDF'):
        records = database.parse_dtc_text(_pdf_text(content), default_make)
    elif lower_name.endswith('.csv'):
        records = database.parse_dtc_csv(content, default_make)
    else:
        records = database.parse_dtc_text(content.decode('utf-8-sig', errors='replace'), default_make)
    for record in records:
        record['source_name'] = record.get('source_name') or filename
    return records


def create_automotive_blueprint(context_provider):
    blueprint = Blueprint('automotive', __name__)

    admin_endpoints = {'automotive.import_vin', 'automotive.import_dtc', 'automotive.deduplicate_dtc',
                       'automotive.save_import_selection', 'automotive.apply_import', 'automotive.discard_import',
                       'automotive.resolve_conflict', 'automotive.apply_parameter_change'}
    write_endpoints = {'automotive.save_vehicle', 'automotive.save_report', 'automotive.vehicle_detail',
                       'automotive.archive_vehicle', 'automotive.add_vehicle_identifier',
                       'automotive.delete_vehicle_identifier', 'automotive.add_vehicle_module',
                       'automotive.delete_vehicle_module', 'automotive.add_vehicle_person',
                       'automotive.delete_vehicle_person', 'automotive.save_diagnostic_session'}
    write_endpoints.update({'automotive.save_parameter_snapshot', 'automotive.stage_parameter_change'})

    @blueprint.before_request
    def protect_automotive_writes():
        if request.method not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            return None
        user = session.get('social_user') or {}
        role = user.get('role')
        if request.endpoint in admin_endpoints and role != 'admin':
            return Response('Administrator access is required.', status=403)
        if request.endpoint in write_endpoints and role not in {'editor', 'admin'}:
            return Response('Editor access is required.', status=403)
        supplied = str(request.form.get('csrf_token') or request.headers.get('X-CSRF-Token') or '')
        expected = str(session.get('social_csrf_token') or '')
        if not expected or not secrets.compare_digest(supplied, expected):
            return Response('Invalid or expired form token.', status=400)
        return None

    def store():
        return AutomotiveStore()

    def people():
        provider = current_app.config.get('AUTOMOTIVE_PEOPLE_PROVIDER')
        return provider() if provider else []

    @blueprint.route('/automotive')
    def index():
        database = store()
        return render_template('automotive.html', title='Automotive', vehicles=database.vehicles(), reports=database.reports(),
                               diagnostic_sessions=database.diagnostic_sessions(), imports=database.imports(),
                               pending_imports=database.pending_imports(), **context_provider())

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
            database = store()
            vehicle_id = database.save_vehicle(request.form)
        except (ValueError, sqlite3.IntegrityError) as exc:
            existing = store().vehicle_by_vin(request.form.get('vin'))
            if isinstance(exc, sqlite3.IntegrityError) and existing:
                return redirect(url_for('automotive.vehicle_detail', vehicle_id=existing['id'], already_saved=1))
            return Response(str(exc), status=400)
        return redirect(url_for('automotive.vehicle_detail', vehicle_id=vehicle_id, saved=1))

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
            records = _dtc_records_from_file(database, content, filename, request.form.get('make', ''))
            pending_id = database.stage_import('dtc', filename, content, records)
        except (ValueError, OSError) as exc:
            return Response(str(exc), status=400)
        return redirect(url_for('automotive.review_import', pending_id=pending_id))

    @blueprint.post('/automotive/databases/dtc/deduplicate')
    def deduplicate_dtc():
        removed = store().deduplicate_dtc_definitions()
        return redirect(url_for('automotive.index', duplicates_removed=removed))

    @blueprint.get('/automotive/imports/<int:pending_id>')
    def review_import(pending_id):
        pending = store().pending_import(pending_id)
        if not pending:
            abort(404)
        choices = (25, 50, 100, 250)
        try:
            per_page = int(request.args.get('per_page', 50)); page = int(request.args.get('page', 1))
        except ValueError:
            per_page, page = 50, 1
        per_page = per_page if per_page in choices else 50
        page_count = max(1, math.ceil(len(pending['records']) / per_page)); page = min(max(page, 1), page_count)
        start = (page - 1) * per_page
        records = [{'index': start + offset, 'record': record} for offset, record in enumerate(pending['records'][start:start + per_page])]
        return render_template('automotive_import_review.html', title='Review Import', pending=pending, records=records,
                               page=page, page_count=page_count, per_page=per_page, per_page_choices=choices,
                               selected_count=len(pending['records']) - len(pending.get('excluded', [])), **context_provider())

    @blueprint.post('/automotive/imports/<int:pending_id>/selection')
    def save_import_selection(pending_id):
        try:
            store().update_pending_selection(pending_id, request.form.getlist('page_index'), request.form.getlist('selected'))
        except ValueError:
            abort(404)
        return redirect(url_for('automotive.review_import', pending_id=pending_id,
                                page=request.form.get('next_page') or request.form.get('page') or 1,
                                per_page=request.form.get('per_page') or 50, selection_saved=1))

    @blueprint.post('/automotive/imports/<int:pending_id>/apply')
    def apply_import(pending_id):
        try:
            if request.form.getlist('page_index'):
                store().update_pending_selection(pending_id, request.form.getlist('page_index'), request.form.getlist('selected'))
            _, count = store().apply_pending_import(pending_id)
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
        database = store()
        code = request.args.get('code', '').strip()
        make = request.args.get('make', '').strip()
        model = request.args.get('model', '').strip()
        category = request.args.get('category', '').strip().upper()
        query = request.args.get('q', '').strip()
        try:
            per_page = int(request.args.get('per_page', 25))
            page = max(1, int(request.args.get('page', 1)))
        except (TypeError, ValueError):
            per_page, page = 25, 1
        per_page = per_page if per_page in {12, 25, 50, 100} else 25
        matches = _collapse_dtc_matches(database.lookup_code(code, make)) if code else []
        browse_rows, browse_total = database.browse_codes(
            make, model, category, query, per_page, (page - 1) * per_page,
        )
        page_count = max(1, math.ceil(browse_total / per_page))
        if page > page_count:
            page = page_count
            browse_rows, browse_total = database.browse_codes(
                make, model, category, query, per_page, (page - 1) * per_page,
            )
        return render_template(
            'dtc_lookup.html', title='Code Lookup', code=code, matches=matches,
            browse_rows=browse_rows, browse_total=browse_total, facets=database.dtc_browse_facets(make),
            selected_make=make, selected_model=model, selected_category=category, browse_query=query,
            page=page, page_count=page_count, per_page=per_page, **context_provider(),
        )

    @blueprint.get('/automotive/codes/<code>')
    def code_detail(code):
        database = store()
        matches = database.lookup_code(code, request.args.get('make', ''))
        if not matches:
            abort(404)
        return render_template('automotive_code.html', title=code.upper(), code=code.upper(),
                               stacks=_stack_dtc_matches(matches), definition_count=len(matches),
                               **context_provider())

    @blueprint.get('/automotive/databases/dtc/conflicts')
    def conflict_review():
        return render_template('automotive_conflicts.html', title='DTC Conflict Review',
                               conflicts=store().dtc_conflicts(), **context_provider())

    @blueprint.post('/automotive/databases/dtc/conflicts/<int:definition_id>')
    def resolve_conflict(definition_id):
        try:
            store().resolve_dtc_conflict(definition_id, request.form.get('action'), request.form.get('priority'))
        except ValueError as exc:
            return Response(str(exc), status=400)
        return redirect(url_for('automotive.conflict_review'))

    @blueprint.get('/automotive/sessions')
    def diagnostic_sessions():
        database = store()
        return render_template('automotive_sessions.html', title='Diagnostic Sessions',
                               sessions=database.diagnostic_sessions(), vehicles=database.vehicles(), **context_provider())

    @blueprint.post('/automotive/sessions')
    def save_diagnostic_session():
        try:
            session_id = store().save_diagnostic_session(request.form, (session.get('social_user') or {}).get('username', ''))
        except ValueError as exc:
            return Response(str(exc), status=400)
        return redirect(url_for('automotive.diagnostic_session_detail', session_id=session_id))

    @blueprint.get('/automotive/sessions/<int:session_id>')
    def diagnostic_session_detail(session_id):
        diagnostic_session = store().diagnostic_session(session_id)
        if not diagnostic_session:
            abort(404)
        return render_template('automotive_session.html', title=diagnostic_session['title'],
                               diagnostic_session=diagnostic_session, **context_provider())

    @blueprint.post('/automotive/vehicles/<int:vehicle_id>/parameters')
    def save_parameter_snapshot(vehicle_id):
        try:
            snapshot_id = store().save_parameter_snapshot(
                vehicle_id, request.form, (session.get('social_user') or {}).get('username', ''))
        except ValueError as exc:
            return Response(str(exc), status=400)
        return redirect(url_for('automotive.parameter_snapshot_detail', snapshot_id=snapshot_id))

    @blueprint.get('/automotive/parameters/<int:snapshot_id>')
    def parameter_snapshot_detail(snapshot_id):
        snapshot = store().parameter_snapshot(snapshot_id)
        if not snapshot:
            abort(404)
        return render_template('automotive_parameters.html', title=snapshot['title'], snapshot=snapshot,
                               **context_provider())

    @blueprint.post('/automotive/parameters/<int:snapshot_id>/changes')
    def stage_parameter_change(snapshot_id):
        try:
            store().stage_parameter_change(snapshot_id, request.form,
                                           (session.get('social_user') or {}).get('username', ''))
        except ValueError as exc:
            return Response(str(exc), status=400)
        return redirect(url_for('automotive.parameter_snapshot_detail', snapshot_id=snapshot_id))

    @blueprint.post('/automotive/parameters/<int:snapshot_id>/changes/<int:change_id>/apply')
    def apply_parameter_change(snapshot_id, change_id):
        try:
            store().apply_parameter_change(change_id, request.form.get('transport'),
                                           (session.get('social_user') or {}).get('username', ''), snapshot_id)
        except ValueError as exc:
            return Response(str(exc), status=400)
        return redirect(url_for('automotive.parameter_snapshot_detail', snapshot_id=snapshot_id, simulated=1))

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
                               parameter_snapshots=database.parameter_snapshots(vehicle_id),
                               people=people(), vehicle_people=database.vehicle_people(vehicle_id),
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

    @blueprint.post('/automotive/vehicles/<int:vehicle_id>/people')
    def add_vehicle_person(vehicle_id):
        available = {str(person['id']): person for person in people()}
        person = available.get(str(request.form.get('person_id') or ''))
        if not person:
            return Response('Select an available person.', status=400)
        try:
            store().add_vehicle_person(vehicle_id, person['id'], person['full_name'],
                                       request.form.get('relationship'), request.form.get('notes'))
        except (ValueError, sqlite3.IntegrityError) as exc:
            return Response(str(exc), status=400)
        return redirect(url_for('automotive.vehicle_detail', vehicle_id=vehicle_id))

    @blueprint.post('/automotive/vehicles/<int:vehicle_id>/people/<int:link_id>/delete')
    def delete_vehicle_person(vehicle_id, link_id):
        try:
            store().delete_vehicle_person(vehicle_id, link_id)
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
