import shutil
import subprocess
from pathlib import Path


def test_long_page_assets_are_loaded_globally():
    header = Path("templates/_header.html").read_text(encoding="utf-8")
    footer = Path("templates/_footer.html").read_text(encoding="utf-8")

    assert "css/long-page.css" in header
    assert "js/long-page.js" in footer


def test_long_page_controller_builds_accessible_remembered_tabs():
    source = Path("static/js/long-page.js").read_text(encoding="utf-8")

    assert "const MIN_SECTIONS = 5" in source
    assert "main.page-shell, main.theme-page, #main-content.content" in source
    assert "mobile-router:long-page-tab" in source
    assert "window.localStorage" in source
    assert "role', 'tabpanel" in source
    assert "role', 'tab" in source
    assert "aria-selected" in source
    assert "ArrowRight" in source
    assert "ArrowLeft" in source
    assert "Home" in source
    assert "End" in source
    assert "hashchange" in source
    assert "Only the selected section is shown" in source


def test_long_page_styles_include_tabs_and_mobile_selector():
    source = Path("static/css/long-page.css").read_text(encoding="utf-8")

    assert ".long-page-tabs-shell" in source
    assert "position: sticky" in source
    assert ".long-page-tablist" in source
    assert "overflow-x: auto" in source
    assert ".long-page-tab-select-group" in source
    assert "[data-long-page-tab-panel][hidden]" in source
    assert "@media (max-width: 767.98px)" in source
    assert "user-reduced-motion" in source


def test_known_long_templates_have_enough_sections_for_auto_enhancement():
    long_templates = (
        "templates/client_detail.html",
        "templates/host_facts.html",
        "templates/model_profile_detail.html",
        "templates/automotive_vehicle.html",
        "templates/social_profile_detail.html",
    )

    for path in long_templates:
        source = Path(path).read_text(encoding="utf-8")
        assert source.count("theme-card") >= 5, path


def test_long_page_javascript_parses_when_node_is_available():
    node = shutil.which("node")
    if not node:
        return

    result = subprocess.run(
        [node, "--check", "static/js/long-page.js"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
