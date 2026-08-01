from pathlib import Path


def line_count(path):
    return len(Path(path).read_text(encoding='utf-8').splitlines())


def test_local_virtual_environments_are_not_committed():
    for directory in ('mobileRouter', '.venv', 'venv', 'env'):
        assert not Path(directory).exists()


def test_legacy_facades_remain_small():
    assert line_count('scripts/networkScan.py') <= 100
    assert line_count('services/social_profiles.py') <= 100


def test_extracted_modules_remain_focused():
    limits = {
        'scripts/network/discovery.py': 250,
        'scripts/network/classification.py': 200,
        'scripts/network/passive_capture.py': 160,
        'services/social_profile/validation.py': 400,
        'services/social_profile/storage.py': 400,
        'services/social_profile/credentials.py': 220,
        'services/social_profile/devices.py': 180,
    }
    for path, maximum in limits.items():
        assert line_count(path) <= maximum, f'{path} has grown beyond {maximum} lines'


def test_application_monolith_does_not_grow_during_migration():
    assert line_count('app.py') <= 4400
