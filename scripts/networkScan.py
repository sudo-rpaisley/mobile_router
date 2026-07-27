import ipaddress
import platform
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed


def _get_ipv4_cidr(interface):
    """Return the IPv4 address with prefix of the interface when supported."""
    ip_tool = shutil.which("ip")
    if ip_tool:
        try:
            output = subprocess.check_output(
                [ip_tool, "-4", "addr", "show", interface], encoding="utf-8")
        except Exception:
            return None
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("inet "):
                parts = line.split()
                if len(parts) >= 2:
                    return parts[1]
    return None


def _ping_command(ip):
    system = platform.system()
    if system == "Windows":
        return ["ping", "-n", "1", "-w", "1000", str(ip)]
    if system == "Darwin":
        return ["ping", "-c", "1", "-W", "1000", str(ip)]
    return ["ping", "-c", "1", "-W", "1", str(ip)]


def _get_ipv4_network(interface):
    """Return the IPv4 network for an interface, when it can be detected."""
    cidr = _get_ipv4_cidr(interface)
    if not cidr:
        return None
    try:
        return ipaddress.ip_interface(cidr).network
    except ValueError:
        return None


def _normalize_mac(mac):
    if not mac:
        return None
    return str(mac).strip().replace("-", ":").lower()


def classify_scan_entry(device, interface=None, network=None):
    """Classify a scan result so UI can separate hosts from local control traffic."""
    ip_text = device.get("ip") if device else None
    mac = _normalize_mac(device.get("mac") or device.get("address") if device else None)
    if network is None and interface:
        network = _get_ipv4_network(interface)

    classification = {
        "network_role": "Host",
        "network_scope": "Unknown",
        "is_internal": False,
        "is_control_traffic": False,
        "scan_note": "Unicast device observed in ARP cache.",
    }

    ip_obj = None
    if ip_text:
        try:
            ip_obj = ipaddress.ip_address(ip_text)
        except ValueError:
            ip_obj = None

    if mac == "ff:ff:ff:ff:ff:ff":
        classification.update({
            "network_role": "Broadcast",
            "network_scope": "Local segment",
            "is_internal": True,
            "is_control_traffic": True,
            "scan_note": "Broadcast address used by the local network; not an individual client.",
        })
    elif mac and mac.startswith("01:00:5e"):
        classification.update({
            "network_role": "Multicast",
            "network_scope": "Local segment",
            "is_internal": True,
            "is_control_traffic": True,
            "scan_note": "IPv4 multicast group for service discovery or routing; not an individual client.",
        })

    if ip_obj:
        if ip_obj == ipaddress.ip_address("255.255.255.255"):
            classification.update({
                "network_role": "Limited broadcast",
                "network_scope": "Local segment",
                "is_internal": True,
                "is_control_traffic": True,
                "scan_note": "All-hosts limited broadcast; not a physical device.",
            })
        elif ip_obj.is_multicast:
            classification.update({
                "network_role": "Multicast",
                "network_scope": "Local segment",
                "is_internal": True,
                "is_control_traffic": True,
                "scan_note": "Multicast group address; used by protocols such as mDNS, LLMNR, IGMP, or SSDP.",
            })
        elif network and ip_obj == network.broadcast_address:
            classification.update({
                "network_role": "Subnet broadcast",
                "network_scope": "Local subnet",
                "is_internal": True,
                "is_control_traffic": True,
                "scan_note": f"Broadcast address for {network}; not an individual client.",
            })
        elif ip_obj.is_private:
            classification.update({
                "network_scope": "Private LAN",
                "is_internal": True,
                "scan_note": "Private RFC1918 unicast address; likely a local host or router.",
            })
            if ip_text.endswith(".1") or ip_text.endswith(".254"):
                classification.update({
                    "network_role": "Likely gateway/router",
                    "scan_note": "Private unicast address commonly used by gateways or virtual network routers.",
                })
        elif ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved:
            classification.update({
                "network_scope": "Special-use",
                "is_internal": True,
                "scan_note": "Special-use address range; review before treating as an external host.",
            })
        elif ip_obj.is_global:
            classification.update({
                "network_scope": "Public Internet",
                "scan_note": "Globally routable unicast address.",
            })

    return classification


def classify_scan_results(devices, interface=None):
    """Return scan results with network-role metadata attached."""
    network = _get_ipv4_network(interface) if interface else None
    return [{**device, **classify_scan_entry(device, interface, network)} for device in devices or []]


def _ping_host(ip):
    """Return the IP string when a host replies to ping, otherwise None."""
    try:
        result = subprocess.run(
            _ping_command(ip),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
            check=False,
        )
    except Exception:
        return None
    return str(ip) if result.returncode == 0 else None


def _dedupe_devices(devices):
    seen = set()
    unique = []
    for device in devices:
        key = device.get("mac") or device.get("ip")
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(device)
    return unique


def _arp_cache_candidates(interface=None):
    """Return ARP cache entries for an interface, falling back to host-wide cache.

    UI adapter labels are not always the kernel interface names (for example a
    friendly "WiFi" label), so an active scan should still show cached LAN
    neighbors instead of reporting an empty result when CIDR detection fails.
    """
    devices = _parse_proc_arp(interface)
    if devices:
        return devices
    devices = _parse_proc_arp()
    if devices:
        return devices
    return _parse_arp_command()


def active_scan(interface):
    """Perform a bounded ping sweep and return live hosts with MAC addresses."""
    cidr = _get_ipv4_cidr(interface)
    if not cidr:
        return sorted(_dedupe_devices(_arp_cache_candidates(interface)), key=lambda item: ipaddress.ip_address(item["ip"]))
    try:
        network = ipaddress.ip_interface(cidr).network
    except ValueError:
        return []

    # A previous implementation pinged each address sequentially with no hard
    # timeout. On a /24 that can look broken from the UI because silent hosts
    # take minutes to exhaust. Keep the scan bounded and harvest the ARP cache
    # afterwards so ICMP-blocking LAN hosts can still show up when discovered.
    hosts = list(network.hosts())
    if len(hosts) > 1024:
        return sorted(_dedupe_devices(_arp_cache_candidates(interface)), key=lambda item: ipaddress.ip_address(item["ip"]))

    live_hosts = []
    workers = min(64, max(1, len(hosts)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_ping_host, ip) for ip in hosts]
        for future in as_completed(futures):
            ip = future.result()
            if ip:
                live_hosts.append({"ip": ip, "mac": get_mac_by_ip(ip)})

    live_hosts.extend(_arp_cache_candidates(interface))
    return sorted(_dedupe_devices(live_hosts), key=lambda item: ipaddress.ip_address(item["ip"]))


def _parse_proc_arp(interface=None):
    devices = []
    try:
        with open("/proc/net/arp") as f:
            next(f)
            for line in f:
                parts = line.split()
                if (
                    len(parts) >= 6
                    and (interface is None or parts[5] == interface)
                    and parts[3] != "00:00:00:00:00:00"
                ):
                    devices.append({"ip": parts[0], "mac": parts[3].lower()})
    except Exception:
        pass
    return devices


def _parse_arp_command():
    arp_tool = shutil.which("arp")
    if not arp_tool:
        return []
    try:
        output = subprocess.check_output([arp_tool, "-a"], encoding="utf-8", errors="ignore")
    except Exception:
        return []

    devices = []
    for line in output.splitlines():
        ip_match = re.search(r"\((\d+(?:\.\d+){3})\)", line) or re.search(r"(?:^|\s)(\d+(?:\.\d+){3})(?:\s|$)", line)
        mac_match = re.search(r"([0-9A-Fa-f]{2}(?:[:-][0-9A-Fa-f]{2}){5})", line)
        if ip_match and mac_match:
            devices.append({"ip": ip_match.group(1), "mac": mac_match.group(1).replace("-", ":").lower()})
    return devices



def packet_passive_scan(interface, timeout=2, packet_limit=250, manufacturer_lookup=None):
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
        raise RuntimeError("Live packet capture requires scapy to be installed") from exc

    devices = {}

    def remember(mac=None, ip=None, protocol=None):
        mac = _normalize_mac(mac) or ""
        ip = (ip or "").strip()
        if not mac and not ip:
            return
        if mac in {"ff:ff:ff:ff:ff:ff", "00:00:00:00:00:00"}:
            return
        key = mac or ip
        entry = devices.setdefault(key, {
            "ip": ip or "Unknown",
            "mac": mac or "Unknown",
            "hostname": "Unknown",
            "manufacturer": manufacturer_lookup(mac) if mac else "Unknown",
            "source": "packet-observation",
            "protocols": [],
        })
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

    capture_filter = "arp or udp port 67 or udp port 68 or udp port 5353 or udp port 1900 or icmp6"
    try:
        sniff(iface=interface, store=False, prn=observe, timeout=timeout, count=packet_limit, filter=capture_filter)
    except Exception as exc:
        message = str(exc).lower()
        if "filter" not in message and "libpcap" not in message and "bpf" not in message:
            raise
        sniff(iface=interface, store=False, prn=observe, timeout=timeout, count=packet_limit)
    return list(devices.values())

def passive_scan(interface):
    """Read the ARP cache for entries associated with the interface when available."""
    devices = _parse_proc_arp(interface)
    if devices:
        return devices
    return _parse_arp_command()


def get_mac_by_ip(ip):
    """Return the MAC address for a given IP from the ARP cache."""
    for device in _parse_proc_arp():
        if device["ip"] == ip:
            return device["mac"]
    for device in _parse_arp_command():
        if device["ip"] == ip:
            return device["mac"]
    return None


def get_ip_by_mac(mac):
    """Return the IP address for a given MAC from the ARP cache."""
    normalized_mac = mac.lower().replace("-", ":")
    for device in _parse_proc_arp():
        if device["mac"] == normalized_mac:
            return device["ip"]
    for device in _parse_arp_command():
        if device["mac"] == normalized_mac:
            return device["ip"]
    return None
