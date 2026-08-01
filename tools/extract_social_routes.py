"""Extract the social-auth and profile routes from the legacy Flask entry point.

The generated route modules use registrar functions rather than module-level
blueprints. Each handler refreshes its dependency namespace from ``app.py`` at
request time, preserving the existing tests' ability to patch application
services and state while the migration is in progress.
"""

from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
ROUTES_DIR = ROOT / "routes"
QUALITY_TEST_PATH = ROOT / "tests" / "test_code_quality.py"


@dataclass(frozen=True)
class RouteGroup:
    path: Path
    registrar: str
    functions: tuple[str, ...]
    description: str


GROUPS = (
    RouteGroup(
        path=ROUTES_DIR / "social_auth.py",
        registrar="register_social_auth_routes",
        description="Authentication and local application-user routes.",
        functions=(
            "social_auth_setup",
            "social_auth_login",
            "social_auth_logout",
            "legacy_social_auth_setup",
            "legacy_social_auth_login",
            "application_users_page",
            "create_application_user",
        ),
    ),
    RouteGroup(
        path=ROUTES_DIR / "social_profiles.py",
        registrar="register_social_profile_routes",
        description="Profile listing, detail, creation, update, and deletion routes.",
        functions=(
            "social_engineering_page",
            "create_social_profile",
            "social_profile_detail",
            "social_profile_photo",
            "update_social_profile",
            "delete_social_profile",
        ),
    ),
    RouteGroup(
        path=ROUTES_DIR / "social_profile_resources.py",
        registrar="register_social_profile_resource_routes",
        description="Credentials, devices, vault, relationships, and attachments.",
        functions=(
            "add_social_profile_credential",
            "delete_social_profile_credential",
            "update_social_profile_credential",
            "add_social_profile_device",
            "delete_social_profile_device",
            "update_social_profile_device",
            "save_vault_verifier",
            "rotate_vault",
            "add_social_profile_relationship",
            "delete_social_profile_relationship",
            "merge_social_profiles",
            "add_social_profile_attachment",
            "download_social_profile_attachment",
            "delete_social_profile_attachment",
        ),
    ),
    RouteGroup(
        path=ROUTES_DIR / "social_profile_transfer.py",
        registrar="register_social_profile_transfer_routes",
        description="Profile import, export, and auditable client actions.",
        functions=(
            "export_social_profiles",
            "import_social_profiles",
            "social_profile_client_audit",
        ),
    ),
)


def function_nodes(source: str) -> dict[str, ast.FunctionDef]:
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


def render_group(
    group: RouteGroup,
    source_lines: list[str],
    nodes: dict[str, ast.FunctionDef],
) -> str:
    body_parts = []
    for name in group.functions:
        node = nodes[name]
        block = "".join(
            source_lines[source_start(node) - 1 : node.end_lineno]
        ).rstrip()
        body_parts.append(
            textwrap.indent(add_refresh_decorator(block), "    ")
        )

    exported = ",\n".join(
        f"        {name!r}: {name}" for name in group.functions
    )
    return (
        f'"""{group.description}"""\n\n'
        "from functools import wraps\n\n\n"
        f"def {group.registrar}(app, context_provider):\n"
        "    globals().update(context_provider())\n\n"
        "    def _refresh_context(view):\n"
        "        @wraps(view)\n"
        "        def wrapped(*args, **kwargs):\n"
        "            globals().update(context_provider())\n"
        "            return view(*args, **kwargs)\n"
        "        return wrapped\n\n"
        + "\n\n".join(body_parts)
        + "\n\n"
        "    return {\n"
        + exported
        + "\n    }\n"
    )


def registration_block() -> str:
    imports = "\n".join(
        f"from {group.path.with_suffix('').as_posix().replace('/', '.')} "
        f"import {group.registrar}"
        for group in GROUPS
    )
    registrations = "\n".join(
        f"globals().update({group.registrar}(app, lambda: globals()))"
        for group in GROUPS
    )
    return imports + "\n\n" + registrations + "\n"


def extract_routes(source: str) -> tuple[str, dict[Path, str]]:
    marker = "from routes.social_auth import register_social_auth_routes"
    if marker in source:
        return source, {}

    nodes = function_nodes(source)
    requested = [name for group in GROUPS for name in group.functions]
    missing = [name for name in requested if name not in nodes]
    if missing:
        raise RuntimeError(f"Missing social route functions: {missing}")

    source_lines = source.splitlines(keepends=True)
    generated = {
        group.path: render_group(group, source_lines, nodes)
        for group in GROUPS
    }

    selected = [nodes[name] for name in requested]
    first_line = min(source_start(node) for node in selected)
    removed_lines: set[int] = set()
    for node in selected:
        removed_lines.update(range(source_start(node), node.end_lineno + 1))

    output: list[str] = []
    for line_number, line in enumerate(source_lines, start=1):
        if line_number == first_line:
            output.append(registration_block())
            output.append("\n")
        if line_number not in removed_lines:
            output.append(line)

    normalized = "".join(output)
    while "\n\n\n\n" in normalized:
        normalized = normalized.replace("\n\n\n\n", "\n\n\n")
    return normalized, generated


def ensure_quality_guard() -> None:
    text = QUALITY_TEST_PATH.read_text(encoding="utf-8")
    marker = "def test_social_routes_are_split_by_responsibility():"
    if marker in text:
        return
    expected = ",\n".join(
        f"        Path({str(group.path.relative_to(ROOT))!r})"
        for group in GROUPS
    )
    addition = f'''\n\ndef test_social_routes_are_split_by_responsibility():
    app_path = Path('app.py')
    assert len(app_path.read_text(encoding='utf-8').splitlines()) <= 3200

    route_modules = {{
{expected}
    }}
    assert all(path.is_file() for path in route_modules)
    assert all(
        len(path.read_text(encoding='utf-8').splitlines()) <= 330
        for path in route_modules
    )
'''
    QUALITY_TEST_PATH.write_text(
        text.rstrip() + addition + "\n",
        encoding="utf-8",
    )


def main() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    updated, generated = extract_routes(source)
    if updated != source:
        APP_PATH.write_text(updated, encoding="utf-8")
    for path, content in generated.items():
        path.write_text(content, encoding="utf-8")
    ensure_quality_guard()


if __name__ == "__main__":
    main()
