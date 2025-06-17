from scapy.all import Dot11, Dot11Beacon, Dot11Elt, RadioTap, sendp


def beaconSpoof(ssid, iface, frames, src="22:22:22:22:22:22", bssid="33:33:33:33:33:33"):
    """Send spoofed beacon frames.

    Parameters
    ----------
    ssid : str
        SSID to advertise.
    iface : str
        Interface to send from.
    frames : int
        Number of frames to send.
    src : str, optional
        Source MAC address (addr2).
    bssid : str, optional
        BSSID address (addr3).
    """

    dot11 = Dot11(type=0, subtype=8, addr1="ff:ff:ff:ff:ff:ff", addr2=src, addr3=bssid)
    beacon = Dot11Beacon(cap="ESS+privacy")
    essid = Dot11Elt(ID="SSID", info=ssid, len=len(ssid))
    rsn = Dot11Elt(
        ID="RSNinfo",
        info=(
            "\x01\x00"  # RSN Version 1
            "\x00\x0f\xac\x02"  # Group Cipher Suite : 00-0f-ac TKIP
            "\x02\x00"  # 2 Pairwise Cipher Suites (next two lines)
            "\x00\x0f\xac\x04"  # AES Cipher
            "\x00\x0f\xac\x02"  # TKIP Cipher
            "\x01\x00"  # 1 Authentication Key Management Suite (line below)
            "\x00\x0f\xac\x02"  # Pre-Shared Key
            "\x00\x00"
        ),
    )

    frame = RadioTap() / dot11 / beacon / essid / rsn

    print(f"Sending {frames} beacon frames on interface {iface} for SSID '{ssid}'")
    sendp(frame, iface=iface, count=frames, inter=0.1)
