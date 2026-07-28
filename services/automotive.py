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
DTC_IDENTITY_FIELDS = ('code', 'category', 'description', 'scope', 'make', 'model', 'year_start', 'year_end', 'module',
                       'engine', 'transmission', 'market', 'protocol', 'language', 'lookup_priority', 'is_override',
                       'confidence', 'status', 'applicability_notes', 'notes')


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
                CREATE TABLE IF NOT EXISTS dtc_definitions (id INTEGER PRIMARY KEY, code TEXT NOT NULL, category TEXT NOT NULL,
                    description TEXT NOT NULL, scope TEXT NOT NULL DEFAULT 'generic', make TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL DEFAULT '', year_start INTEGER, year_end INTEGER, module TEXT NOT NULL DEFAULT '',
                    engine TEXT NOT NULL DEFAULT '', transmission TEXT NOT NULL DEFAULT '', market TEXT NOT NULL DEFAULT '',
                    protocol TEXT NOT NULL DEFAULT '', language TEXT NOT NULL DEFAULT 'en', lookup_priority INTEGER NOT NULL DEFAULT 0,
                    is_override INTEGER NOT NULL DEFAULT 0, source_name TEXT NOT NULL DEFAULT '', source_url TEXT NOT NULL DEFAULT '',
                    source_version TEXT NOT NULL DEFAULT '', retrieved_at TEXT NOT NULL DEFAULT '', license TEXT NOT NULL DEFAULT '',
                    source_sha256 TEXT NOT NULL DEFAULT '', source_line INTEGER, confidence TEXT NOT NULL DEFAULT 'unverified',
                    status TEXT NOT NULL DEFAULT 'active', applicability_notes TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_dtc_definitions_code ON dtc_definitions(code);
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
                CREATE TABLE IF NOT EXISTS vehicle_people (id INTEGER PRIMARY KEY, vehicle_id INTEGER NOT NULL,
                    person_id TEXT NOT NULL, person_name TEXT NOT NULL, relationship TEXT NOT NULL DEFAULT 'associated',
                    notes TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL,
                    FOREIGN KEY(vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE,
                    UNIQUE(vehicle_id,person_id,relationship));
            """)
            columns = {row['name'] for row in db.execute('PRAGMA table_info(vehicles)')}
            if 'archived_at' not in columns:
                db.execute('ALTER TABLE vehicles ADD COLUMN archived_at REAL')
            report_columns = {row['name'] for row in db.execute('PRAGMA table_info(workshop_reports)')}
            if 'code_snapshot' not in report_columns:
                db.execute("ALTER TABLE workshop_reports ADD COLUMN code_snapshot TEXT NOT NULL DEFAULT '{}'")
            if 'updated_at' not in report_columns:
                db.execute('ALTER TABLE workshop_reports ADD COLUMN updated_at REAL')
            pending_columns = {row['name'] for row in db.execute('PRAGMA table_info(pending_imports)')}
            if 'excluded' not in pending_columns:
                db.execute("ALTER TABLE pending_imports ADD COLUMN excluded TEXT NOT NULL DEFAULT '[]'")
            db.execute('DROP TABLE IF EXISTS diagnostic_capabilities')
            db.execute("DELETE FROM pending_imports WHERE kind = 'capability'")
            db.execute("DELETE FROM import_batches WHERE kind = 'capability'")
            legacy_dtc = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='dtc'").fetchone()
            if legacy_dtc:
                db.execute("""INSERT INTO dtc_definitions(code,category,description,scope,make,source_name,status,created_at)
                    SELECT code,SUBSTR(code,1,1),description,CASE WHEN make='' THEN 'generic' ELSE 'manufacturer' END,
                    make,source,'active',? FROM dtc""", (time.time(),))
                db.execute('DROP TABLE dtc')
            dtc_columns = {row['name'] for row in db.execute('PRAGMA table_info(dtc_definitions)')}
            if 'definition_key' not in dtc_columns:
                db.execute("ALTER TABLE dtc_definitions ADD COLUMN definition_key TEXT NOT NULL DEFAULT ''")
            schema_row = db.execute("SELECT value FROM automotive_meta WHERE key='schema_version'").fetchone()
            if not schema_row or schema_row['value'] != '10':
                self._deduplicate_dtc_definitions(db)
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_dtc_definition_key ON dtc_definitions(definition_key) WHERE definition_key<>''")
            db.execute("INSERT OR REPLACE INTO automotive_meta VALUES ('schema_version', '10')")
            self._seed_bundled_wmi(db)

    @staticmethod
    def _definition_key(record):
        """Fingerprint definition content while deliberately ignoring import provenance."""
        empty_defaults = {'language': 'en', 'confidence': 'unverified', 'status': 'active'}
        normalized = []
        for field in DTC_IDENTITY_FIELDS:
            value = record.get(field)
            if value is None or value == '':
                value = empty_defaults.get(field, '')
            if isinstance(value, str):
                value = ' '.join(value.split()).casefold()
            normalized.append(value)
        return hashlib.sha256(json.dumps(normalized, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()

    @classmethod
    def _deduplicate_dtc_definitions(cls, db):
        """Remove existing semantic duplicates, retaining the oldest record and its provenance."""
        groups = {}
        for row in db.execute('SELECT * FROM dtc_definitions ORDER BY id'):
            groups.setdefault(cls._definition_key(dict(row)), []).append(row['id'])
        duplicate_ids = [row_id for ids in groups.values() for row_id in ids[1:]]
        if duplicate_ids:
            db.executemany('DELETE FROM dtc_definitions WHERE id=?', ((row_id,) for row_id in duplicate_ids))
        db.execute("UPDATE dtc_definitions SET definition_key=''")
        db.executemany('UPDATE dtc_definitions SET definition_key=? WHERE id=?',
                       ((key, ids[0]) for key, ids in groups.items()))
        return len(duplicate_ids)

    def deduplicate_dtc_definitions(self):
        """Run an on-demand duplicate cleanup and return the number removed."""
        with self.connect() as db:
            return self._deduplicate_dtc_definitions(db)

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
        if kind not in {'vin', 'dtc'}:
            raise ValueError('Unsupported automotive import type.')
        if kind == 'dtc':
            records = self._unique_dtc_records(records)
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
        result['excluded'] = [int(item) for item in json.loads(result.get('excluded') or '[]')]
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
        excluded = set(str(item) for item in pending.get('excluded', []))
        records = [record for index, record in enumerate(pending['records'])
                   if (selected is None and str(index) not in excluded) or (selected is not None and str(index) in selected)]
        if not records:
            raise ValueError('Select at least one record to import.')
        with self.connect() as db:
            if db.execute('SELECT 1 FROM import_batches WHERE kind=? AND sha256=?', (pending['kind'], pending['sha256'])).fetchone():
                raise ValueError('This exact database file has already been imported.')
            if pending['kind'] == 'vin':
                db.executemany('INSERT OR REPLACE INTO vin_data VALUES (?,?,?,?)', [
                    (row['wmi'], row.get('manufacturer', ''), row.get('country', ''), json.dumps(row.get('details', {}))) for row in records
                ])
                imported_count = len(records)
            else:
                imported_count = 0
                for row in records:
                    imported_count += self._insert_dtc_definition(db, row, pending['source'], pending['sha256'])
            cursor = db.execute('INSERT INTO import_batches(kind,source,sha256,record_count,imported_at) VALUES(?,?,?,?,?)',
                                (pending['kind'], pending['source'], pending['sha256'], imported_count, time.time()))
            db.execute('DELETE FROM pending_imports WHERE id=?', (pending_id,))
        return cursor.lastrowid, imported_count

    def update_pending_selection(self, pending_id, page_indices, selected_indices):
        pending = self.pending_import(pending_id)
        if not pending:
            raise ValueError('Pending import not found.')
        valid = {str(index) for index in range(len(pending['records']))}
        page_indices = set(str(item) for item in page_indices) & valid
        selected_indices = set(str(item) for item in selected_indices) & page_indices
        excluded = set(str(item) for item in pending.get('excluded', []))
        excluded.difference_update(page_indices)
        excluded.update(page_indices - selected_indices)
        with self.connect() as db:
            db.execute('UPDATE pending_imports SET excluded=? WHERE id=?',
                       (json.dumps(sorted(excluded, key=int)), pending_id))
        return len(pending['records']) - len(excluded)

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
                records[code] = {'code': code, 'category': code[0], 'scope': 'manufacturer' if make.strip() else 'generic',
                                 'make': make.strip(), 'description': description, 'language': 'en',
                                 'lookup_priority': 50 if make.strip() else 20, 'is_override': False,
                                 'confidence': 'unverified', 'status': 'active'}
        return list(records.values())

    def import_dtc_text(self, text, make='', source='upload'):
        records = self.parse_dtc_text(text, make)
        inserted = 0
        with self.connect() as db:
            for record in records:
                inserted += self._insert_dtc_definition(db, record, source)
        return inserted

    @staticmethod
    def _optional_int(value, minimum=None, maximum=None):
        text = str(value or '').strip()
        if not text:
            return None
        try:
            number = int(text)
        except ValueError:
            return None
        if minimum is not None and number < minimum or maximum is not None and number > maximum:
            return None
        return number

    @staticmethod
    def _truthy(value):
        return str(value or '').strip().lower() in {'1', 'true', 'yes', 'y', 'on'}

    def _normalize_dtc_row(self, raw, default_make=''):
        row = {str(k or '').strip().lower(): str(v or '').strip() for k, v in raw.items()}
        code = (row.get('code') or row.get('dtc') or '').upper()
        description = row.get('description') or row.get('definition') or row.get('meaning') or row.get('translation') or ''
        if not DTC_RE.fullmatch(code) or not description:
            return None
        scope = (row.get('scope') or row.get('definition_scope') or '').lower()
        make = row.get('make') or row.get('manufacturer') or default_make.strip()
        if make.lower() in {'generic', 'generic obd-ii', 'generic obd2', 'obd-ii', 'obd2'}:
            make = ''
        if not scope:
            scope = 'manufacturer' if make else 'generic'
        scope = {'make': 'manufacturer', 'saab': 'manufacturer'}.get(scope, scope)
        if scope not in {'generic', 'manufacturer', 'model', 'module', 'user_translation'}:
            scope = 'manufacturer' if make else 'generic'
        priority = self._optional_int(row.get('lookup_priority'))
        return {
            'code': code, 'category': code[0], 'description': description, 'scope': scope, 'make': make,
            'model': row.get('model', ''), 'year_start': self._optional_int(row.get('year_start'), 1880, 2200),
            'year_end': self._optional_int(row.get('year_end'), 1880, 2200), 'module': row.get('module', ''),
            'engine': row.get('engine', ''), 'transmission': row.get('transmission', ''), 'market': row.get('market', ''),
            'protocol': row.get('protocol', ''), 'language': row.get('language') or 'en',
            'lookup_priority': priority if priority is not None else (50 if make else 20),
            'is_override': self._truthy(row.get('is_override') or row.get('saab_specific_override')),
            'source_name': row.get('source_name', ''), 'source_url': row.get('source_url', ''),
            'source_version': row.get('source_version', ''), 'retrieved_at': row.get('retrieved_at', ''),
            'license': row.get('license', ''), 'source_sha256': row.get('source_sha256', ''),
            'source_line': self._optional_int(row.get('source_line'), 1),
            'confidence': row.get('confidence') or 'unverified', 'status': row.get('status') or 'active',
            'applicability_notes': row.get('applicability_notes') or row.get('applicability') or '',
            'notes': row.get('notes', ''),
        }

    def parse_dtc_csv(self, content, make=''):
        reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig', errors='replace')))
        records = [record for raw in reader if (record := self._normalize_dtc_row(raw, make))]
        return self._unique_dtc_records(records)

    @classmethod
    def _unique_dtc_records(cls, records):
        """Keep the first copy of each identical definition in an incoming collection."""
        unique = {}
        for record in records:
            unique.setdefault(cls._definition_key(record), record)
        return list(unique.values())

    @staticmethod
    def _insert_dtc_definition(db, record, fallback_source='upload', source_sha256=''):
        fields = ('code', 'category', 'description', 'scope', 'make', 'model', 'year_start', 'year_end', 'module', 'engine',
                  'transmission', 'market', 'protocol', 'language', 'lookup_priority', 'is_override', 'source_name',
                  'source_url', 'source_version', 'retrieved_at', 'license', 'source_sha256', 'source_line', 'confidence',
                  'status', 'applicability_notes', 'notes')
        values = [record.get(field, '') for field in fields]
        values[15] = 1 if values[15] else 0
        values[16] = values[16] or fallback_source
        values[21] = values[21] or source_sha256
        definition_key = AutomotiveStore._definition_key(dict(zip(fields, values)))
        placeholders = ','.join('?' for _ in fields)
        cursor = db.execute(
            f"INSERT OR IGNORE INTO dtc_definitions({','.join(fields)},definition_key,created_at) VALUES({placeholders},?,?)",
            values + [definition_key, time.time()],
        )
        return cursor.rowcount

    def import_dtc_csv(self, content, make='', source='upload'):
        records = self.parse_dtc_csv(content, make)
        inserted = 0
        with self.connect() as db:
            for record in records:
                inserted += self._insert_dtc_definition(db, record, source, self.digest(content))
        return inserted

    def lookup_code(self, code, make=''):
        code = str(code or '').strip().upper()
        with self.connect() as db:
            rows = db.execute("""SELECT * FROM dtc_definitions WHERE code=? AND status='active'
                ORDER BY CASE WHEN LOWER(make)=LOWER(?) AND make<>'' THEN 0 WHEN make='' THEN 1 ELSE 2 END,
                CASE scope WHEN 'module' THEN 0 WHEN 'model' THEN 1 WHEN 'manufacturer' THEN 2
                    WHEN 'user_translation' THEN 3 ELSE 4 END, lookup_priority DESC, id DESC""", (code, make)).fetchall()
        return [dict(row) for row in rows]

    def dtc_browse_facets(self, make=''):
        """Return locally available manufacturers and models for the code browser."""
        with self.connect() as db:
            manufacturers = [dict(row) for row in db.execute(
                """SELECT make, COUNT(DISTINCT code) AS code_count
                   FROM dtc_definitions WHERE status='active' AND TRIM(make)<>''
                   GROUP BY LOWER(make) ORDER BY make COLLATE NOCASE"""
            )]
            model_params = []
            model_filter = ''
            if make:
                model_filter = ' AND LOWER(make)=LOWER(?)'
                model_params.append(make)
            models = [dict(row) for row in db.execute(
                f"""SELECT model, make, COUNT(DISTINCT code) AS code_count
                    FROM dtc_definitions WHERE status='active' AND TRIM(model)<>''{model_filter}
                    GROUP BY LOWER(make), LOWER(model) ORDER BY make COLLATE NOCASE, model COLLATE NOCASE""",
                model_params,
            )]
        return {'manufacturers': manufacturers, 'models': models}

    def browse_codes(self, make='', model='', category='', query='', limit=25, offset=0):
        """Browse active local definitions, collapsing duplicate imported rows."""
        clauses = ["status='active'"]
        params = []
        if make:
            clauses.append('LOWER(make)=LOWER(?)')
            params.append(make)
        if model:
            clauses.append('LOWER(model)=LOWER(?)')
            params.append(model)
        if category:
            clauses.append('UPPER(category)=UPPER(?)')
            params.append(category)
        if query:
            clauses.append('(UPPER(code) LIKE UPPER(?) OR LOWER(description) LIKE LOWER(?))')
            params.extend([f'%{query}%', f'%{query}%'])
        where = ' AND '.join(clauses)
        grouped = f"""SELECT MIN(id) AS id, code, category, description, scope, make, model,
            year_start, year_end, module, engine, applicability_notes,
            MAX(lookup_priority) AS lookup_priority, COUNT(*) AS duplicate_count
            FROM dtc_definitions WHERE {where}
            GROUP BY UPPER(code), LOWER(make), LOWER(model), description, scope,
                year_start, year_end, LOWER(module), LOWER(engine), applicability_notes"""
        with self.connect() as db:
            total = db.execute(f'SELECT COUNT(*) FROM ({grouped})', params).fetchone()[0]
            rows = db.execute(
                grouped + " ORDER BY code, CASE WHEN make='' THEN 1 ELSE 0 END, make COLLATE NOCASE, model COLLATE NOCASE LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()
        return [dict(row) for row in rows], total

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

    def vehicle_by_vin(self, vin):
        normalized = self.normalize_vin(vin)
        with self.connect() as db:
            row = db.execute('SELECT * FROM vehicles WHERE vin=?', (normalized,)).fetchone()
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

    def vehicle_people(self, vehicle_id):
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                'SELECT * FROM vehicle_people WHERE vehicle_id=? ORDER BY relationship,person_name', (vehicle_id,),
            )]

    def add_vehicle_person(self, vehicle_id, person_id, person_name, relationship='associated', notes=''):
        if not self.vehicle(vehicle_id):
            raise ValueError('Vehicle not found.')
        person_id, person_name = str(person_id or '').strip(), str(person_name or '').strip()
        allowed = {'owner', 'primary_driver', 'driver', 'keeper', 'technician', 'previous_owner', 'associated'}
        relationship = str(relationship or 'associated').strip().lower()
        if not person_id or not person_name:
            raise ValueError('Select a person to connect.')
        if relationship not in allowed:
            raise ValueError('Select a valid vehicle relationship.')
        with self.connect() as db:
            cursor = db.execute(
                'INSERT INTO vehicle_people(vehicle_id,person_id,person_name,relationship,notes,created_at) VALUES(?,?,?,?,?,?)',
                (vehicle_id, person_id, person_name[:200], relationship, str(notes or '').strip(), time.time()),
            )
        return cursor.lastrowid

    def delete_vehicle_person(self, vehicle_id, link_id):
        with self.connect() as db:
            cursor = db.execute('DELETE FROM vehicle_people WHERE id=? AND vehicle_id=?', (link_id, vehicle_id))
        if not cursor.rowcount:
            raise ValueError('Vehicle-person connection not found.')

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
