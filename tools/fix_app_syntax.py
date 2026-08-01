"""Repair the known malformed Bluetooth information f-string in app.py."""

from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
BROKEN = """outputs.append(f'{property_name}: {(result.stdout or '').strip()}')"""
FIXED = """outputs.append(f"{property_name}: {(result.stdout or '').strip()}")"""


def main() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    if BROKEN in source:
        APP_PATH.write_text(source.replace(BROKEN, FIXED, 1), encoding="utf-8")
        return
    if FIXED not in source:
        raise RuntimeError("Expected Bluetooth information statement was not found")


if __name__ == "__main__":
    main()
