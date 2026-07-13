import json
import os
import socket
import struct
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, List, Optional

MIN_PORT = 1
MAX_PORT = 65535
MIN_REQUESTS = 1
MAX_REQUESTS = 100
MIN_CONCURRENCY = 1
MAX_CONCURRENCY = 20
MIN_TIMEOUT = 0.1
MAX_TIMEOUT = 5.0
MOB_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "minecraft_mobs.json")
MOB_TOGGLE_STATES = {"on", "off"}


class MinecraftAttackError(ValueError):
    """Raised when a Minecraft load-test request is invalid."""


@dataclass
class MinecraftAttackResult:
    attempted: int
    successful: int
    failed: int
    elapsed_seconds: float
    sample_status: Optional[Dict]
    errors: Dict[str, int]

    def to_dict(self) -> Dict:
        return {
            "attempted": self.attempted,
            "successful": self.successful,
            "failed": self.failed,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "sample_status": self.sample_status,
            "errors": self.errors,
        }


def validate_attack_options(host: str, port: int, requests: int, concurrency: int, timeout: float) -> None:
    if not host or not host.strip():
        raise MinecraftAttackError("Host is required")

    if port < MIN_PORT or port > MAX_PORT:
        raise MinecraftAttackError(f"Port must be between {MIN_PORT} and {MAX_PORT}")

    if requests < MIN_REQUESTS or requests > MAX_REQUESTS:
        raise MinecraftAttackError(f"Requests must be between {MIN_REQUESTS} and {MAX_REQUESTS}")

    if concurrency < MIN_CONCURRENCY or concurrency > MAX_CONCURRENCY:
        raise MinecraftAttackError(f"Concurrency must be between {MIN_CONCURRENCY} and {MAX_CONCURRENCY}")

    if concurrency > requests:
        raise MinecraftAttackError("Concurrency cannot be greater than requests")

    if timeout < MIN_TIMEOUT or timeout > MAX_TIMEOUT:
        raise MinecraftAttackError(f"Timeout must be between {MIN_TIMEOUT} and {MAX_TIMEOUT} seconds")


def load_mob_mappings(config_path: str = MOB_CONFIG_PATH) -> List[Dict]:
    """Load GUI mob toggle metadata from a JSON config file."""
    with open(config_path, "r", encoding="utf-8") as config_file:
        data = json.load(config_file)

    mobs = data.get("mobs", [])
    if not isinstance(mobs, list):
        raise MinecraftAttackError("Mob config must contain a mobs list")

    normalized_mobs = []
    seen_ids = set()
    for mob in mobs:
        mob_id = str(mob.get("id", "")).strip()
        name = str(mob.get("name", "")).strip()
        port = mob.get("port")
        enabled = bool(mob.get("enabled", True))

        if not mob_id or not name:
            raise MinecraftAttackError("Each mob config entry needs an id and name")

        if mob_id in seen_ids:
            raise MinecraftAttackError(f"Duplicate mob id configured: {mob_id}")

        if not isinstance(port, int) or port < MIN_PORT or port > MAX_PORT:
            raise MinecraftAttackError(f"Mob {mob_id} port must be between {MIN_PORT} and {MAX_PORT}")

        normalized_mobs.append({"id": mob_id, "name": name, "port": port, "enabled": enabled})
        seen_ids.add(mob_id)

    return normalized_mobs


def get_mob_mapping(mob_id: str, config_path: str = MOB_CONFIG_PATH) -> Dict:
    for mob in load_mob_mappings(config_path):
        if mob["id"] == mob_id and mob["enabled"]:
            return mob
    raise MinecraftAttackError("Unknown or disabled mob")


def send_mob_toggle(host: str, mob_id: str, state: str, timeout: float = 1.5, config_path: str = MOB_CONFIG_PATH) -> Dict:
    """Send an on/off mob toggle command to the configured mob control port."""
    if not host or not host.strip():
        raise MinecraftAttackError("Host is required")

    if state not in MOB_TOGGLE_STATES:
        raise MinecraftAttackError("Mob state must be on or off")

    if timeout < MIN_TIMEOUT or timeout > MAX_TIMEOUT:
        raise MinecraftAttackError(f"Timeout must be between {MIN_TIMEOUT} and {MAX_TIMEOUT} seconds")

    mob = get_mob_mapping(mob_id, config_path)
    command = f"{mob['id']}:{state}\n".encode("utf-8")
    with socket.create_connection((host.strip(), mob["port"]), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(command)

    return {"mob": mob, "state": state}


def _pack_varint(value: int) -> bytes:
    data = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            byte |= 0x80
        data.append(byte)
        if not value:
            return bytes(data)


def _read_varint(sock: socket.socket) -> int:
    value = 0
    for position in range(5):
        raw = sock.recv(1)
        if not raw:
            raise MinecraftAttackError("Connection closed while reading response")
        byte = raw[0]
        value |= (byte & 0x7F) << (7 * position)
        if not byte & 0x80:
            return value
    raise MinecraftAttackError("Received an invalid VarInt response")


def _pack_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return _pack_varint(len(encoded)) + encoded


def _pack_packet(packet_id: int, payload: bytes = b"") -> bytes:
    packet = _pack_varint(packet_id) + payload
    return _pack_varint(len(packet)) + packet


def query_status(host: str, port: int = 25565, timeout: float = 1.5, protocol_version: int = 760) -> Dict:
    """Query a Minecraft Java server status response using the standard status protocol."""
    host = host.strip()
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        handshake = (
            _pack_varint(protocol_version)
            + _pack_string(host)
            + struct.pack(">H", port)
            + _pack_varint(1)
        )
        sock.sendall(_pack_packet(0, handshake))
        sock.sendall(_pack_packet(0))

        _read_varint(sock)
        packet_id = _read_varint(sock)
        if packet_id != 0:
            raise MinecraftAttackError("Unexpected Minecraft status response")

        payload_length = _read_varint(sock)
        payload = bytearray()
        while len(payload) < payload_length:
            chunk = sock.recv(payload_length - len(payload))
            if not chunk:
                raise MinecraftAttackError("Connection closed while reading status payload")
            payload.extend(chunk)

    return json.loads(payload.decode("utf-8"))


def run_status_load_test(host: str, port: int, requests: int, concurrency: int, timeout: float) -> MinecraftAttackResult:
    """Run a bounded Minecraft status-query load test against an authorized test server."""
    validate_attack_options(host, port, requests, concurrency, timeout)
    host = host.strip()
    successful = 0
    errors: Dict[str, int] = {}
    sample_status = None
    started = time.monotonic()

    def attempt() -> Dict:
        return query_status(host, port, timeout)

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(attempt) for _ in range(requests)]
        for future in as_completed(futures):
            try:
                status = future.result()
                successful += 1
                if sample_status is None:
                    sample_status = status
            except Exception as e:
                message = str(e) or e.__class__.__name__
                errors[message] = errors.get(message, 0) + 1

    elapsed = time.monotonic() - started
    return MinecraftAttackResult(
        attempted=requests,
        successful=successful,
        failed=requests - successful,
        elapsed_seconds=elapsed,
        sample_status=sample_status,
        errors=errors,
    )
