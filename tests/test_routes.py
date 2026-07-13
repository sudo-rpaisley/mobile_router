import unittest
from types import SimpleNamespace
from unittest.mock import patch

import app as app_module
from app import app


class RouteSmokeTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_capabilities_page_renders(self):
        response = self.client.get('/capabilities')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Runtime Capabilities', response.data)


    def test_interface_type_preserves_uppercase_vpn(self):
        vpn_interface = SimpleNamespace(
            name='VPN Adapter',
            interface_type='VPN',
            addresses=[],
            manufacturer='Unknown',
            state='UP',
        )
        with patch.object(app_module, 'network_interfaces', [vpn_interface]):
            response = self.client.get('/vpn')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'VPN Interfaces', response.data)
        self.assertIn(b'VPN Adapter', response.data)

    def test_minecraft_page_renders(self):
        response = self.client.get('/minecraft-attack')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Minecraft Attack Lab', response.data)

    def test_minecraft_status_requires_authorization(self):
        response = self.client.post('/minecraft-attack', data={})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['message'], 'Authorization confirmation is required')

    def test_minecraft_mob_toggle_requires_authorization(self):
        response = self.client.post('/minecraft-attack/mobs/chicken/toggle', data={})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['message'], 'Authorization confirmation is required')

    @patch('routes.minecraft.send_mob_toggle')
    def test_minecraft_mob_toggle_success(self, send_mob_toggle):
        send_mob_toggle.return_value = {
            'mob': {'id': 'chicken', 'name': 'Chicken', 'port': 25571, 'enabled': True},
            'state': 'on',
        }

        response = self.client.post('/minecraft-attack/mobs/chicken/toggle', data={
            'authorized': 'true',
            'host': '127.0.0.1',
            'state': 'on',
            'timeout': '1.5',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['result']['state'], 'on')


if __name__ == '__main__':
    unittest.main()
