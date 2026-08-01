"""Replace copied Bluetooth helpers with shared utility aliases."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Consolidation:
    path: str
    functions: tuple[str, ...]
    import_line: str
    aliases: tuple[str, ...]


CONSOLIDATIONS = (
    Consolidation(
        path="scripts/bluetooth_phone.py",
        functions=("_bluez_dbus_available", "_project_helper_candidates"),
        import_line=(
            "from scripts.bluetooth_support import "
            "bluez_service_available, project_helper_candidates"
        ),
        aliases=(
            "_bluez_dbus_available = bluez_service_available",
            "_project_helper_candidates = project_helper_candidates",
        ),
    ),
    Consolidation(
        path="scripts/bluetooth_phone_runtime.py",
        functions=("_project_helper_candidates",),
        import_line="from scripts.bluetooth_support import project_helper_candidates",
        aliases=("_project_helper_candidates = project_helper_candidates",),
    ),
    Consolidation(
        path="scripts/capabilities.py",
        functions=("_busctl_bluez_available",),
        import_line="from scripts.bluetooth_support import bluez_service_available",
        aliases=("_busctl_bluez_available = bluez_service_available",),
    ),
    Consolidation(
        path="app_support/bluetooth_actions.py",
        functions=("_busctl_bluez_available",),
        import_line="from scripts.bluetooth_support import bluez_service_available",
        aliases=("_busctl_bluez_available = bluez_service_available",),
    ),
)


def consolidate(item: Consolidation) -> None:
    path = ROOT / item.path
    source = path.read_text(encoding="utf-8")
    if all(alias in source for alias in item.aliases):
        return

    tree = ast.parse(source, filename=str(path))
    source_lines = source.splitlines(keepends=True)
    nodes = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = [name for name in item.functions if name not in nodes]
    if missing:
        raise RuntimeError(f"Missing functions in {path}: {missing}")

    selected = [nodes[name] for name in item.functions]
    removed_lines: set[int] = set()
    first_removed = min(node.lineno for node in selected)
    for node in selected:
        removed_lines.update(range(node.lineno, node.end_lineno + 1))

    import_nodes = [
        node
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    import_after = max(node.end_lineno for node in import_nodes)

    output: list[str] = []
    for line_number, line in enumerate(source_lines, start=1):
        if line_number not in removed_lines:
            output.append(line)
        if line_number == import_after and item.import_line not in source:
            output.append(item.import_line + "\n")
        if line_number == first_removed:
            output.append("\n".join(item.aliases) + "\n")

    updated = "".join(output)
    while "\n\n\n\n" in updated:
        updated = updated.replace("\n\n\n\n", "\n\n\n")
    path.write_text(updated, encoding="utf-8")


def main() -> None:
    for item in CONSOLIDATIONS:
        consolidate(item)


if __name__ == "__main__":
    main()
