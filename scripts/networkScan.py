import ipaddress
import platform
import re
import shutil
import subprocess


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


def active_scan(interface):
    """Perform a ping sweep and return live hosts with MAC addresses."""
    cidr = _get_ipv4_cidr(interface)
    if not cidr:
        return []
    try:
        network = ipaddress.ip_interface(cidr).network
    except ValueError:
        return []

    live_hosts = []
    for ip in network.hosts():
        try:
            result = subprocess.run(
                _ping_command(ip),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if result.returncode == 0:
                mac = get_mac_by_ip(str(ip))
                live_hosts.append({"ip": str(ip), "mac": mac})
        except Exception:
            continue
    return live_hosts


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
