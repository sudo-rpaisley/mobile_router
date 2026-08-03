import unittest
from unittest.mock import patch

import app as app_module
from app import app
from services import service_records


class ServiceRecordServiceTest(unittest.TestCase):
    def test_manual_override_survives_refreshed_scan_evidence(self):
        device = {
            "id": "ip:192.0.2.45",
            "ip": "192.0.2.45",
            "open_port_details": [
                {
                    "port": 5555,
                    "protocol": "tcp",
                    "service": "Unknown",
                    "description": "No common service mapping found",
                }
            ],
        }
        edited = service_records.update_override(
            device,
            port=5555,
            protocol="tcp",
            service="Sky diagnostics",
            description="Router diagnostics service",
            notes="Confirmed from the vendor support page.",
            source_name="Sky support",
            source_url="https://example.com/sky-router",
            updated_by="test-admin",
        )
        self.assertEqual(edited["open_port_details"][0]["service"], "Sky diagnostics")
        self.assertEqual(edited["open_port_details"][0]["detected_service"], "Unknown")

        rescanned = {
            **edited,
            "open_port_details": [
                {
                    "port": 5555,
                    "protocol": "tcp",
                    "service": "Unknown",
                    "description": "No common service mapping found",
                    "banner": "fresh scan evidence",
                }
            ],
        }
        reapplied = service_records.apply_overrides(rescanned)

        detail = reapplied["open_port_details"][0]
        self.assertEqual(detail["service"], "Sky diagnostics")
        self.assertEqual(detail["detected_service"], "Unknown")
        self.assertEqual(detail["banner"], "fresh scan evidence")
        self.assertTrue(detail["service_manual_override"])

    def test_removing_override_restores_detected_value(self):
        device = {
            "open_port_details": [
                {"port": 8443, "protocol": "tcp", "service": "HTTPS alternate"}
            ]
        }
        edited = service_records.update_override(
            device,
            port=8443,
            service="Router management",
            updated_by="test-admin",
        )
        cleared = service_records.update_override(
            edited,
            port=8443,
            clear=True,
        )

        self.assertEqual(cleared["open_port_details"][0]["service"], "HTTPS alternate")
        self.assertFalse(cleared["open_port_details"][0].get("service_manual_override"))
        self.assertEqual(cleared.get("service_record_overrides"), [])

    def test_source_url_rejects_credentials(self):
        with self.assertRaisesRegex(ValueError, "must not contain credentials"):
            service_records.valid_source_url("https://user:pass@example.com/reference")


class ServiceRecordRouteTest(unittest.TestCase):
    identifier = "192.0.2.45"
    inventory_key = "ip:192.0.2.45"

    def setUp(self):
        self.client = app.test_client()
        self.previous_users = dict(app_module.social_users)
        app_module.social_users.clear()
        app_module.social_users["test-admin"] = {
            "id": "test-admin",
            "username": "test-admin",
            "role": "admin",
            "password_hash": "unused",
        }
        with app_module.device_inventory_lock:
            self.previous_device = app_module.device_inventory.pop(self.inventory_key, None)
            app_module.device_inventory[self.inventory_key] = {
                "id": self.inventory_key,
                "ip": self.identifier,
                "mac": "aa:bb:cc:dd:ee:ff",
                "manufacturer": "Sky",
                "model": "SR203",
                "model_profile_id": 12,
                "open_ports": [5555],
                "open_port_details": [
                    {
                        "port": 5555,
                        "protocol": "tcp",
                        "service": "Unknown",
                        "description": "No common service mapping found",
                    }
                ],
            }
        self.csrf = "service-record-csrf"
        with self.client.session_transaction() as flask_session:
            flask_session["social_user"] = {
                "username": "test-admin",
                "role": "admin",
            }
            flask_session["social_csrf_token"] = self.csrf

    def tearDown(self):
        with app_module.device_inventory_lock:
            app_module.device_inventory.pop(self.inventory_key, None)
            if self.previous_device is not None:
                app_module.device_inventory[self.inventory_key] = self.previous_device
        app_module.social_users.clear()
        app_module.social_users.update(self.previous_users)

    def test_saved_service_card_destination_contains_editor(self):
        response = self.client.get(
            f"/clients/{self.identifier}/services/5555"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"data-saved-service-editor", response.data)
        self.assertIn(b"Save service record", response.data)
        self.assertIn(b"Reuse this mapping for the matched device model", response.data)

    @patch("app.save_runtime_state")
    @patch("app.record_social_audit")
    @patch("app.append_client_timeline_event")
    def test_post_updates_device_record(self, timeline, audit, save_state):
        response = self.client.post(
            f"/clients/{self.identifier}/services/5555",
            data={
                "csrf_token": self.csrf,
                "protocol": "tcp",
                "service": "Sky diagnostics",
                "description": "Router diagnostics service",
                "notes": "Confirmed in an authorised lab.",
                "sourceName": "Sky support",
                "sourceUrl": "https://example.com/sky-router",
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Saved service record updated", response.data)
        saved = app_module.find_inventory_device(self.identifier)
        self.assertEqual(saved["open_port_details"][0]["service"], "Sky diagnostics")
        self.assertTrue(saved["open_port_details"][0]["service_manual_override"])
        self.assertEqual(saved["service_record_overrides"][0]["source_name"], "Sky support")
        timeline.assert_called_once()
        audit.assert_called_once()
        save_state.assert_called_once_with("saved-service-record")

    @patch("routes.service_records.model_profiles.add_port_rule")
    @patch("app.save_runtime_state")
    @patch("app.record_social_audit")
    @patch("app.append_client_timeline_event")
    def test_can_publish_edit_to_matched_model_profile(
        self, timeline, audit, save_state, add_port_rule
    ):
        add_port_rule.return_value = {"id": 99, "service": "Sky diagnostics"}

        response = self.client.post(
            f"/clients/{self.identifier}/services/5555",
            data={
                "csrf_token": self.csrf,
                "protocol": "tcp",
                "service": "Sky diagnostics",
                "description": "Router diagnostics service",
                "applyToModel": "on",
                "classification": "optional",
                "exposure": "lan-only",
                "risk": "low",
                "sourceReliability": "80",
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"also saved to the matched device-model profile", response.data)
        kwargs = add_port_rule.call_args.kwargs
        self.assertEqual(kwargs["profile_id"], 12)
        self.assertEqual(kwargs["port"], 5555)
        self.assertEqual(kwargs["classification"], "optional")
        self.assertEqual(kwargs["exposure"], "lan-only")

    def test_post_requires_valid_csrf(self):
        response = self.client.post(
            f"/clients/{self.identifier}/services/5555",
            data={
                "csrf_token": "wrong",
                "service": "Sky diagnostics",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid or expired", response.get_json()["message"])


if __name__ == "__main__":
    unittest.main()
