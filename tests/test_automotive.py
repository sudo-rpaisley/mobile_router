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


if __name__ == '__main__':
    unittest.main()
