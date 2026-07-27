import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from scripts.bluetooth_phone_connector import (
    BluetoothPhoneConnectorError,
    MAX_HELPER_RESPONSE_BYTES,
    PBAP_PHONEBOOKS,
    validate_device_id,
)
from scripts.bluetooth_phone_data import parse_pbap_vcards


BLUEZ_OBEX_SERVICE = "org.bluez.obex"
BLUEZ_OBEX_CLIENT_PATH = "/org/bluez/obex"
BLUEZ_OBEX_CLIENT_INTERFACE = "org.bluez.obex.Client1"
BLUEZ_PBAP_INTERFACE = "org.bluez.obex.PhonebookAccess1"
BLUEZ_TRANSFER_INTERFACE = "org.bluez.obex.Transfer1"
OBJECT_PATH_RE = re.compile(r'\bo\s+"([/A-Za-z0-9_]+)"')
STRING_VALUE_RE = re.compile(r'\bs\s+"([^"]*)"')
BLUEZ_DEVICE_RE = re.compile(
    r"^Device\s+((?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})(?:\s+(.*))?$"
)


def list_paired_bluez_devices(bluetoothctl_path=None, runner=None, timeout=10):
    """Return devices BlueZ reports as paired, without starting a scan."""
    bluetoothctl = bluetoothctl_path or shutil.which("bluetoothctl")
    if not bluetoothctl:
        return []
    run = runner or subprocess.run
    try:
        result = run(
            [bluetoothctl, "devices", "Paired"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []

    devices = []
    for line in (result.stdout or "").splitlines():
        match = BLUEZ_DEVICE_RE.match(line.strip())
        if not match:
            continue
        devices.append(
            {
                "id": match.group(1).upper(),
                "name": (match.group(2) or match.group(1)).strip(),
            }
        )
    return devices


class BluezObexConnector:
    """PBAP connector for Linux and OpenWrt using the BlueZ OBEX D-Bus API."""

    def __init__(
        self,
        busctl_path=None,
        bus_scope=None,
        timeout=120,
        runner=None,
        sleeper=None,
        clock=None,
    ):
        self.busctl_path = busctl_path or shutil.which("busctl")
        if not self.busctl_path:
            raise BluetoothPhoneConnectorError(
                "BlueZ phone synchronisation requires busctl and a running obexd service"
            )
        if bus_scope not in {None, "--user", "--system"}:
            raise BluetoothPhoneConnectorError("Unsupported D-Bus scope")
        self.bus_scope = bus_scope
        self.timeout = timeout
        self.runner = runner or subprocess.run
        self.sleeper = sleeper or time.sleep
        self.clock = clock or time.monotonic

    def _command(self, arguments):
        scope = [self.bus_scope] if self.bus_scope else []
        return [self.busctl_path, *scope, *arguments]

    def _run(self, arguments, timeout=15, check=True):
        try:
            result = self.runner(
                self._command(arguments),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise BluetoothPhoneConnectorError(f"BlueZ D-Bus request failed: {exc}") from exc
        if check and result.returncode != 0:
            message = (result.stderr or result.stdout or "BlueZ D-Bus request failed").strip()
            raise BluetoothPhoneConnectorError(message)
        return result

    def _ensure_bus_scope(self):
        if self.bus_scope:
            return
        failures = []
        for scope in ("--user", "--system"):
            self.bus_scope = scope
            result = self._run(
                ["tree", BLUEZ_OBEX_SERVICE],
                timeout=5,
                check=False,
            )
            if result.returncode == 0:
                return
            failures.append((result.stderr or result.stdout or scope).strip())
        self.bus_scope = None
        raise BluetoothPhoneConnectorError(
            "BlueZ obexd was not found on the user or system D-Bus. "
            "Install and start the BlueZ OBEX service."
        )

    @staticmethod
    def _object_path(output, operation):
        match = OBJECT_PATH_RE.search(output or "")
        if not match:
            raise BluetoothPhoneConnectorError(
                f"BlueZ {operation} did not return an object path"
            )
        return match.group(1)

    def _create_session(self, device_id):
        result = self._run(
            [
                "call",
                BLUEZ_OBEX_SERVICE,
                BLUEZ_OBEX_CLIENT_PATH,
                BLUEZ_OBEX_CLIENT_INTERFACE,
                "CreateSession",
                "sa{sv}",
                validate_device_id(device_id),
                "1",
                "Target",
                "s",
                "pbap",
            ],
            timeout=30,
        )
        return self._object_path(result.stdout, "CreateSession")

    def _remove_session(self, session_path):
        self._run(
            [
                "call",
                BLUEZ_OBEX_SERVICE,
                BLUEZ_OBEX_CLIENT_PATH,
                BLUEZ_OBEX_CLIENT_INTERFACE,
                "RemoveSession",
                "o",
                session_path,
            ],
            timeout=15,
            check=False,
        )

    def _select_phonebook(self, session_path, phonebook):
        if phonebook not in PBAP_PHONEBOOKS.values():
            raise BluetoothPhoneConnectorError("Unsupported PBAP phone book")
        self._run(
            [
                "call",
                BLUEZ_OBEX_SERVICE,
                session_path,
                BLUEZ_PBAP_INTERFACE,
                "Select",
                "ss",
                "int",
                phonebook,
            ]
        )

    def _wait_for_transfer(self, transfer_path):
        deadline = self.clock() + self.timeout
        while self.clock() < deadline:
            result = self._run(
                [
                    "get-property",
                    BLUEZ_OBEX_SERVICE,
                    transfer_path,
                    BLUEZ_TRANSFER_INTERFACE,
                    "Status",
                ],
                timeout=10,
            )
            match = STRING_VALUE_RE.search(result.stdout or "")
            status = match.group(1) if match else ""
            if status == "complete":
                return
            if status == "error":
                raise BluetoothPhoneConnectorError("BlueZ OBEX transfer failed")
            self.sleeper(0.25)
        raise BluetoothPhoneConnectorError("BlueZ OBEX transfer timed out")

    def _pull_phonebook(self, session_path, phonebook, target_path):
        self._select_phonebook(session_path, phonebook)
        result = self._run(
            [
                "call",
                BLUEZ_OBEX_SERVICE,
                session_path,
                BLUEZ_PBAP_INTERFACE,
                "PullAll",
                "sa{sv}",
                str(target_path),
                "0",
            ]
        )
        transfer_path = self._object_path(result.stdout, "PullAll")
        self._wait_for_transfer(transfer_path)
        try:
            if target_path.stat().st_size > MAX_HELPER_RESPONSE_BYTES:
                raise BluetoothPhoneConnectorError("BlueZ phone book response is too large")
            return target_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise BluetoothPhoneConnectorError(
                f"Unable to read the downloaded BlueZ phone book: {exc}"
            ) from exc

    def synchronise(self, device_id, enabled_features):
        selected = [
            key
            for key in ("contacts", "call_history")
            if (enabled_features or {}).get(key) is True
        ]
        if not selected:
            raise BluetoothPhoneConnectorError(
                "Select contacts or call history before synchronising"
            )

        self._ensure_bus_scope()
        session_path = self._create_session(device_id)
        synced = {}
        try:
            with tempfile.TemporaryDirectory(prefix="mobile-router-phone-") as directory:
                for feature in selected:
                    target_path = Path(directory) / f"{feature}.vcf"
                    vcard = self._pull_phonebook(
                        session_path,
                        PBAP_PHONEBOOKS[feature],
                        target_path,
                    )
                    record_type = "contacts" if feature == "contacts" else "calls"
                    synced[feature] = parse_pbap_vcards(vcard, record_type)
        finally:
            self._remove_session(session_path)
        return synced
