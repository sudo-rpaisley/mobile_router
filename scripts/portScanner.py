import socket
from typing import List, Tuple

MIN_PORT = 1
MAX_PORT = 65535
DEFAULT_TIMEOUT = 0.5
MAX_PORTS_PER_SCAN = 1024


class PortScanError(ValueError):
    """Raised when a port scan request is invalid."""


def validate_port_range(start: int, end: int) -> Tuple[int, int]:
    """Validate and normalize a TCP port range."""
    if start > end:
        raise PortScanError("Start port must be less than or equal to end port")

    if start < MIN_PORT or end > MAX_PORT:
        raise PortScanError(f"Ports must be between {MIN_PORT} and {MAX_PORT}")

    if (end - start + 1) > MAX_PORTS_PER_SCAN:
        raise PortScanError(f"Port range cannot exceed {MAX_PORTS_PER_SCAN} ports")

    return start, end


def scan_ports(host: str, start: int, end: int, timeout: float = DEFAULT_TIMEOUT) -> List[int]:
    """Scan a range of TCP ports on the given host and return a list of open ports."""
    if not host or not host.strip():
        raise PortScanError("Host is required")

    if timeout <= 0:
        raise PortScanError("Timeout must be greater than zero")

    start, end = validate_port_range(start, end)
    host = host.strip()

    open_ports = []
    for port in range(start, end + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                result = sock.connect_ex((host, port))
                if result == 0:
                    open_ports.append(port)
        except OSError:
            continue
    return open_ports
