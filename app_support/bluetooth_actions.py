"""Host-local Bluetooth capability checks and safe adapter actions."""

import os
import re
import shutil
import subprocess

BLUETOOTHCTL_ACTIONS = {
    'info': 'info',
    'connect': 'connect',
    'disconnect': 'disconnect',
    'pair': 'pair',
    'trust': 'trust',
    'untrust': 'untrust',
    'block': 'block',
    'unblock': 'unblock',
    'remove': 'remove',
}

BLUETOOTH_MAC_RE = re.compile(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$')

class BluetoothToolUnavailable(RuntimeError):
    """Raised when host-local Bluetooth actions cannot be executed."""

def _busctl_bluez_available(busctl):
    try:
        result = subprocess.run(
            [busctl, 'tree', 'org.bluez'],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0

def bluetooth_action_capability():
    bluetoothctl = shutil.which('bluetoothctl')
    if bluetoothctl:
        return {
            'available': True,
            'tool': 'bluetoothctl',
            'path': bluetoothctl,
            'message': 'Bluetooth actions are available through bluetoothctl.',
        }
    busctl = shutil.which('busctl')
    if busctl and _busctl_bluez_available(busctl):
        return {
            'available': True,
            'tool': 'busctl',
            'path': busctl,
            'message': 'Bluetooth actions are available through BlueZ D-Bus via busctl.',
        }
    return {
        'available': False,
        'tool': None,
        'path': None,
        'message': 'Bluetooth actions require BlueZ bluetoothctl, or busctl with a running BlueZ D-Bus service on this host.',
    }

def _bluetooth_device_path_from_busctl(busctl, address, timeout=10):
    device_token = 'dev_' + address.upper().replace(':', '_')
    result = subprocess.run(
        [busctl, 'tree', 'org.bluez'],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or 'BlueZ D-Bus tree lookup failed').strip())

    for line in result.stdout.splitlines():
        if device_token in line:
            match = re.search(r'(/org/bluez/[^\s]+)', line)
            if match:
                return match.group(1)
    raise RuntimeError(f'Bluetooth device {address} was not found in BlueZ D-Bus. Scan or pair the device first.')

def _run_busctl_bluetooth_action(busctl, action, address, timeout=15):
    path = _bluetooth_device_path_from_busctl(busctl, address, timeout=timeout)

    if action in {'connect', 'disconnect', 'pair'}:
        method = {'connect': 'Connect', 'disconnect': 'Disconnect', 'pair': 'Pair'}[action]
        command = [busctl, 'call', 'org.bluez', path, 'org.bluez.Device1', method]
    elif action in {'trust', 'untrust', 'block', 'unblock'}:
        property_name = 'Trusted' if action in {'trust', 'untrust'} else 'Blocked'
        value = 'true' if action in {'trust', 'block'} else 'false'
        command = [busctl, 'set-property', 'org.bluez', path, 'org.bluez.Device1', property_name, 'b', value]
    elif action == 'remove':
        adapter_path = path.rsplit('/dev_', 1)[0]
        command = [busctl, 'call', 'org.bluez', adapter_path, 'org.bluez.Adapter1', 'RemoveDevice', 'o', path]
    elif action == 'info':
        outputs = []
        for property_name in ['Address', 'Name', 'Alias', 'Paired', 'Connected', 'Trusted', 'Blocked']:
            result = subprocess.run(
                [busctl, 'get-property', 'org.bluez', path, 'org.bluez.Device1', property_name],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            if result.returncode == 0:
                outputs.append(f"{property_name}: {(result.stdout or '').strip()}")
        return '\n'.join(outputs) or f'BlueZ D-Bus info completed for {address}'
    else:
        raise ValueError('Unsupported Bluetooth action')

    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    output = (result.stdout or result.stderr or '').strip()
    if result.returncode != 0:
        raise RuntimeError(output or f'busctl Bluetooth {action} failed')
    return output or f'busctl Bluetooth {action} completed for {address}'

def run_bluetoothctl_action(action, address, timeout=15, adapter=None):
    """Run a safe local bluetoothctl action against a device visible to this host."""
    command = BLUETOOTHCTL_ACTIONS.get(action)
    if not command:
        raise ValueError('Unsupported Bluetooth action')
    if not BLUETOOTH_MAC_RE.match(address or ''):
        raise ValueError('A valid Bluetooth device address is required')

    capability = bluetooth_action_capability()
    tool = capability['path']
    if not tool:
        raise BluetoothToolUnavailable(capability['message'])
    if capability['tool'] == 'busctl':
        return _run_busctl_bluetooth_action(tool, action, address, timeout=timeout)

    if adapter:
        result = subprocess.run(
            [tool],
            input=f'select {adapter}\n{command} {address}\n',
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    else:
        result = subprocess.run(
            [tool, command, address],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    output = (result.stdout or result.stderr or '').strip()
    if result.returncode != 0:
        raise RuntimeError(output or f'bluetoothctl {command} failed')
    return output or f'bluetoothctl {command} completed'

def set_interface_power_state(interface_name, desired_state, interface_type=None):
    state = str(desired_state or '').casefold()
    if state not in {'up', 'down'}:
        raise ValueError('Interface state must be up or down')
    system = os.name
    normalized_type = str(interface_type or '').casefold()

    if system == 'nt':
        if normalized_type == 'bluetooth':
            powershell = shutil.which('powershell') or shutil.which('pwsh')
            if not powershell:
                raise RuntimeError('PowerShell is required to toggle Bluetooth adapters on Windows')
            verb = 'Enable-PnpDevice' if state == 'up' else 'Disable-PnpDevice'
            escaped_name = str(interface_name).replace("'", "''")
            command = (
                "$device = Get-PnpDevice -Class Bluetooth -PresentOnly:$false | "
                f"Where-Object {{ $_.FriendlyName -eq '{escaped_name}' -or $_.Name -eq '{escaped_name}' }} | "
                "Select-Object -First 1; "
                "if (-not $device) { throw 'Bluetooth adapter was not found.' }; "
                f"{verb} -InstanceId $device.InstanceId -Confirm:$false"
            )
            result = subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-Command', command], capture_output=True, text=True, timeout=20, check=False)
        else:
            result = subprocess.run(['netsh', 'interface', 'set', 'interface', f'name={interface_name}', f'admin={"enabled" if state == "up" else "disabled"}'], capture_output=True, text=True, timeout=20, check=False)
    else:
        if normalized_type == 'bluetooth':
            bluetoothctl = shutil.which('bluetoothctl')
            if bluetoothctl:
                result = subprocess.run([bluetoothctl, 'power', 'on' if state == 'up' else 'off'], capture_output=True, text=True, timeout=15, check=False)
            else:
                ip_tool = shutil.which('ip')
                if not ip_tool:
                    raise RuntimeError('Toggling this interface requires bluetoothctl or ip')
                result = subprocess.run([ip_tool, 'link', 'set', 'dev', interface_name, state], capture_output=True, text=True, timeout=15, check=False)
        else:
            ip_tool = shutil.which('ip')
            if not ip_tool:
                raise RuntimeError('Toggling interfaces requires the ip command on this host')
            result = subprocess.run([ip_tool, 'link', 'set', 'dev', interface_name, state], capture_output=True, text=True, timeout=15, check=False)

    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or 'Interface state change failed').strip())
    return f'{interface_name} was turned {"on" if state == "up" else "off"}.'

def _bluetooth_truthy(value):
    return str(value or '').strip().casefold() in {'1', 'true', 'yes', 'on', 'connected', 'paired', 'trusted', 'blocked'}

def bluetooth_device_state(device):
    device = device or {}
    status = str(device.get('status') or '').casefold()
    return {
        'connected': _bluetooth_truthy(device.get('connected')) or 'connected' in status,
        'paired': _bluetooth_truthy(device.get('paired')) or 'paired' in status,
        'trusted': _bluetooth_truthy(device.get('trusted')) or 'trusted' in status,
        'blocked': _bluetooth_truthy(device.get('blocked')) or 'blocked' in status,
    }

def bluetooth_contextual_actions(device):
    state = bluetooth_device_state(device)
    actions = [{'action': 'info', 'label': 'Info', 'style': 'outline-secondary', 'icon': 'circle-info'}]
    if state['blocked']:
        actions.append({'action': 'unblock', 'label': 'Unblock', 'style': 'outline-success', 'icon': 'check'})
    else:
        if state['connected']:
            actions.append({'action': 'disconnect', 'label': 'Disconnect', 'style': 'outline-warning', 'icon': 'link-slash'})
        else:
            actions.append({'action': 'connect', 'label': 'Connect', 'style': 'outline-primary', 'icon': 'link'})
        if not state['paired']:
            actions.append({'action': 'pair', 'label': 'Pair', 'style': 'outline-primary', 'icon': 'handshake'})
        if state['trusted']:
            actions.append({'action': 'untrust', 'label': 'Untrust', 'style': 'outline-secondary', 'icon': 'shield'})
        else:
            actions.append({'action': 'trust', 'label': 'Trust', 'style': 'outline-success', 'icon': 'shield-halved'})
        actions.append({'action': 'block', 'label': 'Block', 'style': 'outline-danger', 'icon': 'ban'})
    actions.append({'action': 'remove', 'label': 'Remove Pairing', 'style': 'outline-danger', 'icon': 'trash'})
    return actions
