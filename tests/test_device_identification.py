import io
import unittest
from unittest.mock import patch

import app as app_module
from app import app
from services import device_identification


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, amount):
        return self.payload[:amount]


class DeviceIdentificationEngineTest(unittest.TestCase):
    def test_synology_fingerprint_combines_vendor_ports_and_http_title(self):
        device = {
            'manufacturer': 'Synology Incorporated',
            'mac': '00:11:32:aa:bb:cc',
            'hostname': 'diskstation',
            'open_port_details': [
                {'port': 445, 'service': 'smb'},
                {'port': 5000, 'service': 'http', 'http_title': 'Synology DiskStation'},
                {'port': 5001, 'service': 'https'},
            ],
        }
        safe = {
            'services': [{
                'port': 5001,
                'service': 'https',
                'http': {'title': 'DiskStation Manager', 'server': 'nginx'},
                'tls': {'subject_common_name': 'synology.local'},
            }],
            'upnp': [],
        }

        result = device_identification.identify_device(device, safe_probes=safe)

        self.assertEqual(result['likely_device'], 'Synology NAS')
        self.assertIn(result['confidence'], {'high', 'very high'})
        self.assertGreaterEqual(result['score'], 65)
        self.assertTrue(result['identity_signature'])
        self.assertTrue(any(item['source'] == 'MAC vendor' for item in result['evidence']))

    def test_printer_fingerprint_works_without_exact_model(self):
        device = {
            'manufacturer': 'Hewlett Packard',
            'open_port_details': [
                {'port': 631, 'service': 'ipp', 'description': 'Internet Printing Protocol'},
                {'port': 9100, 'service': 'jetdirect'},
            ],
        }

        result = device_identification.identify_device(device)

        self.assertEqual(result['likely_device'], 'Network printer')
        self.assertGreaterEqual(result['score'], 40)

    def test_private_mac_is_downweighted_and_signature_is_stable(self):
        first = {
            'manufacturer': 'Apple, Inc.',
            'likely_randomized_mac': True,
            'hostname': 'living-room-device',
            'open_port_details': [
                {'port': 7000, 'service': 'airplay'},
                {'port': 7100, 'service': 'raop'},
            ],
        }
        second = {
            **first,
            'mac': 'da:aa:bb:cc:dd:ee',
            'open_port_details': list(reversed(first['open_port_details'])),
        }

        one = device_identification.identify_device(first)
        two = device_identification.identify_device(second)

        self.assertEqual(one['likely_device'], 'Apple TV/HomePod')
        self.assertEqual(one['identity_signature'], two['identity_signature'])
        self.assertTrue(any('private/randomised' in item for item in one['limitations']))
        self.assertFalse(any(item['source'] == 'MAC vendor' for item in one['evidence']))

    def test_upnp_description_is_bounded_and_parsed(self):
        xml = b'''<?xml version="1.0"?>
        <root xmlns="urn:schemas-upnp-org:device-1-0"><device>
          <deviceType>urn:schemas-upnp-org:device:MediaRenderer:1</deviceType>
          <friendlyName>Living Room TV</friendlyName>
          <manufacturer>Example Electronics</manufacturer>
          <modelName>ExampleVision 55</modelName>
          <modelNumber>EV55</modelNumber>
          <serialNumber>ABC123</serialNumber>
        </device></root>'''
        device = {'service_metadata': {'control_url': 'http://192.168.1.20:1400/device.xml'}}

        with patch('services.device_identification._same_device_url', return_value=True):
            result = device_identification.probe_upnp_descriptions(
                device,
                '192.168.1.20',
                opener=lambda request, timeout: FakeResponse(xml),
            )

        self.assertEqual(result[0]['friendly_name'], 'Living Room TV')
        self.assertEqual(result[0]['manufacturer'], 'Example Electronics')
        self.assertEqual(result[0]['model_name'], 'ExampleVision 55')

    def test_deep_probe_requires_explicit_authorization(self):
        with self.assertRaisesRegex(ValueError, 'Confirm authorization'):
            device_identification.deep_device_probe('192.168.1.20', [80])

        with patch('services.device_identification.shutil.which', return_value=None):
            result = device_identification.deep_device_probe(
                '192.168.1.20', [80, 443], authorized=True
            )
        self.assertFalse(result['nmap']['available'])
        self.assertIn('No SNMP community', result['snmp']['message'])

    def test_host_validation_blocks_command_style_input(self):
        with self.assertRaisesRegex(ValueError, 'unsupported characters'):
            device_identification.deep_device_probe(
                '192.168.1.20;reboot', [80], authorized=True
            )


class DeviceIdentificationRouteTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        app_module.social_users.clear()
        app_module.social_audit_log.clear()
        app_module.device_inventory.clear()
        app_module.social_users['test-admin'] = {
            'id': 'test-admin',
            'username': 'test-admin',
            'role': 'admin',
            'password_hash': 'unused',
        }
        app_module.device_inventory['mac:00:11:32:aa:bb:cc'] = {
            'id': 'mac:00:11:32:aa:bb:cc',
            'ip': '192.168.1.20',
            'mac': '00:11:32:aa:bb:cc',
            'manufacturer': 'Synology Incorporated',
            'hostname': 'diskstation',
            'open_port_details': [
                {'port': 445, 'service': 'smb'},
                {'port': 5000, 'service': 'http', 'http_title': 'Synology DiskStation'},
            ],
            'open_ports': [445, 5000],
            'sources': ['test'],
            'interfaces': ['eth0'],
        }
        self.csrf = 'identify-csrf'
        with self.client.session_transaction() as flask_session:
            flask_session['social_user'] = {'username': 'test-admin', 'role': 'admin'}
            flask_session['social_csrf_token'] = self.csrf

    def tearDown(self):
        app_module.device_inventory.clear()
        app_module.social_users.clear()
        app_module.social_audit_log.clear()

    @patch('app.save_runtime_state')
    @patch('app.record_social_audit')
    @patch('app.append_client_timeline_event')
    @patch('app._ttl_os_hint', return_value={'hint': 'Linux/Unix-like', 'evidence': ['TTL 64']})
    @patch('app.client_reachability_history', return_value=[])
    @patch('app._dhcp_lease_display_name', return_value='diskstation')
    @patch('app._reverse_dns_display_name', return_value='diskstation.local')
    def test_passive_identification_persists_assessment(
        self,
        reverse,
        dhcp,
        reachability,
        os_hint,
        timeline,
        audit,
        save,
    ):
        response = self.client.post(
            '/clients/192.168.1.20/identify',
            data={'stage': 'passive', 'csrf_token': self.csrf},
        )

        self.assertEqual(response.status_code, 200)
        result = response.get_json()['identification']
        self.assertEqual(result['likely_device'], 'Synology NAS')
        saved = app_module.device_inventory['mac:00:11:32:aa:bb:cc']
        self.assertEqual(saved['identity_assessment']['likely_device'], 'Synology NAS')
        self.assertEqual(saved['identity_identification_stage'], 'passive')
        self.assertTrue(saved['identity_signature'])
        timeline.assert_called_once()
        audit.assert_called_once()
        save.assert_called_once_with('device-identification:passive')

    @patch('app.save_runtime_state')
    @patch('app.record_social_audit')
    @patch('app.append_client_timeline_event')
    @patch('app._ttl_os_hint', return_value={'hint': 'Unknown', 'evidence': []})
    @patch('app.client_reachability_history', return_value=[])
    @patch('app._dhcp_lease_display_name', return_value='')
    @patch('app._reverse_dns_display_name', return_value='')
    @patch('app.fingerprint_client_services', return_value=[])
    @patch('routes.device_identification.device_identification.supplement_service_probes')
    def test_safe_identification_uses_protocol_probes(
        self,
        supplement,
        fingerprints,
        reverse,
        dhcp,
        reachability,
        os_hint,
        timeline,
        audit,
        save,
    ):
        supplement.return_value = {
            'services': [{'port': 5000, 'http': {'title': 'Synology DiskStation'}}],
            'upnp': [{'friendly_name': 'DiskStation', 'model_name': 'DS920+'}],
        }
        response = self.client.post(
            '/clients/192.168.1.20/identify',
            data={'stage': 'safe', 'csrf_token': self.csrf},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['stage'], 'safe')
        self.assertEqual(payload['safe_probes']['upnp'][0]['model_name'], 'DS920+')
        supplement.assert_called_once()

    def test_deep_identification_requires_authorization(self):
        response = self.client.post(
            '/clients/192.168.1.20/identify',
            data={'stage': 'deep', 'csrf_token': self.csrf},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('Confirm authorization', response.get_json()['message'])

    def test_identification_requires_csrf(self):
        response = self.client.post(
            '/clients/192.168.1.20/identify',
            data={'stage': 'passive', 'csrf_token': 'wrong'},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('CSRF', response.get_json()['message'])

    def test_client_page_loads_identification_interface(self):
        response = self.client.get('/clients/192.168.1.20')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'data-ip-client-intelligence', response.data)
        self.assertIn(b'device-identification.js', response.data)


if __name__ == '__main__':
    unittest.main()
