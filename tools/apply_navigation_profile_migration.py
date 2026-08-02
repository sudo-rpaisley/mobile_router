"""One-shot migration for navigation and account profile improvements."""

import base64
import json
import zlib
from pathlib import Path


ORIGINAL_TEST_WORKFLOW = '''name: Python tests

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


def replace_once(source, old, new, label):
    if source.count(old) != 1:
        raise RuntimeError(
            f"Expected exactly one {label} block, found {source.count(old)}"
        )
    return source.replace(old, new, 1)


def main():
    payload_paths = sorted(Path("tools").glob("nav_payload_*.txt"))
    payload = "".join(path.read_text(encoding="utf-8") for path in payload_paths)
    files = json.loads(zlib.decompress(base64.b64decode(payload)).decode())

    route_source = files["routes/social_auth.py"]
    route_source = replace_once(
        route_source,
        "from app_support.context import bind_context\n",
        "from app_support import navigation as navigation_service\n"
        "from app_support.context import bind_context\n",
        "navigation route import",
    )
    route_source = replace_once(
        route_source,
        """def register_social_auth_routes(app, context_provider):
    _refresh_context = bind_context(globals(), context_provider)

""",
        """def register_social_auth_routes(app, context_provider):
    _refresh_context = bind_context(globals(), context_provider)

    @app.context_processor
    def inject_navigation_context():
        context = context_provider()
        record = current_user_record()
        app_user = (
            social_auth_service.public_user(record)
            if record else current_app_user()
        )

        def app_navigation(title=''):
            return navigation_service.build_navigation_context(
                request.path,
                title,
                request.endpoint,
                app_user,
                context.get('networkTechnologies', ()),
                context.get('network_interfaces', ()),
            )

        return {'app_user': app_user, 'app_navigation': app_navigation}

""",
        "navigation context processor",
    )
    files["routes/social_auth.py"] = route_source
    files[".github/workflows/python-tests.yml"] = ORIGINAL_TEST_WORKFLOW

    for relative_path, content in files.items():
        path = Path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    for temporary in [
        Path("tools/apply_navigation_profile_migration.py"),
        Path(".github/workflows/apply-navigation-profile.yml"),
        *payload_paths,
    ]:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
