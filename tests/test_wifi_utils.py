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
