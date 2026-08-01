"""Bounded metadata-only passive packet observation."""


def _normalize_mac(mac):
    if not mac:
        return None
    return str(mac).strip().replace("-", ":").lower()


def packet_passive_scan(
    interface,
    timeout=2,
    packet_limit=250,
    manufacturer_lookup=None,
):
    """Capture passive packet metadata for devices visible on an interface.

    The capture is metadata-only (MAC/IP/protocol) and bounded by both a short
    timeout and packet count so callers can use it in continuous monitor loops
    without storing payloads or growing memory unbounded.
    """
    interface = (interface or "").strip()
    if not interface:
        raise ValueError("Missing interface")
    timeout = max(1, min(int(timeout), 10))
    packet_limit = max(25, min(int(packet_limit), 1000))
    manufacturer_lookup = manufacturer_lookup or (lambda mac: "Unknown")
    try:
        from scapy.all import ARP, Ether, IP, IPv6, sniff
    except ImportError as exc:
        raise RuntimeError(
            "Live packet capture requires scapy to be installed"
        ) from exc

    devices = {}

    def remember(mac=None, ip=None, protocol=None):
        mac = _normalize_mac(mac) or ""
        ip = (ip or "").strip()
        if not mac and not ip:
            return
        if mac in {"ff:ff:ff:ff:ff:ff", "00:00:00:00:00:00"}:
            return
        key = mac or ip
        entry = devices.setdefault(
            key,
            {
                "ip": ip or "Unknown",
                "mac": mac or "Unknown",
                "hostname": "Unknown",
                "manufacturer": (
                    manufacturer_lookup(mac) if mac else "Unknown"
                ),
                "source": "packet-observation",
                "protocols": [],
            },
        )
        if ip and entry.get("ip") in {"Unknown", ""}:
            entry["ip"] = ip
        if mac and entry.get("mac") in {"Unknown", ""}:
            entry["mac"] = mac
            entry["manufacturer"] = manufacturer_lookup(mac)
        if protocol and protocol not in entry["protocols"]:
            entry["protocols"].append(protocol)

    def observe(packet):
        try:
            src_mac = packet[Ether].src if packet.haslayer(Ether) else None
            if packet.haslayer(ARP):
                arp = packet[ARP]
                remember(arp.hwsrc, arp.psrc, "arp")
                remember(arp.hwdst, arp.pdst, "arp")
            elif packet.haslayer(IP):
                remember(src_mac, packet[IP].src, "ipv4")
            elif packet.haslayer(IPv6):
                remember(src_mac, packet[IPv6].src, "ipv6")
            elif src_mac:
                remember(src_mac, None, "ethernet")
        except Exception:
            return

    capture_filter = (
        "arp or udp port 67 or udp port 68 or udp port 5353 "
        "or udp port 1900 or icmp6"
    )
    try:
        sniff(
            iface=interface,
            store=False,
            prn=observe,
            timeout=timeout,
            count=packet_limit,
            filter=capture_filter,
        )
    except Exception as exc:
        message = str(exc).lower()
        if (
            "filter" not in message
            and "libpcap" not in message
            and "bpf" not in message
        ):
            raise
        sniff(
            iface=interface,
            store=False,
            prn=observe,
            timeout=timeout,
            count=packet_limit,
        )
    return list(devices.values())
