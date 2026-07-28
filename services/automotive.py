"""Offline VIN, diagnostic-code, vehicle, and workshop report storage."""

import csv
import io
import json
import os
import re
import sqlite3
import time
import hashlib
from datetime import datetime


VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
DTC_RE = re.compile(r"\b([PBCU][0-9A-F]{4})\b", re.I)
TRANSLITERATION = {**{str(i): i for i in range(10)}, **dict(zip("ABCDEFGH", range(1, 9))),
                   **dict(zip("JKLMNPR", (1, 2, 3, 4, 5, 7, 9))), **dict(zip("STUVWXYZ", (2, 3, 4, 5, 6, 7, 8, 9)))}
WEIGHTS = (8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2)
MODEL_YEAR_CODES = 'ABCDEFGHJKLMNPRSTVWXY123456789'
BUNDLED_WMI_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'automotive', 'wmi_db.csv')


class AutomotiveStore:
    """SQLite-backed local automotive data store."""

    def __init__(self, path=None):
        self.path = path or os.environ.get('MOBILE_ROUTER_AUTOMOTIVE_DB') or os.path.join(
            os.environ.get('MOBILE_ROUTER_DATA_DIR', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')),
            'automotive.sqlite3',
        )
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._initialize()

    def connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys = ON')
        connection.execute('PRAGMA busy_timeout = 5000')
        return connection

    def _initialize(self):
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS vin_data (wmi TEXT PRIMARY KEY, manufacturer TEXT, country TEXT, details TEXT);
                CREATE TABLE IF NOT EXISTS dtc (code TEXT NOT NULL, make TEXT NOT NULL DEFAULT '', description TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT '', PRIMARY KEY(code, make));
                CREATE TABLE IF NOT EXISTS vehicles (id INTEGER PRIMARY KEY, vin TEXT UNIQUE NOT NULL, nickname TEXT,
                    year TEXT, make TEXT, model TEXT, notes TEXT, created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS workshop_reports (id INTEGER PRIMARY KEY, vehicle_id INTEGER, title TEXT NOT NULL,
                    odometer TEXT, codes TEXT NOT NULL DEFAULT '[]', work_done TEXT, technician TEXT, notes TEXT,
                    created_at REAL NOT NULL, FOREIGN KEY(vehicle_id) REFERENCES vehicles(id));
                CREATE TABLE IF NOT EXISTS automotive_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS import_batches (id INTEGER PRIMARY KEY, kind TEXT NOT NULL, source TEXT NOT NULL,
                    sha256 TEXT NOT NULL, record_count INTEGER NOT NULL, imported_at REAL NOT NULL,
                    UNIQUE(kind, sha256));
                CREATE TABLE IF NOT EXISTS pending_imports (id INTEGER PRIMARY KEY, kind TEXT NOT NULL, source TEXT NOT NULL,
                    sha256 TEXT NOT NULL, records TEXT NOT NULL, created_at REAL NOT NULL,
                    UNIQUE(kind, sha256));
                CREATE TABLE IF NOT EXISTS vehicle_identifiers (id INTEGER PRIMARY KEY, vehicle_id INTEGER NOT NULL,
                    identifier_type TEXT NOT NULL, value TEXT NOT NULL, source TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
                    verified INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL,
                    FOREIGN KEY(vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE);
                CREATE TABLE IF NOT EXISTS vehicle_modules (id INTEGER PRIMARY KEY, vehicle_id INTEGER NOT NULL,
                    module_name TEXT NOT NULL, module_address TEXT NOT NULL DEFAULT '', reported_vin TEXT NOT NULL DEFAULT '',
                    manufacturer TEXT NOT NULL DEFAULT '', part_number TEXT NOT NULL DEFAULT '', hardware_number TEXT NOT NULL DEFAULT '',
                    software_number TEXT NOT NULL DEFAULT '', serial_number TEXT NOT NULL DEFAULT '', calibration_id TEXT NOT NULL DEFAULT '',
                    cvn TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL,
                    FOREIGN KEY(vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE);
                CREATE TABLE IF NOT EXISTS diagnostic_capabilities (id INTEGER PRIMARY KEY, model TEXT NOT NULL,
                    year_start INTEGER, year_end INTEGER, system TEXT NOT NULL, subitem TEXT NOT NULL DEFAULT '',
                    function TEXT NOT NULL, subfunction TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT '',
                    UNIQUE(model,year_start,year_end,system,subitem,function,subfunction));
            """)
            columns = {row['name'] for row in db.execute('PRAGMA table_info(vehicles)')}
            if 'archived_at' not in columns:
                db.execute('ALTER TABLE vehicles ADD COLUMN archived_at REAL')
            report_columns = {row['name'] for row in db.execute('PRAGMA table_info(workshop_reports)')}
            if 'code_snapshot' not in report_columns:
                db.execute("ALTER TABLE workshop_reports ADD COLUMN code_snapshot TEXT NOT NULL DEFAULT '{}'")
            if 'updated_at' not in report_columns:
                db.execute('ALTER TABLE workshop_reports ADD COLUMN updated_at REAL')
            db.execute("INSERT OR REPLACE INTO automotive_meta VALUES ('schema_version', '5')")
            self._seed_bundled_wmi(db)

    @staticmethod
    def _seed_bundled_wmi(db):
        """Add the small shipped WMI baseline without replacing user imports."""
        if not os.path.isfile(BUNDLED_WMI_PATH):
            return
        with open(BUNDLED_WMI_PATH, encoding='utf-8-sig', newline='') as handle:
            for row in csv.DictReader(handle):
                wmi = str(row.get('wmi') or '').strip().upper()
                if re.fullmatch(r'[A-HJ-NPR-Z0-9]{3}', wmi):
                    details = {key: value for key, value in row.items() if key not in {'wmi', 'manufacturer', 'country'} and value}
                    db.execute('INSERT OR IGNORE INTO vin_data VALUES (?,?,?,?)',
                               (wmi, row.get('manufacturer', '').strip(), row.get('country', '').strip(), json.dumps(details)))

    @staticmethod
    def model_year(code, reference_year=None):
        """Resolve the repeating VIN year code to the most plausible past year."""
        code = str(code or '').upper()
        if code not in MODEL_YEAR_CODES:
            return None
        reference_year = reference_year or datetime.now().year
        base = 1980 + MODEL_YEAR_CODES.index(code)
        candidates = [base + (30 * cycle) for cycle in range(4)]
        eligible = [year for year in candidates if year <= reference_year + 1]
        return max(eligible) if eligible else base

    @staticmethod
    def digest(content):
        return hashlib.sha256(content).hexdigest()

    def record_import(self, kind, source, content, count):
        checksum = self.digest(content)
        with self.connect() as db:
            try:
                cursor = db.execute(
                    'INSERT INTO import_batches(kind,source,sha256,record_count,imported_at) VALUES(?,?,?,?,?)',
                    (kind, source or 'upload', checksum, count, time.time()),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError('This exact database file has already been imported.') from exc
        return cursor.lastrowid

    def imports(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM import_batches ORDER BY imported_at DESC')]

    def stage_import(self, kind, source, content, records):
        if kind not in {'vin', 'dtc', 'capability'}:
            raise ValueError('Unsupported automotive import type.')
        if not records:
            raise ValueError('No valid records were found in this file.')
        checksum = self.digest(content)
        with self.connect() as db:
            if db.execute('SELECT 1 FROM import_batches WHERE kind=? AND sha256=?', (kind, checksum)).fetchone():
                raise ValueError('This exact database file has already been imported.')
            try:
                cursor = db.execute(
                    'INSERT INTO pending_imports(kind,source,sha256,records,created_at) VALUES(?,?,?,?,?)',
                    (kind, source or 'upload', checksum, json.dumps(records), time.time()),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError('This file is already waiting for review.') from exc
        return cursor.lastrowid

    def pending_import(self, pending_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM pending_imports WHERE id=?', (pending_id,)).fetchone()
        if not row:
            return None
        result = dict(row); result['records'] = json.loads(result['records'])
        return result

    def pending_imports(self):
        with self.connect() as db:
            rows = db.execute('SELECT id,kind,source,sha256,created_at,records FROM pending_imports ORDER BY created_at DESC').fetchall()
        result = []
        for row in rows:
            item = dict(row); item['record_count'] = len(json.loads(item.pop('records'))); result.append(item)
        return result

    def apply_pending_import(self, pending_id, selected=None):
        pending = self.pending_import(pending_id)
        if not pending:
            raise ValueError('Pending import not found.')
        selected = set(str(item) for item in selected) if selected is not None else None
        records = [record for index, record in enumerate(pending['records']) if selected is None or str(index) in selected]
        if not records:
            raise ValueError('Select at least one record to import.')
        with self.connect() as db:
            if db.execute('SELECT 1 FROM import_batches WHERE kind=? AND sha256=?', (pending['kind'], pending['sha256'])).fetchone():
                raise ValueError('This exact database file has already been imported.')
            if pending['kind'] == 'vin':
                db.executemany('INSERT OR REPLACE INTO vin_data VALUES (?,?,?,?)', [
                    (row['wmi'], row.get('manufacturer', ''), row.get('country', ''), json.dumps(row.get('details', {}))) for row in records
                ])
            elif pending['kind'] == 'dtc':
                db.executemany('INSERT OR REPLACE INTO dtc VALUES (?,?,?,?)', [
                    (row['code'], row.get('make', ''), row['description'], pending['source']) for row in records
                ])
            else:
                db.executemany(
                    'INSERT OR REPLACE INTO diagnostic_capabilities(model,year_start,year_end,system,subitem,function,subfunction,source) VALUES(?,?,?,?,?,?,?,?)',
                    [(row['model'], row.get('year_start'), row.get('year_end'), row['system'], row.get('subitem', ''),
                      row['function'], row.get('subfunction', ''), pending['source']) for row in records],
                )
            cursor = db.execute('INSERT INTO import_batches(kind,source,sha256,record_count,imported_at) VALUES(?,?,?,?,?)',
                                (pending['kind'], pending['source'], pending['sha256'], len(records), time.time()))
            db.execute('DELETE FROM pending_imports WHERE id=?', (pending_id,))
        return cursor.lastrowid, len(records)

    def discard_pending_import(self, pending_id):
        with self.connect() as db:
            cursor = db.execute('DELETE FROM pending_imports WHERE id=?', (pending_id,))
        if not cursor.rowcount:
            raise ValueError('Pending import not found.')

    @staticmethod
    def normalize_vin(value):
        return re.sub(r"[\s-]", "", str(value or '')).upper()

    @classmethod
    def validate_vin(cls, value):
        vin = cls.normalize_vin(value)
        if not VIN_RE.fullmatch(vin):
            return vin, False, 'A VIN must contain 17 letters/digits and cannot contain I, O, or Q.'
        total = sum(TRANSLITERATION[c] * weight for c, weight in zip(vin, WEIGHTS))
        expected = 'X' if total % 11 == 10 else str(total % 11)
        return vin, vin[8] == expected, None

    def lookup_vin(self, value):
        vin, checksum_valid, error = self.validate_vin(value)
        if error:
            raise ValueError(error)
        with self.connect() as db:
            row = db.execute('SELECT * FROM vin_data WHERE wmi = ?', (vin[:3],)).fetchone()
        decoded = dict(row) if row else {}
        if decoded.get('details'):
            decoded.update(json.loads(decoded.pop('details')))
        decoded.update({'vin': vin, 'wmi': vin[:3], 'model_year_code': vin[9], 'plant_code': vin[10],
                        'model_year': self.model_year(vin[9]), 'serial_number': vin[11:],
                        'checksum_valid': checksum_valid, 'database_match': bool(row)})
        return decoded

    def import_vin_csv(self, content):
        records = self.parse_vin_csv(content)
        with self.connect() as db:
            db.executemany('INSERT OR REPLACE INTO vin_data VALUES (?,?,?,?)', [(r['wmi'], r['manufacturer'], r['country'], json.dumps(r['details'])) for r in records])
        return len(records)

    def parse_vin_csv(self, content):
        reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig', errors='replace')))
        records = []
        for raw in reader:
            row = {str(k or '').strip().lower().replace(' ', '_'): str(v or '').strip() for k, v in raw.items()}
            wmi = (row.get('wmi') or row.get('wmi_code') or row.get('prefix') or '')[:3].upper()
            if not re.fullmatch(r'[A-HJ-NPR-Z0-9]{3}', wmi):
                continue
            manufacturer = row.get('manufacturer') or row.get('make') or row.get('manufacturer_name') or ''
            country = row.get('country') or row.get('country_name') or ''
            extras = {k: v for k, v in row.items() if k not in {'wmi', 'wmi_code', 'prefix', 'manufacturer', 'make', 'manufacturer_name', 'country', 'country_name'} and v}
            records.append({'wmi': wmi, 'manufacturer': manufacturer, 'country': country, 'details': extras})
        return records

    def parse_dtc_text(self, text, make=''):
        records = {}
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for index, line in enumerate(lines):
            match = DTC_RE.search(line)
            if not match:
                continue
            code = match.group(1).upper()
            description = re.sub(r'^.*?\b' + re.escape(match.group(1)) + r'\b\s*[-:–—]?\s*', '', line, flags=re.I).strip()
            if not description and index + 1 < len(lines) and not DTC_RE.search(lines[index + 1]):
                description = lines[index + 1]
            if description:
                records[code] = {'code': code, 'make': make.strip(), 'description': description}
        return list(records.values())

    def import_dtc_text(self, text, make='', source='upload'):
        records = self.parse_dtc_text(text, make)
        with self.connect() as db:
            for record in records:
                db.execute('INSERT OR REPLACE INTO dtc VALUES (?, ?, ?, ?)', (record['code'], record['make'], record['description'], source))
        return len(records)

    def parse_dtc_csv(self, content, make=''):
        reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig', errors='replace')))
        records = []
        for raw in reader:
            row = {str(k or '').strip().lower(): str(v or '').strip() for k, v in raw.items()}
            code = (row.get('code') or row.get('dtc') or '').upper()
            description = row.get('description') or row.get('meaning') or row.get('translation') or ''
            if DTC_RE.fullmatch(code) and description:
                records.append({'code': code, 'make': row.get('make') or make.strip(), 'description': description})
        return records

    def import_dtc_csv(self, content, make='', source='upload'):
        records = self.parse_dtc_csv(content, make)
        with self.connect() as db:
            db.executemany('INSERT OR REPLACE INTO dtc VALUES (?,?,?,?)', [(r['code'], r['make'], r['description'], source) for r in records])
        return len(records)

    @staticmethod
    def _year_range(value):
        years = [int(item) for item in re.findall(r'\b(?:19|20)\d{2}\b', str(value or ''))]
        return (min(years), max(years)) if years else (None, None)

    def parse_capability_csv(self, content):
        text = content.decode('utf-8-sig', errors='replace')
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=',\t;')
        except csv.Error:
            dialect = csv.excel_tab if '\t' in text.partition('\n')[0] else csv.excel
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        records = []
        for raw in reader:
            row = {str(key or '').strip().lower(): str(value or '').strip() for key, value in raw.items()}
            model, system = row.get('model', ''), row.get('system', '')
            if not model or not system:
                continue
            year_start, year_end = self._year_range(row.get('year'))
            functions = [item.strip() for item in row.get('function', '').split(';') if item.strip()]
            for function in functions:
                records.append({'model': model, 'year_start': year_start, 'year_end': year_end, 'system': system,
                                'subitem': row.get('subitem', ''), 'function': function,
                                'subfunction': row.get('subfunction', '')})
        return records

    def diagnostic_capabilities(self, model='', year=None, system=''):
        clauses, parameters = [], []
        if model:
            clauses.append('LOWER(model) LIKE ?'); parameters.append(f'%{model.lower()}%')
        if year:
            clauses.append('(year_start IS NULL OR year_start <= ?) AND (year_end IS NULL OR year_end >= ?)')
            parameters.extend([int(year), int(year)])
        if system:
            clauses.append('LOWER(system) = ?'); parameters.append(system.lower())
        query = 'SELECT * FROM diagnostic_capabilities'
        if clauses:
            query += ' WHERE ' + ' AND '.join(clauses)
        query += ' ORDER BY model,year_start,system,subitem,function,subfunction'
        with self.connect() as db:
            return [dict(row) for row in db.execute(query, parameters)]

    def lookup_code(self, code, make=''):
        code = str(code or '').strip().upper()
        with self.connect() as db:
            rows = db.execute('SELECT * FROM dtc WHERE code = ? ORDER BY CASE WHEN make = ? THEN 0 WHEN make = \'\' THEN 1 ELSE 2 END', (code, make)).fetchall()
        return [dict(row) for row in rows]

    def save_vehicle(self, values):
        decoded = self.lookup_vin(values.get('vin'))
        with self.connect() as db:
            cursor = db.execute('INSERT INTO vehicles(vin,nickname,year,make,model,notes,created_at) VALUES(?,?,?,?,?,?,?)',
                (decoded['vin'], values.get('nickname', '').strip(), values.get('year', '').strip(), values.get('make', '').strip(),
                 values.get('model', '').strip(), values.get('notes', '').strip(), time.time()))
        return cursor.lastrowid

    def vehicles(self, include_archived=False):
        with self.connect() as db:
            query = 'SELECT * FROM vehicles' + ('' if include_archived else ' WHERE archived_at IS NULL') + ' ORDER BY created_at DESC'
            return [dict(row) for row in db.execute(query)]

    def vehicle(self, vehicle_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM vehicles WHERE id = ?', (vehicle_id,)).fetchone()
        return dict(row) if row else None

    def update_vehicle(self, vehicle_id, values):
        decoded = self.lookup_vin(values.get('vin'))
        with self.connect() as db:
            cursor = db.execute(
                'UPDATE vehicles SET vin=?,nickname=?,year=?,make=?,model=?,notes=? WHERE id=?',
                (decoded['vin'], values.get('nickname', '').strip(), values.get('year', '').strip(),
                 values.get('make', '').strip(), values.get('model', '').strip(), values.get('notes', '').strip(), vehicle_id),
            )
        if not cursor.rowcount:
            raise ValueError('Vehicle not found.')

    def archive_vehicle(self, vehicle_id):
        with self.connect() as db:
            cursor = db.execute('UPDATE vehicles SET archived_at=? WHERE id=?', (time.time(), vehicle_id))
        if not cursor.rowcount:
            raise ValueError('Vehicle not found.')

    def vehicle_identifiers(self, vehicle_id):
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                'SELECT * FROM vehicle_identifiers WHERE vehicle_id=? ORDER BY created_at,id', (vehicle_id,),
            )]

    def add_vehicle_identifier(self, vehicle_id, values):
        if not self.vehicle(vehicle_id):
            raise ValueError('Vehicle not found.')
        identifier_type = str(values.get('identifier_type') or '').strip().lower()
        value = str(values.get('value') or '').strip().upper()
        allowed = {'chassis_number', 'frame_number', 'body_number', 'engine_serial', 'transmission_serial',
                   'registration', 'fleet_number', 'manufacturer_serial', 'legacy_vehicle_number', 'other'}
        if identifier_type not in allowed:
            raise ValueError('Select a valid identifier type.')
        if not value:
            raise ValueError('Identifier value is required.')
        with self.connect() as db:
            cursor = db.execute(
                'INSERT INTO vehicle_identifiers(vehicle_id,identifier_type,value,source,notes,verified,created_at) VALUES(?,?,?,?,?,?,?)',
                (vehicle_id, identifier_type, value, str(values.get('source') or '').strip()[:200],
                 str(values.get('notes') or '').strip(), 1 if values.get('verified') else 0, time.time()),
            )
        return cursor.lastrowid

    def delete_vehicle_identifier(self, vehicle_id, identifier_id):
        with self.connect() as db:
            cursor = db.execute('DELETE FROM vehicle_identifiers WHERE id=? AND vehicle_id=?', (identifier_id, vehicle_id))
        if not cursor.rowcount:
            raise ValueError('Vehicle identifier not found.')

    def vehicle_modules(self, vehicle_id):
        vehicle = self.vehicle(vehicle_id)
        if not vehicle:
            return []
        with self.connect() as db:
            rows = [dict(row) for row in db.execute('SELECT * FROM vehicle_modules WHERE vehicle_id=? ORDER BY module_name,id', (vehicle_id,))]
        for row in rows:
            reported = self.normalize_vin(row.get('reported_vin'))
            row['vin_match'] = None if not reported else reported == vehicle['vin']
        return rows

    def add_vehicle_module(self, vehicle_id, values):
        if not self.vehicle(vehicle_id):
            raise ValueError('Vehicle not found.')
        name = str(values.get('module_name') or '').strip()
        if not name:
            raise ValueError('Module name is required.')
        reported_vin = self.normalize_vin(values.get('reported_vin'))
        if reported_vin and not VIN_RE.fullmatch(reported_vin):
            raise ValueError('A module-reported VIN must be a valid 17-character VIN.')
        fields = ('module_address', 'manufacturer', 'part_number', 'hardware_number', 'software_number',
                  'serial_number', 'calibration_id', 'cvn', 'notes')
        cleaned = [str(values.get(field) or '').strip() for field in fields]
        with self.connect() as db:
            cursor = db.execute(
                'INSERT INTO vehicle_modules(vehicle_id,module_name,module_address,reported_vin,manufacturer,part_number,hardware_number,software_number,serial_number,calibration_id,cvn,notes,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (vehicle_id, name[:200], cleaned[0][:100], reported_vin, cleaned[1][:200], cleaned[2][:200], cleaned[3][:200],
                 cleaned[4][:200], cleaned[5][:200], cleaned[6][:200], cleaned[7][:200], cleaned[8], time.time()),
            )
        return cursor.lastrowid

    def delete_vehicle_module(self, vehicle_id, module_id):
        with self.connect() as db:
            cursor = db.execute('DELETE FROM vehicle_modules WHERE id=? AND vehicle_id=?', (module_id, vehicle_id))
        if not cursor.rowcount:
            raise ValueError('Vehicle module not found.')

    def save_report(self, values):
        codes = [code.strip().upper() for code in re.split(r'[,\s]+', values.get('codes', '')) if code.strip()]
        invalid = [code for code in codes if not DTC_RE.fullmatch(code)]
        if invalid:
            raise ValueError(f"Invalid diagnostic code: {invalid[0]}")
        vehicle_id = values.get('vehicle_id') or None
        vehicle = self.vehicle(vehicle_id) if vehicle_id else None
        if vehicle_id and not vehicle:
            raise ValueError('Vehicle not found.')
        make = vehicle.get('make', '') if vehicle else ''
        snapshot = {code: self.lookup_code(code, make) for code in codes}
        with self.connect() as db:
            cursor = db.execute('INSERT INTO workshop_reports(vehicle_id,title,odometer,codes,work_done,technician,notes,created_at,updated_at,code_snapshot) VALUES(?,?,?,?,?,?,?,?,?,?)',
                (vehicle_id, values.get('title', '').strip()[:200] or 'Diagnostic report', values.get('odometer', '').strip()[:50],
                 json.dumps(codes), values.get('work_done', '').strip(), values.get('technician', '').strip()[:200],
                 values.get('notes', '').strip(), time.time(), time.time(), json.dumps(snapshot)))
        return cursor.lastrowid

    def reports(self):
        with self.connect() as db:
            rows = db.execute('SELECT r.*, v.vin, v.nickname, v.make, v.model FROM workshop_reports r LEFT JOIN vehicles v ON v.id=r.vehicle_id ORDER BY r.created_at DESC').fetchall()
        result = [dict(row) for row in rows]
        for row in result:
            row['codes'] = json.loads(row['codes'])
            row['code_details'] = json.loads(row.get('code_snapshot') or '{}')
            if not row['code_details'] and row['codes']:
                # Compatibility for reports created before definition snapshots were introduced.
                row['code_details'] = {code: self.lookup_code(code, row.get('make') or '') for code in row['codes']}
        return result

    def report(self, report_id):
        return next((row for row in self.reports() if row['id'] == report_id), None)


def simple_pdf(title, lines):
    """Create a dependency-free, printable PDF for a workshop report."""
    safe = lambda value: str(value).encode('ascii', 'replace').decode().replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    commands = ['BT', '/F1 16 Tf', '50 790 Td', f'({safe(title)}) Tj', '/F1 10 Tf']
    for line in lines:
        commands.extend(['0 -16 Td', f'({safe(line)[:110]}) Tj'])
    commands.append('ET')
    stream = '\n'.join(commands).encode()
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>',
               b'<< /Length %d >>\nstream\n' % len(stream) + stream + b'\nendstream', b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    output = bytearray(b'%PDF-1.4\n'); offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(output)); output.extend(f'{number} 0 obj\n'.encode() + obj + b'\nendobj\n')
    xref = len(output); output.extend(f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode())
    output.extend(b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets[1:]))
    output.extend(f'trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF'.encode())
    return bytes(output)
