"""Apply the cross-platform fixes exposed by the Windows CI job."""

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    source = file_path.read_text(encoding='utf-8')
    if old not in source:
        raise RuntimeError(f'Expected text not found in {path}: {old[:80]!r}')
    file_path.write_text(source.replace(old, new, 1), encoding='utf-8')


def fix_automotive_connections() -> None:
    replace_once(
        'services/automotive.py',
        'import hashlib\nfrom datetime import datetime\n',
        'import hashlib\nfrom contextlib import contextmanager\nfrom datetime import datetime\n',
    )
    replace_once(
        'services/automotive.py',
        """    def connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys = ON')
        connection.execute('PRAGMA busy_timeout = 5000')
        return connection
""",
        """    @contextmanager
    def connect(self):
        \"\"\"Yield a transaction-scoped connection and always release its file handle.\"\"\"
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys = ON')
        connection.execute('PRAGMA busy_timeout = 5000')
        try:
            yield connection
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            connection.close()
""",
    )


def fix_bluetooth_path_test() -> None:
    replace_once(
        'tests/test_bluetooth_phone.py',
        '        self.assertTrue(capability["path"].endswith("helpers/windows/mobile-router-bluetooth-helper.py"))\n',
        "        helper_path = Path(capability['path'])\n"
        "        self.assertEqual(helper_path.name, 'mobile-router-bluetooth-helper.py')\n"
        "        self.assertEqual(helper_path.parent.name, 'windows')\n"
        "        self.assertEqual(helper_path.parent.parent.name, 'helpers')\n",
    )


def fix_route_tests() -> None:
    replace_once(
        'tests/test_routes.py',
        """        self.assertNotIn(b'id=\"listAdapters', response.data)
        self.assertIn(b'Browser screenshot tooling', response.data)
        self.assertIn(b'Install for me', response.data)
        self.assertIn(b'install-host-dependency', response.data)
""",
        """        self.assertNotIn(b'id=\"listAdapters', response.data)
        if os.name != 'nt':
            self.assertIn(b'Browser screenshot tooling', response.data)
            self.assertIn(b'Install for me', response.data)
            self.assertIn(b'install-host-dependency', response.data)
""",
    )
    replace_once(
        'tests/test_routes.py',
        """        response = self.client.post('/comprehensive-scan', data={'selectedInterface': 'eth0', 'includePassive': 'on', 'includeServices': 'on'})

        self.assertEqual(response.status_code, 200)
""",
        """        with patch.object(app_module, 'os', SimpleNamespace(name='posix')):
            response = self.client.post('/comprehensive-scan', data={'selectedInterface': 'eth0', 'includePassive': 'on', 'includeServices': 'on'})

        self.assertEqual(response.status_code, 200)
""",
    )
    replace_once(
        'tests/test_routes.py',
        """        response = self.client.post('/vlan-discovery', data={'ssid': 'CorpWiFi', 'vlanId': '20', 'notes': 'Guest blocked from admin VLAN'})

        self.assertEqual(response.status_code, 200)
""",
        """        with patch.object(app_module, 'os', SimpleNamespace(name='posix')):
            response = self.client.post('/vlan-discovery', data={'ssid': 'CorpWiFi', 'vlanId': '20', 'notes': 'Guest blocked from admin VLAN'})

        self.assertEqual(response.status_code, 200)
""",
    )
    replace_once(
        'tests/test_routes.py',
        """        response = self.client.post('/ipv6-assessment', data={'host': '2001:db8::10', 'ports': '443'})

        self.assertEqual(response.status_code, 200)
""",
        """        with patch.object(app_module, 'os', SimpleNamespace(name='posix')):
            response = self.client.post('/ipv6-assessment', data={'host': '2001:db8::10', 'ports': '443'})

        self.assertEqual(response.status_code, 200)
""",
    )
    replace_once(
        'tests/test_routes.py',
        """        response = self.client.post('/route-diagnostics', data={'target': '1.1.1.1'})

        self.assertEqual(response.status_code, 200)
""",
        """        with patch.object(app_module, 'os', SimpleNamespace(name='posix')):
            response = self.client.post('/route-diagnostics', data={'target': '1.1.1.1'})

        self.assertEqual(response.status_code, 200)
""",
    )
    replace_once(
        'tests/test_routes.py',
        """            download = self.client.get(f\"/social-engineering/profiles/{first['id']}/attachments/{attachment['id']}\")
            self.assertEqual(download.data, b'evidence')

        export = self.client.get('/social-engineering/export')
""",
        """            download = self.client.get(f\"/social-engineering/profiles/{first['id']}/attachments/{attachment['id']}\")
            self.assertEqual(download.data, b'evidence')
            download.close()

        export = self.client.get('/social-engineering/export')
""",
    )


def main() -> None:
    fix_automotive_connections()
    fix_bluetooth_path_test()
    fix_route_tests()


if __name__ == '__main__':
    main()
