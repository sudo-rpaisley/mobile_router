import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Optional, Tuple

MIN_PORT = 1
MAX_PORT = 65535
DEFAULT_TIMEOUT = 0.5
MAX_PORTS_PER_SCAN = 1024
DEFAULT_WORKERS = 128


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
            port, is_open = future.result()
            if is_open:
                open_ports.append(port)
                if on_open:
                    on_open(port)
            if on_progress:
                on_progress(port)

    return sorted(open_ports)
