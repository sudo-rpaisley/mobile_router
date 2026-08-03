import shutil
import subprocess
from pathlib import Path


def test_long_page_assets_are_loaded_globally():
    header = Path("templates/_header.html").read_text(encoding="utf-8")
    footer = Path("templates/_footer.html").read_text(encoding="utf-8")

    assert "css/long-page.css" in header
    assert "js/long-page.js" in footer


def test_long_page_controller_is_progressive_and_remembers_state():
    source = Path("static/js/long-page.js").read_text(encoding="utf-8")

    assert "const MIN_SECTIONS = 5" in source
    assert "main.page-shell, main.theme-page, #main-content.content" in source
    assert "window.localStorage" in source
    assert "IntersectionObserver" in source
    assert "Expand all" in source
    assert "Collapse all" in source
    assert "Essentials" in source
    assert "Find a section" in source
    assert "aria-expanded" in source


def test_long_page_styles_include_sticky_mobile_navigation():
    source = Path("static/css/long-page.css").read_text(encoding="utf-8")

    assert ".long-page-tools" in source
    assert "position: sticky" in source
    assert ".long-page-nav" in source
    assert "overflow-x: auto" in source
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
