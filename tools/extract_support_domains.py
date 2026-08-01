"""Extract state-aware helper domains from the legacy Flask entry point.

Generated support modules refresh their global dependency namespace from
``app.py`` every time a public helper is called. This preserves existing
monkey-patch behaviour during the migration while moving cohesive logic out of
the entry point.
"""

from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
SUPPORT_DIR = ROOT / "app_support"
QUALITY_TEST_PATH = ROOT / "tests" / "test_code_quality.py"


@dataclass(frozen=True)
class SupportGroup:
    path: Path
    configure_name: str
    functions: tuple[str, ...]
    description: str
    maximum_lines: int


GROUPS = (
    SupportGroup(
        path=SUPPORT_DIR / "client_intelligence.py",
        configure_name="configure_client_intelligence_context",
        description="Client identity, timeline, health, metadata, and relationship helpers.",
        maximum_lines=430,
        functions=(
            "_dhcp_lease_display_name",
            "display_name_for_inventory_device",
            "enrich_ip_client_display_name",
            "client_timeline",
            "client_health_summary",
            "_ttl_os_hint",
            "client_intelligence_profile",
            "update_client_metadata",
            "save_client_baseline",
            "client_profile_export",
            "client_relationship_map",
        ),
    ),
    SupportGroup(
        path=SUPPORT_DIR / "client_services.py",
        configure_name="configure_client_services_context",
        description="Client service fingerprinting, scheduled checks, alerts, and HTTP inspection.",
        maximum_lines=330,
        functions=(
            "fingerprint_client_services",
            "save_scheduled_client_check",
            "scan_common_client_ports",
            "run_scheduled_client_check",
            "run_due_scheduled_client_checks",
            "create_client_watch_alert",
            "capture_http_preview_thumbnail",
            "inspect_http_services",
        ),
    ),
    SupportGroup(
        path=SUPPORT_DIR / "passive_monitoring.py",
        configure_name="configure_passive_monitoring_context",
        description="Passive observation analytics, monitor workers, and combined scans.",
        maximum_lines=300,
        functions=(
            "record_passive_observation_analytics",
            "passive_observation_summary",
            "passive_monitor_snapshot",
            "_passive_monitor_worker",
            "set_passive_monitor",
            "comprehensive_network_device_scan",
        ),
    ),
)


def named_functions(source: str) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(source)
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def source_start(node: ast.FunctionDef) -> int:
    decorator_lines = [decorator.lineno for decorator in node.decorator_list]
    return min([node.lineno, *decorator_lines])


def add_refresh_decorator(block: str) -> str:
    lines = block.splitlines()
    def_index = next(
        index for index, line in enumerate(lines)
        if line.startswith("def ")
    )
    lines.insert(def_index, "@_refresh_context")
    return "\n".join(lines)


def module_name(path: Path) -> str:
    return path.with_suffix("").relative_to(ROOT).as_posix().replace("/", ".")


def render_group(
    group: SupportGroup,
    source_lines: list[str],
    nodes: dict[str, ast.FunctionDef],
) -> str:
    functions = []
    for name in group.functions:
        node = nodes[name]
        block = "".join(
            source_lines[source_start(node) - 1 : node.end_lineno]
        ).rstrip()
        functions.append(textwrap.indent(add_refresh_decorator(block), ""))

    exports = ",\n".join(f"    {name!r}" for name in group.functions)
    return (
        f'"""{group.description}"""\n\n'
        "from functools import wraps\n\n\n"
        "_CONTEXT_PROVIDER = None\n\n\n"
        f"def {group.configure_name}(provider):\n"
        "    global _CONTEXT_PROVIDER\n"
        "    _CONTEXT_PROVIDER = provider\n\n\n"
        "def _refresh_context(view):\n"
        "    @wraps(view)\n"
        "    def wrapped(*args, **kwargs):\n"
        "        if _CONTEXT_PROVIDER is not None:\n"
        "            globals().update(_CONTEXT_PROVIDER())\n"
        "        return view(*args, **kwargs)\n"
        "    return wrapped\n\n\n"
        + "\n\n\n".join(functions)
        + "\n\n\n__all__ = [\n"
        + exports
        + "\n]\n"
    )


def import_block() -> str:
    blocks = []
    configurations = []
    for group in GROUPS:
        imported = ",\n".join(
            f"    {name}" for name in group.functions
        )
        blocks.append(
            f"from {module_name(group.path)} import (\n"
            f"    {group.configure_name},\n"
            f"{imported},\n"
            ")"
        )
        configurations.append(
            f"{group.configure_name}(lambda: globals())"
        )
    return "\n".join(blocks) + "\n\n" + "\n".join(configurations) + "\n"


def extract(source: str) -> tuple[str, dict[Path, str]]:
    marker = (
        "from app_support.client_intelligence import ("
    )
    if marker in source:
        return source, {}

    nodes = named_functions(source)
    requested = [name for group in GROUPS for name in group.functions]
    missing = [name for name in requested if name not in nodes]
    if missing:
        raise RuntimeError(f"Missing support-domain functions: {missing}")

    source_lines = source.splitlines(keepends=True)
    generated = {
        group.path: render_group(group, source_lines, nodes)
        for group in GROUPS
    }
    selected = [nodes[name] for name in requested]
    first_line = min(source_start(node) for node in selected)
    removed: set[int] = set()
    for node in selected:
        removed.update(range(source_start(node), node.end_lineno + 1))

    output = []
    for line_number, line in enumerate(source_lines, start=1):
        if line_number == first_line:
            output.append(import_block())
            output.append("\n")
        if line_number not in removed:
            output.append(line)

    normalized = "".join(output)
    while "\n\n\n\n" in normalized:
        normalized = normalized.replace("\n\n\n\n", "\n\n\n")
    return normalized, generated


def ensure_quality_guard() -> None:
    text = QUALITY_TEST_PATH.read_text(encoding="utf-8")
    marker = "def test_stateful_support_domains_are_extracted():"
    if marker in text:
        return
    checks = "\n".join(
        f"    assert len(Path({str(group.path.relative_to(ROOT))!r}).read_text(encoding='utf-8').splitlines()) <= {group.maximum_lines}"
        for group in GROUPS
    )
    addition = f'''\n\ndef test_stateful_support_domains_are_extracted():
    assert len(Path('app.py').read_text(encoding='utf-8').splitlines()) <= 2550
{checks}
'''
    QUALITY_TEST_PATH.write_text(
        text.rstrip() + addition + "\n",
        encoding="utf-8",
    )


def main() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    updated, generated = extract(source)
    if updated != source:
        APP_PATH.write_text(updated, encoding="utf-8")
    for path, content in generated.items():
        path.write_text(content, encoding="utf-8")
    ensure_quality_guard()


if __name__ == "__main__":
    main()
