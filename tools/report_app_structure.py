"""Generate a compact AST inventory for planning the next app.py split."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
REPORT_PATH = ROOT / "app_structure_report.md"


def node_name(node: ast.AST) -> str | None:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        names = [target.id for target in targets if isinstance(target, ast.Name)]
        if len(names) == 1:
            return names[0]
    return None


def decorator_label(node: ast.AST) -> str:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return ""
    labels = []
    for decorator in node.decorator_list:
        try:
            labels.append(ast.unparse(decorator))
        except Exception:
            labels.append(type(decorator).__name__)
    return ", ".join(labels)


def referenced_globals(node: ast.AST) -> list[str]:
    local_names = set()
    loaded_names = set()
    for child in ast.walk(node):
        if isinstance(child, ast.arg):
            local_names.add(child.arg)
        elif isinstance(child, ast.Name):
            if isinstance(child.ctx, (ast.Store, ast.Del)):
                local_names.add(child.id)
            elif isinstance(child.ctx, ast.Load):
                loaded_names.add(child.id)
    return sorted(loaded_names - local_names)


def main() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    rows = []
    for node in tree.body:
        name = node_name(node)
        if not name or not getattr(node, "end_lineno", None):
            continue
        rows.append(
            {
                "name": name,
                "kind": type(node).__name__,
                "start": node.lineno,
                "end": node.end_lineno,
                "lines": node.end_lineno - node.lineno + 1,
                "decorators": decorator_label(node),
                "globals": referenced_globals(node),
            }
        )

    route_rows = [row for row in rows if ".route(" in row["decorators"]]
    large_rows = sorted(rows, key=lambda row: row["lines"], reverse=True)

    output = [
        "# Remaining `app.py` structure",
        "",
        f"Total lines: **{len(source.splitlines())}**",
        f"Top-level named nodes: **{len(rows)}**",
        f"Decorated route handlers: **{len(route_rows)}**",
        "",
        "## Largest top-level nodes",
        "",
        "| Lines | Range | Kind | Name | Decorators |",
        "|---:|---:|---|---|---|",
    ]
    for row in large_rows[:60]:
        output.append(
            f"| {row['lines']} | {row['start']}-{row['end']} | "
            f"{row['kind']} | `{row['name']}` | "
            f"`{row['decorators']}` |"
        )

    output.extend(
        [
            "",
            "## Route handlers in source order",
            "",
            "| Range | Lines | Name | Decorators | Referenced globals |",
            "|---:|---:|---|---|---|",
        ]
    )
    for row in route_rows:
        dependencies = ", ".join(row["globals"][:20])
        if len(row["globals"]) > 20:
            dependencies += ", …"
        output.append(
            f"| {row['start']}-{row['end']} | {row['lines']} | "
            f"`{row['name']}` | `{row['decorators']}` | {dependencies} |"
        )

    REPORT_PATH.write_text("\n".join(output) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
