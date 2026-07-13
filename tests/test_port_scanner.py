import unittest

from scripts.portScanner import PortScanError, scan_ports, validate_port_range


class PortScannerValidationTest(unittest.TestCase):
    def test_accepts_valid_range(self):
        self.assertEqual(validate_port_range(1, 1024), (1, 1024))

    def test_rejects_reversed_range(self):
        with self.assertRaisesRegex(PortScanError, "Start port"):
            validate_port_range(100, 1)

    def test_rejects_out_of_bounds_range(self):
        with self.assertRaisesRegex(PortScanError, "between"):
            validate_port_range(0, 80)

        with self.assertRaisesRegex(PortScanError, "between"):
            validate_port_range(80, 65536)

    def test_rejects_large_range(self):
        with self.assertRaisesRegex(PortScanError, "cannot exceed"):
            validate_port_range(1, 1025)

    def test_rejects_blank_host(self):
        with self.assertRaisesRegex(PortScanError, "Host is required"):
            scan_ports("   ", 1, 1)


if __name__ == "__main__":
    unittest.main()
