"""Shared navigation metadata for breadcrumbs, section tabs, and quick search."""

from urllib.parse import urlsplit


STATIC_SEARCH_ITEMS = (
    ('Interfaces', '/', 'interfaces adapters home'),
    ('Network Scan', '/network-scan', 'scan discovery network'),
    ('Service Discovery', '/service-discovery', 'mdns upnp lldp services'),
    ('Port Scan', '/port-scan', 'ports services network'),
    ('Traceroute', '/traceroute', 'route path diagnostics'),
    ('Diagnostics', '/diagnostics', 'network troubleshooting'),
    ('Advanced Diagnostics', '/advanced-diagnostics', 'advanced troubleshooting'),
    ('Jobs', '/jobs', 'background jobs scans'),
    ('Device Inventory', '/inventory', 'devices clients records'),
    ('VLAN Investigations', '/vlans', 'vlan tags subnets segmentation pfsense probes'),
    ('Alerts', '/alerts', 'notifications devices'),
    ('Reports', '/reports', 'reports exports'),
    ('Evidence Vault', '/evidence', 'evidence notes artifacts'),
    ('Social Engineering', '/social-engineering', 'people profiles records'),
    ('Automotive', '/automotive', 'vehicles workshop'),
    ('VIN Lookup', '/automotive/vin', 'vehicle vin lookup'),
    ('Code Lookup', '/automotive/codes', 'dtc diagnostic codes'),
    ('Diagnostic Sessions', '/automotive/sessions', 'automotive sessions'),
    ('Setup Wizard', '/setup-wizard', 'first run configuration optional downloads'),
    ('Capabilities', '/capabilities', 'system capabilities'),
    ('Roadmap', '/roadmap', 'system roadmap'),
    ('My Account', '/account', 'profile password preferences'),
)

AUTOMOTIVE_SECTION_ITEMS = (
    ('Dashboard', '/automotive', ('/automotive',)),
    ('Vehicles', '/automotive#automotive-vehicles', ('/automotive/vehicles',)),
    ('Diagnostics', '/automotive/sessions', ('/automotive/sessions', '/automotive/parameters')),
    ('VIN Lookup', '/automotive/vin', ('/automotive/vin',)),
    ('Code Lookup', '/automotive/codes', ('/automotive/codes',)),
    ('Reports', '/automotive#automotive-reports', ('/automotive/reports',)),
    ('Databases', '/automotive#automotive-databases', ('/automotive/databases', '/automotive/imports')),
)

ACCOUNT_SECTION_ITEMS = (
    ('Profile', '/account#profile', ('/account',)),
    ('Preferences', '/account#preferences', ()),
    ('Security', '/account#security', ()),
)


def _value(item, name, default=''):
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _clean_path(value):
    parsed = urlsplit(str(value or '/'))
    path = parsed.path or '/'
    return path if path.startswith('/') else '/'


def _current_item(label, url=None):
    return {'label': str(label or '').strip() or 'Page', 'url': url}


def _breadcrumb_items(path, title, technologies):
    if path == '/':
        return []

    items = [_current_item('Home', '/')]
    lower_path = path.casefold()
    technology_map = {str(item).casefold(): str(item) for item in technologies if str(item).casefold() != 'loopback'}
    first_segment = lower_path.strip('/').split('/', 1)[0]

    if lower_path.startswith('/automotive'):
        items.append(_current_item('Automotive', None if path == '/automotive' else '/automotive'))
    elif lower_path.startswith('/clients/'):
        items.extend((_current_item('Records'), _current_item('Device Inventory', '/inventory')))
    elif lower_path.startswith('/vlans'):
        items.extend((_current_item('Records'), _current_item('VLAN Investigations', None if path == '/vlans' else '/vlans')))
    elif lower_path in {'/inventory', '/alerts', '/reports', '/evidence', '/social-engineering'}:
        items.append(_current_item('Records'))
    elif lower_path in {'/network-scan', '/service-discovery', '/port-scan', '/traceroute', '/diagnostics', '/advanced-diagnostics', '/jobs', '/red-team', '/minecraft-attack', '/train-controller'}:
        items.append(_current_item('Tools'))
    elif lower_path in {'/capabilities', '/roadmap', '/users', '/setup-wizard'}:
        items.append(_current_item('System'))
    elif lower_path.startswith('/account'):
        items.append(_current_item('Account'))
    elif first_segment in technology_map:
        technology = technology_map[first_segment]
        items.append(_current_item('Interfaces', '/'))
        items.append(_current_item(technology, None if lower_path == f'/{first_segment}' else f'/{first_segment}'))

    if not items or items[-1].get('url') is not None:
        items.append(_current_item(title))
    elif items[-1]['label'].casefold() != str(title or '').casefold() and path not in {'/automotive'}:
        items.append(_current_item(title))
    return items


def _section_items(path):
    lower_path = path.casefold()
    source = None
    if lower_path.startswith('/automotive'):
        source = AUTOMOTIVE_SECTION_ITEMS
    elif lower_path.startswith('/account'):
        source = ACCOUNT_SECTION_ITEMS
    if not source:
        return []

    items = []
    for label, url, prefixes in source:
        active = False
        for prefix in prefixes:
            if prefix == '/automotive':
                active = lower_path == '/automotive'
            elif prefix == '/account':
                active = lower_path == '/account'
            else:
                active = lower_path.startswith(prefix)
            if active:
                break
        items.append({'label': label, 'url': url, 'active': active})
    return items


def _search_items(interfaces, technologies, favourites, include_admin=False):
    items = [
        {'label': label, 'url': url, 'keywords': keywords, 'favourite': False}
        for label, url, keywords in STATIC_SEARCH_ITEMS
        if include_admin or url != '/setup-wizard'
    ]
    for technology in sorted((str(item) for item in technologies if str(item).casefold() != 'loopback'), key=str.casefold):
        items.append({
            'label': f'{technology} interfaces',
            'url': f'/{technology.casefold()}',
            'keywords': f'interface adapter {technology}',
            'favourite': False,
        })
    for interface in interfaces:
        technology = str(_value(interface, 'interface_type')).strip()
        name = str(_value(interface, 'name')).strip()
        if not technology or not name or technology.casefold() == 'loopback':
            continue
        items.append({
            'label': name,
            'url': f'/{technology.casefold()}/{name}',
            'keywords': f'interface adapter {technology} {name}',
            'favourite': False,
        })
    for favourite in favourites:
        label = str(favourite.get('label') or '').strip()
        url = _clean_path(favourite.get('url'))
        if label:
            items.insert(0, {
                'label': label,
                'url': url,
                'keywords': f'favourite favorite saved {label}',
                'favourite': True,
            })

    deduplicated = []
    seen = set()
    for item in items:
        key = (item['url'], item['label'].casefold())
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(item)
    return deduplicated


def build_navigation_context(path, title, endpoint, user, network_technologies, interfaces):
    """Return template-ready navigation state for the current request."""
    current_path = _clean_path(path)
    user = user or {}
    preferences = dict(user.get('preferences') or {})
    favourites = [
        {'label': str(item.get('label') or '').strip(), 'url': _clean_path(item.get('url'))}
        for item in preferences.get('favourites', [])
        if isinstance(item, dict) and str(item.get('label') or '').strip()
    ][:12]
    technologies = sorted((str(item) for item in network_technologies), key=str.casefold)
    interfaces = list(interfaces or [])
    return {
        'breadcrumbs': _breadcrumb_items(current_path, title, technologies),
        'section_items': _section_items(current_path),
        'search_items': _search_items(
            interfaces,
            technologies,
            favourites,
            include_admin=user.get('role') == 'admin',
        ),
        'favourites': favourites,
        'current_url': current_path,
        'current_label': str(title or 'Current page'),
        'endpoint': endpoint,
    }