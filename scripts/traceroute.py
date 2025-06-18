import subprocess
from typing import List


def traceroute(host: str, max_hops: int = 30, timeout: int = 2) -> List[str]:
    """Run traceroute to the given host and return a list of hop IP addresses."""
    try:
        output = subprocess.check_output(
            ["traceroute", "-n", "-m", str(max_hops), "-w", str(timeout), host],
            stderr=subprocess.STDOUT,
            encoding="utf-8",
        )
    except Exception:
        return []

    hops: List[str] = []
    lines = output.splitlines()
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 2:
            ip = parts[1]
            hops.append(ip)
    return hops
