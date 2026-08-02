"""Route focused support-module helper calls through the application provider."""

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    source = file_path.read_text(encoding='utf-8')
    if old not in source:
        raise RuntimeError(f'Expected text not found in {path}: {old!r}')
    file_path.write_text(source.replace(old, new, 1), encoding='utf-8')


def main() -> None:
    replace_once(
        'app_support/client_profile.py',
        "from app_support.client_identity import (\n    _dhcp_lease_display_name,\n    _ttl_os_hint,\n    enrich_ip_client_display_name,\n)\n",
        '',
    )
    replacements = (
        ('device = enrich_ip_client_display_name(', 'device = deps.enrich_ip_client_display_name('),
        ("dhcp_name = _dhcp_lease_display_name(host) if host else ''", "dhcp_name = deps._dhcp_lease_display_name(host) if host else ''"),
        ("'os_hint': _ttl_os_hint(reachability),", "'os_hint': deps._ttl_os_hint(reachability),"),
        ("'relationships': client_relationship_map(identifier),", "'relationships': deps.client_relationship_map(identifier),"),
        ("'health': client_health_summary(device, host),", "'health': deps.client_health_summary(device, host),"),
        ("'timeline': client_timeline(host, device),", "'timeline': deps.client_timeline(host, device),"),
        ("for item in client_profile_export(identifier).get('evidence', [])[:8]:", "for item in deps.client_profile_export(identifier).get('evidence', [])[:8]:"),
    )
    for old, new in replacements:
        replace_once('app_support/client_profile.py', old, new)
    replace_once(
        'app_support/client_identity.py',
        'existing = display_name_for_inventory_device(device, ip)',
        'existing = deps.display_name_for_inventory_device(device, ip)',
    )
    replace_once(
        'app_support/client_identity.py',
        'detected = _dhcp_lease_display_name(ip)',
        'detected = deps._dhcp_lease_display_name(ip)',
    )
    replace_once(
        'app_support/client_metadata.py',
        'updated = update_client_metadata(',
        'updated = deps.update_client_metadata(',
    )


if __name__ == '__main__':
    main()
