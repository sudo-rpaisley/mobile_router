import unittest
from types import SimpleNamespace
from unittest.mock import patch

import app as app_module
from app import app


class RouteSmokeTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_capabilities_page_renders(self):
        response = self.client.get('/capabilities')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Runtime Capabilities', response.data)
        self.assertIn(b'id="theme-toggle"', response.data)
        self.assertIn(b'id="adapter-auto-update-status"', response.data)
        self.assertNotIn(b'id="listAdapters', response.data)

    def test_roadmap_page_renders_project_ideas(self):
        response = self.client.get('/roadmap')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Project Roadmap', response.data)
        self.assertIn(b'Device inventory page', response.data)
        self.assertIn(b'Bluetooth action checklist', response.data)
        self.assertIn(b'WPA handshake capture lab', response.data)
        self.assertIn(b'Remote cracking orchestration', response.data)
        self.assertIn(b'PineAP-style recon and campaign concepts', response.data)
        self.assertIn(b'Hak5-inspired lab features', response.data)
        self.assertIn(b'Payload profile switchboard', response.data)
        self.assertIn(b'Inline network tap mode', response.data)
        self.assertIn(b'Done', response.data)
        self.assertIn(b'completed', response.data)
        self.assertIn(b'remaining', response.data)



    def test_scrollable_interface_lists_do_not_render_blue_focus_box(self):
        css = open('static/css/adapters-card.css').read()

        self.assertIn('.interface-category-list:focus', css)
        self.assertIn('outline: none;', css)
        self.assertNotIn('outline: 2px solid #007bff', css)

    def test_interface_type_preserves_uppercase_vpn(self):
        vpn_interface = SimpleNamespace(
            name='VPN Adapter',
            interface_type='VPN',
            addresses=[],
            manufacturer='Unknown',
            state='UP',
        )
        with patch.object(app_module, 'network_interfaces', [vpn_interface]):
            response = self.client.get('/vpn')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'VPN Interfaces', response.data)
        self.assertIn(b'VPN Adapter', response.data)

    def test_wireless_type_page_uses_standard_adapter_card_without_scan_controls(self):
        wireless_interface = SimpleNamespace(
            name='WiFi',
            interface_type='Wireless',
            addresses=[],
            manufacturer='Unknown',
            state='UP',
            get_mac_address=lambda: 'c4:3d:1a:f5:91:32',
        )
        with (
            patch.object(app_module, 'network_interfaces', [wireless_interface]),
            patch.object(app_module, 'networkTechnologies', {'Wireless'}),
        ):
            response = self.client.get('/wireless')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'adapter-card', response.data)
        self.assertIn(b'interface-icon', response.data)
        self.assertIn(b'adapter-health-badges', response.data)
        self.assertNotIn(b'adapter-card-large', response.data)
        self.assertNotIn(b'Scan for Networks', response.data)
        self.assertNotIn(b'id="wlans-WiFi"', response.data)

    def test_wireless_adapter_detail_keeps_scan_controls(self):
        wireless_interface = SimpleNamespace(
            name='WiFi',
            interface_type='Wireless',
            addresses=[],
            manufacturer='Unknown',
            state='UP',
            extra_info={},
            get_mac_address=lambda: 'c4:3d:1a:f5:91:32',
        )
        with (
            patch.object(app_module, 'network_interfaces', [wireless_interface]),
            patch.object(app_module, 'networkTechnologies', {'Wireless'}),
        ):
            response = self.client.get('/wireless/WiFi')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Scan for Networks', response.data)
        self.assertIn(b'Action Readiness', response.data)
        self.assertIn(b'id="wlans-WiFi"', response.data)
        self.assertIn(b'data-interface="WiFi"', response.data)




    def test_red_team_card_forms_are_constrained_to_card_width(self):
        css = open('static/css/red-team.css').read()

        self.assertIn('.red-team-grid .form-inline', css)
        self.assertIn('display: grid !important;', css)
        self.assertIn('width: 100% !important;', css)
        self.assertIn('max-width: 100%;', css)

    @patch('app.threading.Thread')
    def test_scan_job_routes_start_and_report_status(self, thread_cls):
        thread_cls.return_value.start.return_value = None
        response = self.client.post('/scan-jobs', data={'scanType': 'wlan', 'selectedInterface': 'WiFi'})
        self.assertEqual(response.status_code, 200)
        job = response.get_json()['job']
        self.assertEqual(job['status'], 'queued')

        response = self.client.get(f"/scan-jobs/{job['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['job']['scan_type'], 'wlan')

    def test_scan_job_rejects_unknown_scan_type(self):
        response = self.client.post('/scan-jobs', data={'scanType': 'unknown', 'selectedInterface': 'WiFi'})
        self.assertEqual(response.status_code, 400)

    def test_export_routes_return_json(self):
        response = self.client.get('/export/interfaces.json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('interfaces', response.get_json())

        response = self.client.get('/export/capabilities.json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('capabilities', response.get_json())


    def test_inventory_page_renders_manufacturer_insights(self):
        app_module.device_inventory.clear()
        app_module.record_inventory_devices([
            {'ip': '192.168.1.10', 'mac': 'b8:27:eb:11:22:33'},
            {'ip': '192.168.1.11', 'mac': 'de:ad:be:ef:00:01'},
        ], 'test-scan', 'eth0')

        response = self.client.get('/inventory')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Device Inventory', response.data)
        self.assertIn(b'Manufacturer/OUI insights', response.data)
        self.assertIn(b'Raspberry Pi Foundation', response.data)
        self.assertIn(b'Needs review', response.data)

    @patch('app.active_scan')
    def test_active_scan_records_inventory_with_manufacturer(self, scan):
        app_module.device_inventory.clear()
        scan.return_value = [{'ip': '192.168.1.10', 'mac': 'b8:27:eb:11:22:33'}]

        response = self.client.post('/active-scan', data={'selectedInterface': 'eth0'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['hosts'][0]['manufacturer'], 'Raspberry Pi Foundation')
        self.assertIn('mac:b8:27:eb:11:22:33', app_module.device_inventory)

    def test_minecraft_page_renders(self):
        response = self.client.get('/minecraft-attack')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Minecraft Attack Lab', response.data)


    @patch('scripts.wifi.utils.get_network_detail')
    def test_wireless_network_detail_page_renders_discovered_devices(self, get_detail):
        get_detail.return_value = {
            'ssid': 'TrainingNet',
            'bssid': 'aa:bb:cc:dd:ee:ff',
            'security': 'WPA2-Personal',
            'channel': '6',
            'signal': 82,
            'signal_label': '82%',
            'interface': 'wlan0',
            'discovered': True,
            'gateway': {'ip': '192.168.1.1', 'mac': '00:11:22:33:44:55', 'manufacturer': 'Training Vendor'},
            'bands': ['5 GHz'],
            'ap_groups': [
                {
                    'label': 'AP group 1',
                    'bssids': ['aa:bb:cc:dd:ee:ff'],
                    'bands': ['5 GHz'],
                    'channels': ['6'],
                    'confidence': 'Low',
                    'reasons': [],
                    'likely_same_physical_ap': False,
                }
            ],
            'access_points': [
                {
                    'bssid': 'aa:bb:cc:dd:ee:ff',
                    'channel': '6',
                    'signal': 82,
                    'signal_label': '82%',
                    'frequency': 5180,
                    'band': '5 GHz',
                    'manufacturer': 'Training Vendor',
                    'signal_quality': 'Strong',
                    'notes': ['DFS channel; may be affected by radar events'],
                    'clients': [{'mac': '11:22:33:44:55:66', 'signal_label': '-42 dBm', 'bssid': 'aa:bb:cc:dd:ee:ff', 'manufacturer': 'Client Vendor'}],
                }
            ],
            'clients': [{'mac': '11:22:33:44:55:66', 'signal_label': '-42 dBm', 'bssid': 'aa:bb:cc:dd:ee:ff', 'manufacturer': 'Client Vendor'}],
        }

        response = self.client.get('/wireless/network?interface=wlan0&ssid=TrainingNet&bssid=aa:bb:cc:dd:ee:ff')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'TrainingNet', response.data)
        self.assertIn(b'Discovered Devices', response.data)
        self.assertIn(b'192.168.1.1', response.data)
        self.assertIn(b'5 GHz', response.data)
        self.assertIn(b'AP Identity Hints', response.data)
        self.assertIn(b'Training Vendor', response.data)
        self.assertIn(b'11:22:33:44:55:66', response.data)

    def test_bluetooth_scan_includes_manufacturer(self):
        async def fake_get_bluetooth_devices():
            return [SimpleNamespace(address='b8:27:eb:11:22:33', name='Lab Speaker')]

        with (
            patch.object(app_module, 'get_bluetooth_devices', fake_get_bluetooth_devices),
            patch.object(app_module.shutil, 'which', return_value=None),
        ):
            response = self.client.post('/bluetooth-scan', data={'selectedInterface': 'hci0'})

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['devices'][0]['manufacturer'], 'Raspberry Pi Foundation')
        self.assertFalse(payload['action_capability']['available'])

    @patch('app.run_bluetoothctl_action')
    def test_bluetooth_action_success(self, run_action):
        run_action.return_value = 'Device disconnected'

        response = self.client.post('/bluetooth-action', data={
            'action': 'disconnect',
            'address': 'aa:bb:cc:dd:ee:ff',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['output'], 'Device disconnected')
        run_action.assert_called_once_with('disconnect', 'aa:bb:cc:dd:ee:ff')

    @patch.object(app_module.shutil, 'which')
    @patch.object(app_module.subprocess, 'run')
    def test_bluetooth_action_capability_uses_busctl_fallback(self, run, which):
        which.side_effect = lambda command: '/usr/bin/busctl' if command == 'busctl' else None
        run.return_value = SimpleNamespace(returncode=0, stdout='/org/bluez/hci0\n', stderr='')

        capability = app_module.bluetooth_action_capability()

        self.assertTrue(capability['available'])
        self.assertEqual(capability['tool'], 'busctl')

    @patch.object(app_module.shutil, 'which')
    @patch.object(app_module.subprocess, 'run')
    def test_bluetooth_action_uses_busctl_when_bluetoothctl_missing(self, run, which):
        which.side_effect = lambda command: '/usr/bin/busctl' if command == 'busctl' else None
        run.side_effect = [
            SimpleNamespace(returncode=0, stdout='/org/bluez/hci0\n', stderr=''),
            SimpleNamespace(returncode=0, stdout='└─/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF\n', stderr=''),
            SimpleNamespace(returncode=0, stdout='', stderr=''),
        ]

        output = app_module.run_bluetoothctl_action('disconnect', 'aa:bb:cc:dd:ee:ff')

        self.assertIn('busctl Bluetooth disconnect completed', output)
        self.assertEqual(
            run.call_args_list[2].args[0][:5],
            ['/usr/bin/busctl', 'call', 'org.bluez', '/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF', 'org.bluez.Device1'],
        )

    @patch.object(app_module.shutil, 'which', return_value=None)
    def test_bluetooth_action_reports_missing_bluetoothctl_as_unavailable(self, _which):
        response = self.client.post('/bluetooth-action', data={
            'action': 'disconnect',
            'address': 'aa:bb:cc:dd:ee:ff',
        })

        self.assertEqual(response.status_code, 501)
        self.assertIn('bluetoothctl', response.get_json()['message'])

    def test_bluetooth_action_rejects_invalid_action(self):
        response = self.client.post('/bluetooth-action', data={
            'action': 'force-disconnect-third-party',
            'address': 'aa:bb:cc:dd:ee:ff',
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['message'], 'Unsupported Bluetooth action')

    @patch('routes.minecraft.send_mob_toggle')
    def test_minecraft_mob_toggle_success(self, send_mob_toggle):
        send_mob_toggle.return_value = {
            'mob': {'id': 'chicken', 'name': 'Chicken', 'port': 25571, 'enabled': True},
            'state': 'on',
        }

        response = self.client.post('/minecraft-attack/mobs/chicken/toggle', data={
            'authorized': 'true',
            'host': '127.0.0.1',
            'state': 'on',
            'timeout': '1.5',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['result']['state'], 'on')


if __name__ == '__main__':
    unittest.main()
