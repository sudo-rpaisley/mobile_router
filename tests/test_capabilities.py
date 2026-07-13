import unittest

from scripts.capabilities import build_capabilities, command_status, package_status


class CapabilitiesTest(unittest.TestCase):
    def test_command_status_shape(self):
        status = command_status(["definitely-not-a-real-command"])
        self.assertIn("definitely-not-a-real-command", status)
        self.assertFalse(status["definitely-not-a-real-command"]["available"])
        self.assertIsNone(status["definitely-not-a-real-command"]["path"])

    def test_package_status_shape(self):
        status = package_status(["sys"])
        self.assertTrue(status["sys"])

    def test_build_capabilities_contains_expected_sections(self):
        capabilities = build_capabilities()
        self.assertIn("platform", capabilities)
        self.assertIn("commands", capabilities)
        self.assertIn("packages", capabilities)
        self.assertIn("features", capabilities)
        self.assertTrue(capabilities["features"]["Core web UI"])
        self.assertTrue(capabilities["features"]["Minecraft status lab"])


    def test_display_sections_are_platform_filtered(self):
        capabilities = build_capabilities()
        self.assertIn("display_commands", capabilities)
        self.assertIn("display_features", capabilities)
        self.assertIn("display_packages", capabilities)


if __name__ == "__main__":
    unittest.main()
