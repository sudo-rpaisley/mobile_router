import json
import subprocess
import sys
from pathlib import Path

from scripts.bluetooth_phone_data import parse_map_messages, parse_pbap_vcards


HELPER_PROTOCOL_VERSION = 1
PBAP_PHONEBOOKS = {
    "contacts": "pb",
    "call_history": "cch",
}
MAP_MESSAGE_FOLDERS = {
    "messages": "telecom/msg/inbox",
}
MAX_HELPER_RESPONSE_BYTES = 32 * 1024 * 1024


class BluetoothPhoneConnectorError(RuntimeError):
    """Raised when a native Bluetooth phone connector cannot complete a request."""


def validate_device_id(value):
    device_id = str(value or "").strip()
    if not device_id:
        raise BluetoothPhoneConnectorError("A paired Bluetooth device identifier is required")
    if len(device_id.encode("utf-8")) > 512:
        raise BluetoothPhoneConnectorError("The Bluetooth device identifier is too long")
    if any(ord(character) < 32 or ord(character) == 127 for character in device_id):
        raise BluetoothPhoneConnectorError(
            "The Bluetooth device identifier cannot contain control characters"
        )
    return device_id


class BluetoothPhoneHelperClient:
    """Portable JSON bridge to a host-specific RFCOMM/OBEX helper.

    The helper receives one JSON request on stdin and returns one JSON object on
    stdout. Keeping the boundary process-based avoids adding native Python
    extensions to constrained OpenWrt installations.
    """

    def __init__(self, helper_path, timeout=120, runner=None):
        self.helper_path = Path(helper_path)
        self.timeout = timeout
        self.runner = runner or subprocess.run

    def _command(self):
        if self.helper_path.suffix.lower() == ".py":
            return [sys.executable, str(self.helper_path)]
        return [str(self.helper_path)]

    def _request(self, action, **payload):
        if not self.helper_path.is_file():
            raise BluetoothPhoneConnectorError(
                f"Bluetooth phone helper was not found: {self.helper_path}"
            )
        request = {
            "protocol_version": HELPER_PROTOCOL_VERSION,
            "action": action,
            **payload,
        }
        try:
            result = self.runner(
                self._command(),
                input=json.dumps(request),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise BluetoothPhoneConnectorError(
                f"Bluetooth phone helper could not be run: {exc}"
            ) from exc

        if result.returncode != 0:
            message = (result.stderr or result.stdout or "Helper request failed").strip()
            raise BluetoothPhoneConnectorError(message)
        encoded_response = (result.stdout or "").encode("utf-8")
        if len(encoded_response) > MAX_HELPER_RESPONSE_BYTES:
            raise BluetoothPhoneConnectorError("Bluetooth phone helper response is too large")
        try:
            response = json.loads(result.stdout or "")
        except json.JSONDecodeError as exc:
            raise BluetoothPhoneConnectorError(
                "Bluetooth phone helper returned invalid JSON"
            ) from exc
        if not isinstance(response, dict):
            raise BluetoothPhoneConnectorError(
                "Bluetooth phone helper response must be a JSON object"
            )
        if response.get("protocol_version") != HELPER_PROTOCOL_VERSION:
            raise BluetoothPhoneConnectorError(
                "Bluetooth phone helper protocol version does not match Mobile Router"
            )
        if response.get("status") != "success":
            raise BluetoothPhoneConnectorError(
                str(response.get("message") or "Bluetooth phone helper request failed")
            )
        return response

    def capabilities(self):
        response = self._request("capabilities")
        capabilities = response.get("capabilities", {})
        if not isinstance(capabilities, dict):
            raise BluetoothPhoneConnectorError(
                "Bluetooth phone helper capabilities must be a JSON object"
            )
        return capabilities

    def set_advertising(self, enabled, display_name=None):
        payload = {"enabled": enabled is True}
        if display_name is not None:
            payload["display_name"] = str(display_name)
        response = self._request("set_advertising", **payload)
        return {
            "enabled": response.get("enabled") is True,
            "message": str(response.get("message") or "Bluetooth advertising updated."),
        }

    def pull_pbap(self, device_id, phonebook):
        if phonebook not in PBAP_PHONEBOOKS.values():
            raise BluetoothPhoneConnectorError("Unsupported PBAP phone book")
        response = self._request(
            "pull_pbap",
            device_id=validate_device_id(device_id),
            phonebook=phonebook,
            vcard_format="3.0",
        )
        payload = response.get("vcard", "")
        if not isinstance(payload, str):
            raise BluetoothPhoneConnectorError(
                "Bluetooth phone helper vCard payload must be text"
            )
        return payload

    def pull_map(self, device_id, folder):
        if folder not in MAP_MESSAGE_FOLDERS.values():
            raise BluetoothPhoneConnectorError("Unsupported MAP message folder")
        response = self._request(
            "pull_map",
            device_id=validate_device_id(device_id),
            folder=folder,
        )
        payload = response.get("messages", response.get("bmessage", ""))
        if not isinstance(payload, (str, list)):
            raise BluetoothPhoneConnectorError(
                "Bluetooth phone helper MAP payload must be text or a message list"
            )
        return payload

    def synchronise(self, device_id, enabled_features):
        selected = {
            key
            for key, enabled in (enabled_features or {}).items()
            if enabled is True and key in {*PBAP_PHONEBOOKS, *MAP_MESSAGE_FOLDERS}
        }
        synced = {}
        if "contacts" in selected:
            synced["contacts"] = parse_pbap_vcards(
                self.pull_pbap(device_id, PBAP_PHONEBOOKS["contacts"]),
                "contacts",
            )
        if "call_history" in selected:
            synced["call_history"] = parse_pbap_vcards(
                self.pull_pbap(device_id, PBAP_PHONEBOOKS["call_history"]),
                "calls",
            )
        if "messages" in selected:
            synced["messages"] = parse_map_messages(
                self.pull_map(device_id, MAP_MESSAGE_FOLDERS["messages"])
            )
        if not synced:
            raise BluetoothPhoneConnectorError(
                "Select contacts, call history, or messages before synchronising"
            )
        return synced
