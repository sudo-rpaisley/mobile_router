import subprocess
from typing import Optional


def deauth(ap_mac: str, target_mac: str, iface: str, frames: int = 1) -> str:
    """Send deauthentication frames using aireplay-ng."""
    cmd = [
        "aireplay-ng",
        "-0",
        str(frames),
        "-a",
        ap_mac,
        "-c",
        target_mac,
        iface,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as e:
        raise RuntimeError("aireplay-ng not found") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"aireplay-ng failed: {e.stderr.strip()}") from e
    return result.stdout.strip()
