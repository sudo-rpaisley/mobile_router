"""Shared host capability and helper-discovery utilities for Bluetooth modules."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path


def bluez_service_available(busctl_path: str) -> bool:
    """Return whether ``org.bluez`` is reachable through the given busctl."""

    try:
        result = subprocess.run(
            [busctl_path, "tree", "org.bluez"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def project_helper_candidates(
    system: str,
    *,
    python_only: bool = False,
    native_only: bool = False,
) -> Iterator[Path]:
    """Yield bundled Bluetooth helper locations in preference order."""

    root = Path(__file__).resolve().parents[1]
    extension = ".exe" if system == "Windows" else ""
    native_names = (
        f"mobile-router-bluetooth-helper{extension}",
        f"bluetooth-phone-helper{extension}",
    )
    python_names = (
        "mobile-router-bluetooth-helper.py",
        "bluetooth-phone-helper.py",
    )
    names = (
        python_names
        if python_only
        else native_names
        if native_only
        else (*native_names, *python_names)
    )
    folders = (
        root,
        root / "bin",
        root / "helpers",
        root / "helpers" / "bluetooth",
        root / "helpers" / system.lower(),
    )
    for folder in folders:
        for name in names:
            yield folder / name
