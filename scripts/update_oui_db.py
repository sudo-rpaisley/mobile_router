"""Download a local IEEE OUI database for offline MAC/Bluetooth vendor lookup."""
import csv
import os
import urllib.request

IEEE_OUI_CSV_URL = 'https://standards-oui.ieee.org/oui/oui.csv'
IEEE_OUI_CSV_URLS = [
    IEEE_OUI_CSV_URL,
    'https://standards.ieee.org/wp-content/uploads/import/documents/standards/products-programs/regauth/oui/oui.csv',
]
DEFAULT_OUTPUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'oui', 'oui_db.csv')


def _normalize_assignment(value):
    cleaned = ''.join(ch for ch in str(value or '') if ch.isalnum())[:6].lower()
    if len(cleaned) != 6:
        return None
    return ':'.join(cleaned[index:index + 2] for index in range(0, 6, 2))


def _fetch_text(url, opener=urllib.request.urlopen):
    request = urllib.request.Request(url, headers={'User-Agent': 'MobileRouterOUIUpdater/1.0'})
    with opener(request, timeout=30) as response:
        return response.read().decode('utf-8-sig')


def download_oui_database(output_path=DEFAULT_OUTPUT, url=None, opener=urllib.request.urlopen):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    errors = []
    text = None
    for candidate in ([url] if url else IEEE_OUI_CSV_URLS):
        try:
            text = _fetch_text(candidate, opener=opener)
            break
        except Exception as exc:
            errors.append(f'{candidate}: {exc}')
    if text is None:
        raise RuntimeError('Unable to download IEEE OUI database. Tried: ' + '; '.join(errors))

    rows = csv.DictReader(text.splitlines())
    entries = []
    for row in rows:
        prefix = _normalize_assignment(row.get('Assignment'))
        name = (row.get('Organization Name') or '').strip()
        if prefix and name:
            entries.append((prefix, name))

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        for prefix, name in sorted(set(entries)):
            f.write(f'{prefix},{name}\n')
    return output_path, len(entries)


if __name__ == '__main__':
    path, count = download_oui_database()
    print(f'Wrote {count} OUI entries to {path}')
