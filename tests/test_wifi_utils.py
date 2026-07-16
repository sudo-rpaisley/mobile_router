from scripts.wifi import utils


def test_add_network_groups_access_points_and_sorts_by_signal():
    utils.networks = {}

    utils._add_network('Office', 'aa:bb:cc:dd:ee:ff', 6, 42, 'WPA2')
    utils._add_network('Office', '11:22:33:44:55:66', 11, 85, 'WPA2')
    utils._add_network('Guest', '22:33:44:55:66:77', 1, 30, 'Open')

    summary = utils.get_networks_summary()

    assert summary[0]['ssid'] == 'Office'
    assert summary[0]['bssid'] == '11:22:33:44:55:66'
    assert summary[0]['signal'] == 85
    assert summary[0]['access_points'] == 2
    assert summary[0]['security'] == 'WPA2'
    assert summary[0]['band'] == '2.4 GHz'
    assert summary[0]['frequency'] == 2462
    assert summary[1]['ssid'] == 'Guest'


def test_parse_signal_handles_numbers_and_unknown_values():
    assert utils._parse_signal('78') == 78
    assert utils._parse_signal('-45') == -45
    assert utils._parse_signal('') is None
    assert utils._parse_signal('unknown') == 'unknown'


def test_parse_supported_modes_from_iw_output():
    output = '''
Wiphy phy0
\tSupported interface modes:
\t\t * IBSS
\t\t * managed
\t\t * AP
\t\t * monitor
\tBand 1:
'''

    assert utils._parse_supported_modes(output) == ['ibss', 'managed', 'ap', 'monitor']


def test_parse_current_mode_from_iw_dev_output():
    output = '''
Interface wlan0
\tifindex 3
\ttype monitor
\twiphy 0
'''

    assert utils._parse_current_mode(output) == 'monitor'


def test_scan_windows_with_netsh_parses_bssid_details(monkeypatch):
    utils.networks = {}
    output = '''
SSID 1 : Office WiFi
    Network type            : Infrastructure
    Authentication          : WPA2-Personal
    Encryption              : CCMP
    BSSID 1                 : aa:bb:cc:dd:ee:ff
         Signal             : 82%
         Channel            : 11
    BSSID 2                 : 11:22:33:44:55:66
         Signal             : 64%
         Channel            : 6
SSID 2 : Guest
    Authentication          : Open
    BSSID 1                 : 22:33:44:55:66:77
         Signal             : 40%
         Channel            : 1
'''

    class Result:
        returncode = 0
        stdout = output
        stderr = ''

    monkeypatch.setattr(utils, '_run_command', lambda command, timeout=20: Result())
    monkeypatch.setattr(utils.time, 'sleep', lambda seconds: None)

    utils._scan_windows_with_netsh()
    summary = utils.get_networks_summary()

    assert summary[0]['ssid'] == 'Office WiFi'
    assert summary[0]['bssid'] == 'aa:bb:cc:dd:ee:ff'
    assert summary[0]['signal'] == 82
    assert summary[0]['channel'] == 11
    assert summary[0]['band'] == '2.4 GHz'
    assert summary[0]['security'] == 'WPA2-Personal'
    assert summary[0]['access_points'] == 2
    assert summary[1]['ssid'] == 'Guest'
    assert summary[1]['security'] == 'Open'


def test_windows_scan_refreshes_and_falls_back_to_all_interfaces(monkeypatch):
    utils.networks = {}
    calls = []

    class Result:
        def __init__(self, stdout=''):
            self.returncode = 0
            self.stdout = stdout
            self.stderr = ''

    connected_only = '\nSSID 1 : Home\n    Authentication          : WPA2-Personal\n    BSSID 1                 : aa:bb:cc:dd:ee:ff\n         Signal             : 72%\n         Channel            : 6\n'
    all_networks = '\nSSID 1 : Home\n    Authentication          : WPA2-Personal\n    BSSID 1                 : aa:bb:cc:dd:ee:ff\n         Signal             : 72%\n         Channel            : 6\nSSID 2 : Cafe\n    Authentication          : Open\n    BSSID 1                 : 11:22:33:44:55:66\n         Signal             : 41%\n         Channel            : 11\n'

    def fake_run(command, timeout=20):
        calls.append(command)
        if command[:3] == ['netsh', 'wlan', 'scan']:
            return Result()
        if any(part == 'interface=Wi-Fi' for part in command):
            return Result(connected_only)
        return Result(all_networks)

    monkeypatch.setattr(utils.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(utils.time, 'sleep', lambda seconds: None)
    monkeypatch.setattr(utils, '_run_command', fake_run)
    monkeypatch.setattr(utils, '_scan_windows_with_pywifi', lambda interface_name: None)
    monkeypatch.setattr(utils, 'display_all_networks', lambda: None)
    monkeypatch.setattr(utils, 'send_alerts', lambda: None)

    utils.scan_networks('Wi-Fi')

    assert ['netsh', 'wlan', 'scan', 'interface=Wi-Fi'] in calls
    assert ['netsh', 'wlan', 'show', 'networks', 'mode=bssid'] in calls
    assert [network['ssid'] for network in utils.get_networks_summary()] == ['Home', 'Cafe']

def test_scan_linux_with_iw_parses_multiple_bss_results(monkeypatch):
    utils.networks = {}
    output = '''
BSS aa:bb:cc:dd:ee:ff(on wlan0)
	freq: 2412
	signal: -42.00 dBm
	SSID: Office
	DS Parameter set: channel 1
	capability: ESS Privacy ShortSlotTime (0x0411)
	RSN:
	WPS:
	 * Wi-Fi Protected Setup State: 2 (Configured)
BSS 11:22:33:44:55:66(on wlan0)
	freq: 2437
	signal: -61.00 dBm
	SSID: Guest
	DS Parameter set: channel 6
	capability: ESS ShortSlotTime (0x0401)
'''

    class Result:
        returncode = 0
        stdout = output
        stderr = ''

    monkeypatch.setattr(utils, '_run_command', lambda command, timeout=20: Result())

    utils._scan_linux_with_iw('wlan0')
    summary = utils.get_networks_summary()

    assert [network['ssid'] for network in summary] == ['Office', 'Guest']
    assert summary[0]['bssid'] == 'aa:bb:cc:dd:ee:ff'
    assert summary[0]['channel'] == 1
    assert summary[0]['signal'] == -42
    assert summary[0]['security'] == 'WPA2/WPA3'
    assert summary[0]['wps'] is True
    assert summary[0]['wps_access_points'] == 1
    assert 'WPS is advertised' in summary[0]['wps_note']
    assert summary[1]['security'] == 'Open'
    assert summary[1]['wps'] is False


def test_record_observed_device_adds_client_to_matching_access_point():
    utils.networks = {}
    utils._add_network('Office', 'AA:BB:CC:DD:EE:FF', 6, -42, 'WPA2')

    recorded = utils._record_observed_device('aa:bb:cc:dd:ee:ff', '10:22:33:44:55:66', -51)
    detail = utils.get_network_detail(ssid='Office')

    assert recorded is True
    assert detail['clients'] == [
        {
            'mac': '10:22:33:44:55:66',
            'signal': -51,
            'signal_label': '-51 dBm',
            'bssid': 'aa:bb:cc:dd:ee:ff',
            'manufacturer': 'Unknown',
        }
    ]
    assert detail['access_points'][0]['clients'][0]['mac'] == '10:22:33:44:55:66'


def test_record_observed_device_ignores_ap_broadcast_and_unknown_bssid():
    utils.networks = {}
    utils._add_network('Office', 'aa:bb:cc:dd:ee:ff', 6, -42, 'WPA2')

    assert utils._record_observed_device('aa:bb:cc:dd:ee:ff', 'aa:bb:cc:dd:ee:ff', -51) is False
    assert utils._record_observed_device('aa:bb:cc:dd:ee:ff', 'ff:ff:ff:ff:ff:ff', -51) is False
    assert utils._record_observed_device('22:33:44:55:66:77', '10:22:33:44:55:66', -51) is False
    assert utils.get_network_detail(ssid='Office')['clients'] == []


def test_linux_scan_listens_for_devices_after_active_scan(monkeypatch):
    utils.networks = {}

    monkeypatch.setattr(utils.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(
        utils,
        '_scan_linux_with_nmcli',
        lambda interface_name: utils._add_network('Office', 'aa:bb:cc:dd:ee:ff', 6, -42, 'WPA2'),
    )
    monkeypatch.setattr(utils, '_scan_linux_with_iw', lambda interface_name: None)
    monkeypatch.setattr(
        utils,
        '_scan_linux_with_scapy',
        lambda interface_name, timeout: utils._record_observed_device('aa:bb:cc:dd:ee:ff', '10:22:33:44:55:66', -51),
    )
    monkeypatch.setattr(utils, 'display_all_networks', lambda: None)
    monkeypatch.setattr(utils, 'send_alerts', lambda: None)

    utils.scan_networks('wlan0', timeout=12)
    detail = utils.get_network_detail(ssid='Office')

    assert detail['clients'][0]['mac'] == '10:22:33:44:55:66'


def test_parse_linux_default_gateway_from_ip_route():
    output = 'default via 192.168.20.1 dev wlan0 proto dhcp src 192.168.20.45 metric 600\n'

    assert utils._parse_linux_default_gateway(output) == '192.168.20.1'


def test_parse_windows_default_gateway_from_netsh():
    output = '''
Configuration for interface "Wi-Fi"
    DHCP enabled:                         Yes
    Default Gateway:                      192.168.20.1
'''

    assert utils._parse_windows_default_gateway(output) == '192.168.20.1'


def test_network_detail_includes_default_gateway(monkeypatch):
    utils.networks = {}
    utils._add_network('Office', 'aa:bb:cc:dd:ee:ff', 6, -42, 'WPA2')
    monkeypatch.setattr(
        utils,
        'get_default_gateway',
        lambda interface_name=None: {'ip': '192.168.20.1', 'mac': '00:11:22:33:44:55'},
    )

    detail = utils.get_network_detail(ssid='Office', interface_name='wlan0')

    assert detail['gateway'] == {'ip': '192.168.20.1', 'mac': '00:11:22:33:44:55'}


def test_ap_radio_details_labels_24ghz_and_channel_notes():
    details = utils._ap_radio_details(11, 26)

    assert details['band'] == '2.4 GHz'
    assert details['frequency'] == 2462
    assert details['signal_quality'] == 'Weak'
    assert details['notes'] == ['Preferred non-overlapping 2.4 GHz channel']


def test_ap_radio_details_labels_5ghz_dfs_channel():
    details = utils._ap_radio_details(100, -61)

    assert details['band'] == '5 GHz'
    assert details['frequency'] == 5500
    assert details['signal_quality'] == 'Good'
    assert details['notes'] == ['DFS channel; may be affected by radar events']


def test_network_detail_includes_ap_radio_details(monkeypatch):
    utils.networks = {}
    utils._add_network('Office', 'aa:bb:cc:dd:ee:ff', 36, -51, 'WPA2')
    monkeypatch.setattr(
        utils,
        'get_default_gateway',
        lambda interface_name=None: {'ip': None, 'mac': None},
    )

    detail = utils.get_network_detail(ssid='Office')

    assert detail['bands'] == ['5 GHz']
    assert detail['access_points'][0]['band'] == '5 GHz'
    assert detail['access_points'][0]['frequency'] == 5180
    assert detail['access_points'][0]['signal_quality'] == 'Excellent'


def test_network_detail_includes_wps_exposure(monkeypatch):
    utils.networks = {}
    utils._add_network('Office', 'aa:bb:cc:dd:ee:ff', 6, -42, 'WPA2', wps=True, wps_status='2 (Configured)')
    monkeypatch.setattr(
        utils,
        'get_default_gateway',
        lambda interface_name=None: {'ip': None, 'mac': None},
    )

    detail = utils.get_network_detail(ssid='Office')

    assert detail['wps'] is True
    assert detail['wps_access_points'] == 1
    assert detail['access_points'][0]['wps'] is True
    assert 'WPS is advertised' in detail['wps_note']


def test_network_detail_includes_mac_manufacturers(monkeypatch):
    utils.networks = {}
    utils._add_network('Office', 'b8:27:eb:11:22:33', 6, -42, 'WPA2')
    utils._record_observed_device('b8:27:eb:11:22:33', '00:0c:29:44:55:66', -51)
    monkeypatch.setattr(
        utils,
        'get_default_gateway',
        lambda interface_name=None: {
            'ip': '192.168.1.1',
            'mac': '00:50:56:aa:bb:cc',
            'manufacturer': 'VMware',
        },
    )

    detail = utils.get_network_detail(ssid='Office')

    assert detail['access_points'][0]['manufacturer'] == 'Raspberry Pi Foundation'
    assert detail['clients'][0]['manufacturer'] == 'VMware'
    assert detail['gateway']['manufacturer'] == 'VMware'


def test_group_access_points_marks_related_bssids_as_same_physical_ap(monkeypatch):
    utils.networks = {}
    utils._add_network('Office', 'd0:21:f9:d9:c9:49', 161, 90, 'WPA2')
    utils._add_network('Office', 'd6:21:f9:d9:c9:48', 1, 91, 'WPA2')
    monkeypatch.setattr(
        utils,
        'get_default_gateway',
        lambda interface_name=None: {'ip': None, 'mac': None},
    )

    detail = utils.get_network_detail(ssid='Office')

    assert detail['ap_groups'][0]['likely_same_physical_ap'] is True
    assert detail['ap_groups'][0]['confidence'] == 'High'
    assert len(detail['ap_groups'][0]['bssids']) == 2
    assert all(ap['physical_ap_group'] == 'AP group 1' for ap in detail['access_points'])
    assert detail['ap_groups'][0]['reasons']
