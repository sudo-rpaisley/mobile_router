import shutil
import subprocess
import time
import unittest
from pathlib import Path

import app as app_module
from app import app


class DeviceWorkspaceRouteTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.inventory_backup = dict(app_module.device_inventory)
        self.timelines_backup = dict(app_module.client_timelines)
        self.users_backup = dict(app_module.social_users)
        app_module.device_inventory.clear()
        app_module.client_timelines.clear()
        app_module.social_users.clear()
        app_module.social_users["workspace-admin"] = {
            "id": "workspace-admin",
            "username": "workspace-admin",
            "role": "admin",
            "password_hash": "unused",
        }
        self.host = "192.0.2.40"
        app_module.device_inventory[f"ip:{self.host}"] = {
            "id": f"ip:{self.host}",
            "ip": self.host,
            "mac": "00:11:22:33:44:55",
            "name": "Test router",
            "display_name": "Test router",
            "manufacturer": "Example Networks",
            "model": "XR-1",
            "sources": ["active-scan", "mdns"],
            "interfaces": ["eth0"],
            "open_ports": [22, 443],
            "open_port_details": [
                {"port": 22, "service": "SSH", "description": "Secure shell"},
                {"port": 443, "service": "HTTPS", "description": "Web administration"},
            ],
            "expected_open_ports": [22, 443],
            "last_port_scan": time.time(),
            "last_seen": time.time(),
            "device_role_guess": {"role": "Gateway/router", "confidence": "high"},
            "observed_names": [{"name": "test-router.local", "source": "mDNS"}],
            "identity_assessment": {
                "label": "Example XR-1 router",
                "confidence": "high",
                "evidence": ["Model and service combination matched"],
            },
            "host_facts": [],
        }
        app_module.client_timelines[self.host] = [
            {
                "time": time.time(),
                "time_label": "2026-08-03 12:00:00",
                "type": "Port scan",
                "message": "Saved two open services.",
                "source": "test",
            }
        ]
        with self.client.session_transaction() as flask_session:
            flask_session["social_user"] = {
                "username": "workspace-admin",
                "role": "admin",
            }
            flask_session["social_csrf_token"] = "workspace-csrf"

    def tearDown(self):
        app_module.device_inventory.clear()
        app_module.device_inventory.update(self.inventory_backup)
        app_module.client_timelines.clear()
        app_module.client_timelines.update(self.timelines_backup)
        app_module.social_users.clear()
        app_module.social_users.update(self.users_backup)

    def test_client_page_has_six_stable_workspaces_and_lazy_panels(self):
        response = self.client.get(f"/clients/{self.host}")

        self.assertEqual(response.status_code, 200)
        for name in (b"Overview", b"Identity", b"Network", b"Services", b"Security", b"History"):
            self.assertIn(name, response.data)
        self.assertIn(b'data-long-page-disabled', response.data)
        self.assertIn(b'data-device-workspace', response.data)
        self.assertIn(b'data-workspace-url="/clients/192.0.2.40/workspace/services"', response.data)
        self.assertIn(b'Device overview', response.data)
        self.assertIn(b'Device identity and metadata', response.data)
        self.assertNotIn(b'Saved service profile', response.data)
        self.assertIn(b'device-workspace.js', response.data)

    def test_services_workspace_is_rendered_on_demand(self):
        response = self.client.get(f"/clients/{self.host}/workspace/services")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Saved service profile', response.data)
        self.assertIn(b'Device port scan', response.data)
        self.assertIn(b'22/tcp', response.data)
        self.assertIn(b'443/tcp', response.data)

    def test_security_and_history_workspaces_render_fresh_data(self):
        security = self.client.get(f"/clients/{self.host}/workspace/security")
        history = self.client.get(f"/clients/{self.host}/workspace/history")

        self.assertEqual(security.status_code, 200)
        self.assertIn(b'Security posture and drift', security.data)
        self.assertIn(b'Service baseline drift', security.data)
        self.assertEqual(history.status_code, 200)
        self.assertIn(b'Timeline, reachability, and exports', history.data)
        self.assertIn(b'Saved two open services', history.data)


class DeviceWorkspaceAssetTest(unittest.TestCase):
    def test_workspace_assets_cover_lazy_loading_and_unsaved_changes(self):
        script = Path("static/js/device-workspace.js").read_text(encoding="utf-8")
        css = Path("static/css/device-workspace.css").read_text(encoding="utf-8")

        self.assertIn("fetch(url", script)
        self.assertIn("beforeunload", script)
        self.assertIn("unsaved changes", script)
        self.assertIn("device-workspace:form-saved", script)
        self.assertIn("ArrowRight", script)
        self.assertIn("workspace-services", script)
        self.assertIn(".device-compact-header", css)
        self.assertIn("position: sticky", css)
        self.assertIn(".device-workspace-tab.is-dirty", css)
        self.assertIn(".device-dashboard-grid", css)
        self.assertIn("@media (max-width: 767.98px)", css)

    def test_workspace_javascript_parses_when_node_is_available(self):
        node = shutil.which("node")
        if not node:
            return

        for path in (
            "static/js/device-workspace.js",
            "static/js/ip_client.js",
            "static/js/port_scan_live.js",
        ):
            result = subprocess.run(
                [node, "--check", path],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, f"{path}: {result.stderr}")


if __name__ == "__main__":
    unittest.main()
