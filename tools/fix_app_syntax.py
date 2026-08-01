"""Apply deterministic repairs exposed by the first full CI run."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
ROUTE_TEST_PATH = ROOT / "tests" / "test_routes.py"

BROKEN_APP = """outputs.append(f'{property_name}: {(result.stdout or '').strip()}')"""
FIXED_APP = """outputs.append(f"{property_name}: {(result.stdout or '').strip()}")"""
BROKEN_DEVICE_ASSERTION = """self.assertEqual(response.data.count(b'Device scan'), 1)"""
FIXED_DEVICE_ASSERTION = """self.assertEqual(
            response.data.count(
                b'href="/clients/192.168.20.10">Device scan</a>'
            ),
            1,
        )"""
BROKEN_TOOLS_ASSERTION = """self.assertEqual(response.data.count(b'Tools scan'), 1)"""
FIXED_TOOLS_ASSERTION = """self.assertEqual(
            response.data.count(
                b'href="/port-scan?host=192.168.20.10">Tools scan</a>'
            ),
            1,
        )"""


def replace_once(path: Path, broken: str, fixed: str) -> None:
    source = path.read_text(encoding="utf-8")
    if broken in source:
        path.write_text(source.replace(broken, fixed, 1), encoding="utf-8")
        return
    if fixed not in source:
        raise RuntimeError(f"Expected statement was not found in {path}")


def main() -> None:
    replace_once(APP_PATH, BROKEN_APP, FIXED_APP)
    replace_once(
        ROUTE_TEST_PATH,
        BROKEN_DEVICE_ASSERTION,
        FIXED_DEVICE_ASSERTION,
    )
    replace_once(
        ROUTE_TEST_PATH,
        BROKEN_TOOLS_ASSERTION,
        FIXED_TOOLS_ASSERTION,
    )


if __name__ == "__main__":
    main()
