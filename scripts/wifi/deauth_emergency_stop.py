"""Create the local emergency-stop flag for a bounded deauth lab run."""

from services.deauth_control import emergency_stop_path, request_emergency_stop


def main() -> int:
    path = request_emergency_stop()
    print(f"Emergency stop requested via {path}")
    print(f"Controller flag path: {emergency_stop_path()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
