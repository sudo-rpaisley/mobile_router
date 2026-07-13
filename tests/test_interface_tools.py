from scripts import interfaceTools


def test_normalize_interface_state_maps_common_platform_statuses():
    assert interfaceTools._normalize_interface_state('up') == 'UP'
    assert interfaceTools._normalize_interface_state('Connected') == 'UP'
    assert interfaceTools._normalize_interface_state('Disconnected') == 'DOWN'
    assert interfaceTools._normalize_interface_state('Disconnected', 'Bluetooth') == 'UP'
    assert interfaceTools._normalize_interface_state('disabled') == 'DOWN'
    assert interfaceTools._normalize_interface_state('not available') == 'UNKNOWN'


def test_network_interface_uses_windows_metadata_status(monkeypatch):
    monkeypatch.setitem(interfaceTools._WINDOWS_INTERFACE_METADATA, 'WiFi', {'Status': 'Up'})

    adapter = interfaceTools.NetworkInterface('WiFi', 'Wireless')

    assert adapter.state == 'UP'


def test_bluetooth_interface_treats_disconnected_metadata_as_powered(monkeypatch):
    monkeypatch.setitem(interfaceTools._WINDOWS_INTERFACE_METADATA, 'Bluetooth Network Connection', {'Status': 'Disconnected'})

    adapter = interfaceTools.NetworkInterface('Bluetooth Network Connection', 'Bluetooth')

    assert adapter.state == 'UP'


def test_parse_windows_bluetooth_devices_extracts_names_and_addresses():
    output = r'''[
      {"FriendlyName":"Keyboard","InstanceId":"BTHENUM\\DEV_001122AABBCC\\7&abc","Status":"OK"},
      {"Name":"Headphones","InstanceId":"BTHENUM\\DEV_DDEEFF001122\\7&def","Status":"OK"}
    ]'''

    devices = interfaceTools._parse_windows_bluetooth_devices(output)

    assert [(device.name, device.address) for device in devices] == [
        ('Keyboard', '00:11:22:aa:bb:cc'),
        ('Headphones', 'dd:ee:ff:00:11:22'),
    ]


def test_parse_bluetoothctl_devices():
    output = 'Device AA:BB:CC:DD:EE:FF Speaker\nDevice 11:22:33:44:55:66 Phone\n'

    devices = interfaceTools._parse_bluetoothctl_devices(output)

    assert [(device.name, device.address) for device in devices] == [
        ('Speaker', 'aa:bb:cc:dd:ee:ff'),
        ('Phone', '11:22:33:44:55:66'),
    ]
