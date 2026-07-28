import os
import tempfile
import unittest
from unittest.mock import patch

from services.automotive import AutomotiveStore, simple_pdf
from routes.automotive import MAX_ARCHIVE_UNCOMPRESSED_BYTES, _validate_download_url


class AutomotiveStoreTest(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix='.sqlite3')
        os.close(handle)
        self.addCleanup(os.unlink, self.path)
        self.store = AutomotiveStore(self.path)

    def test_import_and_offline_vin_lookup(self):
        count = self.store.import_vin_csv(b'wmi,manufacturer,country,vehicle type\n1HG,Honda,United States,Passenger car\n')
        self.assertEqual(count, 1)
        result = self.store.lookup_vin('1HGCM82633A004352')
        self.assertEqual(result['manufacturer'], 'Honda')
        self.assertEqual(result['vehicle_type'], 'Passenger car')
        self.assertTrue(result['checksum_valid'])

    def test_bundled_saab_wmi_and_model_year(self):
        result = self.store.lookup_vin('YS3DH38KX22031788')
        self.assertEqual(result['manufacturer'], 'Saab Automobile AB')
        self.assertEqual(result['country'], 'Sweden')
        self.assertEqual(result['model_year'], 2002)
        self.assertTrue(result['database_match'])

    def test_vin_validation(self):
        with self.assertRaisesRegex(ValueError, '17'):
            self.store.lookup_vin('NOT-A-VIN')

    def test_code_import_prioritizes_vehicle_translation(self):
        self.store.import_dtc_csv(b'code,description,make\nP0300,Generic misfire,\nP0300,Saab-specific misfire,Saab\n')
        matches = self.store.lookup_code('p0300', 'Saab')
        self.assertEqual(matches[0]['description'], 'Saab-specific misfire')
        self.assertEqual(matches[1]['description'], 'Generic misfire')

    def test_text_parser_and_reports(self):
        self.assertEqual(self.store.import_dtc_text('P0171 - System too lean\nP0300: Random misfire', 'Saab'), 2)
        vehicle_id = self.store.save_vehicle({'vin': '1HGCM82633A004352', 'nickname': 'Daily', 'make': 'Saab'})
        report_id = self.store.save_report({'vehicle_id': str(vehicle_id), 'title': 'Service', 'codes': 'P0171, P0300', 'work_done': 'Checked intake'})
        report = self.store.report(report_id)
        self.assertEqual(report['codes'], ['P0171', 'P0300'])
        self.assertEqual(report['code_details']['P0171'][0]['description'], 'System too lean')

    def test_pdf_is_valid_download_payload(self):
        payload = simple_pdf('Workshop report', ['VIN: 123', 'Work done: test'])
        self.assertTrue(payload.startswith(b'%PDF-1.4'))
        self.assertTrue(payload.endswith(b'%%EOF'))

    def test_reports_snapshot_translations(self):
        self.store.import_dtc_text('P0171 - Original definition', 'Saab')
        vehicle_id = self.store.save_vehicle({'vin': '1HGCM82633A004352', 'make': 'Saab'})
        report_id = self.store.save_report({'vehicle_id': str(vehicle_id), 'codes': 'P0171'})
        self.store.import_dtc_text('P0171 - Changed definition', 'Saab')
        self.assertEqual(self.store.report(report_id)['code_details']['P0171'][0]['description'], 'Original definition')

    def test_import_provenance_rejects_duplicate_file(self):
        content = b'wmi,manufacturer\n1HG,Honda\n'
        self.store.record_import('vin', 'first.csv', content, 1)
        with self.assertRaisesRegex(ValueError, 'already'):
            self.store.record_import('vin', 'second.csv', content, 1)
        self.assertEqual(self.store.imports()[0]['sha256'], self.store.digest(content))

    def test_vehicle_can_be_updated_and_archived(self):
        vehicle_id = self.store.save_vehicle({'vin': '1HGCM82633A004352', 'nickname': 'Old'})
        self.store.update_vehicle(vehicle_id, {'vin': '1HGCM82633A004352', 'nickname': 'Updated'})
        self.assertEqual(self.store.vehicle(vehicle_id)['nickname'], 'Updated')
        self.store.archive_vehicle(vehicle_id)
        self.assertEqual(self.store.vehicles(), [])

    def test_download_url_rejects_private_destinations(self):
        with patch('routes.automotive.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 80))]):
            with self.assertRaisesRegex(ValueError, 'local, private'):
                _validate_download_url('http://example.test/codes.csv')

    def test_report_rejects_invalid_code(self):
        with self.assertRaisesRegex(ValueError, 'Invalid diagnostic code'):
            self.store.save_report({'codes': 'NOTACODE'})

    def test_staged_import_does_not_change_live_lookup_until_approved(self):
        content = b'wmi,manufacturer,country\nWVW,Volkswagen,Germany\n1HG,Honda,USA\n'
        records = self.store.parse_vin_csv(content)
        pending_id = self.store.stage_import('vin', 'vehicles.csv', content, records)
        self.assertEqual(self.store.lookup_vin('WVWZZZ1JZXW000001').get('manufacturer'), None)
        _, count = self.store.apply_pending_import(pending_id, ['0'])
        self.assertEqual(count, 1)
        self.assertEqual(self.store.lookup_vin('WVWZZZ1JZXW000001')['manufacturer'], 'Volkswagen')
        self.assertEqual(self.store.lookup_vin('1HGCM82633A004352').get('manufacturer'), None)
        self.assertIsNone(self.store.pending_import(pending_id))

    def test_staged_import_can_be_discarded(self):
        content = b'code,description\nP0300,Random misfire\n'
        pending_id = self.store.stage_import('dtc', 'codes.csv', content, self.store.parse_dtc_csv(content))
        self.store.discard_pending_import(pending_id)
        self.assertEqual(self.store.lookup_code('P0300'), [])

    def test_duplicate_is_rejected_before_live_records_change(self):
        content = b'wmi,manufacturer\n1HG,Honda\n'
        first = self.store.stage_import('vin', 'first.csv', content, self.store.parse_vin_csv(content))
        self.store.apply_pending_import(first)
        with self.assertRaisesRegex(ValueError, 'already'):
            self.store.stage_import('vin', 'duplicate.csv', content, [{'wmi': '1HG', 'manufacturer': 'Changed'}])
        self.assertEqual(self.store.lookup_vin('1HGCM82633A004352')['manufacturer'], 'Honda')

    def test_vehicle_additional_identifiers(self):
        vehicle_id = self.store.save_vehicle({'vin': 'YS3DH38KX22031788', 'nickname': 'Saab'})
        identifier_id = self.store.add_vehicle_identifier(vehicle_id, {
            'identifier_type': 'engine_serial', 'value': 'b205e-12345', 'source': 'Engine stamp', 'verified': '1',
        })
        identifier = self.store.vehicle_identifiers(vehicle_id)[0]
        self.assertEqual(identifier['value'], 'B205E-12345')
        self.assertEqual(identifier['verified'], 1)
        self.store.delete_vehicle_identifier(vehicle_id, identifier_id)
        self.assertEqual(self.store.vehicle_identifiers(vehicle_id), [])

    def test_vehicle_modules_compare_reported_vin(self):
        vehicle_id = self.store.save_vehicle({'vin': 'YS3DH38KX22031788'})
        matching_id = self.store.add_vehicle_module(vehicle_id, {
            'module_name': 'Engine ECU', 'module_address': '7E0', 'reported_vin': 'ys3dh38kx22031788',
            'part_number': '55500000', 'serial_number': 'ECU-123', 'calibration_id': 'CAL-1', 'cvn': 'ABCD1234',
        })
        self.store.add_vehicle_module(vehicle_id, {'module_name': 'Used cluster', 'reported_vin': '1HGCM82633A004352'})
        modules = self.store.vehicle_modules(vehicle_id)
        self.assertTrue(next(item for item in modules if item['module_name'] == 'Engine ECU')['vin_match'])
        self.assertFalse(next(item for item in modules if item['module_name'] == 'Used cluster')['vin_match'])
        self.store.delete_vehicle_module(vehicle_id, matching_id)
        self.assertEqual(len(self.store.vehicle_modules(vehicle_id)), 1)

    def test_module_rejects_malformed_reported_vin(self):
        vehicle_id = self.store.save_vehicle({'vin': 'YS3DH38KX22031788'})
        with self.assertRaisesRegex(ValueError, 'module-reported VIN'):
            self.store.add_vehicle_module(vehicle_id, {'module_name': 'ECU', 'reported_vin': 'short'})

    def test_removed_capability_import_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            self.store.stage_import('capability', 'wrong-document.csv', b'wrong', [{'model': 'SAAB 9-5'}])
        with self.store.connect() as db:
            table = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='diagnostic_capabilities'").fetchone()
        self.assertIsNone(table)

    def test_detailed_dtc_csv_preserves_provenance_and_applicability(self):
        content = (
            'code,category,definition,definition_scope,manufacturer,model,year_start,year_end,module,'
            'lookup_priority,saab_specific_override,source_name,source_url,license,confidence,applicability,notes\n'
            'B0001,B,Driver Frontal Stage 1 Deployment Control,Generic,Generic OBD-II,,,,SRS,2,No,'
            'Wal33D generic B-codes,https://example.test/b_codes.txt,MIT,community,'
            'Apply only where the vehicle and module support this DTC.,Imported example\n'
        ).encode()
        records = self.store.parse_dtc_csv(content)
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record['description'], 'Driver Frontal Stage 1 Deployment Control')
        self.assertEqual(record['scope'], 'generic')
        self.assertEqual(record['make'], '')
        self.assertEqual(record['module'], 'SRS')
        self.assertEqual(record['lookup_priority'], 2)
        self.assertEqual(record['source_name'], 'Wal33D generic B-codes')
        self.assertEqual(record['confidence'], 'community')
        pending_id = self.store.stage_import('dtc', 'detailed.csv', content, records)
        self.store.apply_pending_import(pending_id)
        saved = self.store.lookup_code('B0001')[0]
        self.assertEqual(saved['source_url'], 'https://example.test/b_codes.txt')
        self.assertEqual(saved['applicability_notes'], 'Apply only where the vehicle and module support this DTC.')

    def test_multiple_definitions_for_same_code_are_retained_and_ranked(self):
        self.store.import_dtc_csv(b'code,description,make,lookup_priority\nP0300,Generic misfire,,20\n')
        self.store.import_dtc_csv(b'code,description,make,lookup_priority\nP0300,Saab misfire,Saab,50\n')
        matches = self.store.lookup_code('P0300', 'Saab')
        self.assertEqual([item['description'] for item in matches], ['Saab misfire', 'Generic misfire'])

    def test_vehicle_can_connect_to_people(self):
        vehicle_id = self.store.save_vehicle({'vin': 'YS3DH38KX22031788'})
        link_id = self.store.add_vehicle_person(vehicle_id, 'person-1', 'Alex Owner', 'primary_driver', 'Daily driver')
        link = self.store.vehicle_people(vehicle_id)[0]
        self.assertEqual(link['person_name'], 'Alex Owner')
        self.assertEqual(link['relationship'], 'primary_driver')
        self.store.delete_vehicle_person(vehicle_id, link_id)
        self.assertEqual(self.store.vehicle_people(vehicle_id), [])

    def test_zip_uncompressed_limit_is_larger_than_upload_limit(self):
        self.assertEqual(MAX_ARCHIVE_UNCOMPRESSED_BYTES, 250 * 1024 * 1024)


if __name__ == '__main__':
    unittest.main()
