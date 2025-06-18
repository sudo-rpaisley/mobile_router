import socket
from typing import List

def scan_ports(host: str, start: int, end: int, timeout: float = 0.5) -> List[int]:
    """Scan a range of TCP ports on the given host and return a list of open ports."""
    open_ports = []
    for port in range(start, end + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                result = sock.connect_ex((host, port))
                if result == 0:
                    open_ports.append(port)
        except Exception:
            continue
    return open_ports
