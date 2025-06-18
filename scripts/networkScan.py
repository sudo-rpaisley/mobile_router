import subprocess
import ipaddress


def _get_ipv4_cidr(interface):
    """Return the IPv4 address with prefix of the interface."""
    try:
        output = subprocess.check_output(
            ["ip", "-4", "addr", "show", interface], encoding="utf-8")
    except Exception:
        return None
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("inet "):
            parts = line.split()
            if len(parts) >= 2:
                return parts[1]
    return None


def active_scan(interface):
    """Perform a ping sweep to discover live hosts."""
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
                ["ping", "-c", "1", "-W", "1", str(ip)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if result.returncode == 0:
                live_hosts.append(str(ip))
        except Exception:
            continue
    return live_hosts


def passive_scan(interface):
    """Read the ARP table for entries associated with the interface."""
    devices = []
    try:
        with open("/proc/net/arp") as f:
            next(f)  # skip header
            for line in f:
                parts = line.split()
                if (
                    len(parts) >= 6
                    and parts[5] == interface
                    and parts[3] != "00:00:00:00:00:00"
                ):
                    devices.append({"ip": parts[0], "mac": parts[3]})
    except Exception:
        pass
    return devices
