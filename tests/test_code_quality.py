import ast
from collections import Counter
from pathlib import Path

import app as app_module


def test_app_has_no_duplicate_top_level_definitions():
    tree = ast.parse(Path('app.py').read_text(encoding='utf-8'))
    names = [node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]

    assert not [name for name, count in Counter(names).items() if count > 1]


def test_roadmap_titles_are_unique_and_in_their_correct_sections():
    entries = [(section['title'], item['title']) for section in app_module.ROADMAP_SECTIONS for item in section['items']]
    title_counts = Counter(title for _, title in entries)

    assert not [title for title, count in title_counts.items() if count > 1]
    train_titles = {title for section, title in entries if section == 'Train Controller integration'}
    assert all(title.startswith('Train Controller') for title in train_titles)


def test_header_references_only_the_retained_bootstrap_builds():
    header = Path('templates/_header.html').read_text(encoding='utf-8')

    assert "css/bootstrap.min.css" in header
    assert "js/bootstrap.min.js" in header
    assert 'bootstrap.bundle' not in header

def test_app_is_split_into_manageable_modules():
    app_path = Path('app.py')
    assert len(app_path.read_text(encoding='utf-8').splitlines()) <= 4000

    expected_modules = {
        Path('app_support/roadmap.py'),
        Path('app_support/bluetooth_actions.py'),
        Path('app_support/identifiers.py'),
    }
    assert all(path.is_file() for path in expected_modules)

def test_discovery_parsers_are_extracted():
    app_path = Path('app.py')
    assert len(app_path.read_text(encoding='utf-8').splitlines()) <= 3750
    assert Path('app_support/network_discovery.py').is_file()

def test_social_routes_are_split_by_responsibility():
    app_path = Path('app.py')
    assert len(app_path.read_text(encoding='utf-8').splitlines()) <= 3200

    route_modules = {
        Path('routes/social_auth.py'),
        Path('routes/social_profiles.py'),
        Path('routes/social_profile_resources.py'),
        Path('routes/social_profile_transfer.py')
    }
    assert all(path.is_file() for path in route_modules)
    assert all(
        len(path.read_text(encoding='utf-8').splitlines()) <= 330
        for path in route_modules
    )

def test_stateful_support_domains_are_extracted():
    assert len(Path('app.py').read_text(encoding='utf-8').splitlines()) <= 2550
    assert len(Path('app_support/client_intelligence.py').read_text(encoding='utf-8').splitlines()) <= 430
    assert len(Path('app_support/client_services.py').read_text(encoding='utf-8').splitlines()) <= 330
    assert len(Path('app_support/passive_monitoring.py').read_text(encoding='utf-8').splitlines()) <= 300

