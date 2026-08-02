"""Repair the accidental reintroduction of pre-refactor application blocks."""

from pathlib import Path


APP_PATH = Path('app.py')
ROADMAP_PATH = Path('app_support/roadmap.py')
SOCIAL_PROFILES_PATH = Path('routes/social_profiles.py')


SOCIAL_ROUTE_REGISTRATION = """

from routes.social_auth import register_social_auth_routes
from routes.social_profiles import register_social_profile_routes
from routes.social_profile_resources import register_social_profile_resource_routes
from routes.social_profile_identity import register_social_profile_identity_routes
from routes.social_profile_transfer import register_social_profile_transfer_routes

globals().update(register_social_auth_routes(app, lambda: globals()))
globals().update(register_social_profile_routes(app, lambda: globals()))
globals().update(register_social_profile_resource_routes(app, lambda: globals()))
globals().update(register_social_profile_identity_routes(app, lambda: globals()))
globals().update(register_social_profile_transfer_routes(app, lambda: globals()))
"""


AUTOMOTIVE_ROADMAP = """    {
        'title': 'Automotive diagnostics',
        'items': [
            {'title': 'Offline VIN, DTC, vehicle, and workshop records', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Automotive pages now provide local WMI/VIN and DTC lookups, saved vehicles, translation snapshots, report exports, and SQLite persistence.', 'description': 'Provide the local automotive data and reporting foundation without online lookups.'},
            {'title': 'Staged automotive database imports', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'VIN and DTC uploads are checksum-tracked, staged for row review, selectively approved in one transaction, or discarded.', 'description': 'Review parsed VIN and DTC records before they affect live lookup results.'},
            {'title': 'Vehicle and module identity inventory', 'priority': 'High', 'priority_class': 'danger', 'status': 'Done', 'completed_note': 'Vehicle pages retain chassis, frame, body, engine, transmission, registration, fleet, and legacy identifiers plus ECU/module identities, calibration data, and module-reported VIN match warnings.', 'description': 'Keep one canonical vehicle VIN while tracking physical identifiers and every control-module identity observation.'},
            {'title': 'Simulated OBD-II reader', 'priority': 'High', 'priority_class': 'danger', 'description': 'Build an ELM327-style simulator for connection, VIN, current/pending/permanent DTC, freeze-frame, readiness, live-PID, timeout, malformed-response, and clear-code scenarios before hardware arrives.'},
            {'title': 'Transport-neutral OBD architecture', 'priority': 'High', 'priority_class': 'danger', 'description': 'Define shared discovery, connect, command, timeout, cancellation, and disconnect contracts for simulated, USB serial, Bluetooth Classic, BLE, and Wi-Fi readers.'},
            {'title': 'Immutable diagnostic sessions', 'priority': 'High', 'priority_class': 'danger', 'description': 'Persist adapter identity, protocol, vehicle VIN, raw responses, categorized DTCs, freeze-frame values, readiness monitors, PID samples, warnings, and before/after state.'},
            {'title': 'Automotive diagnostics workspace', 'priority': 'High', 'priority_class': 'danger', 'description': 'Add reader and vehicle selection, connection state, quick/full scans, readiness, freeze-frame, live data, saved sessions, and create-report actions.'},
            {'title': 'USB serial ELM327 and STN support', 'priority': 'High', 'priority_class': 'danger', 'description': 'Discover ports, probe baud rates, initialize supported adapters, detect protocols, enforce bounded commands, cancel work, and retain raw exchanges.'},
            {'title': 'Bluetooth Classic and Wi-Fi OBD transports', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Support paired RFCOMM/SPP readers and configured TCP readers through the same diagnostic-session service.'},
            {'title': 'Adapter-specific Bluetooth LE plugins', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Add BLE GATT transports as explicit adapter plugins rather than treating every BLE reader as a generic serial device.'},
            {'title': 'Safe DTC clearing workflow', 'priority': 'High', 'priority_class': 'danger', 'description': 'Require a saved pre-clear scan and explicit warning, record the action, explain readiness reset, and automatically capture a post-clear scan.'},
            {'title': 'Full downloadable VIN decoder dataset', 'priority': 'High', 'priority_class': 'danger', 'description': 'Add a versioned authoritative dataset adapter for make, model, year, body, engine, plant, restraint, and manufacturer-specific VDS decoding while keeping runtime lookup offline.'},
            {'title': 'Versioned DTC definition library', 'priority': 'High', 'priority_class': 'danger', 'description': 'Preserve multiple sourced definitions and translations by make, model, year, engine, module, language, source page, confidence, and superseded state instead of replacing code/make pairs.'},
            {'title': 'PDF provenance and OCR review', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Retain original documents, page numbers, extracted context, confidence, and corrections, with optional OCR staging for image-only diagnostic manuals.'},
            {'title': 'Professional workshop PDF reports', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Add Unicode, wrapping, pagination, DTC tables, branding, dates, diagnostic sessions, before/after results, parts, labor, recommendations, attachments, and signatures.'},
            {'title': 'Report revisions and finalization', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Support draft, final, amended, and void states with revision history, finalized-by identity, and immutable finalized records.'},
            {'title': 'Automotive backup and restore', 'priority': 'Medium', 'priority_class': 'warning', 'description': 'Export, validate, and restore the complete automotive database, source documents, vehicle histories, sessions, reports, and import provenance.'},
            {'title': 'Automotive route, browser, and hardware tests', 'priority': 'High', 'priority_class': 'danger', 'description': 'Cover authentication, CSRF, uploads, redirects, corrupt PDFs, migrations, rollback, reader simulation, diagnostic sessions, report downloads, accessibility, and mobile layouts.'},
        ],
    },
"""


def replace_between(source, start_marker, end_marker, replacement):
    start = source.find(start_marker)
    if start < 0:
        raise RuntimeError(f'Missing start marker: {start_marker!r}')
    end = source.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f'Missing end marker: {end_marker!r}')
    return source[:start] + replacement + source[end:]


def repair_app():
    source = APP_PATH.read_text(encoding='utf-8')
    if '\nROADMAP_SECTIONS = [' in source:
        source = replace_between(
            source,
            '\nROADMAP_SECTIONS = [',
            '\n\nfrom app_support.bluetooth_actions import (',
            '\n\nfrom app_support.roadmap import ROADMAP_SECTIONS, remaining_roadmap_items',
        )
    if "\n@app.route('/setup', methods=['GET', 'POST'])" in source:
        source = replace_between(
            source,
            "\n@app.route('/setup', methods=['GET', 'POST'])",
            "\n\napp.config['TRAIN_CONTROLLER_EVIDENCE_RECORDER']",
            SOCIAL_ROUTE_REGISTRATION,
        )
    if '@app.route' in source:
        raise RuntimeError('Direct route decorators remain in app.py after repair')
    APP_PATH.write_text(source, encoding='utf-8')


def repair_profile_cleanup():
    source = SOCIAL_PROFILES_PATH.read_text(encoding='utf-8')
    marker = """        for attachment in profile.get('attachments', []):
            attachment_path = os.path.join(SOCIAL_PROFILE_ATTACHMENT_DIR, attachment.get('filename', ''))
            if os.path.isfile(attachment_path):
                os.unlink(attachment_path)
"""
    addition = marker + """        for collection, directory in (
            (profile.get('identity_documents', []), SOCIAL_PROFILE_ID_DIR),
            (profile.get('signatures', []), SOCIAL_PROFILE_SIGNATURE_DIR),
        ):
            for item in collection:
                path = os.path.join(directory, item.get('filename', ''))
                if os.path.isfile(path):
                    os.unlink(path)
"""
    if 'SOCIAL_PROFILE_ID_DIR' not in source:
        if marker not in source:
            raise RuntimeError('Unable to locate profile attachment cleanup')
        source = source.replace(marker, addition, 1)
        SOCIAL_PROFILES_PATH.write_text(source, encoding='utf-8')


def repair_roadmap():
    source = ROADMAP_PATH.read_text(encoding='utf-8')
    if "'title': 'Automotive diagnostics'" not in source:
        marker = """    {
        'title': 'Train Controller integration',
"""
        if marker not in source:
            raise RuntimeError('Unable to locate Train Controller roadmap section')
        source = source.replace(marker, AUTOMOTIVE_ROADMAP + marker, 1)
        ROADMAP_PATH.write_text(source, encoding='utf-8')


def main():
    repair_app()
    repair_profile_cleanup()
    repair_roadmap()


if __name__ == '__main__':
    main()
