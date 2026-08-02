"""One-shot update for the legacy navigation smoke assertion."""

from pathlib import Path


ORIGINAL_WORKFLOW = '''name: Python tests

on:
  pull_request:
  push:
    branches:
      - main

permissions:
  contents: read

jobs:
  test:
    name: test (${{ matrix.os }})
    strategy:
      fail-fast: false
      matrix:
        os:
          - ubuntu-latest
          - windows-latest
    runs-on: ${{ matrix.os }}
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - name: Install development dependencies
        run: python -m pip install -r requirements-dev.txt

      - name: Compile Python sources
        run: python -m compileall -q app.py app_support routes services scripts tests tools

      - name: Import application
        run: python -c "import app; print('Application imported successfully')"

      - name: Generate duplicate-code report
        run: python tools/report_duplicate_code.py

      - name: Upload duplicate-code report
        uses: actions/upload-artifact@v4
        with:
          name: duplicate-code-report-${{ runner.os }}
          path: duplicate_code_report.md

      - name: Run tests
        run: python -m pytest -q
'''


def main():
    test_path = Path('tests/test_routes.py')
    source = test_path.read_text(encoding='utf-8')
    old = "        self.assertNotIn(b'href=\"/network-scan\"', response.data)\n"
    new = "        self.assertIn(b'href=\"/network-scan\"', response.data)\n"
    if source.count(old) != 1:
        raise RuntimeError(f'Expected one legacy Network Scan assertion, found {source.count(old)}')
    test_path.write_text(source.replace(old, new, 1), encoding='utf-8')
    Path('.github/workflows/python-tests.yml').write_text(ORIGINAL_WORKFLOW, encoding='utf-8')
    Path('tools/update_navigation_route_test.py').unlink(missing_ok=True)


if __name__ == '__main__':
    main()
