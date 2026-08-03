import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as app_module
from app import app
from services import host_facts


class HostFactsServiceTest(unittest.TestCase):
    @patch(
        "services.host_facts._local_default_gateways",
        return_value=["192.0.2.1"],
    )
    def test_passive_facts_include_role_ipv6_and_stability(self, gateways):
        device = {
            "ip": "192.0.2.1",
            "mac": "aa:bb:cc:dd:ee:ff",
            "manufacturer": "Example Networks",
            "model": "XR1",
            "ipv6_addresses": ["2001:db8::1"],
            "first_seen": 100.0,
            "last_seen": 400.0,
            "interfaces": ["wlan0"],
            "sources": ["arp-scan"],
            "open_port_details": [
                {"port": 53, "service": "DNS"},
                {"port": 67, "service": "DHCP"},
                {"port": 443, "service": "HTTPS"},
            ],
        }

        facts = host_facts.passive_facts(
            device,
            relationships={"nodes": [1, 2], "links": [1]},
        )
        by_key = {item["key"]: item for item in facts}

        self.assertEqual(
            by_key["network.inferred_role"]["value"]["role"],
            "Default gateway/router",
        )
        self.assertEqual(
            by_key["identity.ipv6"]["value"],
            ["2001:db8::1"],
        )
        self.assertEqual(
            by_key["stability.observation_window_seconds"]["value"],
            300,
        )
        self.assertEqual(
            by_key["network.relationship_counts"]["value"]["nodes"],
            2,
        )

    def test_merge_marks_changes_against_explicit_baseline(self):
        initial = [
            host_facts.fact(
                "identity.model",
                "Model",
                "XR1",
                "UPnP",
                "high",
                observed_at=10,
            )
        ]
        device = host_facts.apply_fact_run(
            {},
            initial,
            mode="passive",
            actor="tester",
            now=10,
        )
        baseline = host_facts.save_baseline(
            device,
            actor="tester",
            now=20,
        )
        changed = [
            host_facts.fact(
                "identity.model",
                "Model",
                "XR2",
                "UPnP",
                "high",
                observed_at=30,
            )
        ]
        updated = host_facts.apply_fact_run(
            baseline,
            changed,
            mode="safe",
            actor="tester",
            now=30,
        )

        item = next(
            item
            for item in updated["host_facts"]
            if item["key"] == "identity.model"
        )
        self.assertTrue(item["changed_since_baseline"])
        self.assertEqual(item["previous_value"], "XR1")
        self.assertEqual(updated["host_fact_runs"][0]["changed_count"], 1)

    def test_credential_store_persists_reference_not_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credentials.json"
            profile = host_facts.save_credential_reference(
                path,
                name="Router SNMP",
                kind="snmp-v2c",
                secret_env="TEST_ROUTER_SNMP",
                username="readonly",
                actor="tester",
            )
            raw = path.read_text(encoding="utf-8")
            self.assertIn("TEST_ROUTER_SNMP", raw)
            self.assertNotIn("super-secret", raw)
            self.assertEqual(
                host_facts.resolve_secret(
                    profile,
                    {"TEST_ROUTER_SNMP": "super-secret"},
                ),
                "super-secret",
            )

    @patch("services.host_facts.device_identification.deep_device_probe")
    def test_deep_facts_extract_snmp_uptime(self, probe):
        probe.return_value = {
            "nmap": {"available": True, "output": "Running: Linux"},
            "snmp": {
                "available": True,
                "output": (
                    "SNMPv2-MIB::sysUpTime.0 = "
                    "Timeticks: (123450) 0:20:34.50"
                ),
            },
        }
        facts = host_facts.deep_facts(
            {"open_port_details": [{"port": 443}]},
            "192.0.2.10",
            authorized=True,
            snmp_community="public",
        )
        uptime = next(
            item for item in facts if item["key"] == "uptime.snmp"
        )
        self.assertEqual(uptime["value"]["seconds"], 1234.5)


class HostFactsRouteTest(unittest.TestCase):
    identifier = "192.0.2.77"
    inventory_key = "ip:192.0.2.77"

    def setUp(self):
        self.client = app.test_client()
        self.tempdir = tempfile.TemporaryDirectory()
        self.credential_path = Path(self.tempdir.name) / "credentials.json"
        self.previous_users = dict(app_module.social_users)
        app_module.social_users.clear()
        app_module.social_users["test-admin"] = {
            "id": "test-admin",
            "username": "test-admin",
            "role": "admin",
            "password_hash": "unused",
        }
        with app_module.device_inventory_lock:
            self.previous_device = app_module.device_inventory.pop(
                self.inventory_key,
                None,
            )
            app_module.device_inventory[self.inventory_key] = {
                "id": self.inventory_key,
                "ip": self.identifier,
                "mac": "aa:bb:cc:dd:ee:77",
                "manufacturer": "Example Networks",
                "model": "XR1",
                "first_seen": 100.0,
                "last_seen": 200.0,
                "open_ports": [22, 443],
                "open_port_details": [
                    {
                        "port": 22,
                        "protocol": "tcp",
                        "service": "SSH",
                    },
                    {
                        "port": 443,
                        "protocol": "tcp",
                        "service": "HTTPS",
                    },
                ],
            }
        self.csrf = "host-facts-csrf"
        with self.client.session_transaction() as flask_session:
            flask_session["social_user"] = {
                "username": "test-admin",
                "role": "admin",
            }
            flask_session["social_csrf_token"] = self.csrf
        self.path_patch = patch(
            "routes.host_facts._credential_path",
            return_value=self.credential_path,
        )
        self.path_patch.start()

    def tearDown(self):
        self.path_patch.stop()
        self.tempdir.cleanup()
        with app_module.device_inventory_lock:
            app_module.device_inventory.pop(self.inventory_key, None)
            if self.previous_device is not None:
                app_module.device_inventory[self.inventory_key] = (
                    self.previous_device
                )
        app_module.social_users.clear()
        app_module.social_users.update(self.previous_users)

    def test_workspace_renders_and_client_page_loads_entry_script(self):
        response = self.client.get(
            f"/clients/{self.identifier}/host-facts"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Host Facts &amp; Capabilities", response.data)
        self.assertIn(b"Collect passive facts", response.data)

        client_page = self.client.get(f"/clients/{self.identifier}")
        self.assertEqual(client_page.status_code, 200)
        self.assertIn(b"/static/js/host-facts.js", client_page.data)

    @patch("routes.host_facts.host_facts.passive_facts")
    @patch("app.save_runtime_state")
    @patch("app.record_social_audit")
    @patch("app.append_client_timeline_event")
    def test_passive_collection_persists_facts(
        self,
        timeline,
        audit,
        save_state,
        passive,
    ):
        passive.return_value = [
            host_facts.fact(
                "network.inferred_role",
                "Role",
                "Router",
                "Test",
                "high",
            )
        ]
        response = self.client.post(
            f"/clients/{self.identifier}/host-facts/collect",
            data={"csrf_token": self.csrf, "mode": "passive"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Collected 1 passive host fact", response.data)
        saved = app_module.find_inventory_device(self.identifier)
        self.assertEqual(
            saved["host_facts"][0]["key"],
            "network.inferred_role",
        )
        save_state.assert_called_once_with("host-facts:passive")
        timeline.assert_called_once()
        audit.assert_called_once()

    @patch("routes.host_facts.host_facts.safe_facts")
    @patch("app.fingerprint_client_services", return_value=[])
    @patch("app.save_runtime_state")
    @patch("app.record_social_audit")
    @patch("app.append_client_timeline_event")
    def test_safe_collection_requires_authorization(
        self,
        timeline,
        audit,
        save_state,
        fingerprints,
        safe,
    ):
        denied = self.client.post(
            f"/clients/{self.identifier}/host-facts/collect",
            data={"csrf_token": self.csrf, "mode": "safe"},
            follow_redirects=True,
        )
        self.assertIn(b"Confirm authorization", denied.data)
        safe.assert_not_called()

        safe.return_value = [
            host_facts.fact(
                "protocol.tls.443",
                "TLS",
                {"protocol": "TLSv1.3"},
                "Test",
                "high",
            )
        ]
        allowed = self.client.post(
            f"/clients/{self.identifier}/host-facts/collect",
            data={
                "csrf_token": self.csrf,
                "mode": "safe",
                "authorized": "on",
            },
            follow_redirects=True,
        )
        self.assertEqual(allowed.status_code, 200)
        safe.assert_called_once()

    @patch("app.save_runtime_state")
    @patch("app.record_social_audit")
    @patch("app.append_client_timeline_event")
    def test_baseline_and_export(self, timeline, audit, save_state):
        with app_module.device_inventory_lock:
            app_module.device_inventory[self.inventory_key]["host_facts"] = [
                host_facts.fact(
                    "identity.model",
                    "Model",
                    "XR1",
                    "Test",
                    "high",
                )
            ]
        response = self.client.post(
            f"/clients/{self.identifier}/host-facts/baseline",
            data={"csrf_token": self.csrf},
            follow_redirects=True,
        )
        self.assertIn(b"Host facts baseline saved", response.data)
        exported = self.client.get(
            f"/clients/{self.identifier}/host-facts.json"
        )
        self.assertEqual(exported.status_code, 200)
        payload = exported.get_json()
        self.assertEqual(
            payload["schema"],
            "mobile-router-host-facts-v1",
        )
        self.assertIsNotNone(payload["baseline"])

    def test_credential_reference_requires_csrf_and_does_not_store_secret(self):
        invalid = self.client.post(
            (
                f"/clients/{self.identifier}/host-facts/"
                "credential-references"
            ),
            data={
                "csrf_token": "wrong",
                "name": "Router SNMP",
                "kind": "snmp-v2c",
                "secretEnv": "TEST_ROUTER_SNMP",
            },
        )
        self.assertEqual(invalid.status_code, 400)

        with patch.dict(
            os.environ,
            {"TEST_ROUTER_SNMP": "super-secret"},
        ):
            valid = self.client.post(
                (
                    f"/clients/{self.identifier}/host-facts/"
                    "credential-references"
                ),
                data={
                    "csrf_token": self.csrf,
                    "name": "Router SNMP",
                    "kind": "snmp-v2c",
                    "secretEnv": "TEST_ROUTER_SNMP",
                },
                follow_redirects=True,
            )
        self.assertEqual(valid.status_code, 200)
        payload = json.loads(
            self.credential_path.read_text(encoding="utf-8")
        )
        self.assertEqual(
            payload["profiles"][0]["secret_env"],
            "TEST_ROUTER_SNMP",
        )
        self.assertNotIn(
            "super-secret",
            self.credential_path.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
