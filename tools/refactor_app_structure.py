"""Apply deterministic, idempotent structural refactors to the legacy Flask app.

This tool deliberately uses the Python AST only to identify complete top-level
nodes. The original source text for each node is retained verbatim, which keeps
behavioural changes to a minimum while moving cohesive responsibilities out of
``app.py``.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
SUPPORT_DIR = ROOT / "app_support"
QUALITY_TEST_PATH = ROOT / "tests" / "test_code_quality.py"


@dataclass(frozen=True)
class Extraction:
    destination: Path
    names: tuple[str, ...]
    import_statement: str
    header: str


def top_level_name(node: ast.AST) -> str | None:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        targets: Iterable[ast.expr]
        if isinstance(node, ast.Assign):
            targets = node.targets
        else:
            targets = (node.target,)
        simple_names = [target.id for target in targets if isinstance(target, ast.Name)]
        if len(simple_names) == 1:
            return simple_names[0]
    return None


def render_module(header: str, source_lines: list[str], nodes: list[ast.AST]) -> str:
    parts = [header.rstrip(), ""]
    for node in sorted(nodes, key=lambda item: item.lineno):
        parts.append("".join(source_lines[node.lineno - 1 : node.end_lineno]).rstrip())
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def extract_nodes(source: str, extractions: tuple[Extraction, ...]) -> tuple[str, dict[Path, str]]:
    tree = ast.parse(source)
    source_lines = source.splitlines(keepends=True)
    nodes_by_name = {
        name: node
        for node in tree.body
        if (name := top_level_name(node)) is not None
    }

    replacements: dict[int, str] = {}
    removed_lines: set[int] = set()
    generated: dict[Path, str] = {}

    for extraction in extractions:
        missing = [name for name in extraction.names if name not in nodes_by_name]
        already_extracted = all(name not in source for name in extraction.names) and extraction.destination.exists()
        if missing:
            if already_extracted:
                continue
            raise RuntimeError(
                f"Cannot extract {extraction.destination}: missing top-level nodes {missing}"
            )

        selected = [nodes_by_name[name] for name in extraction.names]
        first_line = min(node.lineno for node in selected)
        replacements[first_line] = extraction.import_statement.rstrip() + "\n"
        generated[extraction.destination] = render_module(
            extraction.header, source_lines, selected
        )

        for node in selected:
            removed_lines.update(range(node.lineno, node.end_lineno + 1))

    if not generated:
        return source, generated

    output: list[str] = []
    for line_number, line in enumerate(source_lines, start=1):
        if line_number in replacements:
            output.append(replacements[line_number])
            output.append("\n")
        if line_number not in removed_lines:
            output.append(line)

    normalized = "".join(output)
    while "\n\n\n\n" in normalized:
        normalized = normalized.replace("\n\n\n\n", "\n\n\n")
    return normalized, generated


def ensure_quality_guards() -> None:
    text = QUALITY_TEST_PATH.read_text(encoding="utf-8")
    marker = "def test_app_is_split_into_manageable_modules():"
    if marker in text:
        return
    addition = '''\n\ndef test_app_is_split_into_manageable_modules():
    app_path = Path('app.py')
    assert len(app_path.read_text(encoding='utf-8').splitlines()) <= 4000

    expected_modules = {
        Path('app_support/roadmap.py'),
        Path('app_support/bluetooth_actions.py'),
        Path('app_support/identifiers.py'),
    }
    assert all(path.is_file() for path in expected_modules)
'''
    QUALITY_TEST_PATH.write_text(text.rstrip() + addition + "\n", encoding="utf-8")


def main() -> None:
    SUPPORT_DIR.mkdir(exist_ok=True)
    init_path = SUPPORT_DIR / "__init__.py"
    if not init_path.exists():
        init_path.write_text(
            '"""Application support modules extracted from the Flask entry point."""\n',
            encoding="utf-8",
        )

    source = APP_PATH.read_text(encoding="utf-8")
    extractions = (
        Extraction(
            destination=SUPPORT_DIR / "roadmap.py",
            names=("ROADMAP_SECTIONS", "remaining_roadmap_items"),
            import_statement=(
                "from app_support.roadmap import ROADMAP_SECTIONS, remaining_roadmap_items"
            ),
            header='"""Static product-roadmap data and projections."""',
        ),
        Extraction(
            destination=SUPPORT_DIR / "bluetooth_actions.py",
            names=(
                "BLUETOOTHCTL_ACTIONS",
                "BLUETOOTH_MAC_RE",
                "BluetoothToolUnavailable",
                "_busctl_bluez_available",
                "bluetooth_action_capability",
                "_bluetooth_device_path_from_busctl",
                "_run_busctl_bluetooth_action",
                "run_bluetoothctl_action",
                "set_interface_power_state",
                "_bluetooth_truthy",
                "bluetooth_device_state",
                "bluetooth_contextual_actions",
            ),
            import_statement=(
                "from app_support.bluetooth_actions import (\n"
                "    BLUETOOTHCTL_ACTIONS,\n"
                "    BLUETOOTH_MAC_RE,\n"
                "    BluetoothToolUnavailable,\n"
                "    _bluetooth_device_path_from_busctl,\n"
                "    _bluetooth_truthy,\n"
                "    _busctl_bluez_available,\n"
                "    _run_busctl_bluetooth_action,\n"
                "    bluetooth_action_capability,\n"
                "    bluetooth_contextual_actions,\n"
                "    bluetooth_device_state,\n"
                "    run_bluetoothctl_action,\n"
                "    set_interface_power_state,\n"
                ")"
            ),
            header=(
                '"""Host-local Bluetooth capability checks and safe adapter actions."""\n\n'
                "import os\n"
                "import re\n"
                "import shutil\n"
                "import subprocess\n"
            ),
        ),
        Extraction(
            destination=SUPPORT_DIR / "identifiers.py",
            names=("MAC_RE", "normalize_mac", "inventory_key"),
            import_statement=(
                "from app_support.identifiers import MAC_RE, inventory_key, normalize_mac"
            ),
            header=(
                '"""Normalization and stable-key helpers for discovered devices."""\n\n'
                "import re\n"
            ),
        ),
    )

    updated_source, generated = extract_nodes(source, extractions)
    if updated_source != source:
        APP_PATH.write_text(updated_source, encoding="utf-8")
    for path, content in generated.items():
        path.write_text(content, encoding="utf-8")

    ensure_quality_guards()


if __name__ == "__main__":
    main()
