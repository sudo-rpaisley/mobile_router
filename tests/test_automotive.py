import os
import tempfile
import unittest
from unittest.mock import patch

from services.automotive import AutomotiveStore, simple_pdf
from routes.automotive import _validate_download_url


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


if __name__ == '__main__':
    unittest.main()
