import json
import os
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import app as app_module
from app import app
from services.oui import lookup_manufacturer, oui_database_status


class RouteSmokeTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_capabilities_page_renders(self):
        response = self.client.get('/capabilities')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Runtime Capabilities', response.data)
        self.assertIn(b'Central Capability Registry', response.data)
        self.assertIn(b'id="theme-toggle"', response.data)
        self.assertIn(b'id="adapter-auto-update-status"', response.data)
        self.assertIn(b'Tools', response.data)
        self.assertNotIn(b'href="/network-scan"', response.data)
        self.assertNotIn(b'href="/bluetooth-phone"', response.data)
        self.assertIn(b'Records', response.data)
        self.assertIn(b'System', response.data)
        self.assertNotIn(b'id="listAdapters', response.data)
        self.assertIn(b'Browser screenshot tooling', response.data)
        self.assertIn(b'Install for me', response.data)
        self.assertIn(b'install-host-dependency', response.data)

    def test_roadmap_page_renders_project_ideas(self):
        response = self.client.get('/roadmap')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Project Roadmap', response.data)
        self.assertIn(b'Device inventory page', response.data)
        self.assertIn(b'Persistent local inventory state', response.data)
        self.assertIn(b'Bluetooth action checklist', response.data)
        self.assertIn(b'WPS exposure checks', response.data)
        self.assertNotIn(b'Authorization guardrails', response.data)
        self.assertNotIn(b'Demo/simulation mode', response.data)
        self.assertIn(b'WPA handshake capture lab', response.data)
        self.assertIn(b'Remote cracking orchestration', response.data)
        self.assertIn(b'PineAP-style recon and campaign engine', response.data)
        self.assertIn(b'Hak5-inspired lab features', response.data)
        self.assertIn(b'Payload profile switchboard', response.data)
        self.assertIn(b'Inline network tap mode', response.data)
        self.assertIn(b'Central capability registry', response.data)
        self.assertIn(b'Background scan jobs', response.data)
        self.assertIn(b'Layout density and navigation review', response.data)
        self.assertIn(b'Tabbed interface detail layout', response.data)
        self.assertIn(b'Guided modes and progression', response.data)
        self.assertIn(b'Full and training mode switch', response.data)
        self.assertIn(b'Progressive training unlocks', response.data)
        self.assertIn(b'Guided focus overlay', response.data)
        self.assertIn(b'Training trophies and milestones', response.data)
        self.assertIn(b'Training trophies', response.data)
        self.assertIn(b'Scan milestone trophies', response.data)
        self.assertIn(b'Wireless analysis trophies', response.data)
        self.assertIn(b'Bluetooth workflow trophies', response.data)
        self.assertIn(b'Reporting and evidence trophies', response.data)
        self.assertIn(b'Training completion trophies', response.data)
        self.assertIn(b'Grouped discovery notifications', response.data)
        self.assertIn(b'Comprehensive network device scan', response.data)
        self.assertIn(b'IP client profiles and watchlists', response.data)
        self.assertIn(b'Client relationship map', response.data)
        self.assertIn(b'Scheduled client checks', response.data)
        self.assertIn(b'Client remediation checklist', response.data)
        self.assertIn(b'Client change approval log', response.data)
        self.assertIn(b'Core network tools', response.data)
        self.assertIn(b'Ping and reachability testing', response.data)
        self.assertIn(b'ARP and neighbor discovery viewer', response.data)
        self.assertIn(b'Comprehensive network scans now include local ARP cache', response.data)
        self.assertIn(b'DNS lookup and diagnostics toolkit', response.data)
        self.assertIn(b'Route table and gateway diagnostics', response.data)
        self.assertIn(b'Packet capture and protocol summary', response.data)
        self.assertIn(b'Service fingerprinting and banner detection', response.data)
        self.assertIn(b'Extended network tools', response.data)
        self.assertIn(b'TLS certificate inspection', response.data)
        self.assertIn(b'DHCP lease and server inspection', response.data)
        self.assertIn(b'mDNS and Bonjour service discovery', response.data)
        self.assertIn(b'UPnP and SSDP discovery', response.data)
        self.assertIn(b'IPv6 assessment toolkit', response.data)
        self.assertIn(b'Dedicated wireless occupancy report page', response.data)
        self.assertIn(b'Server-side wireless occupancy history', response.data)
        self.assertIn(b'Bluetooth metadata refresh pipeline', response.data)
        self.assertIn(b'Bluetooth destructive-action confirmations', response.data)
        self.assertIn(b'Browser-level UI smoke tests', response.data)
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
        self.assertIn(b'Network Device Scan', response.data)
        self.assertIn(b'id="comprehensive-scan-btn"', response.data)
        self.assertIn(b'<option value="WiFi" selected>', response.data)
        self.assertIn(b'network_scan.js', response.data)
        self.assertIn(b'Action Readiness', response.data)
        self.assertIn(b'id="wlans-WiFi"', response.data)
        self.assertIn(b'data-interface="WiFi"', response.data)





    def test_bluetooth_interface_detail_links_to_phone_integration(self):
        bluetooth_interface = SimpleNamespace(
            name='hci0',
            interface_type='Bluetooth',
            addresses=[],
            manufacturer='Unknown',
            state='UP',
            extra_info={},
            get_mac_address=lambda: '00:11:22:33:44:55',
        )
        with (
            patch.object(app_module, 'network_interfaces', [bluetooth_interface]),
            patch.object(app_module, 'networkTechnologies', {'Bluetooth'}),
        ):
            response = self.client.get('/bluetooth/hci0')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'action="/bluetooth-phone"', response.data)
        self.assertIn(b'Phone Integration', response.data)
        self.assertIn(b'id="advertise-enabled"', response.data)
        self.assertIn(b'Changes autosave', response.data)
        self.assertIn(b'bluetooth-phone-autosave.js', response.data)
        self.assertNotIn(b'Save and apply', response.data)
        self.assertIn(b'Pair phones and request authorised contacts', response.data)
        self.assertNotIn(b'Network Device Scan', response.data)
        self.assertNotIn(b'network_scan.js', response.data)

    def test_network_scan_controls_render_on_interface_detail(self):
        ethernet_interface = SimpleNamespace(
            name='eth0',
            interface_type='Ethernet',
            addresses=[],
            manufacturer='Unknown',
            state='UP',
            extra_info={},
            get_mac_address=lambda: '00:11:22:33:44:55',
        )
        with (
            patch.object(app_module, 'network_interfaces', [ethernet_interface]),
            patch.object(app_module, 'networkTechnologies', {'Ethernet'}),
        ):
            response = self.client.get('/ethernet/eth0')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Network Device Scan', response.data)
        self.assertIn(b'id="active-scan-btn"', response.data)
        self.assertIn(b'id="passive-scan-btn"', response.data)
        self.assertIn(b'id="comprehensive-scan-btn"', response.data)
        self.assertIn(b'<option value="eth0" selected>', response.data)
        self.assertIn(b'network_scan.js', response.data)

    def test_red_team_card_forms_are_constrained_to_card_width(self):
        css = open('static/css/red-team.css').read()

        self.assertIn('.red-team-grid .form-inline', css)
        self.assertIn('display: grid !important;', css)
        self.assertIn('width: 100% !important;', css)
        self.assertIn('max-width: 100%;', css)


    def test_deauth_lab_card_requires_authorization_context(self):
        response = self.client.get('/red-team')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Student Deauth Lab', response.data)
        self.assertIn(b'id="Deauth-Authorized"', response.data)
        self.assertIn(b'authorized isolated class lab', response.data)

    def test_deauth_route_requires_authorization_and_frame_limit(self):
        response = self.client.post('/deauth', data={
            'selectedInterface': 'wlan0mon',
            'ap': 'AA:BB:CC:DD:EE:FF',
            'frames': '6',
            'authorized': 'on',
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('between 1 and 5', response.get_json()['message'])

        response = self.client.post('/deauth', data={
            'selectedInterface': 'wlan0mon',
            'ap': 'AA:BB:CC:DD:EE:FF',
            'frames': '2',
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('authorized isolated lab', response.get_json()['message'])

    def test_deauth_route_normalizes_authorized_lab_request(self):
        deauth = Mock()
        with patch.dict('sys.modules', {'scripts.wifi.deauth': SimpleNamespace(deauth=deauth)}):
            response = self.client.post('/deauth', data={
                'selectedInterface': 'wlan0mon',
                'ap': 'AA-BB-CC-DD-EE-FF',
                'target': '11-22-33-44-55-66',
                'frames': '2',
                'authorized': 'on',
            })

        self.assertEqual(response.status_code, 200)
        self.assertIn('authorized lab deauth frames', response.get_json()['message'])
        deauth.assert_called_once_with('aa:bb:cc:dd:ee:ff', '11:22:33:44:55:66', 'wlan0mon', 2)

    def test_evil_twin_lab_card_requires_explicit_targeting_and_consent(self):
        response = self.client.get('/red-team')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Evil Twin &amp; Captive Portal Lab', response.data)
        self.assertIn(b'id="EvilTwin-SSID"', response.data)
        self.assertIn(b'id="EvilTwin-BSSID"', response.data)
        self.assertIn(b'no credentials will be collected', response.data)
        self.assertIn(b'Detection guidance', response.data)

    def test_evil_twin_lab_route_requires_authorization_and_bounds(self):
        response = self.client.post('/evil-twin-lab', data={
            'selectedInterface': 'wlan0mon',
            'ssid': 'ClassLab',
            'bssid': 'AA:BB:CC:DD:EE:FF',
            'channel': '6',
            'durationMinutes': '45',
            'action': 'start',
            'authorized': 'on',
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('between 1 and 30', response.get_json()['message'])

        response = self.client.post('/evil-twin-lab', data={
            'selectedInterface': 'wlan0mon',
            'ssid': 'ClassLab',
            'bssid': 'AA:BB:CC:DD:EE:FF',
            'channel': '6',
            'durationMinutes': '10',
            'action': 'plan',
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('authorized isolated lab', response.get_json()['message'])

    def test_evil_twin_lab_route_records_safe_guidance(self):
        response = self.client.post('/evil-twin-lab', data={
            'selectedInterface': 'wlan0mon',
            'ssid': 'ClassLab',
            'bssid': 'AA-BB-CC-DD-EE-FF',
            'channel': '6',
            'durationMinutes': '10',
            'portalMessage': 'Training portal only.',
            'action': 'cleanup',
            'authorized': 'on',
        })

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn('cleanup checklist', payload['message'])
        self.assertEqual(payload['run']['bssid'], 'aa:bb:cc:dd:ee:ff')
        self.assertIn('do not request, collect, or store credentials', ' '.join(payload['run']['operator_steps']))
        self.assertIn('duplicate SSIDs', payload['run']['detection_guidance'][0])

    def test_pineap_and_handshake_cards_are_available(self):
        response = self.client.get('/red-team')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'PineAP-Style Lab Console', response.data)
        self.assertIn(b'id="Pineap-Modules"', response.data)
        self.assertIn(b'WPA Handshake Capture Lab', response.data)
        self.assertIn(b'Export handshake catalog JSON', response.data)

    def test_pineap_lab_recon_runs_scoped_scan_and_modules(self):
        with (
            patch('scripts.wifi.utils.scan_networks') as scan_networks,
            patch('scripts.wifi.utils.get_networks_summary', return_value=[{'ssid': 'ClassLab', 'bssid': 'aa:bb:cc:dd:ee:ff'}]),
        ):
            response = self.client.post('/pineap-lab', data={
                'selectedInterface': 'wlan0mon',
                'action': 'recon',
                'modules': 'recon,detection-report',
                'authorized': 'on',
            })

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn('Recorded recon workflow', payload['message'])
        self.assertEqual(payload['run']['recon'][0]['ssid'], 'ClassLab')
        self.assertIn('does not collect credentials', payload['run']['safety'])
        scan_networks.assert_called_once_with('wlan0mon')

    def test_pineap_lab_requires_authorization_and_known_modules(self):
        response = self.client.post('/pineap-lab', data={
            'selectedInterface': 'wlan0mon',
            'action': 'campaign',
            'ssid': 'ClassLab',
            'modules': 'recon,unknown',
            'authorized': 'on',
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('Unknown lab module', response.get_json()['message'])

        response = self.client.post('/pineap-lab', data={
            'selectedInterface': 'wlan0mon',
            'action': 'campaign',
            'ssid': 'ClassLab',
            'modules': 'recon',
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('authorized isolated lab', response.get_json()['message'])

    def test_handshake_lab_catalogs_evidence_and_exports(self):
        response = self.client.post('/handshake-lab', data={
            'selectedInterface': 'wlan0mon',
            'ssid': 'ClassLab',
            'bssid': 'AA-BB-CC-DD-EE-FF',
            'channel': '6',
            'captureType': 'pmkid',
            'validationNotes': 'PMKID observed in authorized lab capture.',
            'authorized': 'on',
        })

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['record']['bssid'], 'aa:bb:cc:dd:ee:ff')
        self.assertEqual(payload['record']['validation_status'], 'cataloged')
        self.assertIn('password cracking is out of scope', ' '.join(payload['record']['validation_checks']))

        export = self.client.get('/handshake-lab.json')
        self.assertEqual(export.status_code, 200)
        self.assertTrue(any(item['ssid'] == 'ClassLab' for item in export.get_json()['handshakes']))

        csv_export = self.client.get('/handshake-lab.csv')
        self.assertEqual(csv_export.status_code, 200)
        self.assertIn(b'ClassLab', csv_export.data)

    def test_handshake_lab_requires_authorized_lab_scope(self):
        response = self.client.post('/handshake-lab', data={
            'selectedInterface': 'wlan0mon',
            'ssid': 'ClassLab',
            'bssid': 'AA:BB:CC:DD:EE:FF',
            'channel': '6',
            'captureType': 'wpa-handshake',
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('authorized isolated lab', response.get_json()['message'])

    @patch('app.threading.Thread')
    def test_scan_job_routes_start_and_report_status(self, thread_cls):
        thread_cls.return_value.start.return_value = None
        response = self.client.post('/scan-jobs', data={'scanType': 'wlan', 'selectedInterface': 'WiFi'})
        self.assertEqual(response.status_code, 200)
        job = response.get_json()['job']
        self.assertEqual(job['status'], 'queued')
        self.assertIn('message', job)
        self.assertIn('events', job)
        self.assertEqual(job['result_counts'], {'devices': 0, 'wlans': 0})

        response = self.client.get(f"/scan-jobs/{job['id']}")
        self.assertEqual(response.status_code, 200)
        status_job = response.get_json()['job']
        self.assertEqual(status_job['scan_type'], 'wlan')
        self.assertEqual(status_job['progress'], 10)
        self.assertTrue(status_job['events'])


    @patch('app.threading.Thread')
    def test_duplicate_scan_job_reuses_running_job(self, thread_cls):
        thread_cls.return_value.start.return_value = None
        first = self.client.post('/scan-jobs', data={'scanType': 'bluetooth', 'selectedInterface': 'hci0'}).get_json()['job']
        second = self.client.post('/scan-jobs', data={'scanType': 'bluetooth', 'selectedInterface': 'hci0'}).get_json()['job']

        self.assertEqual(first['id'], second['id'])
        self.assertEqual(thread_cls.call_count, 1)

    def test_scan_job_rejects_unknown_scan_type(self):
        response = self.client.post('/scan-jobs', data={'scanType': 'unknown', 'selectedInterface': 'WiFi'})
        self.assertEqual(response.status_code, 400)

    def test_capability_registry_export_returns_entries(self):
        response = self.client.get('/capabilities/registry.json')

        self.assertEqual(response.status_code, 200)
        registry = response.get_json()['registry']
        self.assertTrue(any(item['id'] == 'wifi-network-scan' for item in registry))
        self.assertTrue(any(item['id'] == 'reports' for item in registry))

    @patch('routes.capabilities.install_host_dependency')
    def test_capabilities_can_install_browser_screenshot_dependency(self, install_dependency):
        install_dependency.return_value = {'dependency': 'browser-screenshot', 'installed': True, 'message': 'Browser screenshot tooling installed.'}

        response = self.client.post('/capabilities/install-host-dependency', data={'dependency': 'browser-screenshot', 'confirm': 'install'})

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['status'], 'success')
        self.assertTrue(payload['installed'])
        install_dependency.assert_called_once_with('browser-screenshot')

    def test_capabilities_host_dependency_install_requires_confirmation(self):
        response = self.client.post('/capabilities/install-host-dependency', data={'dependency': 'browser-screenshot'})

        self.assertEqual(response.status_code, 400)
        self.assertIn('Confirm host package installation', response.get_json()['message'])

    def test_adapter_updates_returns_partial_fragments_when_changed(self):
        response = self.client.post('/adapters/updates', json={'snapshot': 'stale', 'title': 'Home'})

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload['changed'])
        self.assertIn('primary_nav_links', payload['fragments'])
        self.assertIn('interface_categories', payload['fragments'])

        response = self.client.post('/adapters/updates', json={'snapshot': payload['snapshot'], 'title': 'Home'})
        self.assertFalse(response.get_json()['changed'])

    def test_export_routes_return_json(self):
        response = self.client.get('/export/interfaces.json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('interfaces', response.get_json())

        response = self.client.get('/export/capabilities.json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('capabilities', response.get_json())

    def test_diagnostics_page_and_nav_render(self):
        response = self.client.get('/diagnostics')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Ping &amp; Route Diagnostics', response.data)
        self.assertIn(b'id="ping-host"', response.data)
        self.assertIn(b'id="route-diagnostics-btn"', response.data)

    def test_network_scan_page_includes_comprehensive_device_scan(self):
        response = self.client.get('/network-scan')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Comprehensive Device Scan', response.data)
        self.assertIn(b'id="sweep-cidr"', response.data)
        self.assertIn(b'Include mDNS, UPnP/SSDP, and LLDP/CDP', response.data)
        self.assertIn(b'interface.css', response.data)

    def test_network_scan_results_render_device_cards_and_scan_all_actions(self):
        with open('static/js/network_scan.js') as handle:
            js = handle.read()

        self.assertIn('network-device-card', js)
        self.assertIn('Scan all common ports', js)
        self.assertIn('Scan all ports', js)
        self.assertIn('data-port-scan-all', js)
        self.assertIn('Device profile', js)
        self.assertIn('Port scan', js)

    @patch('app.discover_lldp_neighbors')
    @patch('app.discover_upnp_devices')
    @patch('app.discover_mdns_services')
    @patch('app._run_text_command')
    @patch('app.passive_scan')
    @patch('app.active_scan')
    def test_comprehensive_scan_combines_methods_and_inventory(self, active, passive, run_command, mdns, upnp, lldp):
        app_module.device_inventory.clear()
        app_module.new_device_alerts.clear()
        active.return_value = [{'ip': '192.168.1.10', 'mac': 'AA:BB:CC:DD:EE:10'}]
        passive.return_value = [{'ip': '192.168.1.11', 'mac': 'AA:BB:CC:DD:EE:11'}]
        run_command.side_effect = [
            {'output': '192.168.1.12 dev eth0 lladdr aa:bb:cc:dd:ee:12 REACHABLE'},
            {'output': '? (192.168.1.13) at aa:bb:cc:dd:ee:13 [ether] on eth0'},
        ]
        mdns.return_value = {'services': [{'ip': '192.168.1.14', 'hostname': 'printer.local', 'name': 'Printer', 'role': 'Printer'}]}
        upnp.return_value = {'devices': [{'ip': '192.168.1.1', 'friendly_name': 'Gateway', 'manufacturer': 'Training', 'role': 'Gateway/router'}]}
        lldp.return_value = {'neighbors': [{'management_address': '192.168.1.2', 'name': 'Switch', 'role': 'Switch/router neighbor'}]}

        response = self.client.post('/comprehensive-scan', data={'selectedInterface': 'eth0', 'includePassive': 'on', 'includeServices': 'on'})

        self.assertEqual(response.status_code, 200)
        result = response.get_json()['result']
        self.assertEqual(result['summary']['total_devices'], 7)
        self.assertIn('active-arp', result['methods'])
        self.assertIn('mdns', result['methods'])
        self.assertTrue(any('neighbor-table' in item['discovery_methods'] for item in result['devices']))
        self.assertIsNotNone(app_module.find_inventory_device('192.168.1.14'))
        self.assertEqual(app_module.alert_records()[0]['alert_type'], 'grouped-discovery')

    @patch('app.discover_lldp_neighbors')
    @patch('app.discover_upnp_devices')
    @patch('app.discover_mdns_services')
    @patch('app._run_text_command')
    @patch('app.run_ping_sweep')
    @patch('app.passive_scan')
    @patch('app.active_scan')
    def test_comprehensive_scan_can_skip_passive_and_add_ping_sweep(self, active, passive, ping_sweep, run_command, mdns, upnp, lldp):
        app_module.device_inventory.clear()
        active.return_value = []
        run_command.side_effect = [{'output': ''}, {'output': ''}]
        mdns.return_value = {'services': []}
        upnp.return_value = {'devices': []}
        lldp.return_value = {'neighbors': []}
        ping_sweep.return_value = {'results': [{'host': '192.168.1.20', 'reachable': True}]}

        response = self.client.post('/comprehensive-scan', data={'selectedInterface': 'eth0', 'includePassive': '', 'includeServices': 'on', 'sweepCidr': '192.168.1.0/30'})

        self.assertEqual(response.status_code, 200)
        result = response.get_json()['result']
        self.assertIn('ping-sweep', result['methods'])
        self.assertFalse(passive.called)
        self.assertEqual(result['devices'][0]['ip'], '192.168.1.20')

    def test_service_discovery_page_renders_protocol_controls(self):
        response = self.client.get('/service-discovery')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Service Discovery', response.data)
        self.assertIn(b'id="mdns-discovery-btn"', response.data)
        self.assertIn(b'id="upnp-discovery-btn"', response.data)
        self.assertIn(b'id="neighbor-discovery-btn"', response.data)

    def test_advanced_diagnostics_page_renders_toolkit_controls(self):
        response = self.client.get('/advanced-diagnostics')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Advanced Diagnostics', response.data)
        self.assertIn(b'id="vlan-discovery-btn"', response.data)
        self.assertIn(b'id="egress-diagnostics-btn"', response.data)
        self.assertIn(b'id="iperf-client-btn"', response.data)
        self.assertIn(b'id="snmp-discovery-btn"', response.data)
        self.assertIn(b'id="ipv6-assessment-btn"', response.data)

    @patch('app._run_text_command')
    @patch('app.shutil.which', return_value='/usr/bin/avahi-browse')
    def test_mdns_discovery_parses_services_and_updates_inventory(self, which, run_command):
        app_module.device_inventory.clear()
        run_command.return_value = {
            'returncode': 0,
            'output': '=;eth0;IPv4;Office Printer;_ipp._tcp;local;printer.local;192.168.1.40;631;txtvers=1;note=Lab',
        }

        response = self.client.post('/mdns-discovery', data={'selectedInterface': 'eth0'})

        self.assertEqual(response.status_code, 200)
        result = response.get_json()['result']
        self.assertEqual(result['services'][0]['hostname'], 'printer.local')
        self.assertEqual(result['services'][0]['role'], 'Printer')
        inventory = app_module.find_inventory_device('192.168.1.40')
        self.assertEqual(inventory['service_metadata']['service_type'], '_ipp._tcp')

    @patch('app.discover_upnp_devices')
    def test_upnp_discovery_route_returns_devices(self, discover):
        discover.return_value = {
            'available': True,
            'message': 'Discovered 1 UPnP/SSDP device(s).',
            'devices': [{
                'friendly_name': 'Lab Gateway',
                'ip': '192.168.1.1',
                'manufacturer': 'Training Vendor',
                'model': 'Router 1',
                'service_type': 'urn:schemas-upnp-org:device:InternetGatewayDevice:1',
                'control_url': 'http://192.168.1.1/rootDesc.xml',
            }],
        }

        response = self.client.post('/upnp-discovery', data={'timeout': '1'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['result']['devices'][0]['friendly_name'], 'Lab Gateway')
        discover.assert_called_once_with(timeout=1)

    @patch('app._run_text_command')
    @patch('app.shutil.which', return_value='/usr/sbin/lldpctl')
    def test_lldp_neighbor_discovery_parses_ports_vlans_and_management(self, which, run_command):
        app_module.device_inventory.clear()
        run_command.return_value = {
            'returncode': 0,
            'output': '\n'.join([
                'lldp.eth0.chassis.name="Lab-Switch"',
                'lldp.eth0.port.ifname="Gi1/0/1"',
                'lldp.eth0.mgmt-ip="192.168.1.2"',
                'lldp.eth0.vlan.1.vid="20"',
            ]),
        }

        response = self.client.post('/neighbor-discovery', data={'selectedInterface': 'eth0'})

        self.assertEqual(response.status_code, 200)
        neighbor = response.get_json()['result']['neighbors'][0]
        self.assertEqual(neighbor['name'], 'Lab-Switch')
        self.assertEqual(neighbor['port_id'], 'Gi1/0/1')
        self.assertEqual(neighbor['vlans'], ['20'])
        inventory = app_module.find_inventory_device('192.168.1.2')
        self.assertEqual(inventory['device_type'], 'Switch/router neighbor')

    @patch('app._run_text_command')
    def test_vlan_discovery_tracks_interfaces_and_notes(self, run_command):
        app_module.vlan_segmentation_notes.clear()
        run_command.return_value = {
            'returncode': 0,
            'output': '5: eth0.20@eth0: <BROADCAST> mtu 1500\n    vlan protocol 802.1Q id 20 <REORDER_HDR>',
        }

        response = self.client.post('/vlan-discovery', data={'ssid': 'CorpWiFi', 'vlanId': '20', 'notes': 'Guest blocked from admin VLAN'})

        self.assertEqual(response.status_code, 200)
        result = response.get_json()['result']
        self.assertEqual(result['vlans'][0]['interface'], 'eth0.20')
        self.assertEqual(result['created_note']['ssid'], 'CorpWiFi')
        self.assertIn('inter-VLAN firewall rules', result['created_note']['validation_context'])

    @patch('app.build_route_diagnostics', return_value={'vpn_hints': [{'interface': 'tun0'}]})
    @patch('app._run_text_command')
    def test_egress_diagnostics_reports_nat_dns_ipv6_and_proxy(self, run_command, route_diag):
        run_command.side_effect = [
            {'output': 'default via fe80::1 dev eth0'},
            {'output': 'default via 192.168.1.1 dev eth0'},
        ]
        with (
            patch('urllib.request.urlopen') as urlopen,
            patch('builtins.open', unittest.mock.mock_open(read_data='nameserver 9.9.9.9\n')),
            patch.dict('os.environ', {'HTTPS_PROXY': 'http://proxy.local:8080'}, clear=False),
        ):
            urlopen.return_value.__enter__.return_value.read.return_value = b'203.0.113.5'
            response = self.client.post('/egress-diagnostics', data={'selectedInterface': 'eth0'})

        self.assertEqual(response.status_code, 200)
        result = response.get_json()['result']
        self.assertEqual(result['public_ip'], '203.0.113.5')
        self.assertEqual(result['dns_resolvers'], ['9.9.9.9'])
        self.assertEqual(result['vpn_hints'][0]['interface'], 'tun0')
        self.assertIn('HTTPS_PROXY', result['proxy_hints'])

    @patch('app.subprocess.run')
    @patch('app.shutil.which', return_value='/usr/bin/iperf3')
    def test_iperf3_client_runs_bounded_json_test(self, which, run):
        run.return_value = SimpleNamespace(returncode=0, stdout='{"end":{"sum_received":{"bits_per_second":1000}}}', stderr='')

        response = self.client.post('/iperf3-test', data={'mode': 'client', 'host': '192.168.1.10', 'port': '5201', 'seconds': '3'})

        self.assertEqual(response.status_code, 200)
        result = response.get_json()['result']
        self.assertEqual(result['summary']['bits_per_second'], 1000)
        self.assertIn('-t', result['command'])

    @patch('app.subprocess.run')
    @patch('app.shutil.which', return_value='/usr/bin/snmpwalk')
    def test_snmp_discovery_requires_authorization_and_records_inventory(self, which, run):
        app_module.device_inventory.clear()
        response = self.client.post('/snmp-discovery', data={'host': '192.168.1.2', 'community': 'public'})
        self.assertEqual(response.status_code, 400)

        run.return_value = SimpleNamespace(returncode=0, stdout='Lab Switch\nInterface 1\n', stderr='')
        response = self.client.post('/snmp-discovery', data={'host': '192.168.1.2', 'community': 'public', 'authorized': 'on'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['result']['values'][0], 'Lab Switch')
        inventory = app_module.find_inventory_device('192.168.1.2')
        self.assertEqual(inventory['device_type'], 'SNMP device')

    @patch('app.shutil.which', return_value='/usr/bin/traceroute')
    @patch('app.socket.create_connection')
    @patch('app.socket.getaddrinfo', return_value=[(None, None, None, None, ('2001:db8::10', 0, 0, 0))])
    @patch('app._run_text_command')
    def test_ipv6_assessment_reports_ping_dns_neighbors_and_ports(self, run_command, getaddrinfo, create_connection, which):
        run_command.side_effect = [
            {'output': '3 packets transmitted, 3 received'},
            {'output': 'traceroute to 2001:db8::10'},
            {'output': 'fe80::1 dev eth0 lladdr 00:11:22:33:44:55 router'},
            {'output': 'default via fe80::1 dev eth0'},
        ]
        create_connection.return_value.__enter__.return_value = None

        response = self.client.post('/ipv6-assessment', data={'host': '2001:db8::10', 'ports': '443'})

        self.assertEqual(response.status_code, 200)
        result = response.get_json()['result']
        self.assertEqual(result['dns_aaaa'], ['2001:db8::10'])
        self.assertIn('fe80::1', result['neighbors'])
        self.assertEqual(result['ports'][0]['status'], 'open')

    @patch('app.subprocess.run')
    def test_ping_route_reports_loss_latency_and_history(self, run):
        run.return_value = SimpleNamespace(
            returncode=0,
            stdout='4 packets transmitted, 4 received, 0% packet loss\nrtt min/avg/max/mdev = 1.1/2.2/3.3/0.1 ms',
            stderr='',
        )
        app_module.ping_history.clear()

        response = self.client.post('/ping', data={'host': '192.0.2.10', 'count': '4', 'timeout': '1'})

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['result']['packet_loss_percent'], 0.0)
        self.assertEqual(payload['result']['latency']['avg_ms'], 2.2)
        self.assertTrue(payload['history'])

    @patch('app.run_ping_check')
    def test_ping_sweep_limits_and_summarizes_hosts(self, ping_check):
        ping_check.side_effect = lambda host, count=1, timeout=1: {
            'host': host,
            'reachable': host.endswith('.1'),
            'packet_loss_percent': 0.0 if host.endswith('.1') else 100.0,
            'latency': {},
            'checked_at': 1,
        }

        response = self.client.post('/ping-sweep', data={'cidr': '192.168.1.0/30'})

        self.assertEqual(response.status_code, 200)
        sweep = response.get_json()['sweep']
        self.assertEqual(sweep['total_hosts'], 2)
        self.assertEqual(sweep['reachable_hosts'], 1)

    @patch('app.subprocess.run')
    def test_route_diagnostics_reports_gateways_vpn_and_scan_path(self, run):
        def fake_run(command, **kwargs):
            if command == ['ip', '-4', 'route', 'show']:
                return SimpleNamespace(returncode=0, stdout='default via 192.168.1.1 dev eth0 proto dhcp metric 100\n10.8.0.0/24 dev tun0 proto kernel metric 50', stderr='')
            if command == ['ip', '-6', 'route', 'show']:
                return SimpleNamespace(returncode=0, stdout='default via fe80::1 dev eth0 metric 1024', stderr='')
            return SimpleNamespace(returncode=0, stdout='1.1.1.1 via 192.168.1.1 dev eth0 src 192.168.1.20', stderr='')
        run.side_effect = fake_run

        response = self.client.post('/route-diagnostics', data={'target': '1.1.1.1'})

        self.assertEqual(response.status_code, 200)
        diagnostics = response.get_json()['diagnostics']
        self.assertEqual(diagnostics['default_gateways'][0]['gateway'], '192.168.1.1')
        self.assertEqual(diagnostics['vpn_hints'][0]['interface'], 'tun0')
        self.assertIn('1.1.1.1 via 192.168.1.1', diagnostics['scan_path_context'])



    def test_port_scan_pages_include_cancel_controls(self):
        response = self.client.get('/port-scan')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'data-port-scan-cancel', response.data)

        with patch('app.get_mac_by_ip', return_value='48:b0:2d:ef:ec:f2'):
            response = self.client.get('/clients/192.168.20.1')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Device Port Scan', response.data)
        self.assertIn(b'data-port-scan-cancel', response.data)

    def test_evidence_vault_records_and_exports_artifacts(self):
        app_module.evidence_vault.clear()

        response = self.client.get('/evidence')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Evidence and Loot Vault', response.data)

        response = self.client.post('/evidence', data={
            'title': 'Router scan output',
            'category': 'scan-output',
            'source': 'active-scan',
            'device': '192.168.20.1',
            'notes': 'Gateway exposed SSH and DNS during lab scan.',
            'content': 'Open ports: 22, 53',
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['status'], 'success')
        self.assertEqual(payload['evidence']['category'], 'scan-output')

        response = self.client.get('/evidence.json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['evidence'][0]['title'], 'Router scan output')

        response = self.client.get('/reports.json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['evidence'][0]['title'], 'Router scan output')

    def test_reports_page_and_exports_render(self):
        app_module.device_inventory.clear()
        app_module.new_device_alerts.clear()
        app_module.record_inventory_devices([
            {'ip': '192.168.20.10', 'mac': '48:b0:2d:ef:ec:f2'},
        ], 'test-scan', 'eth0')

        response = self.client.get('/reports')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Reports', response.data)
        self.assertIn(b'/reports.json', response.data)

        response = self.client.get('/reports.json')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn('devices', payload)
        self.assertIn('capabilities', payload)
        self.assertIn('alerts', payload)

        response = self.client.get('/reports.csv')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response.content_type)
        self.assertIn(b'Mobile Router Report', response.data)

        response = self.client.get('/reports.md')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'# Mobile Router Report', response.data)

        response = self.client.get('/reports.html')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Mobile Router Report', response.data)


    def test_oui_lookup_accepts_common_formats_and_fallbacks(self):
        status = oui_database_status()

        self.assertTrue(status['loaded'])
        self.assertGreaterEqual(status['entries'], status['fallback_entries'])
        self.assertIn(status['coverage'], {'compact', 'full'})
        self.assertEqual(status['needs_refresh'], status['entries'] < status['full_entry_threshold'])
        self.assertEqual(lookup_manufacturer('b8:27:eb:11:22:33'), 'Raspberry Pi Foundation')
        self.assertEqual(lookup_manufacturer('B8-27-EB-11-22-33'), 'Raspberry Pi Foundation')
        self.assertEqual(lookup_manufacturer('b827eb112233'), 'Raspberry Pi Foundation')
        self.assertEqual(lookup_manufacturer('52:54:00:12:34:56'), 'QEMU/KVM Virtual NIC')
        self.assertEqual(lookup_manufacturer('8c:49:62:bd:7d:37'), 'Roku, Inc.')
        self.assertEqual(lookup_manufacturer('8C-49-62-BD-7D-37'), 'Roku, Inc.')
        from scripts.wifi import utils as wifi_utils
        self.assertEqual(wifi_utils._mac_manufacturer('8c:49:62:bd:7d:37'), 'Roku, Inc.')
        self.assertEqual(app_module.lookup_manufacturer('8c:49:62:bd:7d:37'), 'Roku, Inc.')
        self.assertEqual(lookup_manufacturer('not-a-mac'), 'Unknown')

    def test_oui_downloader_tries_fallback_urls(self):
        from scripts import update_oui_db

        calls = []

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'Registry,Assignment,Organization Name\nMA-L,8C4962,"Roku, Inc."\n'

        def fake_open(request, timeout=30):
            calls.append(request.full_url)
            if len(calls) == 1:
                raise OSError('blocked')
            return FakeResponse()

        with tempfile.TemporaryDirectory() as tmpdir:
            path, count = update_oui_db.download_oui_database(
                output_path=os.path.join(tmpdir, 'oui_db.csv'),
                opener=fake_open,
            )
            self.assertEqual(count, 1)
            self.assertGreaterEqual(len(calls), 2)
            with open(path, encoding='utf-8') as handle:
                self.assertIn('8c:49:62,Roku, Inc.', handle.read())

    @patch('routes.capabilities.refresh_oui_database')
    @patch('routes.capabilities.download_oui_database')
    def test_capabilities_can_download_full_oui_database(self, download_oui, refresh_oui):
        download_oui.return_value = ('/tmp/oui_db.csv', 35000)
        refresh_oui.return_value = {'loaded': True, 'entries': 35000, 'coverage': 'full', 'needs_refresh': False}

        response = self.client.post('/capabilities/update-oui-database', data={'confirm': 'download'})

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['count'], 35000)
        self.assertEqual(payload['oui_database']['coverage'], 'full')

    def test_capabilities_oui_download_requires_confirmation(self):
        response = self.client.post('/capabilities/update-oui-database', data={})

        self.assertEqual(response.status_code, 400)
        self.assertIn('Confirm full IEEE OUI database download', response.get_json()['message'])

    def test_capabilities_page_shows_oui_database_health(self):
        response = self.client.get('/capabilities')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'OUI Vendor Lookup', response.data)
        self.assertIn(b'Fallback entries', response.data)
        self.assertIn(b'python scripts/update_oui_db.py', response.data)
        self.assertIn(b'Coverage', response.data)
        self.assertIn(b'Download full OUI database', response.data)

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

    @patch('scripts.networkScan._get_ipv4_cidr', return_value='192.168.20.2/24')
    def test_scan_classification_marks_internal_control_traffic(self, _cidr):
        from scripts.networkScan import classify_scan_results

        devices = classify_scan_results([
            {'ip': '224.0.0.251', 'mac': '01:00:5e:00:00:fb'},
            {'ip': '192.168.20.255', 'mac': 'ff:ff:ff:ff:ff:ff'},
            {'ip': '192.168.20.1', 'mac': 'ac:16:2d:a2:71:9e'},
            {'ip': '8.8.8.8', 'mac': '00:11:22:33:44:55'},
        ], 'eth0')

        self.assertEqual(devices[0]['network_role'], 'Multicast')
        self.assertTrue(devices[0]['is_control_traffic'])
        self.assertEqual(devices[1]['network_role'], 'Subnet broadcast')
        self.assertTrue(devices[1]['is_control_traffic'])
        self.assertEqual(devices[2]['network_role'], 'Likely gateway/router')
        self.assertEqual(devices[2]['network_scope'], 'Private LAN')
        self.assertEqual(devices[3]['network_scope'], 'Public Internet')

    @patch('app.passive_scan')
    @patch('scripts.networkScan._get_ipv4_cidr', return_value='192.168.20.2/24')
    def test_passive_scan_response_includes_network_role_metadata(self, _cidr, scan):
        app_module.device_inventory.clear()
        scan.return_value = [{'ip': '224.0.0.251', 'mac': '01:00:5e:00:00:fb'}]

        response = self.client.post('/passive-scan', data={'selectedInterface': 'eth0'})

        self.assertEqual(response.status_code, 200)
        device = response.get_json()['devices'][0]
        self.assertEqual(device['network_role'], 'Multicast')
        self.assertEqual(device['network_scope'], 'Local segment')
        self.assertTrue(device['is_control_traffic'])

    @patch('scripts.networkScan._parse_proc_arp', return_value=[
        {'ip': '192.168.20.3', 'mac': '48:b0:2d:ef:ec:f2'},
    ])
    @patch('scripts.networkScan.get_mac_by_ip', return_value='ac:16:2d:a2:71:9e')
    @patch('scripts.networkScan._ping_host', side_effect=lambda ip: str(ip) if str(ip) == '192.168.20.1' else None)
    @patch('scripts.networkScan._get_ipv4_cidr', return_value='192.168.20.2/29')
    def test_active_scan_is_bounded_and_merges_arp_cache(self, _cidr, _ping, _mac, _arp):
        from scripts.networkScan import active_scan

        hosts = active_scan('eth0')

        self.assertEqual(hosts, [
            {'ip': '192.168.20.1', 'mac': 'ac:16:2d:a2:71:9e'},
            {'ip': '192.168.20.3', 'mac': '48:b0:2d:ef:ec:f2'},
        ])

    @patch('scripts.networkScan._get_ipv4_cidr', return_value='10.0.0.1/20')
    @patch('scripts.networkScan._parse_proc_arp', return_value=[])
    @patch('scripts.networkScan._parse_arp_command', return_value=[])
    def test_active_scan_skips_overly_large_subnets(self, _arp_command, _proc_arp, _cidr):
        from scripts.networkScan import active_scan

        self.assertEqual(active_scan('eth0'), [])

    @patch('scripts.networkScan._parse_arp_command', return_value=[])
    @patch('scripts.networkScan._parse_proc_arp')
    @patch('scripts.networkScan._get_ipv4_cidr', return_value=None)
    def test_active_scan_falls_back_to_arp_cache_when_cidr_unknown(self, _cidr, proc_arp, _arp_command):
        from scripts.networkScan import active_scan

        proc_arp.side_effect = [[], [{'ip': '192.168.20.40', 'mac': 'aa:bb:cc:dd:ee:40'}]]

        self.assertEqual(active_scan('WiFi'), [{'ip': '192.168.20.40', 'mac': 'aa:bb:cc:dd:ee:40'}])

    def test_port_scan_page_mentions_device_prefill(self):
        response = self.client.get('/port-scan?host=192.168.20.10')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'live progress updates', response.data)
        self.assertIn(b'id="scan-host"', response.data)
        self.assertIn(b'port_scan_live.js', response.data)

    def test_client_detail_links_to_device_port_scan(self):
        app_module.device_inventory.clear()
        app_module.record_device_open_ports('192.168.20.10', [
            {'port': 22, 'service': 'SSH', 'description': 'Secure shell remote administration'},
            {'port': 80, 'service': 'HTTP', 'description': 'Web server'},
        ])

        response = self.client.get('/clients/192.168.20.10')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Saved Service Profile', response.data)
        self.assertIn(b'22/tcp', response.data)
        self.assertIn(b'SSH', response.data)
        self.assertIn(b'href="http://192.168.20.10:80/"', response.data)
        self.assertIn(b'target="_blank"', response.data)
        self.assertIn(b'Device Port Scan', response.data)
        self.assertIn(b'Common ports', response.data)
        self.assertIn(b'All ports', response.data)
        self.assertIn(b'/port-scan?host=192.168.20.10', response.data)
        self.assertIn(b'IP Client Actions', response.data)
        self.assertIn(b'Client Health', response.data)
        self.assertIn(b'Watch this device', response.data)
        self.assertIn(b'Inspect web services', response.data)
        self.assertIn(b'Fingerprint services', response.data)
        self.assertIn(b'Save baseline', response.data)
        self.assertIn(b'Client Profile Metadata', response.data)
        self.assertIn(b'Expected open ports', response.data)
        self.assertIn(b'Export JSON', response.data)
        self.assertIn(b'Export Markdown', response.data)
        self.assertIn(b'Client Relationship Map', response.data)
        self.assertIn(b'Scheduled Client Checks', response.data)
        self.assertIn(b'Client Timeline', response.data)
        self.assertIn(b'Port scan', response.data)
        self.assertIn(b'data-ip-client-ping', response.data)
        self.assertIn(b'data-ip-client-route', response.data)
        self.assertIn(b'data-ip-client-traceroute', response.data)
        self.assertIn(b'Save evidence note', response.data)
        self.assertIn(b'port_scan_live.js', response.data)
        self.assertIn(b'ip_client.js', response.data)

    def test_ip_client_detail_uses_detected_inventory_name_as_title(self):
        app_module.device_inventory.clear()
        app_module.record_inventory_devices([
            {'ip': '192.168.20.30', 'hostname': 'printer.local', 'name': 'Lab Printer', 'manufacturer': 'PrinterCo'},
        ], 'mdns-discovery', 'eth0')

        response = self.client.get('/clients/192.168.20.30')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<h1 class="page-title">Lab Printer</h1>', response.data)
        self.assertIn(b'Device identity and manufacturer details', response.data)

    @patch('app._dhcp_lease_display_name', return_value='')
    @patch('app.socket.gethostbyaddr', return_value=('camera.lab.local', [], ['192.168.20.31']))
    def test_ip_client_detail_detects_reverse_dns_name(self, _reverse_dns, _dhcp):
        app_module.device_inventory.clear()
        app_module.record_inventory_devices([
            {'ip': '192.168.20.31', 'mac': '48:b0:2d:ef:ec:f3', 'manufacturer': 'CameraCo'},
        ], 'active-scan', 'eth0')

        response = self.client.get('/clients/192.168.20.31')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<h1 class="page-title">camera.lab.local</h1>', response.data)
        self.assertIn(b'display name learned from reverse-dns', response.data)
        device = app_module.find_inventory_device('192.168.20.31')
        self.assertEqual(device['detected_display_name'], 'camera.lab.local')

    def test_ip_client_actions_script_posts_diagnostics_and_evidence(self):
        js = open('static/js/ip_client.js').read()

        self.assertIn("url: '/ping'", js)
        self.assertIn("url: '/route-diagnostics'", js)
        self.assertIn("url: '/traceroute'", js)
        self.assertIn("url: '/evidence'", js)
        self.assertIn('data-ip-client-evidence-form', js)
        self.assertIn('data-ip-client-watch', js)
        self.assertIn('http-inspect', js)
        self.assertIn('data-ip-client-baseline', js)
        self.assertIn('data-ip-client-metadata-form', js)
        self.assertIn('data-ip-client-fingerprint', js)
        self.assertIn('data-ip-client-intelligence', js)
        self.assertIn('/intelligence', js)
        self.assertIn('Device intelligence snapshot', js)
        self.assertIn('data-ip-client-scheduled-form', js)

    def test_port_scan_scripts_link_web_ports_and_quick_scan_in_place(self):
        live_js = open('static/js/port_scan_live.js').read()
        jobs_js = open('static/js/jobs.js').read()
        network_js = open('static/js/network_scan.js').read()

        self.assertIn('info.web_url', live_js)
        self.assertIn('target="_blank"', live_js)
        self.assertIn('info.web_url', jobs_js)
        self.assertIn('data-port-scan-quick', network_js)
        self.assertIn("url: '/port-scan-jobs'", network_js)
        self.assertIn('startQuickPortScan', network_js)
        self.assertIn('pollQuickPortScan', network_js)
        self.assertIn('/summary', network_js)
        self.assertIn('data-network-device-notes-form', network_js)
        self.assertIn('data-network-device-filter', network_js)
        self.assertIn('data-port-scan-quick-progress', network_js)
        self.assertIn('data-network-device-label-form', network_js)
        self.assertIn('/wireless/network/label', network_js)
        self.assertIn('isNetworkDeviceListMode', network_js)
        self.assertIn('refreshNetworkDeviceList', network_js)
        self.assertIn('/wireless/network/clients.json', network_js)
        self.assertNotIn('window.location.reload()', network_js)
        self.assertIn('Active scan saved', network_js)

    def test_client_summary_returns_latest_card_fields(self):
        app_module.device_inventory.clear()
        app_module.record_device_open_ports('192.168.20.70', [
            {'port': 80, 'service': 'HTTP', 'description': 'Web server', 'http_title': 'Router Console'},
        ])
        app_module.update_client_metadata('192.168.20.70', {'tags': 'router,critical', 'notes': 'Core gateway'})

        response = self.client.get('/clients/192.168.20.70/summary')

        self.assertEqual(response.status_code, 200)
        device = response.get_json()['device']
        self.assertEqual(device['client_tags'], ['critical', 'router'])
        self.assertEqual(device['client_notes'], 'Core gateway')
        self.assertEqual(device['open_port_details'][0]['web_url'], 'http://192.168.20.70:80/')
        self.assertEqual(device['open_port_details'][0]['http_title'], 'Router Console')

    @patch('app.fingerprint_client_services')
    @patch('app._dhcp_lease_display_name', return_value='camera-dhcp')
    @patch('app._reverse_dns_display_name', return_value='camera.lab.local')
    @patch('app.socket.getaddrinfo', return_value=[(None, None, None, None, ('192.168.20.71', 0))])
    def test_client_intelligence_reports_dns_dhcp_os_services_and_recommendations(self, _addrinfo, _reverse, _dhcp, fingerprint):
        app_module.device_inventory.clear()
        app_module.ping_history.clear()
        fingerprint.return_value = [{'port': 80, 'service': 'HTTP', 'confidence': 'high'}]
        app_module.record_inventory_devices([
            {'ip': '192.168.20.71', 'mac': '02:11:22:33:44:55', 'manufacturer': 'Unknown'},
        ], 'active-scan', 'eth0')
        app_module.record_device_open_ports('192.168.20.71', [
            {'port': 80, 'service': 'HTTP', 'description': 'Web service'},
            {'port': 445, 'service': 'SMB', 'description': 'SMB file sharing'},
        ])
        app_module.ping_history.append({'host': '192.168.20.71', 'output': '64 bytes from 192.168.20.71: icmp_seq=1 ttl=64 time=1.2 ms', 'checked_at': time.time()})

        response = self.client.post('/clients/192.168.20.71/intelligence', data={'activeProbe': 'on'})

        self.assertEqual(response.status_code, 200)
        info = response.get_json()['intelligence']
        self.assertEqual(info['dhcp']['hostname'], 'camera-dhcp')
        self.assertEqual(info['dns']['reverse'], 'camera.lab.local')
        self.assertEqual(info['dns']['forward'][0]['addresses'], ['192.168.20.71'])
        self.assertIn('Linux/Unix', info['os_hint']['hint'])
        self.assertEqual(info['services']['open_port_count'], 2)
        self.assertEqual(info['services']['sensitive_port_count'], 1)
        self.assertEqual(info['services']['fingerprints'][0]['service'], 'HTTP')
        self.assertTrue(any('Sensitive' in item for item in info['recommendations']))

    def test_client_metadata_baseline_and_exports(self):
        app_module.device_inventory.clear()
        app_module.record_device_open_ports('192.168.20.10', [
            {'port': 22, 'service': 'SSH', 'description': 'Secure shell remote administration'},
            {'port': 80, 'service': 'HTTP', 'description': 'Web service'},
        ])

        response = self.client.post('/clients/192.168.20.10/metadata', data={
            'tags': 'trusted, router',
            'owner': 'Lab',
            'location': 'Bench',
            'expectedPorts': '22,443',
            'notes': 'Expected lab gateway.',
        })
        self.assertEqual(response.status_code, 200)
        device = response.get_json()['device']
        self.assertEqual(device['client_tags'], ['router', 'trusted'])
        self.assertEqual(device['client_owner'], 'Lab')
        self.assertEqual(device['expected_open_ports'], [22, 443])

        response = self.client.get('/clients/192.168.20.10')
        self.assertIn(b'Drift detected', response.data)
        self.assertIn(b'Unexpected 80', response.data)
        self.assertIn(b'Missing 443', response.data)

        response = self.client.post('/clients/192.168.20.10/baseline')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['baseline']['status'], 'Baseline saved')

        response = self.client.get('/clients/192.168.20.10/export.json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['host'], '192.168.20.10')

        response = self.client.get('/clients/192.168.20.10/export.md')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Client profile: 192.168.20.10', response.data)

    @patch('app.inspect_http_services')
    def test_client_relationship_fingerprint_schedule_and_inventory_badges(self, inspect_http):
        app_module.device_inventory.clear()
        app_module.scheduled_client_checks.clear()
        app_module.watched_clients.clear()
        inspect_http.return_value = [{'port': 80, 'url': 'http://192.168.20.10:80/', 'status': 200, 'title': 'Router UI', 'server': 'lab', 'error': None}]
        app_module.record_inventory_devices([
            {'ip': '192.168.20.10', 'mac': '48:b0:2d:ef:ec:f2', 'manufacturer': 'Example', 'interfaces': ['eth0']}
        ], 'active-scan', 'eth0')
        app_module.record_device_open_ports('192.168.20.10', [
            {'port': 80, 'service': 'HTTP', 'description': 'Web service'},
        ])
        app_module.update_client_metadata('192.168.20.10', {'tags': 'router', 'expectedPorts': '22'})
        app_module.watched_clients.add('192.168.20.10')

        response = self.client.get('/clients/192.168.20.10/relationship-map')
        self.assertEqual(response.status_code, 200)
        node_labels = [node['label'] for node in response.get_json()['map']['nodes']]
        self.assertIn('192.168.20.10', node_labels)
        self.assertIn('80/tcp HTTP', node_labels)

        response = self.client.post('/clients/192.168.20.10/fingerprint')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['fingerprints'][0]['http']['title'], 'Router UI')

        response = self.client.post('/clients/192.168.20.10/scheduled-check', data={
            'intervalMinutes': '30',
            'checks': 'ping,common-ports,baseline-drift',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['plan']['interval_minutes'], 30)
        self.assertIn('baseline-drift', response.get_json()['plan']['checks'])

        response = self.client.get('/inventory')
        self.assertIn(b'Drift', response.data)
        self.assertIn(b'Watched', response.data)
        self.assertIn(b'router', response.data)

    @patch('app.scan_common_client_ports')
    @patch('app.run_ping_check')
    def test_scheduled_check_can_run_saved_plan_on_demand_and_due(self, ping_check, common_ports):
        app_module.device_inventory.clear()
        app_module.scheduled_client_checks.clear()
        app_module.client_timelines.clear()
        ping_check.return_value = {'host': '192.168.20.10', 'reachable': True, 'packet_loss_percent': 0}
        common_ports.return_value = [{'port': 80, 'service': 'HTTP', 'description': 'Web service'}]
        app_module.record_inventory_devices([
            {'ip': '192.168.20.10', 'mac': '48:b0:2d:ef:ec:f2', 'interfaces': ['eth0']}
        ], 'active-scan', 'eth0')

        response = self.client.post('/clients/192.168.20.10/scheduled-check', data={
            'intervalMinutes': '30',
            'checks': 'ping,common-ports,baseline-drift',
        })
        self.assertEqual(response.status_code, 200)

        response = self.client.post('/clients/192.168.20.10/scheduled-check/run')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn('ping', payload['plan']['last_result'])
        self.assertIn('common_ports', payload['plan']['last_result'])
        self.assertIsNotNone(payload['plan']['last_run'])
        self.assertIn('192.168.20.10', app_module.client_timelines)

        app_module.scheduled_client_checks['192.168.20.10']['last_run'] = 0
        response = self.client.post('/scheduled-checks/run-due')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['count'], 1)

    def test_client_watch_alerts_on_new_open_ports(self):
        app_module.device_inventory.clear()
        app_module.new_device_alerts.clear()
        app_module.watched_clients.clear()

        response = self.client.post('/clients/192.168.20.10/watch', data={'watch': 'on'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['watched'])

        app_module.record_device_open_ports('192.168.20.10', [
            {'port': 22, 'service': 'SSH', 'description': 'Secure shell remote administration'},
        ])

        alerts = app_module.alert_records()
        self.assertEqual(alerts[0]['alert_type'], 'watched-client')
        self.assertIn('New open port', alerts[0]['title'])

    @patch('app.inspect_http_services')
    def test_client_http_inspector_uses_saved_web_ports(self, inspect_http):
        app_module.device_inventory.clear()
        inspect_http.return_value = [{'port': 80, 'url': 'http://192.168.20.10:80/', 'status': 200, 'title': 'Router', 'server': 'lab', 'error': None}]
        app_module.record_device_open_ports('192.168.20.10', [
            {'port': 22, 'service': 'SSH', 'description': 'Secure shell remote administration'},
            {'port': 80, 'service': 'HTTP', 'description': 'Web service'},
        ])

        response = self.client.post('/clients/192.168.20.10/http-inspect')

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['results'][0]['title'], 'Router')
        inspect_http.assert_called_once_with('192.168.20.10', [80])


    def test_bluetooth_client_detail_uses_device_name_and_metadata(self):
        app_module.device_inventory.clear()
        app_module.record_inventory_devices([
            {
                'address': '6a:76:8a:0c:36:70',
                'name': 'Trail Speaker',
                'manufacturer': 'Audio Lab',
                'status': 'OK',
                'device_class': 'Bluetooth',
                'instance_id': 'BTHENUM\\DEV_6A768A0C3670',
            }
        ], 'bluetooth-scan', 'hci0')

        response = self.client.get('/clients/6a:76:8a:0c:36:70')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Trail Speaker', response.data)
        self.assertIn(b'Bluetooth Device', response.data)
        self.assertIn(b'Bluetooth Address', response.data)
        self.assertIn(b'6a:76:8a:0c:36:70', response.data)
        self.assertIn(b'Status', response.data)
        self.assertIn(b'OK', response.data)
        self.assertNotIn(b'IP Address', response.data)
        self.assertIn(b'Bluetooth Controls', response.data)
        self.assertIn(b'data-action="connect"', response.data)
        self.assertIn(b'data-action="pair"', response.data)
        self.assertIn(b'Refresh This Device', response.data)
        self.assertIn(b'Forget From Inventory', response.data)
        self.assertIn(b'Bluetooth Action History', response.data)
        self.assertIn(b'Default host adapter', response.data)
        self.assertIn(b'bluetooth-scan.js', response.data)
        self.assertNotIn(b'Bluetooth Notes', response.data)
        self.assertNotIn(b'Device Port Scan', response.data)
        self.assertNotIn(b'IP Client Actions', response.data)
        self.assertNotIn(b'port_scan_live.js', response.data)
        self.assertNotIn(b'ip_client.js', response.data)


    def test_bluetooth_client_detail_uses_contextual_connected_actions(self):
        app_module.device_inventory.clear()
        app_module.record_inventory_devices([
            {
                'address': '6a:76:8a:0c:36:71',
                'name': 'Connected Speaker',
                'manufacturer': 'Audio Lab',
                'connected': True,
                'paired': True,
                'trusted': True,
            }
        ], 'bluetooth-scan', 'hci0')

        response = self.client.get('/clients/6a:76:8a:0c:36:71')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'data-action="disconnect"', response.data)
        self.assertIn(b'data-action="untrust"', response.data)
        self.assertNotIn(b'data-action="connect"', response.data)
        self.assertNotIn(b'data-action="pair"', response.data)


    @patch('app.set_interface_power_state')
    def test_interface_power_endpoint_toggles_interface(self, set_power):
        set_power.return_value = 'WiFi was turned off.'

        response = self.client.post('/interfaces/WiFi/state', data={'state': 'down'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['message'], 'WiFi was turned off.')
        set_power.assert_called_once()

    def test_interface_detail_includes_power_controls(self):
        wireless_interface = SimpleNamespace(
            name='WiFi',
            interface_type='Wireless',
            state='UP',
            addresses=[],
            manufacturer='Unknown',
            extra_info={},
        )

        with (
            patch.object(app_module, 'network_interfaces', [wireless_interface]),
            patch.object(app_module, 'networkTechnologies', {'Wireless'}),
        ):
            response = self.client.get('/wireless/WiFi')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'data-interface-power', response.data)
        self.assertIn(b'Turn on', response.data)
        self.assertIn(b'Turn off', response.data)
        self.assertIn(b'interface-power.js', response.data)

    def test_inventory_links_host_devices_to_port_scan(self):
        app_module.device_inventory.clear()
        app_module.record_inventory_devices([
            {'ip': '192.168.20.10', 'mac': '48:b0:2d:ef:ec:f2'},
            {'ip': '224.0.0.251', 'mac': '01:00:5e:00:00:fb', 'is_control_traffic': True},
        ], 'test-scan', 'eth0')

        response = self.client.get('/inventory')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'/clients/192.168.20.10', response.data)
        self.assertIn(b'/port-scan?host=192.168.20.10', response.data)
        self.assertEqual(response.data.count(b'Device scan'), 1)
        self.assertEqual(response.data.count(b'Tools scan'), 1)
        self.assertIn(b'Export devices + ports', response.data)
        self.assertIn(b'Import devices + ports', response.data)

    def test_runtime_state_persists_inventory_ports_labels_and_profiles(self):
        app_module.device_inventory.clear()
        app_module.client_timelines.clear()
        app_module.wireless_network_labels.clear()
        app_module.watched_clients.clear()
        app_module.scheduled_client_checks.clear()

        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = os.path.join(tmpdir, 'runtime_state.json')
            with patch.object(app_module.persistence_service, 'state_path', return_value=state_path):
                app_module.record_inventory_devices([
                    {'ip': '192.168.90.10', 'mac': 'b8:27:eb:90:00:10', 'interfaces': ['wlan0']},
                ], 'active-scan', 'wlan0')
                app_module.record_device_open_ports('192.168.90.10', [
                    {'port': 80, 'service': 'HTTP', 'description': 'Web service'},
                ])
                app_module.update_client_metadata('192.168.90.10', {'tags': 'trusted', 'notes': 'Do not rescan heavily.'})
                app_module.wireless_network_labels['wlan0|TrainingNet||b8:27:eb:90:00:10'] = 'Living room TV'
                app_module.save_runtime_state('test')

            with open(state_path, encoding='utf-8') as handle:
                payload = json.load(handle)

        device = next(item for item in payload['device_inventory'].values() if item.get('ip') == '192.168.90.10')
        self.assertEqual(device['open_ports'], [80])
        self.assertEqual(device['client_tags'], ['trusted'])
        self.assertEqual(payload['wireless_network_labels']['wlan0|TrainingNet||b8:27:eb:90:00:10'], 'Living room TV')
        self.assertIn('192.168.90.10', payload['client_timelines'])

    def test_inventory_export_and_import_preserves_open_ports(self):
        app_module.device_inventory.clear()
        app_module.record_inventory_devices([
            {'ip': '192.168.20.88', 'mac': '48:b0:2d:ef:ec:f8', 'hostname': 'nas.local', 'manufacturer': 'StorageCo'},
        ], 'test-scan', 'eth0')
        app_module.record_device_open_ports('192.168.20.88', [
            {'port': 443, 'service': 'HTTPS', 'description': 'Secure web server', 'http_title': 'NAS Admin'},
        ])

        response = self.client.get('/inventory/export.json')

        self.assertEqual(response.status_code, 200)
        exported = response.get_json()
        self.assertEqual(exported['schema'], 'mobile-router-inventory-v1')
        exported_device = next(item for item in exported['devices'] if item.get('ip') == '192.168.20.88')
        self.assertEqual(exported_device['open_port_details'][0]['port'], 443)

        app_module.device_inventory.clear()
        response = self.client.post('/inventory/import', json=exported, headers={'X-Requested-With': 'XMLHttpRequest'})

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['imported_port_profiles'], 1)
        device = app_module.find_inventory_device('192.168.20.88')
        self.assertEqual(device['open_port_details'][0]['port'], 443)
        self.assertEqual(device['open_port_details'][0]['http_title'], 'NAS Admin')

    @patch('scripts.portScanner.scan_ports', return_value=[80, 443])
    def test_port_scan_route_saves_open_ports_to_device_profile(self, _scan_ports):
        app_module.device_inventory.clear()

        response = self.client.post('/port-scan', data={'host': '192.168.20.44', 'start': '80', 'end': '443'})

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['ports'], [80, 443])
        device = app_module.find_inventory_device('192.168.20.44')
        self.assertEqual(device['open_ports'], [80, 443])
        self.assertEqual(device['open_port_details'][0]['service'], 'HTTP')
        self.assertEqual(device['open_port_details'][1]['service'], 'HTTPS')
        self.assertEqual(device['open_port_details'][1]['web_url'], 'https://192.168.20.44:443/')

    def test_new_device_alerts_are_created_and_can_be_read(self):
        app_module.device_inventory.clear()
        app_module.new_device_alerts.clear()

        app_module.record_inventory_devices([
            {'ip': '192.168.20.10', 'mac': '48:b0:2d:ef:ec:f2'},
            {'ip': '224.0.0.251', 'mac': '01:00:5e:00:00:fb', 'is_control_traffic': True},
        ], 'test-scan', 'eth0')

        response = self.client.get('/alerts/status')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['unread_count'], 1)
        self.assertEqual(payload['alerts'][0]['ip'], '192.168.20.10')
        self.assertEqual(payload['alerts'][0]['device_url'], '/clients/48%3Ab0%3A2d%3Aef%3Aec%3Af2')

        alert_id = payload['alerts'][0]['id']
        response = self.client.post(f'/alerts/{alert_id}/read')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['unread_count'], 0)

    def test_grouped_discovery_alerts_batch_active_scan_devices(self):
        app_module.device_inventory.clear()
        app_module.new_device_alerts.clear()

        app_module.record_inventory_devices([
            {'ip': '192.168.20.10', 'mac': '48:b0:2d:ef:ec:f2'},
            {'ip': '192.168.20.11', 'mac': 'b8:27:eb:11:22:33'},
        ], 'active-scan', 'eth0')

        alerts = app_module.alert_records()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['alert_type'], 'grouped-discovery')
        self.assertEqual(alerts[0]['device_count'], 2)
        self.assertEqual(alerts[0]['device_url'], '/inventory')

    def test_passive_discovery_keeps_individual_later_alerts(self):
        app_module.device_inventory.clear()
        app_module.new_device_alerts.clear()

        app_module.record_inventory_devices([
            {'ip': '192.168.20.10', 'mac': '48:b0:2d:ef:ec:f2'},
            {'ip': '192.168.20.11', 'mac': 'b8:27:eb:11:22:33'},
        ], 'passive-scan', 'eth0')

        alerts = app_module.alert_records()
        self.assertEqual(len(alerts), 2)
        self.assertTrue(all(alert.get('alert_type') != 'grouped-discovery' for alert in alerts))

    def test_alerts_page_and_nav_indicator_render(self):
        app_module.new_device_alerts.clear()
        app_module.create_new_device_alert({
            'id': 'mac:48:b0:2d:ef:ec:f2',
            'ip': '192.168.20.10',
            'mac': '48:b0:2d:ef:ec:f2',
            'manufacturer': 'Unknown',
        }, 'test-scan', 'eth0')

        response = self.client.get('/alerts')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'New Device Alerts', response.data)
        self.assertIn(b'192.168.20.10', response.data)
        self.assertIn(b'View device', response.data)
        self.assertIn(b'data-device-url=', response.data)
        self.assertIn(b'alerts.js', response.data)

        response = self.client.get('/capabilities')
        self.assertIn(b'id="new-device-alert-indicator"', response.data)

    @patch('app.threading.Thread')
    def test_port_scan_job_routes_start_and_report_status(self, thread_cls):
        app_module.port_scan_jobs.clear()
        thread_cls.return_value.start.return_value = None

        response = self.client.post('/port-scan-jobs', data={
            'host': '192.168.20.10',
            'start': '1',
            'end': '65535',
            'label': 'all-port scan',
        })

        self.assertEqual(response.status_code, 200)
        job = response.get_json()['job']
        self.assertEqual(job['status'], 'queued')
        self.assertEqual(job['total_ports'], 65535)

        response = self.client.get(f"/port-scan-jobs/{job['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['job']['host'], '192.168.20.10')

    @patch('scripts.portScanner.scan_ports')
    def test_port_scan_job_records_live_open_ports_and_progress(self, scan_ports):
        app_module.port_scan_jobs.clear()
        job_id = 'test-job'
        app_module.port_scan_jobs[job_id] = {
            'id': job_id,
            'host': '192.168.20.10',
            'start': 20,
            'end': 22,
            'label': 'custom',
            'status': 'queued',
            'open_ports': [],
            'open_port_details': [],
            'scanned_ports': 0,
            'total_ports': 3,
            'current_port': None,
            'progress': 0,
            'message': 'queued',
            'created_at': 0,
            'updated_at': 0,
        }

        def fake_scan(host, start, end, on_open=None, on_progress=None, should_cancel=None, max_ports=None):
            for port in [20, 21, 22]:
                if port == 22:
                    on_open(port)
                on_progress(port)
            return [22]

        scan_ports.side_effect = fake_scan

        app_module.run_port_scan_job(job_id)

        job = app_module.port_scan_jobs[job_id]
        self.assertEqual(job['status'], 'complete')
        self.assertEqual(job['open_ports'], [22])
        self.assertEqual(job['open_port_details'][0]['service'], 'SSH')
        self.assertEqual(job['scanned_ports'], 3)
        self.assertEqual(job['progress'], 100)
        device = app_module.find_inventory_device('192.168.20.10')
        self.assertEqual(device['open_ports'], [22])
        self.assertEqual(device['open_port_details'][0]['service'], 'SSH')

    def test_jobs_page_and_status_show_running_count(self):
        app_module.scan_jobs.clear()
        app_module.port_scan_jobs.clear()
        app_module.port_scan_jobs['port-job'] = {
            'id': 'port-job',
            'host': '192.168.20.10',
            'start': 1,
            'end': 1024,
            'label': 'common port scan',
            'status': 'running',
            'open_ports': [22],
            'open_port_details': [{'port': 22, 'service': 'SSH', 'description': 'Secure shell remote administration'}],
            'scanned_ports': 20,
            'total_ports': 1024,
            'current_port': 22,
            'progress': 2,
            'message': 'Open port found: 22',
            'cancel_requested': False,
            'created_at': 1,
            'updated_at': 2,
        }

        response = self.client.get('/jobs')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Live Jobs', response.data)
        self.assertIn(b'jobs.js', response.data)

        response = self.client.get('/jobs/status')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['running_count'], 1)
        self.assertEqual(payload['jobs'][0]['open_ports'], [22])
        self.assertEqual(payload['jobs'][0]['open_port_details'][0]['service'], 'SSH')

    def test_job_cancel_endpoint_cancels_port_scan_job(self):
        app_module.port_scan_jobs.clear()
        app_module.port_scan_jobs['port-job'] = {
            'id': 'port-job',
            'host': '192.168.20.10',
            'start': 1,
            'end': 1024,
            'label': 'common port scan',
            'status': 'running',
            'open_ports': [],
            'open_port_details': [],
            'scanned_ports': 0,
            'total_ports': 1024,
            'current_port': None,
            'progress': 0,
            'message': 'running',
            'cancel_requested': False,
            'created_at': 1,
            'updated_at': 1,
        }

        response = self.client.post('/jobs/port-job/cancel')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(app_module.port_scan_jobs['port-job']['cancel_requested'])
        self.assertEqual(response.get_json()['job']['message'], 'Cancellation requested.')

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
            'wps': True,
            'wps_status': '2 (Configured)',
            'wps_note': 'WPS is advertised by this AP. Review lab router settings and disable WPS when possible because WPS can weaken credential protection, especially when PIN enrolment is enabled.',
            'wps_access_points': 1,
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
                    'wps': True,
                    'wps_status': '2 (Configured)',
                    'clients': [{'mac': '11:22:33:44:55:66', 'signal_label': '-42 dBm', 'bssid': 'aa:bb:cc:dd:ee:ff', 'manufacturer': 'Client Vendor'}],
                }
            ],
            'clients': [{'mac': '11:22:33:44:55:66', 'signal_label': '-42 dBm', 'bssid': 'aa:bb:cc:dd:ee:ff', 'manufacturer': 'Client Vendor'}],
        }

        response = self.client.get('/wireless/network?interface=wlan0&ssid=TrainingNet&bssid=aa:bb:cc:dd:ee:ff')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'TrainingNet', response.data)
        self.assertIn(b'id="network-devices-tab"', response.data)
        self.assertIn(b'AP Details', response.data)
        self.assertIn(b'Devices Found On This Network Interface', response.data)
        self.assertIn(b'network-device-card', response.data)
        self.assertIn(b'192.168.1.1', response.data)
        self.assertIn(b'5 GHz', response.data)
        self.assertIn(b'AP Identity Hints', response.data)
        self.assertIn(b'WPS Exposure', response.data)
        self.assertIn(b'WPS exposed', response.data)
        self.assertIn(b'Training Vendor', response.data)
        self.assertIn(b'11:22:33:44:55:66', response.data)
        self.assertNotIn(b'href="#network-device-scan"', response.data)
        self.assertIn(b'Continuous passive capture', response.data)
        self.assertIn(b'data-passive-monitor-toggle', response.data)
        self.assertIn(b'Passive-only analytics', response.data)
        self.assertIn(b'data-passive-analytics-panel', response.data)
        self.assertIn(b'Network Device Scan', response.data)
        self.assertIn(b'id="comprehensive-scan-btn"', response.data)
        self.assertIn(b'<option value="wlan0" selected>', response.data)
        self.assertLess(response.data.index(b'id="network-devices-pane"'), response.data.index(b'id="network-device-scan"'))
        self.assertIn(b'data-network-device-list-scan', response.data)
        self.assertIn(b'data-network-device-list', response.data)
        self.assertIn(b'Scan all common ports', response.data)
        self.assertIn(b'Scan all ports', response.data)
        self.assertIn(b'network_scan.js', response.data)


    def test_device_intelligence_tracks_names_role_and_randomized_mac(self):
        app_module.device_inventory.clear()
        app_module.record_inventory_devices([
            {'ip': '192.168.30.20', 'mac': '02:11:22:33:44:55', 'hostname': 'office-printer.local'}
        ], 'mdns-discovery', 'wlan0')
        app_module.record_device_open_ports('192.168.30.20', [
            {'port': 631, 'service': 'IPP', 'description': 'Internet Printing Protocol'}
        ])

        device = app_module.find_inventory_device('192.168.30.20')

        self.assertTrue(device['likely_randomized_mac'])
        self.assertEqual(device['device_role_guess']['role'], 'Printer')
        self.assertEqual(device['observed_names'][0]['name'], 'office-printer.local')
        payload = app_module.inventory_export_payload([device])
        exported = payload['devices'][0]
        self.assertTrue(exported['likely_randomized_mac'])
        self.assertEqual(exported['device_role_guess']['role'], 'Printer')
        self.assertEqual(exported['observed_names'][0]['source'], 'mdns-discovery')

    @patch('app.device_intel.tls_certificate_metadata')
    @patch('app.inspect_http_services')
    def test_web_service_enrichment_adds_favicon_and_tls_metadata(self, inspect, tls):
        inspect.return_value = [{
            'port': 443,
            'status': 200,
            'title': 'NAS Admin',
            'server': 'nginx',
            'favicon': {'sha256': 'abc123', 'size': 42},
        }]
        tls.return_value = {'subject_common_name': 'nas.local', 'issuer_common_name': 'Lab CA'}

        detail = app_module.enrich_web_port_metadata('192.168.30.30', {
            'port': 443,
            'service': 'HTTPS',
            'description': 'HTTPS web service',
        })

        self.assertEqual(detail['http_favicon']['sha256'], 'abc123')
        self.assertEqual(detail['tls_certificate']['subject_common_name'], 'nas.local')

    def test_wireless_network_detail_exposes_passive_monitor_toggle(self):
        app_module.device_inventory.clear()
        app_module.wireless_network_client_cache.clear()
        app_module.wireless_network_labels.clear()
        app_module.passive_monitor_jobs.clear()
        app_module.passive_observation_analytics.clear()
        app_module.record_inventory_devices([
            {'ip': '192.168.20.10', 'mac': 'AA:BB:CC:DD:EE:10', 'hostname': 'Camera'}
        ], 'passive-monitor', 'wlan0')

        response = self.client.get('/wireless/network?interface=wlan0&ssid=TrainingNet&bssid=aa:bb:cc:dd:ee:ff')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'data-passive-monitor-toggle', response.data)
        self.assertIn(b'Passive-only analytics', response.data)
        self.assertIn(b'data-passive-analytics-panel', response.data)
        with open('static/js/network_scan.js') as handle:
            js = handle.read()
        self.assertIn('/passive-monitor/status', js)
        self.assertIn('/passive-monitor/toggle', js)
        self.assertIn('/passive-analytics.json', js)
        self.assertIn(b'The app does not send probe packets for this mode', response.data)

    @patch('app.passive_scan')
    def test_passive_monitor_toggle_records_observed_cache_devices(self, passive):
        app_module.device_inventory.clear()
        app_module.passive_monitor_jobs.clear()
        passive.return_value = [{'ip': '192.168.20.55', 'mac': 'AA:BB:CC:DD:EE:55'}]

        response = self.client.post('/passive-monitor/toggle', data={
            'selectedInterface': 'wlan0',
            'enabled': 'on',
            'interval': '5',
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['status']['enabled'])
        for _ in range(20):
            if app_module.find_inventory_device('192.168.20.55'):
                break
            time.sleep(0.05)
        device = app_module.find_inventory_device('192.168.20.55')
        self.assertIsNotNone(device)
        self.assertIn('passive-monitor', device['sources'])

        response = self.client.post('/passive-monitor/toggle', data={
            'selectedInterface': 'wlan0',
            'enabled': '',
            'interval': '5',
        })
        self.assertFalse(response.get_json()['status']['enabled'])

    @patch('app.passive_scan')
    def test_passive_scan_records_passive_only_analytics_and_quiet_devices(self, passive):
        app_module.device_inventory.clear()
        app_module.passive_observation_analytics.clear()
        passive.return_value = [{'ip': '192.168.20.55', 'mac': 'AA:BB:CC:DD:EE:55'}]

        response = self.client.post('/passive-scan', data={'selectedInterface': 'wlan0'})
        self.assertEqual(response.status_code, 200)
        analytics = response.get_json()['analytics']
        self.assertEqual(analytics['known_device_count'], 1)
        self.assertEqual(analytics['active_device_count'], 1)
        self.assertEqual(analytics['recently_disappeared_count'], 0)

        passive.return_value = []
        response = self.client.post('/passive-scan', data={'selectedInterface': 'wlan0'})
        self.assertEqual(response.status_code, 200)
        analytics = response.get_json()['analytics']
        self.assertEqual(analytics['known_device_count'], 1)
        self.assertEqual(analytics['active_device_count'], 0)
        self.assertEqual(analytics['recently_disappeared_count'], 1)

        response = self.client.get('/passive-analytics.json?selectedInterface=wlan0')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['analytics']['recently_disappeared'][0]['ip'], '192.168.20.55')

    @patch('scripts.wifi.utils.get_network_detail')
    def test_wireless_network_detail_persists_clients_between_reloads(self, get_detail):
        app_module.device_inventory.clear()
        app_module.wireless_network_client_cache.clear()
        first = {
            'ssid': 'TrainingNet',
            'bssid': 'aa:bb:cc:dd:ee:ff',
            'security': 'WPA2-Personal',
            'channel': '6',
            'signal': 82,
            'signal_label': '82%',
            'interface': 'wlan0',
            'discovered': True,
            'gateway': {},
            'bands': ['5 GHz'],
            'wps': False,
            'wps_status': None,
            'wps_note': None,
            'wps_access_points': 0,
            'ap_groups': [],
            'access_points': [],
            'clients': [{'mac': '11:22:33:44:55:66', 'signal_label': '-42 dBm', 'bssid': 'aa:bb:cc:dd:ee:ff', 'manufacturer': 'Client Vendor'}],
        }
        second = {**first, 'clients': [], 'discovered': False}
        get_detail.side_effect = [first, second]

        response = self.client.get('/wireless/network?interface=wlan0&ssid=TrainingNet&bssid=aa:bb:cc:dd:ee:ff')
        self.assertIn(b'11:22:33:44:55:66', response.data)

        response = self.client.get('/wireless/network?interface=wlan0&ssid=TrainingNet&bssid=aa:bb:cc:dd:ee:ff')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'11:22:33:44:55:66', response.data)
        self.assertIn(b'This list is persisted', response.data)

    @patch('scripts.wifi.utils.get_network_detail')
    def test_wireless_network_detail_lists_inventory_devices_for_interface(self, get_detail):
        app_module.device_inventory.clear()
        app_module.wireless_network_client_cache.clear()
        app_module.record_inventory_devices([
            {'ip': '192.168.50.22', 'mac': '48:b0:2d:ef:ec:f2', 'hostname': 'laptop.local', 'manufacturer': 'LaptopCo'},
        ], 'comprehensive-network-scan', 'wlan0')
        get_detail.return_value = {
            'ssid': 'TrainingNet',
            'bssid': 'aa:bb:cc:dd:ee:ff',
            'security': 'WPA2-Personal',
            'channel': '6',
            'signal': 82,
            'signal_label': '82%',
            'interface': 'wlan0',
            'discovered': True,
            'gateway': {},
            'bands': [],
            'wps': False,
            'wps_status': None,
            'wps_note': None,
            'wps_access_points': 0,
            'ap_groups': [],
            'access_points': [],
            'clients': [],
        }

        response = self.client.get('/wireless/network?interface=wlan0&ssid=TrainingNet&bssid=aa:bb:cc:dd:ee:ff')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'laptop.local', response.data)
        self.assertIn(b'192.168.50.22', response.data)
        self.assertIn(b'/clients/192.168.50.22', response.data)
        self.assertIn(b'data-port-scan-quick', response.data)
        self.assertIn(b'data-label="common port scan"', response.data)
        self.assertIn(b'data-label="all-port scan"', response.data)
        self.assertIn(b'data-network-device-filter="gateway"', response.data)
        self.assertIn(b'data-network-device-notes-form', response.data)
        self.assertIn(b'data-known-state="New"', response.data)
        self.assertIn(b'Export device list', response.data)
        self.assertIn(b'data-network-device-label-form', response.data)
        self.assertIn(b'data-port-scan-quick-progress', response.data)
        self.assertIn(b'Scan all common ports', response.data)
        self.assertIn(b'data-hosts="192.168.50.22"', response.data)

    @patch('scripts.wifi.utils.get_network_detail')
    def test_wireless_network_labels_disappeared_and_export(self, get_detail):
        app_module.device_inventory.clear()
        app_module.wireless_network_client_cache.clear()
        app_module.wireless_network_labels.clear()
        first = {
            'ssid': 'TrainingNet',
            'bssid': 'aa:bb:cc:dd:ee:ff',
            'security': 'WPA2-Personal',
            'channel': '6',
            'signal': 82,
            'signal_label': '82%',
            'interface': 'wlan0',
            'discovered': True,
            'gateway': {},
            'bands': [],
            'wps': False,
            'wps_status': None,
            'wps_note': None,
            'wps_access_points': 0,
            'ap_groups': [],
            'access_points': [],
            'clients': [{'ip': '192.168.50.33', 'mac': '48:b0:2d:ef:ec:f3', 'manufacturer': 'TvCo'}],
        }
        second = {**first, 'clients': []}
        get_detail.side_effect = [first, second, second]

        self.client.get('/wireless/network?interface=wlan0&ssid=TrainingNet&bssid=aa:bb:cc:dd:ee:ff')
        response = self.client.post('/wireless/network/label', data={
            'interface': 'wlan0',
            'ssid': 'TrainingNet',
            'bssid': 'aa:bb:cc:dd:ee:ff',
            'identity': '48:b0:2d:ef:ec:f3',
            'label': 'Living room TV',
        })
        self.assertEqual(response.status_code, 200)

        response = self.client.get('/wireless/network?interface=wlan0&ssid=TrainingNet&bssid=aa:bb:cc:dd:ee:ff')
        self.assertIn(b'Recently Disappeared Devices', response.data)
        self.assertIn(b'Living room TV', response.data)

        response = self.client.get('/wireless/network/clients.csv?interface=wlan0&ssid=TrainingNet&bssid=aa:bb:cc:dd:ee:ff')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Living room TV', response.data)
        self.assertIn(b'disappeared', response.data)
        self.assertIn(b'open_port_details_json', response.data)

    def test_service_detail_page_and_port_card_links(self):
        app_module.device_inventory.clear()
        app_module.record_device_open_ports('192.168.20.80', [
            {'port': 80, 'service': 'HTTP', 'description': 'Web server', 'http_title': 'Router Console'},
        ])

        response = self.client.get('/clients/192.168.20.80')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'class="port-service-number"', response.data)
        self.assertIn(b'href="http://192.168.20.80:80/"', response.data)
        self.assertIn(b'/clients/192.168.20.80/services/80', response.data)
        self.assertIn(b'web-service-hover-preview', response.data)

        response = self.client.get('/clients/192.168.20.80/services/80')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'192.168.20.80:80', response.data)
        self.assertIn(b'Router Console', response.data)

    @patch('scripts.wifi.utils.get_network_detail')
    def test_wireless_network_device_cards_resolve_oui_manufacturer(self, get_detail):
        app_module.device_inventory.clear()
        app_module.wireless_network_client_cache.clear()
        get_detail.return_value = {
            'ssid': 'TrainingNet',
            'bssid': 'aa:bb:cc:dd:ee:ff',
            'security': 'WPA2-Personal',
            'access_points': [],
            'clients': [{'ip': '192.168.77.20', 'mac': '8c:49:62:bd:7d:37'}],
            'interface': 'wlan0',
        }

        response = self.client.get('/wireless/network?interface=wlan0&ssid=TrainingNet&bssid=aa:bb:cc:dd:ee:ff')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Roku, Inc.', response.data)
        self.assertNotIn(b'<i class="fa-solid fa-industry"></i> Unknown', response.data)

    def test_wireless_network_clients_json_returns_persisted_device_list(self):
        app_module.device_inventory.clear()
        app_module.record_inventory_devices([
            {'ip': '192.168.77.10', 'mac': '48:b0:2d:ef:77:10', 'manufacturer': 'ClientCo', 'interfaces': ['wlan0']},
        ], 'active-scan', 'wlan0')

        response = self.client.get('/wireless/network/clients.json?interface=wlan0&ssid=TrainingNet')

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(any(client.get('ip') == '192.168.77.10' for client in payload['clients']))
        self.assertGreaterEqual(payload['client_count'], 1)

    def test_wireless_network_cards_link_to_device_scan_panel(self):
        js = open('static/js/wireless-adapters.js').read()

        self.assertIn('#network-device-scan', js)
        self.assertIn('Device scan', js)

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
        payload = response.get_json()
        self.assertEqual(payload['output'], 'Device disconnected')
        self.assertEqual(payload['history'][0]['action'], 'disconnect')
        run_action.assert_called_once_with('disconnect', 'aa:bb:cc:dd:ee:ff', adapter=None)

    @patch('app.run_bluetoothctl_action')
    def test_bluetooth_device_refresh_uses_single_device_info(self, run_action):
        run_action.return_value = 'Name: Trail Speaker'

        response = self.client.post('/bluetooth-device/aa:bb:cc:dd:ee:ff/refresh', data={'adapter': 'hci0'})

        self.assertEqual(response.status_code, 200)
        self.assertIn('Name: Trail Speaker', response.get_json()['output'])
        run_action.assert_called_once_with('info', 'aa:bb:cc:dd:ee:ff', adapter='hci0')

    def test_forget_inventory_device_removes_only_mobile_router_record(self):
        app_module.device_inventory.clear()
        app_module.record_inventory_devices([{'address': '6a:76:8a:0c:36:72', 'name': 'Old Speaker'}], 'bluetooth-scan', 'hci0')

        response = self.client.post('/inventory/6a:76:8a:0c:36:72/forget')

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(app_module.find_inventory_device('6a:76:8a:0c:36:72'))

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
