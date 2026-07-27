import unittest
from unittest.mock import patch

import pytest

pytest.importorskip("scapy")
from scapy.layers.dot11 import Dot11, Dot11Deauth, RadioTap

from scripts.wifi.deauth import build_deauth_packet, deauth


class WifiDeauthPacketTest(unittest.TestCase):
    def test_build_deauth_packet_sets_management_deauth_header(self):
        packet = build_deauth_packet(
            "aa:bb:cc:dd:ee:ff",
            "11:22:33:44:55:66",
        )

        self.assertTrue(packet.haslayer(RadioTap))
        self.assertTrue(packet.haslayer(Dot11))
        self.assertTrue(packet.haslayer(Dot11Deauth))
        dot11 = packet[Dot11]
        self.assertEqual(dot11.type, 0)
        self.assertEqual(dot11.subtype, 12)
        self.assertEqual(dot11.addr1, "11:22:33:44:55:66")
        self.assertEqual(dot11.addr2, "aa:bb:cc:dd:ee:ff")
        self.assertEqual(dot11.addr3, "aa:bb:cc:dd:ee:ff")
        self.assertEqual(packet[Dot11Deauth].reason, 7)

    @patch("scripts.wifi.deauth.sendp")
    def test_deauth_sends_built_80211_packet(self, sendp):
        deauth("aa:bb:cc:dd:ee:ff", "ff:ff:ff:ff:ff:ff", "wlan0mon", frames=2)

        packet = sendp.call_args.args[0]
        self.assertEqual(packet[Dot11].type, 0)
        self.assertEqual(packet[Dot11].subtype, 12)
        self.assertEqual(packet[Dot11].addr1, "ff:ff:ff:ff:ff:ff")
        sendp.assert_called_once_with(
            packet,
            iface="wlan0mon",
            count=2,
            inter=0.1,
            verbose=False,
        )


if __name__ == "__main__":
    unittest.main()
