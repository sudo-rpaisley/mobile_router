import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app import app
from scripts.bluetooth_phone import (
    BluetoothPhoneSettingsError,
    apply_bluetooth_display_name,
    bluetooth_pairing_mode_capability,
    enable_bluetooth_pairing_mode,
    bluetooth_display_name_capability,
    build_settings,
    load_bluetooth_phone_settings,
    save_bluetooth_phone_settings,
)
from scripts.bluetooth_phone_data import parse_map_messages, parse_pbap_vcards, unfold_vcard_lines
from scripts.bluetooth_phone_connector import (
    BluetoothPhoneConnectorError,
    BluetoothPhoneHelperClient,
    validate_device_id,
)
from scripts.bluetooth_phone_bluez import (
    BluezObexConnector,
    list_paired_bluez_devices,
)
from scripts.bluetooth_phone_runtime import (
    build_bluetooth_phone_runtime,
    detect_host_environment,
)


class BluetoothPhoneSettingsTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "bluetooth_phone.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_missing_config_uses_private_defaults(self):
        settings = load_bluetooth_phone_settings(self.config_path)

        self.assertEqual(settings["display_name"], "Mobile Router")
        self.assertTrue(settings["enabled_features"])
        self.assertFalse(any(settings["enabled_features"].values()))

    def test_settings_round_trip_selected_features(self):
        settings = build_settings(
            "Camper Router",
            ["contacts", "call_history", "tethering"],
        )

        save_bluetooth_phone_settings(settings, self.config_path)
        loaded = load_bluetooth_phone_settings(self.config_path)

        self.assertEqual(loaded["display_name"], "Camper Router")
        self.assertTrue(loaded["enabled_features"]["contacts"])
        self.assertTrue(loaded["enabled_features"]["call_history"])
        self.assertTrue(loaded["enabled_features"]["tethering"])
        self.assertFalse(loaded["enabled_features"]["messages"])

    def test_unknown_feature_is_rejected(self):
        with self.assertRaisesRegex(
            BluetoothPhoneSettingsError,
            "Unsupported Bluetooth phone feature",
        ):
            build_settings("Mobile Router", ["contacts", "all_phone_data"])

    def test_control_characters_in_display_name_are_rejected(self):
        with self.assertRaisesRegex(BluetoothPhoneSettingsError, "control characters"):
            build_settings("Router\nName", [])

    def test_invalid_json_is_reported(self):
        self.config_path.write_text("{not-json", encoding="utf-8")

        with self.assertRaisesRegex(
            BluetoothPhoneSettingsError,
            "Unable to read Bluetooth phone settings",
        ):
            load_bluetooth_phone_settings(self.config_path)

    def test_saved_file_contains_only_normalised_settings(self):
        settings = build_settings("Mobile Router", ["contacts"])
        save_bluetooth_phone_settings(settings, self.config_path)

        saved = json.loads(self.config_path.read_text(encoding="utf-8"))

        self.assertEqual(set(saved), {"display_name", "advertise_enabled", "enabled_features"})
        self.assertTrue(saved["enabled_features"]["contacts"])

    def test_windows_name_capability_does_not_rename_the_computer(self):
        capability = bluetooth_display_name_capability(system="Windows")

        self.assertFalse(capability["available"])
        self.assertIn("computer name", capability["message"])

    @patch("scripts.bluetooth_phone.subprocess.run")
    @patch("scripts.bluetooth_phone.bluetooth_display_name_capability")
    def test_apply_display_name_uses_safe_bluetoothctl_arguments(self, capability, run):
        capability.return_value = {
            "available": True,
            "tool": "bluetoothctl",
            "path": "/usr/bin/bluetoothctl",
            "message": "Available",
        }
        run.return_value = SimpleNamespace(returncode=0, stdout="", stderr="")

        result = apply_bluetooth_display_name("Camper Router")

        self.assertTrue(result["applied"])
        self.assertEqual(
            run.call_args.args[0],
            ["/usr/bin/bluetoothctl", "system-alias", "Camper Router"],
        )

    @patch("scripts.bluetooth_phone.subprocess.run")
    @patch("scripts.bluetooth_phone.bluetooth_pairing_mode_capability")
    def test_enable_pairing_mode_makes_adapter_pairable_and_discoverable(self, capability, run):
        capability.return_value = {
            "available": True,
            "tool": "bluetoothctl",
            "path": "/usr/bin/bluetoothctl",
            "message": "Available",
        }
        run.return_value = SimpleNamespace(returncode=0, stdout="", stderr="")

        result = enable_bluetooth_pairing_mode("Camper Router")

        self.assertTrue(result["enabled"])
        self.assertEqual(
            [call.args[0] for call in run.call_args_list],
            [
                ["/usr/bin/bluetoothctl", "power", "on"],
                ["/usr/bin/bluetoothctl", "system-alias", "Camper Router"],
                ["/usr/bin/bluetoothctl", "agent", "NoInputNoOutput"],
                ["/usr/bin/bluetoothctl", "default-agent"],
                ["/usr/bin/bluetoothctl", "pairable", "on"],
                ["/usr/bin/bluetoothctl", "discoverable", "on"],
            ],
        )

    def test_pairing_mode_capability_is_linux_bluez_only(self):
        self.assertFalse(bluetooth_pairing_mode_capability(system="Windows")["available"])


class BluetoothPhoneRouteTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "bluetooth_phone.json"
        self.previous_config = app.config.get("BLUETOOTH_PHONE_CONFIG")
        app.config["BLUETOOTH_PHONE_CONFIG"] = str(self.config_path)
        self.client = app.test_client()

    def tearDown(self):
        if self.previous_config is None:
            app.config.pop("BLUETOOTH_PHONE_CONFIG", None)
        else:
            app.config["BLUETOOTH_PHONE_CONFIG"] = self.previous_config
        self.temp_dir.cleanup()

    @patch("routes.bluetooth_phone.bluetooth_pairing_mode_capability")
    def test_page_renders_independent_feature_checkboxes(self, capability):
        capability.return_value = {
            "available": False,
            "tool": None,
            "path": None,
            "message": "Service name only",
        }

        response = self.client.get("/bluetooth-phone")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Phone Integration", response.data)
        self.assertIn(b'id="feature-contacts"', response.data)
        self.assertIn(b'id="feature-call_history"', response.data)
        self.assertIn(b'id="feature-messages"', response.data)
        self.assertIn(b'id="feature-call_controls"', response.data)
        self.assertIn(b'id="feature-media_controls"', response.data)
        self.assertIn(b'id="feature-tethering"', response.data)
        self.assertIn(b"Advertised phone device", response.data)
        self.assertIn(b'id="advertise-enabled"', response.data)
        self.assertIn(b"Allowed phone features", response.data)
        self.assertNotIn(b"Host compatibility", response.data)
        self.assertNotIn(b"Phone compatibility", response.data)
        self.assertNotIn(b"Synchronise phone data", response.data)

    @patch("routes.bluetooth_phone.bluetooth_pairing_mode_capability")
    def test_post_saves_only_selected_features(self, capability):
        capability.return_value = {
            "available": False,
            "tool": None,
            "path": None,
            "message": "Service name only",
        }

        response = self.client.post(
            "/bluetooth-phone",
            data={
                "display_name": "Robert's Mobile Router",
                "features": ["contacts", "call_history"],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Bluetooth phone settings saved", response.data)
        saved = load_bluetooth_phone_settings(self.config_path)
        self.assertEqual(saved["display_name"], "Robert's Mobile Router")
        self.assertTrue(saved["enabled_features"]["contacts"])
        self.assertTrue(saved["enabled_features"]["call_history"])
        self.assertFalse(saved["enabled_features"]["messages"])

    @patch("routes.bluetooth_phone.bluetooth_pairing_mode_capability")
    def test_post_rejects_unknown_feature(self, capability):
        capability.return_value = {
            "available": False,
            "tool": None,
            "path": None,
            "message": "Service name only",
        }

        response = self.client.post(
            "/bluetooth-phone",
            data={"display_name": "Mobile Router", "features": "everything"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Unsupported Bluetooth phone feature", response.data)
        self.assertFalse(self.config_path.exists())

    @patch("routes.bluetooth_phone.enable_bluetooth_pairing_mode")
    def test_post_can_enable_advertising_with_saved_name(self, enable_pairing):
        enable_pairing.return_value = {
            "enabled": True,
            "display_name": "Camper Router",
            "tool": "bluetoothctl",
            "message": 'Bluetooth advertising is on for "Camper Router".',
        }

        response = self.client.post(
            "/bluetooth-phone",
            data={
                "display_name": "Camper Router",
                "features": "contacts",
                "advertise_enabled": "true",
            },
        )

        self.assertEqual(response.status_code, 200)
        enable_pairing.assert_called_once_with("Camper Router")
        self.assertIn(b"Bluetooth advertising is on", response.data)
        saved = load_bluetooth_phone_settings(self.config_path)
        self.assertTrue(saved["advertise_enabled"])

    @patch("routes.bluetooth_phone.enable_bluetooth_pairing_mode")
    def test_pairing_mode_endpoint_uses_saved_display_name(self, enable_pairing):
        save_bluetooth_phone_settings(
            build_settings("Camper Router", ["contacts"]),
            self.config_path,
        )
        enable_pairing.return_value = {
            "enabled": True,
            "display_name": "Camper Router",
            "tool": "bluetoothctl",
            "message": "Bluetooth pairing mode is enabled for \"Camper Router\".",
        }

        response = self.client.post("/bluetooth-phone/pairing-mode")

        self.assertEqual(response.status_code, 200)
        enable_pairing.assert_called_once_with("Camper Router")
        self.assertIn(b"pairing mode is enabled", response.data)

    @patch("routes.bluetooth_phone.build_bluetooth_phone_runtime")
    def test_status_endpoint_reports_runtime_backend(self, build_runtime):
        build_runtime.return_value = {
            "host": {"id": "windows", "label": "Windows"},
            "backend": {"id": "windows-rfcomm", "connector_ready": False},
            "commands": {},
            "helper": {"available": False, "path": None},
            "features": {},
            "phones": {},
        }

        response = self.client.get("/bluetooth-phone/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["runtime"]["host"]["id"], "windows")

    @patch("routes.bluetooth_phone.BluezObexConnector")
    @patch("routes.bluetooth_phone.build_bluetooth_phone_runtime")
    def test_sync_downloads_only_enabled_phone_data(self, build_runtime, connector):
        save_bluetooth_phone_settings(
            build_settings("Mobile Router", ["contacts", "call_history"]),
            self.config_path,
        )
        build_runtime.return_value = {
            "host": {"id": "linux"},
            "backend": {"connector_ready": True},
            "commands": {"busctl": {"available": True}},
            "helper": {"available": False, "path": None},
            "bluez_obex": {"available": True, "scope": "--user"},
        }
        connector.return_value.synchronise.return_value = {
            "contacts": [{"display_name": "Test Contact"}],
            "call_history": [{"number": "123", "call_type": "missed"}],
        }

        response = self.client.post(
            "/bluetooth-phone/sync",
            data={
                "device_id": "AA:BB:CC:DD:EE:FF",
                "confirm_phone_access": "true",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/json")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        exported = json.loads(response.data)
        self.assertEqual(exported["features"], ["call_history", "contacts"])
        connector.return_value.synchronise.assert_called_once()

    def test_sync_requires_explicit_authorisation(self):
        response = self.client.post(
            "/bluetooth-phone/sync",
            data={"device_id": "AA:BB:CC:DD:EE:FF"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("authorised", response.get_json()["message"])

    @patch("routes.bluetooth_phone.BluetoothPhoneHelperClient")
    @patch("routes.bluetooth_phone.build_bluetooth_phone_runtime")
    def test_sync_uses_configured_native_helper_on_windows(self, build_runtime, helper_client):
        save_bluetooth_phone_settings(
            build_settings("Mobile Router", ["contacts"]),
            self.config_path,
        )
        build_runtime.return_value = {
            "host": {"id": "windows"},
            "backend": {"connector_ready": True},
            "commands": {},
            "helper": {"available": True, "path": "C:/MobileRouter/phone-helper.exe"},
            "bluez_obex": {"available": False, "scope": None},
        }
        helper_client.return_value.synchronise.return_value = {
            "contacts": [{"display_name": "Windows Contact"}],
        }

        response = self.client.post(
            "/bluetooth-phone/sync",
            data={
                "device_id": "windows-device-id",
                "confirm_phone_access": "true",
            },
        )

        self.assertEqual(response.status_code, 200)
        helper_client.assert_called_once_with("C:/MobileRouter/phone-helper.exe")

    def test_helper_synchronises_messages_with_map_payload(self):
        helper = Path(self.temp_dir.name) / "helper.py"
        helper.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "request = json.load(sys.stdin)\n"
            "response = {\"protocol_version\": 1, \"status\": \"success\"}\n"
            "if request[\"action\"] == \"pull_map\":\n"
            "    response[\"messages\"] = [{\"handle\": \"1\", \"sender\": \"+15551234567\", \"text\": \"Arrived\", \"read\": True}]\n"
            "else:\n"
            "    response[\"vcard\"] = \"\"\n"
            "json.dump(response, sys.stdout)\n",
            encoding="utf-8",
        )
        helper.chmod(0o755)

        client = BluetoothPhoneHelperClient(helper)
        data = client.synchronise("AA:BB:CC:DD:EE:FF", {"messages": True})

        self.assertEqual(data["messages"][0]["text"], "Arrived")
        self.assertTrue(data["messages"][0]["read"])


class BluetoothPhoneRuntimeTest(unittest.TestCase):
    def test_detects_supported_host_families(self):
        self.assertEqual(detect_host_environment(system="Windows", openwrt=False)["id"], "windows")
        self.assertEqual(detect_host_environment(system="Darwin", openwrt=False)["id"], "macos")
        self.assertEqual(detect_host_environment(system="Linux", openwrt=False)["id"], "linux")
        openwrt = detect_host_environment(system="Linux", openwrt=True)
        self.assertEqual(openwrt["id"], "openwrt")
        self.assertTrue(openwrt["limited"])

    def test_linux_and_openwrt_share_bluez_backend(self):
        settings = build_settings("Mobile Router", ["contacts", "messages"])

        def lookup(command):
            return f"/usr/bin/{command}" if command in {"bluetoothctl", "obexctl"} else None

        linux = build_bluetooth_phone_runtime(
            settings,
            system="Linux",
            openwrt=False,
            command_lookup=lookup,
        )
        openwrt = build_bluetooth_phone_runtime(
            settings,
            system="Linux",
            openwrt=True,
            command_lookup=lookup,
        )

        self.assertEqual(linux["backend"]["id"], "bluez-obex")
        self.assertEqual(openwrt["backend"]["id"], "bluez-obex")
        self.assertTrue(linux["backend"]["prerequisites_ready"])
        self.assertFalse(linux["backend"]["connector_ready"])

    def test_linux_busctl_enables_built_in_bluez_connector(self):
        settings = build_settings("Mobile Router", ["contacts"])

        def lookup(command):
            return f"/usr/bin/{command}" if command in {"busctl", "bluetoothctl"} else None

        runtime = build_bluetooth_phone_runtime(
            settings,
            system="Linux",
            openwrt=False,
            command_lookup=lookup,
            bluez_obex_lookup=lambda _commands: {
                "available": True,
                "scope": "--user",
            },
        )

        self.assertTrue(runtime["backend"]["prerequisites_ready"])
        self.assertTrue(runtime["backend"]["connector_ready"])
        self.assertEqual(runtime["features"]["contacts"]["status"], "ready")

    def test_map_is_not_marked_ready_by_pbap_connector(self):
        settings = build_settings("Mobile Router", ["contacts", "messages"])

        def lookup(command):
            return f"/usr/bin/{command}" if command in {"busctl", "bluetoothctl"} else None

        runtime = build_bluetooth_phone_runtime(
            settings,
            system="Linux",
            openwrt=False,
            command_lookup=lookup,
            bluez_obex_lookup=lambda _commands: {
                "available": True,
                "scope": "--system",
            },
        )

        self.assertEqual(runtime["features"]["contacts"]["status"], "ready")
        self.assertEqual(runtime["features"]["messages"]["status"], "transport_required")

    def test_linux_does_not_report_ready_when_obexd_is_stopped(self):
        settings = build_settings("Mobile Router", ["contacts"])

        def lookup(command):
            return f"/usr/bin/{command}" if command in {"busctl", "bluetoothctl"} else None

        runtime = build_bluetooth_phone_runtime(
            settings,
            system="Linux",
            openwrt=False,
            command_lookup=lookup,
            bluez_obex_lookup=lambda _commands: {
                "available": False,
                "scope": None,
            },
        )

        self.assertFalse(runtime["backend"]["connector_ready"])
        self.assertIn("obexd", " ".join(runtime["backend"]["missing"]))

    def test_windows_and_macos_use_native_helper_backends(self):
        settings = build_settings("Mobile Router", ["contacts"])
        no_commands = lambda _command: None

        windows = build_bluetooth_phone_runtime(
            settings,
            system="Windows",
            openwrt=False,
            command_lookup=no_commands,
        )
        macos = build_bluetooth_phone_runtime(
            settings,
            system="Darwin",
            openwrt=False,
            command_lookup=no_commands,
        )

        self.assertEqual(windows["backend"]["id"], "windows-rfcomm")
        self.assertEqual(macos["backend"]["id"], "macos-iobluetooth")
        self.assertIn("helper", windows["backend"]["missing"][0].lower())
        self.assertIn("helper", macos["backend"]["missing"][0].lower())

    def test_phone_matrix_includes_android_and_iphone_profiles(self):
        settings = build_settings("Mobile Router", [])
        runtime = build_bluetooth_phone_runtime(
            settings,
            system="Windows",
            openwrt=False,
            command_lookup=lambda _command: None,
        )

        self.assertEqual(runtime["phones"]["android"]["features"]["contacts"], "PBAP")
        self.assertEqual(runtime["phones"]["iphone"]["features"]["call_history"], "PBAP 1.2")
        self.assertEqual(runtime["phones"]["iphone"]["features"]["messages"], "MAP 1.4")

    def test_control_features_are_not_marked_ready_by_obex_helper(self):
        settings = build_settings("Mobile Router", ["contacts", "call_controls"])
        with tempfile.NamedTemporaryFile() as helper:
            with patch.dict(
                "os.environ",
                {"MOBILE_ROUTER_BLUETOOTH_HELPER": helper.name},
                clear=False,
            ):
                runtime = build_bluetooth_phone_runtime(
                    settings,
                    system="Windows",
                    openwrt=False,
                    command_lookup=lambda _command: None,
                )

        self.assertEqual(runtime["features"]["contacts"]["status"], "ready")
        self.assertEqual(
            runtime["features"]["call_controls"]["status"],
            "host_integration_required",
        )

    def test_helper_backend_marks_messages_ready(self):
        settings = build_settings("Mobile Router", ["messages"])
        with tempfile.NamedTemporaryFile() as helper:
            with patch.dict(
                "os.environ",
                {"MOBILE_ROUTER_BLUETOOTH_HELPER": helper.name},
                clear=False,
            ):
                runtime = build_bluetooth_phone_runtime(
                    settings,
                    system="Windows",
                    openwrt=False,
                    command_lookup=lambda _command: None,
                )

        self.assertEqual(runtime["features"]["messages"]["status"], "ready")


class BluetoothPhoneDataTest(unittest.TestCase):
    def test_parses_pbap_contact_vcard(self):
        payload = """BEGIN:VCARD\r
VERSION:3.0\r
N:Paisley;Robert;;;\r
FN:Robert Paisley\r
TEL;TYPE=CELL:+447700900123\r
TEL;TYPE=HOME:01234567890\r
EMAIL;TYPE=HOME:robert@example.test\r
ORG:Mobile Router\r
TITLE:Developer\r
END:VCARD\r
"""

        contacts = parse_pbap_vcards(payload, "contacts")

        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0]["display_name"], "Robert Paisley")
        self.assertEqual(contacts[0]["given_name"], "Robert")
        self.assertEqual(contacts[0]["family_name"], "Paisley")
        self.assertEqual(contacts[0]["phones"][0]["number"], "+447700900123")
        self.assertEqual(contacts[0]["phones"][0]["types"], ["cell"])
        self.assertEqual(contacts[0]["organisation"], "Mobile Router")

    def test_parses_pbap_call_history_vcards(self):
        payload = """BEGIN:VCARD
VERSION:2.1
N:Paisley;Robert
FN:Robert Paisley
TEL:+447700900123
X-IRMC-CALL-DATETIME;TYPE=RECEIVED:20260716T143000
END:VCARD
BEGIN:VCARD
VERSION:2.1
N:Unknown;;;;
TEL:01234567890
X-IRMC-CALL-DATETIME;TYPE=MISSED:20260716T150000Z
END:VCARD
"""

        calls = parse_pbap_vcards(payload, "calls")

        self.assertEqual([call["call_type"] for call in calls], ["incoming", "missed"])
        self.assertEqual(calls[0]["timestamp"], "2026-07-16T14:30:00")
        self.assertEqual(calls[1]["timestamp"], "2026-07-16T15:00:00")

    def test_parses_map_message_list_payload(self):
        messages = parse_map_messages([
            {
                "handle": "42",
                "sender": "+15551234567",
                "body": "Camp check-in",
                "read": True,
            }
        ])

        self.assertEqual(messages[0]["handle"], "42")
        self.assertEqual(messages[0]["text"], "Camp check-in")
        self.assertTrue(messages[0]["read"])


    def test_unfolds_folded_vcard_lines(self):
        lines = unfold_vcard_lines("NOTE:This is a long\r\n note\r\nTEL:123")

        self.assertEqual(lines[0], "NOTE:This is a longnote")

    def test_preserves_escaped_name_separator(self):
        payload = """BEGIN:VCARD
VERSION:3.0
N:Example;Semi\\;Colon;;;
TEL:123
END:VCARD
"""

        contact = parse_pbap_vcards(payload, "contacts")[0]

        self.assertEqual(contact["given_name"], "Semi;Colon")


class BluetoothPhoneConnectorTest(unittest.TestCase):
    def setUp(self):
        self.helper = tempfile.NamedTemporaryFile()

    def tearDown(self):
        self.helper.close()

    def test_helper_request_uses_json_stdin_without_a_shell(self):
        response = {
            "protocol_version": 1,
            "status": "success",
            "vcard": "BEGIN:VCARD\nFN:Test Contact\nEND:VCARD\n",
        }
        runner = unittest.mock.Mock(
            return_value=SimpleNamespace(
                returncode=0,
                stdout=json.dumps(response),
                stderr="",
            )
        )
        client = BluetoothPhoneHelperClient(self.helper.name, runner=runner)

        payload = client.pull_pbap("AA:BB:CC:DD:EE:FF", "pb")

        self.assertIn("Test Contact", payload)
        command = runner.call_args.args[0]
        request_payload = json.loads(runner.call_args.kwargs["input"])
        self.assertEqual(command, [self.helper.name])
        self.assertEqual(request_payload["action"], "pull_pbap")
        self.assertEqual(request_payload["phonebook"], "pb")

    def test_synchronise_only_requests_enabled_pbap_features(self):
        contacts = "BEGIN:VCARD\nFN:Test Contact\nTEL:123\nEND:VCARD\n"
        calls = "BEGIN:VCARD\nTEL:456\nX-IRMC-CALL-DATETIME;TYPE=MISSED:20260716T150000\nEND:VCARD\n"
        responses = [
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {"protocol_version": 1, "status": "success", "vcard": contacts}
                ),
                stderr="",
            ),
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {"protocol_version": 1, "status": "success", "vcard": calls}
                ),
                stderr="",
            ),
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "protocol_version": 1,
                        "status": "success",
                        "messages": [{"handle": "1", "text": "Hello"}],
                    }
                ),
                stderr="",
            ),
        ]
        runner = unittest.mock.Mock(side_effect=responses)
        client = BluetoothPhoneHelperClient(self.helper.name, runner=runner)

        data = client.synchronise(
            "AA:BB:CC:DD:EE:FF",
            {"contacts": True, "call_history": True, "messages": True},
        )

        self.assertEqual(set(data), {"contacts", "call_history", "messages"})
        self.assertEqual(data["contacts"][0]["display_name"], "Test Contact")
        self.assertEqual(data["call_history"][0]["call_type"], "missed")
        self.assertEqual(data["messages"][0]["text"], "Hello")
        self.assertEqual(runner.call_count, 3)

    def test_helper_protocol_errors_are_reported(self):
        runner = unittest.mock.Mock(
            return_value=SimpleNamespace(returncode=0, stdout="not-json", stderr="")
        )
        client = BluetoothPhoneHelperClient(self.helper.name, runner=runner)

        with self.assertRaisesRegex(BluetoothPhoneConnectorError, "invalid JSON"):
            client.capabilities()

    def test_device_id_rejects_control_characters(self):
        with self.assertRaisesRegex(BluetoothPhoneConnectorError, "control characters"):
            validate_device_id("phone\nidentifier")


class BluezObexConnectorTest(unittest.TestCase):
    def test_lists_only_valid_paired_bluez_devices(self):
        runner = unittest.mock.Mock(
            return_value=SimpleNamespace(
                returncode=0,
                stdout=(
                    "Device AA:BB:CC:DD:EE:FF Robert's Phone\n"
                    "Not a device line\n"
                    "Device 11:22:33:44:55:66 iPhone\n"
                ),
                stderr="",
            )
        )

        devices = list_paired_bluez_devices(
            bluetoothctl_path="/usr/bin/bluetoothctl",
            runner=runner,
        )

        self.assertEqual([device["name"] for device in devices], ["Robert's Phone", "iPhone"])

    def test_bluez_sync_uses_pb_and_combined_call_history(self):
        contacts = "BEGIN:VCARD\nFN:Test Contact\nTEL:123\nEND:VCARD\n"
        calls = "BEGIN:VCARD\nTEL:456\nX-IRMC-CALL-DATETIME;TYPE=MISSED:20260716T150000\nEND:VCARD\n"
        selected_phonebooks = []

        def runner(command, **_kwargs):
            if "CreateSession" in command:
                return SimpleNamespace(
                    returncode=0,
                    stdout='o "/org/bluez/obex/client/session0"',
                    stderr="",
                )
            if "Select" in command:
                selected_phonebooks.append(command[-1])
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            if "PullAll" in command:
                target = Path(command[command.index("sa{sv}") + 1])
                target.write_text(
                    contacts if selected_phonebooks[-1] == "pb" else calls,
                    encoding="utf-8",
                )
                transfer_number = len(selected_phonebooks) - 1
                return SimpleNamespace(
                    returncode=0,
                    stdout=f'o "/org/bluez/obex/client/session0/transfer{transfer_number}" 0',
                    stderr="",
                )
            if "get-property" in command:
                return SimpleNamespace(returncode=0, stdout='s "complete"', stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        connector = BluezObexConnector(
            busctl_path="/usr/bin/busctl",
            bus_scope="--user",
            runner=runner,
        )

        data = connector.synchronise(
            "AA:BB:CC:DD:EE:FF",
            {"contacts": True, "call_history": True},
        )

        self.assertEqual(selected_phonebooks, ["pb", "cch"])
        self.assertEqual(data["contacts"][0]["display_name"], "Test Contact")
        self.assertEqual(data["call_history"][0]["call_type"], "missed")


if __name__ == "__main__":
    unittest.main()
