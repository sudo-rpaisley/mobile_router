import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as app_module
from app import app
from services import model_profiles


class ModelProfileServiceTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database = Path(self.tempdir.name) / "profiles.sqlite3"

    def tearDown(self):
        self.tempdir.cleanup()

    def create_profile(self, **overrides):
        values = {
            "manufacturer": "Sky",
            "model": "SR203",
            "scope": "exact",
            "aliases": ["Sky Broadband Hub"],
            "actor": "tester",
        }
        values.update(overrides)
        return model_profiles.upsert_profile(self.database, **values)

    def test_profile_hierarchy_and_alias_matching(self):
        manufacturer = self.create_profile(
            scope="manufacturer", model="", aliases=[], notes="Sky defaults"
        )
        family = self.create_profile(
            scope="family", model="", family="Sky Hub", aliases=[]
        )
        exact = self.create_profile()
        model_profiles.add_port_rule(
            self.database,
            profile_id=manufacturer["id"],
            port=53,
            protocol="udp",
            service="DNS forwarder",
            classification="expected",
        )
        model_profiles.add_port_rule(
            self.database,
            profile_id=family["id"],
            port=80,
            service="Family web redirect",
            classification="optional",
        )
        model_profiles.add_port_rule(
            self.database,
            profile_id=exact["id"],
            port=443,
            service="SR203 administration",
            classification="expected",
        )
        device = {
            "manufacturer": "Sky",
            "model": "Sky Broadband Hub",
            "model_family": "Sky Hub",
            "open_port_details": [
                {"port": 53, "protocol": "udp", "service": "Unknown"},
                {"port": 80, "protocol": "tcp", "service": "Unknown"},
                {"port": 443, "protocol": "tcp", "service": "Unknown"},
            ],
        }

        result = model_profiles.apply_device_profile(self.database, device)

        self.assertEqual([item["scope"] for item in result["profiles"]], [
            "manufacturer", "family", "exact"
        ])
        self.assertTrue(result["drift"]["matches_profile"])
        services = {item["port"]: item["service"] for item in result["device"]["open_port_details"]}
        self.assertEqual(services[443], "SR203 administration")

    def test_hardware_and_firmware_applicability(self):
        profile = self.create_profile(
            hardware_revision="B",
            firmware_min="7.00",
            firmware_max="7.09",
        )
        model_profiles.add_port_rule(
            self.database,
            profile_id=profile["id"],
            port=4567,
            service="ISP diagnostics",
            classification="firmware-specific",
            firmware_min="7.03",
            firmware_max="7.05",
        )
        matching = {
            "manufacturer": "Sky",
            "model": "SR203",
            "hardware_revision": "B",
            "firmware": "7.04.1",
            "open_port_details": [{"port": 4567, "protocol": "tcp"}],
        }
        outside = {**matching, "firmware": "8.00"}

        matched = model_profiles.apply_device_profile(self.database, matching)
        unmatched = model_profiles.apply_device_profile(self.database, outside)

        self.assertEqual(matched["primary_profile"]["id"], profile["id"])
        self.assertIsNone(unmatched["primary_profile"])

    def test_drift_and_device_override(self):
        profile = self.create_profile()
        model_profiles.add_port_rule(
            self.database,
            profile_id=profile["id"],
            port=443,
            service="Administration",
            classification="expected",
            risk="high",
            remediation="Restrict to the management network.",
        )
        device = {
            "manufacturer": "Sky",
            "model": "SR203",
            "open_port_details": [{"port": 51023, "protocol": "tcp", "service": "Unknown"}],
        }
        drifted = model_profiles.apply_device_profile(self.database, device)
        overridden = model_profiles.set_device_override(
            device,
            port=51023,
            service="Locally configured support service",
        )
        after_override = model_profiles.apply_device_profile(self.database, overridden)

        self.assertEqual(drifted["drift"]["unexpected"][0]["port"], 51023)
        self.assertEqual(drifted["drift"]["missing_expected"][0]["port"], 443)
        self.assertFalse(any(item["port"] == 51023 for item in after_override["drift"]["unexpected"]))

    def test_conflict_is_preserved_and_resolved(self):
        profile = self.create_profile()
        first = model_profiles.add_port_rule(
            self.database,
            profile_id=profile["id"],
            port=4567,
            service="TR-069 management",
            classification="expected",
            source_name="Source A",
        )
        conflict = model_profiles.add_port_rule(
            self.database,
            profile_id=profile["id"],
            port=4567,
            service="Sky diagnostics",
            classification="optional",
            source_name="Source B",
        )

        self.assertEqual(conflict["status"], "conflict")
        self.assertEqual(first["service"], "TR-069 management")
        resolved = model_profiles.resolve_conflict(
            self.database, conflict["conflict_id"], "incoming", actor="reviewer"
        )
        self.assertEqual(resolved["ports"][0]["service"], "Sky diagnostics")
        self.assertFalse(resolved["conflicts"])

    def test_revision_history_and_rollback(self):
        profile = self.create_profile(notes="Initial")
        model_profiles.add_port_rule(
            self.database,
            profile_id=profile["id"],
            port=80,
            service="Initial web service",
        )
        model_profiles.add_port_rule(
            self.database,
            profile_id=profile["id"],
            port=80,
            service="Changed web service",
            allow_replace=True,
        )
        history = model_profiles.revision_history(self.database, profile["id"])
        target = next(item for item in history if item["action"] == "port-rule-created")

        rolled_back = model_profiles.rollback(
            self.database, profile["id"], target["revision"], actor="reviewer"
        )

        self.assertEqual(rolled_back["ports"][0]["service"], "Initial web service")
        self.assertEqual(model_profiles.revision_history(self.database, profile["id"])[0]["action"], "profile-rollback")

    def test_signed_registry_round_trip_and_tamper_detection(self):
        profile = self.create_profile()
        model_profiles.add_port_rule(
            self.database,
            profile_id=profile["id"],
            port=443,
            service="Administration",
        )
        payload = model_profiles.export_registry(
            self.database,
            publisher="test-publisher",
            version="1.0.0",
            signing_key="secret",
        )
        verified = model_profiles.verify_registry(
            payload,
            trusted={"test-publisher": "secret"},
            require_signature=True,
        )
        target = Path(self.tempdir.name) / "imported.sqlite3"
        imported = model_profiles.import_registry(
            target,
            payload,
            trusted={"test-publisher": "secret"},
            require_signature=True,
        )

        self.assertEqual(verified["signature_status"], "verified")
        self.assertEqual(imported["imported"], 1)
        payload["profiles"][0]["model"] = "Tampered"
        with self.assertRaisesRegex(ValueError, "digest"):
            model_profiles.verify_registry(
                payload,
                trusted={"test-publisher": "secret"},
                require_signature=True,
            )

    def test_fleet_summary_and_privacy_clean_contribution(self):
        profile = self.create_profile()
        model_profiles.add_port_rule(
            self.database,
            profile_id=profile["id"],
            port=443,
            service="Administration",
        )
        inventory = [
            {
                "id": "private-id",
                "ip": "192.168.1.1",
                "mac": "aa:bb:cc:dd:ee:ff",
                "hostname": "private-router",
                "manufacturer": "Sky",
                "model": "SR203",
                "firmware": "7.04",
                "open_port_details": [{"port": 443, "protocol": "tcp"}],
            }
        ]
        fleet = model_profiles.fleet_summary(self.database, inventory, profile["id"])
        contribution = model_profiles.contribution_payload(
            self.database, profile["id"], inventory
        )
        serialized = json.dumps(contribution)

        self.assertEqual(fleet["device_count"], 1)
        self.assertNotIn("192.168.1.1", serialized)
        self.assertNotIn("aa:bb:cc:dd:ee:ff", serialized)
        self.assertNotIn("private-router", serialized)


class ModelProfileRouteTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database = Path(self.tempdir.name) / "route.sqlite3"
        self.path_patch = patch(
            "routes.model_profiles._database_path", return_value=self.database
        )
        self.path_patch.start()
        app_module.device_inventory.clear()
        app_module.social_users.clear()
        app_module.social_users["test-admin"] = {
            "id": "test-admin",
            "username": "test-admin",
            "role": "admin",
            "password_hash": "unused",
        }
        app_module.device_inventory["ip:192.168.1.1"] = {
            "id": "ip:192.168.1.1",
            "ip": "192.168.1.1",
            "mac": "aa:bb:cc:dd:ee:ff",
            "manufacturer": "Sky",
            "model": "SR203",
            "open_port_details": [{"port": 443, "protocol": "tcp", "service": "Unknown"}],
            "interfaces": ["eth0"],
        }
        self.client = app.test_client()
        self.csrf = "model-profile-csrf"
        with self.client.session_transaction() as flask_session:
            flask_session["social_user"] = {
                "username": "test-admin",
                "role": "admin",
            }
            flask_session["social_csrf_token"] = self.csrf

    def tearDown(self):
        self.path_patch.stop()
        app_module.device_inventory.clear()
        app_module.social_users.clear()
        self.tempdir.cleanup()

    def post(self, url, data=None):
        return self.client.post(url, data={"csrf_token": self.csrf, **(data or {})})

    def test_library_pages_and_profile_crud(self):
        page = self.client.get("/models")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Device Model Library", page.data)

        created = self.post(
            "/api/model-profiles",
            {
                "manufacturer": "Sky",
                "model": "SR203",
                "scope": "exact",
                "aliases": "Sky Broadband Hub",
            },
        )
        self.assertEqual(created.status_code, 200)
        profile_id = created.get_json()["profile"]["id"]
        detail_page = self.client.get(f"/models/{profile_id}")
        self.assertEqual(detail_page.status_code, 200)
        self.assertIn(b"Port and Service Rules", detail_page.data)

        rule = self.post(
            f"/api/model-profiles/{profile_id}/ports",
            {
                "port": "443",
                "protocol": "tcp",
                "service": "Sky administration",
                "classification": "expected",
                "risk": "high",
            },
        )
        self.assertEqual(rule.status_code, 200)
        self.assertEqual(rule.get_json()["profile"]["ports"][0]["port"], 443)

    def test_client_profile_apply_and_manual_override(self):
        profile = model_profiles.upsert_profile(
            self.database,
            manufacturer="Sky",
            model="SR203",
            actor="test",
        )
        model_profiles.add_port_rule(
            self.database,
            profile_id=profile["id"],
            port=443,
            service="Sky administration",
            classification="expected",
        )
        loaded = self.client.get("/clients/192.168.1.1/model-profile")
        self.assertEqual(loaded.status_code, 200)
        self.assertTrue(loaded.get_json()["result"]["drift"]["matches_profile"])

        overridden = self.post(
            "/clients/192.168.1.1/model-profile/override",
            {
                "port": "51023",
                "protocol": "tcp",
                "service": "Local support service",
                "classification": "local-configuration",
            },
        )
        self.assertEqual(overridden.status_code, 200)
        self.assertEqual(
            app_module.device_inventory["ip:192.168.1.1"]["model_port_overrides"][0]["port"],
            51023,
        )

    def test_registry_preview_and_ui_script(self):
        profile = model_profiles.upsert_profile(
            self.database,
            manufacturer="Sky",
            model="SR203",
        )
        payload = model_profiles.export_registry(
            self.database,
            publisher="test-publisher",
            signing_key="secret",
        )
        with patch.dict(
            os.environ,
            {"MOBILE_ROUTER_MODEL_REGISTRY_KEYS": json.dumps({"test-publisher": "secret"})},
        ):
            preview = self.post(
                "/api/model-registry/preview",
                {"registryJson": json.dumps(payload), "requireSignature": "on"},
            )
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.get_json()["verification"]["profile_count"], 1)

        client_page = self.client.get("/clients/192.168.1.1")
        self.assertEqual(client_page.status_code, 200)
        self.assertIn(b"model-profiles.js", client_page.data)
        self.assertTrue(profile["id"])


if __name__ == "__main__":
    unittest.main()
