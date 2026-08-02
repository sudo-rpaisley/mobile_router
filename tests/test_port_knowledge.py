import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as app_module
from app import app
from services import port_knowledge


class PortKnowledgeServiceTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database = Path(self.tempdir.name) / "knowledge.sqlite3"

    def tearDown(self):
        self.tempdir.cleanup()

    def test_confirmed_mapping_is_reused_for_same_model(self):
        mapping = port_knowledge.add_mapping(
            self.database,
            manufacturer="Sky",
            model="SR203",
            port=51000,
            service="Sky router management service",
            description="Model-specific management endpoint",
            source_name="Vendor support page",
            source_url="https://example.com/sky-sr203",
            verified_by="admin",
        )
        device = {
            "manufacturer": "Sky",
            "model": "SR203",
            "open_port_details": [{"port": 51000, "service": "Unknown"}],
        }

        result = port_knowledge.apply(self.database, device)

        detail = result["device"]["open_port_details"][0]
        self.assertEqual(detail["service"], "Sky router management service")
        self.assertEqual(detail["knowledge_mapping_id"], mapping["id"])
        self.assertEqual(detail["knowledge_source_url"], "https://example.com/sky-sr203")

    def test_mapping_does_not_cross_models(self):
        port_knowledge.add_mapping(
            self.database,
            manufacturer="Sky",
            model="SR203",
            port=51000,
            service="Sky router management service",
        )
        other = {
            "manufacturer": "Sky",
            "model": "SR213",
            "open_port_details": [{"port": 51000, "service": "Unknown"}],
        }

        result = port_knowledge.apply(self.database, other)

        self.assertFalse(result["applied"])
        self.assertEqual(result["device"]["open_port_details"][0]["service"], "Unknown")

    def test_two_distinct_devices_promote_consistent_candidate(self):
        first = {
            "manufacturer": "Example",
            "model": "Router X",
            "identity_signature": "device-one",
            "open_port_details": [
                {"port": 49160, "service": "router-control", "description": "Control service"}
            ],
        }
        second = {
            **first,
            "identity_signature": "device-two",
        }

        initial = port_knowledge.observe(self.database, first)
        learned = port_knowledge.observe(self.database, second)

        self.assertFalse(initial["promoted"])
        self.assertEqual(len(learned["promoted"]), 1)
        mapping = port_knowledge.mappings(
            self.database,
            manufacturer="Example",
            model="Router X",
        )[0]
        self.assertEqual(mapping["confidence"], "learned")
        self.assertEqual(mapping["distinct_devices"], 2)

    def test_unidentified_high_port_remains_candidate(self):
        for signature in ("one", "two"):
            port_knowledge.observe(
                self.database,
                {
                    "manufacturer": "Sky",
                    "model": "SR203",
                    "identity_signature": signature,
                    "open_port_details": [{"port": 55000, "service": "Unknown"}],
                },
            )

        self.assertFalse(
            port_knowledge.mappings(
                self.database,
                manufacturer="Sky",
                model="SR203",
            )
        )
        candidate = port_knowledge.candidates(
            self.database,
            manufacturer="Sky",
            model="SR203",
        )[0]
        self.assertEqual(candidate["service"], "Model-specific service")
        self.assertEqual(candidate["distinct_devices"], 2)

    def test_upnp_model_becomes_reusable_identity(self):
        identity = port_knowledge.extract_identity(
            {"manufacturer": "Unknown"},
            safe_probes={
                "upnp": [
                    {
                        "manufacturer": "Sky",
                        "model_name": "Sky Broadband Hub",
                        "model_number": "SR203",
                    }
                ]
            },
            assessment={"likely_device": "Gateway/router"},
        )

        self.assertEqual(identity["manufacturer"], "Sky")
        self.assertEqual(identity["model"], "Sky Broadband Hub SR203")
        self.assertEqual(identity["source"], "UPnP device description")

    def test_registry_round_trip(self):
        port_knowledge.add_mapping(
            self.database,
            manufacturer="Example",
            model="Model A",
            port=12345,
            protocol="udp",
            service="Telemetry",
        )
        exported = port_knowledge.export_registry(self.database)
        other = Path(self.tempdir.name) / "other.sqlite3"

        result = port_knowledge.import_registry(
            other,
            exported,
            source_name="Test registry",
        )

        self.assertEqual(result["imported"], 1)
        imported = port_knowledge.mappings(
            other,
            manufacturer="Example",
            model="Model A",
        )[0]
        self.assertEqual(imported["protocol"], "udp")
        self.assertEqual(imported["service"], "Telemetry")

    @patch("services.port_knowledge.socket.getaddrinfo")
    def test_online_registry_rejects_private_destination(self, getaddrinfo):
        getaddrinfo.return_value = [(None, None, None, None, ("192.168.1.2", 443))]

        with self.assertRaisesRegex(ValueError, "non-public"):
            port_knowledge.public_https_url("https://registry.example/ports.json")


class PortKnowledgeRouteTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database = Path(self.tempdir.name) / "route.sqlite3"
        self.client = app.test_client()
        app_module.device_inventory.clear()
        app_module.social_users.clear()
        app_module.social_audit_log.clear()
        app_module.social_users["test-admin"] = {
            "id": "test-admin",
            "username": "test-admin",
            "role": "admin",
            "password_hash": "unused",
        }
        self.csrf = "port-knowledge-csrf"
        with self.client.session_transaction() as flask_session:
            flask_session["social_user"] = {
                "username": "test-admin",
                "role": "admin",
            }
            flask_session["social_csrf_token"] = self.csrf
        app_module.device_inventory["mac:00:11:22:33:44:55"] = {
            "id": "mac:00:11:22:33:44:55",
            "ip": "192.0.2.10",
            "mac": "00:11:22:33:44:55",
            "manufacturer": "Sky",
            "model": "SR203",
            "open_ports": [51000],
            "open_port_details": [{"port": 51000, "service": "Unknown"}],
            "sources": ["test"],
            "interfaces": ["eth0"],
        }
        self.path_patch = patch(
            "routes.port_knowledge._database_path",
            return_value=self.database,
        )
        self.path_patch.start()

    def tearDown(self):
        self.path_patch.stop()
        app_module.device_inventory.clear()
        app_module.social_users.clear()
        app_module.social_audit_log.clear()
        self.tempdir.cleanup()

    def test_client_page_loads_model_port_knowledge_script(self):
        response = self.client.get("/clients/192.0.2.10")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"port-knowledge.js", response.data)

    def test_manual_mapping_is_saved_and_applied(self):
        response = self.client.post(
            "/clients/192.0.2.10/port-knowledge/mappings",
            data={
                "manufacturer": "Sky",
                "model": "SR203",
                "port": "51000",
                "protocol": "tcp",
                "service": "Sky router management service",
                "description": "Documented high-port service",
                "sourceName": "Research note",
                "sourceUrl": "https://example.com/sky",
                "csrf_token": self.csrf,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["mapping"]["model"], "SR203")
        device = app_module.find_inventory_device("192.0.2.10")
        self.assertEqual(
            device["open_port_details"][0]["service"],
            "Sky router management service",
        )
        self.assertTrue(
            any(item["action"] == "port-knowledge.mapping.add" for item in app_module.social_audit_log)
        )

    def test_mapping_is_reused_on_second_device(self):
        port_knowledge.add_mapping(
            self.database,
            manufacturer="Sky",
            model="SR203",
            port=51000,
            service="Sky router management service",
        )
        app_module.device_inventory["mac:00:11:22:33:44:66"] = {
            "id": "mac:00:11:22:33:44:66",
            "ip": "192.0.2.11",
            "mac": "00:11:22:33:44:66",
            "manufacturer": "Sky",
            "model": "SR203",
            "open_ports": [51000],
            "open_port_details": [{"port": 51000, "service": "Unknown"}],
            "sources": ["test"],
            "interfaces": ["eth0"],
        }

        overview = self.client.get("/clients/192.0.2.11/port-knowledge")
        self.assertTrue(overview.get_json()["knowledge"]["needs_application"])
        response = self.client.post(
            "/clients/192.0.2.11/port-knowledge/learn",
            data={"csrf_token": self.csrf},
        )

        self.assertEqual(response.status_code, 200)
        device = app_module.find_inventory_device("192.0.2.11")
        self.assertEqual(
            device["open_port_details"][0]["service"],
            "Sky router management service",
        )

    def test_write_routes_require_csrf(self):
        response = self.client.post(
            "/clients/192.0.2.10/port-knowledge/learn",
            data={"csrf_token": "wrong"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("CSRF", response.get_json()["message"])

    def test_structured_registry_import(self):
        payload = {
            "schema": port_knowledge.SCHEMA,
            "mappings": [
                {
                    "manufacturer": "Example",
                    "model": "Router Z",
                    "port": 45000,
                    "protocol": "tcp",
                    "service": "Vendor telemetry",
                }
            ],
        }

        response = self.client.post(
            "/port-knowledge/import",
            data={
                "registryJson": json.dumps(payload),
                "csrf_token": self.csrf,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["result"]["imported"], 1)

    def test_sync_requires_configured_allowlist(self):
        with patch.dict("os.environ", {}, clear=True):
            response = self.client.post(
                "/port-knowledge/sync",
                data={"csrf_token": self.csrf},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("MOBILE_ROUTER_PORT_REGISTRY_URLS", response.get_json()["message"])


if __name__ == "__main__":
    unittest.main()
