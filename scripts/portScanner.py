import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Optional, Tuple

MIN_PORT = 1
MAX_PORT = 65535
DEFAULT_TIMEOUT = 0.5
MAX_PORTS_PER_SCAN = 1024
DEFAULT_WORKERS = 128

COMMON_SERVICE_HINTS = {
    20: ('FTP data', 'File transfer data channel'),
    21: ('FTP', 'File transfer control channel'),
    22: ('SSH', 'Secure shell remote administration'),
    23: ('Telnet', 'Unencrypted remote shell'),
    25: ('SMTP', 'Mail transfer'),
    53: ('DNS', 'Domain name service'),
    67: ('DHCP server', 'Dynamic host configuration'),
    68: ('DHCP client', 'Dynamic host configuration'),
    80: ('HTTP', 'Web server'),
    110: ('POP3', 'Mail retrieval'),
    123: ('NTP', 'Network time'),
    135: ('MS RPC', 'Windows RPC endpoint mapper'),
    139: ('NetBIOS', 'Windows file/printer sharing'),
    143: ('IMAP', 'Mail retrieval'),
    161: ('SNMP', 'Network monitoring'),
    389: ('LDAP', 'Directory service'),
    443: ('HTTPS', 'Encrypted web server'),
    445: ('SMB', 'Windows file sharing'),
    465: ('SMTPS', 'Encrypted mail submission'),
    587: ('SMTP submission', 'Mail submission'),
    631: ('IPP', 'Printer service'),
    993: ('IMAPS', 'Encrypted mail retrieval'),
    995: ('POP3S', 'Encrypted mail retrieval'),
    1433: ('MSSQL', 'Microsoft SQL Server'),
    1521: ('Oracle DB', 'Oracle database listener'),
    2049: ('NFS', 'Network file system'),
    3306: ('MySQL', 'MySQL/MariaDB database'),
    3389: ('RDP', 'Windows remote desktop'),
    5432: ('PostgreSQL', 'PostgreSQL database'),
    5900: ('VNC', 'Remote framebuffer desktop'),
    6379: ('Redis', 'Redis database'),
    8080: ('HTTP alternate', 'Alternate web server/proxy'),
    8443: ('HTTPS alternate', 'Alternate encrypted web server'),
    27017: ('MongoDB', 'MongoDB database'),
}


def identify_port_service(port: int) -> Dict[str, str]:
    """Return best-effort service metadata for a TCP port."""
    if port in COMMON_SERVICE_HINTS:
        service, description = COMMON_SERVICE_HINTS[port]
        return {'port': port, 'service': service, 'description': description}
    try:
        service = socket.getservbyport(port, 'tcp').upper()
    except OSError:
        service = 'Unknown'
    description = 'Registered TCP service' if service != 'Unknown' else 'No common service mapping found'
    return {'port': port, 'service': service, 'description': description}


def describe_open_ports(ports: List[int]) -> List[Dict[str, str]]:
    """Return service metadata for open ports."""
    return [identify_port_service(port) for port in sorted(ports)]


class PortScanError(ValueError):
    """Raised when a port scan request is invalid."""


def validate_port_range(start: int, end: int, max_ports: Optional[int] = MAX_PORTS_PER_SCAN) -> Tuple[int, int]:
    """Validate and normalize a TCP port range."""
    if start > end:
        raise PortScanError("Start port must be less than or equal to end port")

    if start < MIN_PORT or end > MAX_PORT:
        raise PortScanError(f"Ports must be between {MIN_PORT} and {MAX_PORT}")

    if max_ports is not None and (end - start + 1) > max_ports:
        raise PortScanError(f"Port range cannot exceed {max_ports} ports")

    return start, end


def _check_port(host: str, port: int, timeout: float) -> Tuple[int, bool]:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            return port, sock.connect_ex((host, port)) == 0
    except OSError:
        return port, False


def scan_ports(
    host: str,
    start: int,
    end: int,
    timeout: float = DEFAULT_TIMEOUT,
    on_open: Optional[Callable[[int], None]] = None,
    on_progress: Optional[Callable[[int], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
    max_ports: Optional[int] = MAX_PORTS_PER_SCAN,
    workers: int = DEFAULT_WORKERS,
) -> List[int]:
    """Scan TCP ports concurrently and optionally stream open/progress events."""
    if not host or not host.strip():
        raise PortScanError("Host is required")

    if timeout <= 0:
        raise PortScanError("Timeout must be greater than zero")

    start, end = validate_port_range(start, end, max_ports=max_ports)
    host = host.strip()
    ports = range(start, end + 1)
    worker_count = min(max(1, workers), len(ports))

    open_ports = []
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(_check_port, host, port, timeout) for port in ports]
        for future in as_completed(futures):
            if should_cancel and should_cancel():
                for pending in futures:
                    pending.cancel()
                break
            port, is_open = future.result()
            if is_open:
                open_ports.append(port)
                if on_open:
                    on_open(port)
            if on_progress:
                on_progress(port)

    return sorted(open_ports)
