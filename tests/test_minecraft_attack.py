import json
import os
import tempfile
import unittest

from scripts.minecraft_attack import (
    MAX_CONCURRENCY,
    MAX_REQUESTS,
    MinecraftAttackError,
    load_mob_mappings,
    send_mob_toggle,
    validate_attack_options,
)


class MinecraftAttackValidationTest(unittest.TestCase):
    def test_accepts_bounded_options(self):
        validate_attack_options("127.0.0.1", 25565, 10, 2, 1.5)

    def test_rejects_blank_host(self):
        with self.assertRaisesRegex(MinecraftAttackError, "Host is required"):
            validate_attack_options(" ", 25565, 10, 2, 1.5)

    def test_rejects_invalid_port(self):
        with self.assertRaisesRegex(MinecraftAttackError, "Port must"):
            validate_attack_options("127.0.0.1", 70000, 10, 2, 1.5)

    def test_rejects_too_many_requests(self):
        with self.assertRaisesRegex(MinecraftAttackError, "Requests must"):
            validate_attack_options("127.0.0.1", 25565, MAX_REQUESTS + 1, 2, 1.5)

    def test_rejects_too_much_concurrency(self):
        with self.assertRaisesRegex(MinecraftAttackError, "Concurrency must"):
            validate_attack_options("127.0.0.1", 25565, MAX_REQUESTS, MAX_CONCURRENCY + 1, 1.5)

    def test_rejects_concurrency_greater_than_requests(self):
        with self.assertRaisesRegex(MinecraftAttackError, "Concurrency cannot"):
            validate_attack_options("127.0.0.1", 25565, 1, 2, 1.5)

    def test_rejects_invalid_timeout(self):
        with self.assertRaisesRegex(MinecraftAttackError, "Timeout must"):
            validate_attack_options("127.0.0.1", 25565, 10, 2, 0)


class MinecraftMobConfigTest(unittest.TestCase):
    def write_config(self, data):
        config_path = os.path.join(self.temp_dir.name, "minecraft_mobs.json")
        with open(config_path, "w", encoding="utf-8") as config:
            json.dump(data, config)
        return config_path

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_loads_mob_mappings_from_config(self):
        config_path = self.write_config({"mobs": [{"id": "chicken", "name": "Chicken", "port": 25571}]})

        self.assertEqual(
            load_mob_mappings(config_path),
            [{"id": "chicken", "name": "Chicken", "port": 25571, "enabled": True}],
        )

    def test_rejects_duplicate_mob_ids(self):
        config_path = self.write_config({
            "mobs": [
                {"id": "chicken", "name": "Chicken", "port": 25571},
                {"id": "chicken", "name": "Chicken 2", "port": 25572},
            ]
        })

        with self.assertRaisesRegex(MinecraftAttackError, "Duplicate mob id"):
            load_mob_mappings(config_path)

    def test_rejects_invalid_mob_ports(self):
        config_path = self.write_config({"mobs": [{"id": "chicken", "name": "Chicken", "port": 70000}]})

        with self.assertRaisesRegex(MinecraftAttackError, "port must"):
            load_mob_mappings(config_path)

    def test_rejects_invalid_mob_toggle_state(self):
        config_path = self.write_config({"mobs": [{"id": "chicken", "name": "Chicken", "port": 25571}]})

        with self.assertRaisesRegex(MinecraftAttackError, "state must"):
            send_mob_toggle("127.0.0.1", "chicken", "maybe", config_path=config_path)


if __name__ == "__main__":
    unittest.main()
