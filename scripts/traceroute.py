import platform
import shutil
import subprocess
from typing import List


def _traceroute_command(host: str, max_hops: int, timeout: int):
    system = platform.system()
    if system == "Windows":
        return ["tracert", "-d", "-h", str(max_hops), "-w", str(timeout * 1000), host]

    traceroute_tool = shutil.which("traceroute")
    if traceroute_tool:
        return [traceroute_tool, "-n", "-m", str(max_hops), "-w", str(timeout), host]

    tracepath_tool = shutil.which("tracepath")
    if tracepath_tool:
        return [tracepath_tool, "-n", "-m", str(max_hops), host]

    return None


def traceroute(host: str, max_hops: int = 30, timeout: int = 2) -> List[str]:
    """Run traceroute/tracert/tracepath and return a list of hop IP addresses."""
    command = _traceroute_command(host, max_hops, timeout)
    if not command:
        return []

    try:
        output = subprocess.check_output(
            command,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="ignore",
        )
    except Exception:
        return []

    hops: List[str] = []
    lines = output.splitlines()
    for line in lines[1:]:
        parts = line.split()
        for part in parts[1:]:
            cleaned = part.strip("[]")
            if cleaned.count(".") == 3 and all(piece.isdigit() for piece in cleaned.split(".")):
                hops.append(cleaned)
                break
    return hops
