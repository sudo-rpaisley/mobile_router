import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

import app as app_module
from app import app
from services import vlan_investigations as vlan_service


class VlanInvestigationServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobile-router-vlan-")
        self.database = Path(self.temp_dir) / "vlans.sqlite3"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=False)

    def save_vlan(self, **overrides):
        payload = {
            "name": "Users",
            "tag": "20",
            "subnet": "192.168.20.0/24",
            "gateway": "192.168.20.1",
            "interface_name": "igb1.20",
            "router_name": "pfSense",
            "probe_mode": "routed",
            **overrides,
        }
        return vlan_service.save_vlan(self.database, payload)

    def test_vlan_validation_and_device_decoration(self):
        vlan = self.save_vlan()

        self.assertEqual(vlan["label"], "VLAN 20 · Users")
        self.assertEqual(vlan["usable_hosts"], 254)
        decorated = vlan_service.decorate_device(
            self.database,
            {"ip": "192.168.20.42", "name": "Laptop"},
        )
        self.assertEqual(decorated["vlan_id"], vlan["id"])
        self.assertEqual(decorated["vlan_tag"], 20)
        self.assertEqual(decorated["vlan_assignment_source"], "subnet-match")
        self.assertEqual(decorated["vlan_confidence"], "high")

    def test_vlan_rejects_invalid_tags_gateways_and_overlaps(self):
        self.save_vlan()
        with self.assertRaisesRegex(ValueError, "1 to 4094"):
            self.save_vlan(name="Invalid tag", tag="4095", subnet="192.168.30.0/24", gateway="192.168.30.1")
        with self.assertRaisesRegex(ValueError, "inside the VLAN subnet"):
            self.save_vlan(name="Wrong gateway", tag="30", subnet="192.168.30.0/24", gateway="192.168.40.1")
        with self.assertRaisesRegex(ValueError, "overlaps existing VLAN"):
            self.save_vlan(name="Overlap", tag="21", subnet="192.168.20.128/25", gateway="192.168.20.129")

    def test_bounded_investigation_limits_hosts_and_ports(self):
        network = vlan_service.bounded_investigation_network("10.10.0.0/22")
        self.assertEqual(network.prefixlen, 22)
        with self.assertRaisesRegex(ValueError, "safety limit"):
            vlan_service.bounded_investigation_network("10.10.0.0/21")
        self.assertEqual(vlan_service.parse_ports("22, 443, 22"), [22, 443])
        with self.assertRaisesRegex(ValueError, "At most 16"):
            vlan_service.parse_ports(",".join(str(port) for port in range(1, 18)))

    def test_investigations_and_segmentation_results_are_persisted(self):
        source = self.save_vlan()
        destination = vlan_service.save_vlan(
            self.database,
            {
                "name": "Servers",
                "tag": "40",
                "subnet": "192.168.40.0/24",
                "gateway": "192.168.40.1",
            },
        )
        investigation = vlan_service.save_investigation(
            self.database,
            source["id"],
            "routed",
            "complete",
            {"scan_path_context": "via 192.168.20.1"},
            [{"host": "192.168.20.10", "reachable": True}],
            {"total_hosts": 254, "reachable_hosts": 1},
        )
        self.assertEqual(investigation["summary"]["reachable_hosts"], 1)
        rule = vlan_service.save_segmentation_rule(
            self.database,
            {
                "source_vlan_id": source["id"],
                "destination_vlan_id": destination["id"],
                "destination": "192.168.40.10",
                "protocol": "tcp",
                "port": "22",
                "expectation": "block",
            },
        )
        result = vlan_service.record_segmentation_result(
            self.database,
            rule["id"],
            "allow",
            "main-host routed perspective",
            "Connection accepted",
            4.2,
        )
        self.assertTrue(result["mismatch"])
        matrix = vlan_service.segmentation_matrix(self.database)
        self.assertEqual(matrix[0]["source_vlan"]["label"], "VLAN 20 · Users")
        self.assertEqual(matrix[0]["destination_vlan"]["label"], "VLAN 40 · Servers")
        self.assertTrue(matrix[0]["latest_result"]["mismatch"])

    def test_pfsense_payload_normalises_vlan_and_device_records(self):
        parsed = vlan_service.parse_pfsense_payload(
            {
                "hostname": "cornelius-pfsense",
                "vlans": [
                    {
                        "tag": 50,
                        "name": "IoT",
                        "subnet": "10.50.0.0/24",
                        "gateway": "10.50.0.1",
                        "interface": "igb2.50",
                    }
                ],
                "leases": [
                    {
                        "ip": "10.50.0.20",
                        "mac": "aa:bb:cc:dd:ee:20",
                        "hostname": "lamp",
                        "vlan": 50,
                    }
                ],
                "arp_table": [
                    {
                        "ip": "10.50.0.21",
                        "mac": "aa:bb:cc:dd:ee:21",
                    }
                ],
            }
        )
        self.assertEqual(parsed["vlans"][0]["tag"], 50)
        self.assertEqual(parsed["vlans"][0]["subnet"], "10.50.0.0/24")
        self.assertEqual(parsed["devices"][0]["hostname"], "lamp")
        self.assertEqual(len(parsed["devices"]), 2)

    def test_integration_stores_environment_reference_not_secret(self):
        os.environ["MOBILE_ROUTER_TEST_PFSENSE_TOKEN"] = "secret-token"
        self.addCleanup(os.environ.pop, "MOBILE_ROUTER_TEST_PFSENSE_TOKEN", None)
        integration = vlan_service.save_integration(
            self.database,
            {
                "name": "Lab pfSense",
                "base_url": "https://192.168.10.1",
                "token_env": "MOBILE_ROUTER_TEST_PFSENSE_TOKEN",
                "verify_tls": "on",
            },
        )
        self.assertEqual(integration["token_env"], "MOBILE_ROUTER_TEST_PFSENSE_TOKEN")
        self.assertTrue(integration["token_configured"])
        self.assertNotIn("secret-token", json.dumps(integration))
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            vlan_service.save_integration(
                self.database,
                {"name": "Unsafe", "base_url": "http://192.168.10.1"},
            )

    def test_remote_probe_signature_timestamp_and_replay_protection(self):
        vlan = self.save_vlan()
        secret_env = "MOBILE_ROUTER_TEST_VLAN_PROBE_KEY"
        os.environ[secret_env] = "test-probe-secret"
        self.addCleanup(os.environ.pop, secret_env, None)
        probe = vlan_service.save_remote_probe(
            self.database,
            {"name": "Users probe", "vlan_id": vlan["id"], "secret_env": secret_env},
        )
        body = json.dumps({"devices": [{"ip": "192.168.20.44"}]}).encode("utf-8")
        timestamp = int(time.time())
        nonce = "nonce-12345678"
        signature = vlan_service.probe_signature(
            os.environ[secret_env], timestamp, nonce, body
        )
        verified_probe, payload = vlan_service.verify_probe_submission(
            self.database,
            probe["id"],
            body,
            timestamp,
            nonce,
            signature,
            now=timestamp,
        )
        self.assertEqual(verified_probe["id"], probe["id"])
        self.assertEqual(payload["devices"][0]["ip"], "192.168.20.44")
        with self.assertRaisesRegex(ValueError, "already been used"):
            vlan_service.verify_probe_submission(
                self.database,
                probe["id"],
                body,
                timestamp,
                nonce,
                signature,
                now=timestamp,
            )
        with self.assertRaisesRegex(ValueError, "five-minute"):
            vlan_service.verify_probe_submission(
                self.database,
                probe["id"],
                body,
                timestamp - 1000,
                "another-nonce-1234",
                vlan_service.probe_signature(
                    os.environ[secret_env], timestamp - 1000, "another-nonce-1234", body
                ),
                now=timestamp,
            )


class VlanInvestigationRouteTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobile-router-vlan-route-")
        self.original_instance_path = app.instance_path
        app.instance_path = self.temp_dir
        self.client = app.test_client()
        self.inventory_backup = dict(app_module.device_inventory)
        self.users_backup = dict(app_module.social_users)
        app_module.device_inventory.clear()
        app_module.social_users.clear()
        app_module.social_users["vlan-admin"] = {
            "id": "vlan-admin",
            "username": "vlan-admin",
            "role": "admin",
            "password_hash": "unused",
        }
        with self.client.session_transaction() as flask_session:
            flask_session["social_user"] = {"username": "vlan-admin", "role": "admin"}
            flask_session["social_csrf_token"] = "vlan-csrf"

    def tearDown(self):
        app.instance_path = self.original_instance_path
        app_module.device_inventory.clear()
        app_module.device_inventory.update(self.inventory_backup)
        app_module.social_users.clear()
        app_module.social_users.update(self.users_backup)
        shutil.rmtree(self.temp_dir, ignore_errors=False)

    def create_vlan(self, name="Users", tag="20", subnet="192.168.20.0/24"):
        response = self.client.post(
            "/vlans",
            data={
                "name": name,
                "tag": tag,
                "subnet": subnet,
                "gateway": str(next(__import__("ipaddress").ip_network(subnet).hosts())),
                "probe_mode": "routed",
                "csrf_token": "vlan-csrf",
            },
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()["vlan"]

    def test_vlan_page_requires_login_and_writes_require_csrf(self):
        with self.client.session_transaction() as flask_session:
            flask_session.pop("social_user", None)
        self.assertEqual(self.client.get("/vlans").status_code, 401)
        with self.client.session_transaction() as flask_session:
            flask_session["social_user"] = {"username": "vlan-admin", "role": "admin"}
        response = self.client.post(
            "/vlans",
            data={"name": "Users", "tag": "20", "subnet": "192.168.20.0/24"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("CSRF", response.get_json()["message"])

    def test_vlan_tag_is_prominent_in_library_inventory_client_and_network_workspace(self):
        vlan = self.create_vlan()
        app_module.record_inventory_devices(
            [{"ip": "192.168.20.44", "mac": "00:11:22:33:44:55", "name": "Workstation"}],
            "test-scan",
            "eth0",
        )

        library = self.client.get("/vlans")
        inventory = self.client.get("/inventory")
        client_page = self.client.get("/clients/192.168.20.44")
        network_panel = self.client.get("/clients/192.168.20.44/workspace/network")
        lookup = self.client.get("/api/v1/vlans/lookup?ips=192.168.20.44")

        self.assertIn(b"VLAN 20 \xc2\xb7 Users", library.data)
        self.assertIn(b"VLAN 20 \xc2\xb7 Users", inventory.data)
        self.assertIn(b"VLAN 20 \xc2\xb7 Users", client_page.data)
        self.assertIn(b"VLAN 20 \xc2\xb7 Users", network_panel.data)
        self.assertEqual(lookup.status_code, 200)
        self.assertEqual(lookup.get_json()["vlans"]["192.168.20.44"]["id"], vlan["id"])
        device = app_module.find_inventory_device("192.168.20.44")
        self.assertEqual(device["vlan_tag"], 20)
        self.assertEqual(device["vlan_name"], "Users")

    @patch("routes.vlan_investigations._routed_investigation")
    def test_authorised_routed_investigation_is_saved(self, investigate):
        vlan = self.create_vlan()
        investigate.return_value = (
            {"scan_path_context": "via 192.168.20.1"},
            [{"host": "192.168.20.44", "reachable": True}],
            {
                "total_hosts": 254,
                "reachable_hosts": 1,
                "unreachable_hosts": 253,
                "selected_ports": [22, 443],
                "recorded_devices": 1,
                "visibility": "routed",
                "duration_seconds": 0.1,
            },
        )
        response = self.client.post(
            f"/vlans/{vlan['id']}/investigate",
            data={
                "ports": "22,443",
                "authorised": "on",
                "csrf_token": "vlan-csrf",
            },
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()["investigation"]
        self.assertEqual(payload["summary"]["reachable_hosts"], 1)
        investigate.assert_called_once()

    def test_pfsense_json_import_creates_vlan_and_assigns_device(self):
        payload = {
            "hostname": "pfSense",
            "vlans": [
                {
                    "tag": 50,
                    "name": "IoT",
                    "subnet": "10.50.0.0/24",
                    "gateway": "10.50.0.1",
                    "interface": "igb2.50",
                }
            ],
            "leases": [
                {
                    "ip": "10.50.0.20",
                    "mac": "aa:bb:cc:dd:ee:20",
                    "hostname": "lamp",
                    "vlan": 50,
                }
            ],
        }
        response = self.client.post(
            "/vlans/pfsense/import",
            data={
                "csrf_token": "vlan-csrf",
                "pfsense_file": (io.BytesIO(json.dumps(payload).encode("utf-8")), "pfsense.json"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["vlans"][0]["label"], "VLAN 50 · IoT")
        device = app_module.find_inventory_device("10.50.0.20")
        self.assertEqual(device["vlan_tag"], 50)
        self.assertEqual(device["vlan_label"], "VLAN 50 · IoT")


class VlanInvestigationAssetTest(unittest.TestCase):
    def test_navigation_templates_and_dynamic_assets_include_vlan_support(self):
        navigation = Path("app_support/navigation.py").read_text(encoding="utf-8")
        primary = Path("templates/_primary-nav-links.html").read_text(encoding="utf-8")
        footer = Path("templates/_footer.html").read_text(encoding="utf-8")
        inventory = Path("templates/inventory.html").read_text(encoding="utf-8")
        network = Path("templates/client_workspace/_network.html").read_text(encoding="utf-8")
        script = Path("static/js/vlan-tags.js").read_text(encoding="utf-8")

        self.assertIn("VLAN Investigations", navigation)
        self.assertIn('href="/vlans"', primary)
        self.assertIn("vlan-tags.js", footer)
        self.assertIn("Network / VLAN", inventory)
        self.assertIn("Open this VLAN investigation", network)
        self.assertIn("MutationObserver", script)
        self.assertIn("data-network-device-card", script)
        self.assertIn("data-device-workspace", script)

    def test_vlan_javascript_parses_when_node_is_available(self):
        node = shutil.which("node")
        if not node:
            return
        for path in ("static/js/vlans.js", "static/js/vlan-tags.js"):
            result = subprocess.run(
                [node, "--check", path],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, f"{path}: {result.stderr}")


if __name__ == "__main__":
    unittest.main()
