from unittest.mock import patch

from scripts import networkScan
from scripts.network import classification, discovery, passive_capture


def test_network_scan_is_a_small_compatibility_facade():
    assert networkScan.active_scan
    assert classification.classify_scan_results
    assert discovery.active_scan
    assert passive_capture.packet_passive_scan


def test_legacy_classification_patch_points_still_work():
    with patch.object(
        networkScan,
        '_get_ipv4_cidr',
        return_value='192.168.20.2/24',
    ):
        devices = networkScan.classify_scan_results(
            [
                {'ip': '224.0.0.251', 'mac': '01:00:5e:00:00:fb'},
                {'ip': '192.168.20.255', 'mac': 'ff:ff:ff:ff:ff:ff'},
                {'ip': '192.168.20.1', 'mac': 'ac:16:2d:a2:71:9e'},
                {'ip': '8.8.8.8', 'mac': '00:11:22:33:44:55'},
            ],
            'eth0',
        )

    assert devices[0]['network_role'] == 'Multicast'
    assert devices[1]['is_control_traffic'] is True
    assert devices[2]['network_role'] == 'Likely gateway/router'
    assert devices[3]['network_scope'] == 'Public Internet'


def test_legacy_active_scan_patch_points_still_work():
    with (
        patch.object(
            networkScan,
            '_get_ipv4_cidr',
            return_value='192.168.20.2/29',
        ),
        patch.object(
            networkScan,
            '_ping_host',
            side_effect=lambda ip: (
                str(ip) if str(ip) == '192.168.20.1' else None
            ),
        ),
        patch.object(
            networkScan,
            'get_mac_by_ip',
            return_value='ac:16:2d:a2:71:9e',
        ),
        patch.object(
            networkScan,
            '_parse_proc_arp',
            return_value=[
                {
                    'ip': '192.168.20.3',
                    'mac': '48:b0:2d:ef:ec:f2',
                }
            ],
        ),
    ):
        hosts = networkScan.active_scan('eth0')

    assert hosts == [
        {'ip': '192.168.20.1', 'mac': 'ac:16:2d:a2:71:9e'},
        {'ip': '192.168.20.3', 'mac': '48:b0:2d:ef:ec:f2'},
    ]
