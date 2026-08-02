import ast
from collections import Counter
from pathlib import Path

import app as app_module


def line_count(path):
    return len(Path(path).read_text(encoding='utf-8').splitlines())


def test_app_has_no_duplicate_top_level_definitions():
    tree = ast.parse(Path('app.py').read_text(encoding='utf-8'))
    names = [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]

    assert not [name for name, count in Counter(names).items() if count > 1]


def test_application_imports_and_exposes_flask_app():
    assert app_module.app is not None
    assert app_module.app.name == 'app'


def test_registered_route_rules_are_unique():
    route_keys = [
        (
            rule.rule,
            tuple(sorted(set(rule.methods or ()) - {'HEAD', 'OPTIONS'})),
        )
        for rule in app_module.app.url_map.iter_rules()
    ]
    duplicates = [
        key for key, count in Counter(route_keys).items() if count > 1
    ]

    assert not duplicates


def test_expected_route_registrars_are_called_once():
    app_source = Path('app.py').read_text(encoding='utf-8')
    registrars = (
        'register_core_routes',
        'register_client_routes',
        'register_diagnostic_routes',
        'register_interface_routes',
        'register_lab_routes',
        'register_social_auth_routes',
        'register_social_profile_routes',
        'register_social_profile_resource_routes',
        'register_social_profile_identity_routes',
        'register_social_profile_transfer_routes',
    )

    for registrar in registrars:
        assert app_source.count(f'{registrar}(app') == 1, registrar


def test_roadmap_titles_are_unique_and_in_their_correct_sections():
    entries = [
        (section['title'], item['title'])
        for section in app_module.ROADMAP_SECTIONS
        for item in section['items']
    ]
    title_counts = Counter(title for _, title in entries)

    assert not [title for title, count in title_counts.items() if count > 1]
    train_titles = {
        title for section, title in entries
        if section == 'Train Controller integration'
    }
    assert all(title.startswith('Train Controller') for title in train_titles)


def test_header_references_only_the_retained_bootstrap_builds():
    header = Path('templates/_header.html').read_text(encoding='utf-8')

    assert "css/bootstrap.min.css" in header
    assert "js/bootstrap.min.js" in header
    assert 'bootstrap.bundle' not in header


def test_app_is_split_into_manageable_modules():
    assert line_count('app.py') <= 1550
    expected_modules = {
        Path('app_support/roadmap.py'),
        Path('app_support/bluetooth_actions.py'),
        Path('app_support/identifiers.py'),
    }
    assert all(path.is_file() for path in expected_modules)


def test_discovery_parsers_are_extracted():
    assert line_count('app.py') <= 1550
    assert Path('app_support/network_discovery.py').is_file()


def test_social_routes_are_split_by_responsibility():
    assert line_count('app.py') <= 1550
    route_modules = {
        Path('routes/social_auth.py'),
        Path('routes/social_profiles.py'),
        Path('routes/social_profile_resources.py'),
        Path('routes/social_profile_transfer.py'),
    }
    assert all(path.is_file() for path in route_modules)
    assert all(line_count(path) <= 330 for path in route_modules)


def test_stateful_support_domains_are_extracted():
    assert line_count('app.py') <= 1550
    limits = {
        'app_support/client_intelligence.py': 80,
        'app_support/client_intelligence_dependencies.py': 100,
        'app_support/client_identity.py': 220,
        'app_support/client_metadata.py': 180,
        'app_support/client_profile.py': 340,
        'app_support/client_services.py': 330,
        'app_support/passive_monitoring.py': 80,
        'app_support/passive_monitoring_dependencies.py': 100,
        'app_support/passive_analytics.py': 220,
        'app_support/passive_monitor_control.py': 220,
        'app_support/comprehensive_scan.py': 220,
    }
    for path, maximum in limits.items():
        assert Path(path).is_file(), path
        assert line_count(path) <= maximum, f'{path} has grown beyond {maximum} lines'
    assert all(
        Path(path).is_file()
        for path in (
            'app_support/client_service_dependencies.py',
            'app_support/client_service_http.py',
            'app_support/client_service_scheduling.py',
        )
    )


def test_app_entry_point_is_composition_focused():
    app_source = Path('app.py').read_text(encoding='utf-8')
    assert len(app_source.splitlines()) <= 1550
    assert '@app.route' not in app_source
    limits = {
        'routes/core_routes.py': 380,
        'routes/client_routes.py': 520,
        'routes/diagnostic_routes.py': 420,
        'routes/interface_routes.py': 480,
        'routes/lab_routes.py': 400,
    }
    for path, maximum in limits.items():
        assert line_count(path) <= maximum


def test_migrated_modules_use_non_mutating_dependency_access():
    migrated_paths = (
        'routes/core_routes.py',
        'app_support/client_services.py',
        'app_support/client_intelligence.py',
        'app_support/client_intelligence_dependencies.py',
        'app_support/client_identity.py',
        'app_support/client_metadata.py',
        'app_support/client_profile.py',
        'app_support/passive_monitoring.py',
        'app_support/passive_monitoring_dependencies.py',
        'app_support/passive_analytics.py',
        'app_support/passive_monitor_control.py',
        'app_support/comprehensive_scan.py',
    )
    migrated_sources = {
        path: Path(path).read_text(encoding='utf-8')
        for path in migrated_paths
    }
    for path, source in migrated_sources.items():
        assert 'globals().update' not in source, path
        assert 'bind_context' not in source, path
        assert 'context_refresher' not in source, path

    assert 'dependency_proxy' in migrated_sources['routes/core_routes.py']
    assert 'dependency_proxy' in migrated_sources[
        'app_support/client_intelligence_dependencies.py'
    ]
    assert 'dependency_proxy' in migrated_sources[
        'app_support/passive_monitoring_dependencies.py'
    ]
    assert 'client_service_dependencies' in Path(
        'app_support/client_service_http.py'
    ).read_text(encoding='utf-8')
