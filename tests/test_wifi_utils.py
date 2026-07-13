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

    monkeypatch.setattr(utils, '_run_command', lambda command: Result())

    utils._scan_windows_with_netsh()
    summary = utils.get_networks_summary()

    assert summary[0]['ssid'] == 'Office WiFi'
    assert summary[0]['bssid'] == 'aa:bb:cc:dd:ee:ff'
    assert summary[0]['signal'] == 82
    assert summary[0]['channel'] == 11
    assert summary[0]['security'] == 'WPA2-Personal'
    assert summary[0]['access_points'] == 2
    assert summary[1]['ssid'] == 'Guest'
    assert summary[1]['security'] == 'Open'


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
    assert summary[1]['security'] == 'Open'
