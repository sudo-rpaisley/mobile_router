import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import app as app_module
from app import app
from services.deauth_control import (
    BoundedDeauthController,
    validate_start_request,
)


class BoundedDeauthControllerTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.marker = root / "active.json"
        self.flag = root / "stop.flag"

    def tearDown(self):
        self.tempdir.cleanup()

    def make_controller(self, **overrides):
        options = {
            "max_run_seconds": 0.25,
            "heartbeat_grace_seconds": 0.08,
            "send_interval_seconds": 0.01,
            "active_marker": self.marker,
            "emergency_flag": self.flag,
        }
        options.update(overrides)
        return BoundedDeauthController(**options)

    def wait_inactive(self, controller, timeout=1.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = controller.status()
            if not status["active"]:
                return status
            time.sleep(0.01)
        self.fail("Bounded deauth controller did not stop")

    def test_startup_cleanup_fails_closed_and_removes_stale_marker(self):
        self.marker.parent.mkdir(parents=True, exist_ok=True)
        self.marker.write_text('{"id": "stale"}', encoding="utf-8")
        controller = self.make_controller()

        self.assertFalse(self.marker.exists())
        self.assertTrue(self.flag.exists())
        self.assertFalse(controller.status()["active"])

    def test_manual_stop_ends_active_job(self):
        controller = self.make_controller()
        sent = []
        job = controller.start(
            ap_mac="aa:bb:cc:dd:ee:ff",
            target_mac="11:22:33:44:55:66",
            interface="wlan0mon",
            operator="admin",
            send_frame=lambda: sent.append(time.time()),
        )
        self.assertTrue(job["active"])
        deadline = time.time() + 0.1
        while time.time() < deadline and not sent:
            time.sleep(0.005)
        controller.stop(job["id"], "manual_stop")
        stopped = self.wait_inactive(controller)

        self.assertEqual(stopped["stop_reason"], "manual_stop")
        self.assertGreaterEqual(stopped["frames_sent"], 1)
        self.assertFalse(self.marker.exists())

    def test_missing_heartbeat_stops_job(self):
        controller = self.make_controller()
        controller.start(
            ap_mac="aa:bb:cc:dd:ee:ff",
            target_mac="11:22:33:44:55:66",
            interface="wlan0mon",
            operator="admin",
            send_frame=lambda: None,
        )

        stopped = self.wait_inactive(controller)
        self.assertEqual(stopped["stop_reason"], "heartbeat_timeout")

    def test_hard_deadline_cannot_be_renewed_by_heartbeats(self):
        controller = self.make_controller(
            max_run_seconds=0.12,
            heartbeat_grace_seconds=0.06,
        )
        job = controller.start(
            ap_mac="aa:bb:cc:dd:ee:ff",
            target_mac="11:22:33:44:55:66",
            interface="wlan0mon",
            operator="admin",
            send_frame=lambda: None,
        )

        deadline = time.time() + 0.3
        while time.time() < deadline and controller.status()["active"]:
            try:
                controller.heartbeat(job["id"])
            except ValueError:
                break
            time.sleep(0.02)

        stopped = self.wait_inactive(controller)
        self.assertEqual(stopped["stop_reason"], "hard_timeout")

    def test_emergency_stop_flag_ends_job(self):
        controller = self.make_controller()
        controller.start(
            ap_mac="aa:bb:cc:dd:ee:ff",
            target_mac="11:22:33:44:55:66",
            interface="wlan0mon",
            operator="admin",
            send_frame=lambda: None,
        )
        controller.emergency_stop()

        stopped = self.wait_inactive(controller)
        self.assertEqual(stopped["stop_reason"], "emergency_stop")
        self.assertTrue(self.flag.exists())

    def test_start_request_keeps_authorization_and_ap_checks(self):
        normalize = lambda value: str(value or "").lower() or None
        ap, target = validate_start_request(
            {
                "ap": "AA:BB:CC:DD:EE:FF",
                "target": "",
                "authorized": "on",
            },
            normalize,
        )
        self.assertEqual(ap, "aa:bb:cc:dd:ee:ff")
        self.assertEqual(target, "ff:ff:ff:ff:ff:ff")

        with self.assertRaisesRegex(ValueError, "authorized isolated"):
            validate_start_request(
                {"ap": "aa:bb:cc:dd:ee:ff", "authorized": ""},
                normalize,
            )


class DeauthControlRouteTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        app_module.social_users.clear()
        app_module.social_users["test-admin"] = {
            "id": "test-admin",
            "username": "test-admin",
            "role": "admin",
            "password_hash": "unused",
        }
        self.csrf = "deauth-test-csrf"
        with self.client.session_transaction() as flask_session:
            flask_session["social_user"] = {
                "username": "test-admin",
                "role": "admin",
            }
            flask_session["social_csrf_token"] = self.csrf

    def test_red_team_uses_start_stop_controller_not_frame_input(self):
        response = self.client.get("/red-team")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="Deauth-Start"', response.data)
        self.assertIn(b'id="Deauth-Stop"', response.data)
        self.assertIn(b"deauth-control.js", response.data)
        self.assertNotIn(b'id="Deauth-Frames"', response.data)

    @patch("services.deauth_control.start_deauth")
    def test_start_route_is_admin_csrf_protected_and_returns_job(self, start):
        start.return_value = {
            "active": True,
            "id": "job-1",
            "status": "running",
            "hard_deadline": time.time() + 15,
        }

        response = self.client.post(
            "/deauth/start",
            data={
                "ap": "aa:bb:cc:dd:ee:ff",
                "target": "11:22:33:44:55:66",
                "authorized": "on",
                "selectedInterface": "wlan0mon",
                "csrf_token": self.csrf,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["job"]["id"], "job-1")
        start.assert_called_once()

        bad_csrf = self.client.post(
            "/deauth/start",
            data={
                "ap": "aa:bb:cc:dd:ee:ff",
                "authorized": "on",
                "selectedInterface": "wlan0mon",
                "csrf_token": "wrong",
            },
        )
        self.assertEqual(bad_csrf.status_code, 400)

    @patch("services.deauth_control.emergency_stop_deauth")
    def test_emergency_stop_route(self, emergency_stop):
        emergency_stop.return_value = {
            "active": False,
            "id": "job-1",
            "status": "stopped",
            "stop_reason": "web_emergency_stop",
        }

        response = self.client.post(
            "/deauth/emergency-stop",
            data={"csrf_token": self.csrf},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["job"]["stop_reason"],
            "web_emergency_stop",
        )


if __name__ == "__main__":
    unittest.main()
