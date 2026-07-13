from scripts import interfaceTools


def test_normalize_interface_state_maps_common_platform_statuses():
    assert interfaceTools._normalize_interface_state('up') == 'UP'
    assert interfaceTools._normalize_interface_state('Connected') == 'UP'
    assert interfaceTools._normalize_interface_state('Disconnected') == 'DOWN'
    assert interfaceTools._normalize_interface_state('disabled') == 'DOWN'
    assert interfaceTools._normalize_interface_state('not available') == 'UNKNOWN'


def test_network_interface_uses_windows_metadata_status(monkeypatch):
    monkeypatch.setitem(interfaceTools._WINDOWS_INTERFACE_METADATA, 'WiFi', {'Status': 'Up'})

    adapter = interfaceTools.NetworkInterface('WiFi', 'Wireless')

    assert adapter.state == 'UP'
