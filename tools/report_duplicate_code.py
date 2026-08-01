"""Report exact and structurally similar Python implementations.

The report is intentionally conservative: exact matches are strong candidates
for consolidation, while structural matches are review prompts rather than
instructions to merge code automatically.
"""

from __future__ import annotations

import ast
import hashlib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = (
    ROOT / "app.py",
    ROOT / "app_support",
    ROOT / "routes",
    ROOT / "services",
    ROOT / "scripts",
)
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".venv", "venv", "mobileRouter"}
MIN_FUNCTION_LINES = 5
MIN_BLOCK_LINES = 6


@dataclass(frozen=True)
class FunctionRecord:
    path: Path
    name: str
    start: int
    end: int
    exact_fingerprint: str
    shape_fingerprint: str

    @property
    def line_count(self) -> int:
        return self.end - self.start + 1


class ShapeNormalizer(ast.NodeTransformer):
    """Remove local naming and literal differences while preserving operations."""

    def visit_Name(self, node: ast.Name) -> ast.AST:
        return ast.copy_location(ast.Name(id="NAME", ctx=node.ctx), node)

    def visit_arg(self, node: ast.arg) -> ast.AST:
        return ast.copy_location(ast.arg(arg="ARG", annotation=None), node)

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        value = node.value
        if value is None or isinstance(value, bool):
            normalized = value
        elif isinstance(value, str):
            normalized = "STRING"
        elif isinstance(value, (int, float, complex)):
            normalized = 0
        else:
            normalized = "CONSTANT"
        return ast.copy_location(ast.Constant(value=normalized), node)


def python_files() -> list[Path]:
    paths: set[Path] = set()
    for scan_root in SCAN_ROOTS:
        if scan_root.is_file():
            paths.add(scan_root)
            continue
        if not scan_root.exists():
            continue
        for path in scan_root.rglob("*.py"):
            if EXCLUDED_PARTS.intersection(path.parts):
                continue
            paths.add(path)
    return sorted(paths)


def fingerprint(node: ast.AST) -> str:
    dumped = ast.dump(node, annotate_fields=False, include_attributes=False)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def function_records(path: Path) -> list[FunctionRecord]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    records: list[FunctionRecord] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        end = getattr(node, "end_lineno", node.lineno)
        if end - node.lineno + 1 < MIN_FUNCTION_LINES:
            continue
        exact_body = ast.Module(body=node.body, type_ignores=[])
        shape_body = ShapeNormalizer().visit(ast.fix_missing_locations(ast.Module(body=node.body, type_ignores=[])))
        records.append(
            FunctionRecord(
                path=path.relative_to(ROOT),
                name=node.name,
                start=node.lineno,
                end=end,
                exact_fingerprint=fingerprint(exact_body),
                shape_fingerprint=fingerprint(shape_body),
            )
        )
    return records


def repeated_line_blocks(paths: list[Path]) -> list[tuple[str, list[tuple[Path, int]]]]:
    occurrences: dict[str, list[tuple[Path, int]]] = defaultdict(list)
    source_by_key: dict[str, str] = {}
    for path in paths:
        lines = path.read_text(encoding="utf-8").splitlines()
        for index in range(0, max(0, len(lines) - MIN_BLOCK_LINES + 1)):
            window = lines[index : index + MIN_BLOCK_LINES]
            normalized = "\n".join(line.strip() for line in window)
            if not normalized or normalized.count("\n") < MIN_BLOCK_LINES - 1:
                continue
            if all(not line or line.startswith(("import ", "from ", "#")) for line in normalized.splitlines()):
                continue
            digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            occurrences[digest].append((path.relative_to(ROOT), index + 1))
            source_by_key.setdefault(digest, normalized)

    groups = []
    for digest, places in occurrences.items():
        unique_files = {path for path, _line in places}
        if len(unique_files) < 2:
            continue
        groups.append((source_by_key[digest], sorted(places)))
    groups.sort(key=lambda item: (-len(item[1]), item[0]))
    return groups[:30]


def render_groups(title: str, groups: dict[str, list[FunctionRecord]], exact: bool) -> list[str]:
    rendered = [f"## {title}", ""]
    qualifying = [records for records in groups.values() if len(records) > 1]
    qualifying.sort(key=lambda records: (-sum(record.line_count for record in records), records[0].name))
    if not qualifying:
        rendered.extend(["No matches found.", ""])
        return rendered

    for records in qualifying[:40]:
        total = sum(record.line_count for record in records)
        label = "Exact" if exact else "Structural"
        rendered.append(f"### {label} group: {len(records)} functions, {total} total lines")
        rendered.append("")
        for record in sorted(records, key=lambda item: (str(item.path), item.start)):
            rendered.append(
                f"- `{record.path}:{record.start}-{record.end}` — `{record.name}` ({record.line_count} lines)"
            )
        rendered.append("")
    return rendered


def build_report() -> str:
    paths = python_files()
    records = [record for path in paths for record in function_records(path)]
    exact_groups: dict[str, list[FunctionRecord]] = defaultdict(list)
    shape_groups: dict[str, list[FunctionRecord]] = defaultdict(list)
    for record in records:
        exact_groups[record.exact_fingerprint].append(record)
        shape_groups[record.shape_fingerprint].append(record)

    lines = [
        "# Duplicate Python code report",
        "",
        f"Scanned **{len(paths)} Python files** and **{len(records)} non-trivial functions**.",
        "",
        "Exact groups are high-confidence consolidation candidates. Structural groups only share control-flow shape and require manual review.",
        "",
    ]
    lines.extend(render_groups("Exact duplicate function bodies", exact_groups, exact=True))
    lines.extend(render_groups("Structurally similar function bodies", shape_groups, exact=False))

    blocks = repeated_line_blocks(paths)
    lines.extend(["## Repeated six-line source blocks", ""])
    if not blocks:
        lines.extend(["No repeated blocks found.", ""])
    else:
        for index, (source, places) in enumerate(blocks, start=1):
            lines.append(f"### Block {index}: {len(places)} occurrences")
            lines.append("")
            for path, line in places:
                lines.append(f"- `{path}:{line}`")
            lines.extend(["", "```python", source, "```", ""])

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    report = build_report()
    output_path = ROOT / "duplicate_code_report.md"
    output_path.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
