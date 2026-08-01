"""Move all remaining Flask route handlers into focused registrar modules."""

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
class RouteFamily:
    key: str
    path: Path
    registrar: str
    description: str
    maximum_lines: int


FAMILIES = (
    RouteFamily(
        "core",
        ROUTES_DIR / "core_routes.py",
        "register_core_routes",
        "Core pages, adapter exports, evidence, reports, and contact routes.",
        380,
    ),
    RouteFamily(
        "clients",
        ROUTES_DIR / "client_routes.py",
        "register_client_routes",
        "Inventory, client intelligence, alerts, and scan-result routes.",
        520,
    ),
    RouteFamily(
        "diagnostics",
        ROUTES_DIR / "diagnostic_routes.py",
        "register_diagnostic_routes",
        "Port scans, jobs, diagnostics, and service-discovery routes.",
        420,
    ),
    RouteFamily(
        "interfaces",
        ROUTES_DIR / "interface_routes.py",
        "register_interface_routes",
        "Wireless, Bluetooth, adapter state, and interface-detail routes.",
        480,
    ),
    RouteFamily(
        "labs",
        ROUTES_DIR / "lab_routes.py",
        "register_lab_routes",
        "Authorised network and wireless laboratory action routes.",
        400,
    ),
)
FAMILY_BY_KEY = {family.key: family for family in FAMILIES}


LAB_PATHS = {
    "/syn-flood",
    "/syn-flood-broadcast",
    "/spoof-mac",
    "/beacon-advertise",
    "/deauth",
    "/evil-twin-lab",
    "/pineap-lab",
    "/handshake-lab",
    "/handshake-lab.<fmt>",
    "/aireplay-deauth",
}
CLIENT_PREFIXES = (
    "/inventory",
    "/alerts",
    "/clients",
    "/scheduled-checks",
    "/active-scan",
    "/passive",
    "/comprehensive-scan",
    "/http-previews",
)
DIAGNOSTIC_PREFIXES = (
    "/port-scan",
    "/jobs",
    "/traceroute",
    "/ping",
    "/route-diagnostics",
    "/mdns",
    "/upnp",
    "/neighbor",
    "/vlan",
    "/egress",
    "/iperf3",
    "/snmp",
    "/ipv6",
)
INTERFACE_PREFIXES = (
    "/wireless",
    "/interfaces",
    "/wlan",
    "/scan-jobs",
    "/bluetooth",
)


def route_path(node: ast.FunctionDef) -> str | None:
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        function = decorator.func
        if not (
            isinstance(function, ast.Attribute)
            and function.attr == "route"
            and isinstance(function.value, ast.Name)
            and function.value.id == "app"
        ):
            continue
        if decorator.args and isinstance(decorator.args[0], ast.Constant):
            value = decorator.args[0].value
            return value if isinstance(value, str) else None
    return None


def classify(path: str) -> str:
    if path in LAB_PATHS:
        return "labs"
    if path.startswith(CLIENT_PREFIXES):
        return "clients"
    if path.startswith(DIAGNOSTIC_PREFIXES):
        return "diagnostics"
    if path.startswith(INTERFACE_PREFIXES) or path.startswith("/<interface_type>"):
        return "interfaces"
    return "core"


def source_start(node: ast.FunctionDef) -> int:
    return min(
        [node.lineno, *[decorator.lineno for decorator in node.decorator_list]]
    )


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


def render_family(
    family: RouteFamily,
    members: list[ast.FunctionDef],
    source_lines: list[str],
) -> str:
    bodies = []
    for node in members:
        block = "".join(
            source_lines[source_start(node) - 1 : node.end_lineno]
        ).rstrip()
        bodies.append(
            textwrap.indent(add_refresh_decorator(block), "    ")
        )
    exports = ",\n".join(
        f"        {node.name!r}: {node.name}" for node in members
    )
    return (
        f'"""{family.description}"""\n\n'
        "from functools import wraps\n\n\n"
        f"def {family.registrar}(app, context_provider):\n"
        "    globals().update(context_provider())\n\n"
        "    def _refresh_context(view):\n"
        "        @wraps(view)\n"
        "        def wrapped(*args, **kwargs):\n"
        "            globals().update(context_provider())\n"
        "            return view(*args, **kwargs)\n"
        "        return wrapped\n\n"
        + "\n\n".join(bodies)
        + "\n\n"
        "    return {\n"
        + exports
        + "\n    }\n"
    )


def registration_block(active_families: list[RouteFamily]) -> str:
    imports = "\n".join(
        f"from {module_name(family.path)} import {family.registrar}"
        for family in active_families
    )
    registrations = "\n".join(
        f"globals().update({family.registrar}(app, lambda: globals()))"
        for family in active_families
    )
    return imports + "\n\n" + registrations + "\n"


def extract(source: str) -> tuple[str, dict[Path, str]]:
    marker = "from routes.core_routes import register_core_routes"
    if marker in source:
        return source, {}

    tree = ast.parse(source)
    route_nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and route_path(node) is not None
    ]
    if not route_nodes:
        raise RuntimeError("No remaining app.route handlers were found")

    grouped: dict[str, list[ast.FunctionDef]] = {
        family.key: [] for family in FAMILIES
    }
    for node in route_nodes:
        grouped[classify(route_path(node) or "")].append(node)

    active_families = [
        family for family in FAMILIES if grouped[family.key]
    ]
    source_lines = source.splitlines(keepends=True)
    generated = {
        family.path: render_family(
            family,
            grouped[family.key],
            source_lines,
        )
        for family in active_families
    }

    first_line = min(source_start(node) for node in route_nodes)
    removed: set[int] = set()
    for node in route_nodes:
        removed.update(range(source_start(node), node.end_lineno + 1))

    output = []
    for line_number, line in enumerate(source_lines, start=1):
        if line_number == first_line:
            output.append(registration_block(active_families))
            output.append("\n")
        if line_number not in removed:
            output.append(line)

    normalized = "".join(output)
    while "\n\n\n\n" in normalized:
        normalized = normalized.replace("\n\n\n\n", "\n\n\n")
    return normalized, generated


def ensure_quality_guard() -> None:
    text = QUALITY_TEST_PATH.read_text(encoding="utf-8")
    marker = "def test_app_entry_point_is_composition_focused():"
    if marker in text:
        return
    module_checks = "\n".join(
        f"    assert len(Path({str(family.path.relative_to(ROOT))!r}).read_text(encoding='utf-8').splitlines()) <= {family.maximum_lines}"
        for family in FAMILIES
    )
    addition = f'''\n\ndef test_app_entry_point_is_composition_focused():
    app_source = Path('app.py').read_text(encoding='utf-8')
    assert len(app_source.splitlines()) <= 1550
    assert '@app.route' not in app_source
{module_checks}
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
