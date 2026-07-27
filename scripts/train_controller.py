"""Native DCC-EX controller integration.

The module deliberately owns persistence, validation and TCP protocol details so
the web layer never accepts arbitrary DCC commands or writes configuration.
"""
from __future__ import annotations

import ipaddress
import json
import os
import socket
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


class TrainControllerError(ValueError):
    """A safe, user-facing train controller error."""


TRAINING_STEPS = (
    ("add_controller", "Add a controller", "Record the address of an authorized DCC-EX command station."),
    ("setup", "Initialize the controller", "Connect and send the standard track setup sequence."),
    ("add_engine", "Add an engine", "Add a DCC cab address assigned to this controller."),
    ("lights", "Turn on lights", "Send the first safe locomotive function command."),
    ("throttle", "Move the engine", "Use a bounded speed control, then return it to zero."),
)


class TrainControllerService:
    def __init__(self, data_path, enabled=None, port=None, timeout=None, socket_factory=None):
        self.data_path = Path(data_path)
        self.enabled = _env_enabled("TRAIN_CONTROLLER_ENABLED") if enabled is None else bool(enabled)
        self.port = int(port or os.getenv("TRAIN_CONTROLLER_PORT", "2560"))
        self.timeout = float(timeout or os.getenv("TRAIN_CONTROLLER_TIMEOUT", "2"))
        self.socket_factory = socket_factory or socket.create_connection
        self._lock = threading.RLock()

    def capability(self):
        reason = None if self.enabled else "Hardware controls were disabled by TRAIN_CONTROLLER_ENABLED=0."
        return {
            "available": self.enabled,
            "reason": reason,
            "port": self.port,
            "protocol": "DCC-EX TCP",
            "reachability": "checked_on_action" if self.enabled else "not_checked",
        }

    def state(self):
        with self._lock:
            return deepcopy(self._load())

    def set_mode(self, mode):
        if mode not in {"full", "training"}:
            raise TrainControllerError("Mode must be full or training")
        return self._mutate(lambda data: data.update(mode=mode))

    def set_layout_name(self, name):
        name = _short_text(name, "Layout name")
        return self._mutate(lambda data: data.update(layout_name=name))

    def add_controller(self, ip, name=""):
        address = _valid_ip(ip)
        name = _short_text(name, "Controller name")
        def change(data):
            if any(item["ip"] == address for item in data["controllers"]):
                raise TrainControllerError("Controller already exists")
            data["controllers"].append({"id": uuid.uuid4().hex[:12], "ip": address, "name": name, "engines": []})
            self._complete(data, "add_controller")
        return self._mutate(change)

    def delete_controller(self, controller_id):
        def change(data):
            controller = self._controller(data, controller_id)
            data["controllers"].remove(controller)
        return self._mutate(change)

    def update_controller(self, controller_id, ip, name=""):
        address = _valid_ip(ip)
        name = _short_text(name, "Controller name")

        def change(data):
            controller = self._controller(data, controller_id)
            if any(item["id"] != controller_id and item["ip"] == address for item in data["controllers"]):
                raise TrainControllerError("Controller already exists")
            controller.update(ip=address, name=name)

        return self._mutate(change)

    def add_engine(self, controller_id, address, name=""):
        cab = _cab(address)
        name = _short_text(name, "Engine name")
        def change(data):
            if data["mode"] == "training" and not self._step_unlocked(data, "add_engine"):
                raise TrainControllerError("Complete the current Training Guide step before adding an engine")
            controller = self._controller(data, controller_id)
            if any(engine["address"] == cab for engine in controller["engines"]):
                raise TrainControllerError("Engine address already exists on this controller")
            controller["engines"].append({"id": uuid.uuid4().hex[:12], "address": cab, "name": name})
            self._complete(data, "add_engine")
        return self._mutate(change)

    def delete_engine(self, controller_id, engine_id):
        def change(data):
            controller = self._controller(data, controller_id)
            engine = self._engine(controller, engine_id)
            controller["engines"].remove(engine)
        return self._mutate(change)

    def update_engine(self, controller_id, engine_id, address, name=""):
        cab = _cab(address)
        name = _short_text(name, "Engine name")

        def change(data):
            controller = self._controller(data, controller_id)
            engine = self._engine(controller, engine_id)
            if any(item["id"] != engine_id and item["address"] == cab for item in controller["engines"]):
                raise TrainControllerError("Engine address already exists on this controller")
            engine.update(address=cab, name=name)

        return self._mutate(change)

    def import_engines(self, controller_id, addresses):
        if not isinstance(addresses, list):
            raise TrainControllerError("Engine addresses must be a list")
        cabs = list(dict.fromkeys(_cab(value) for value in addresses))
        if len(cabs) > 127:
            raise TrainControllerError("At most 127 engine addresses can be imported")

        def change(data):
            controller = self._controller(data, controller_id)
            existing = {engine["address"] for engine in controller["engines"]}
            for cab in cabs:
                if cab not in existing:
                    controller["engines"].append({"id": uuid.uuid4().hex[:12], "address": cab, "name": ""})
            if cabs:
                self._complete(data, "add_engine")

        return self._mutate(change)

    def run_action(self, controller_id, action, engine_id=None, speed=None):
        if not self.enabled:
            raise TrainControllerError(self.capability()["reason"])
        data = self.state()
        controller = self._controller(data, controller_id)
        required_step = {"setup": "setup", "lights": "lights", "throttle": "throttle"}.get(action)
        if data["mode"] == "training" and action == "horn" and "throttle" not in data["training"]["completed"]:
            raise TrainControllerError("Complete the Training Guide before using the horn")
        if data["mode"] == "training" and required_step and not self._step_unlocked(data, required_step):
            raise TrainControllerError("Complete the current Training Guide step before using this control")
        if action == "setup":
            commands = ["<1>", "<1 MAIN>", "<1 PROG>", "<1 JOIN>"]
        elif action == "emergency_stop":
            commands = ["<!>"]
        else:
            engine = self._engine(controller, engine_id)
            cab = engine["address"]
            if action == "lights":
                commands = [f"<f {cab} 0 1>"]
            elif action == "horn":
                commands = [f"<f {cab} 1 1>"]
            elif action == "stop":
                commands = [f"<t {cab} 0 1>"]
            elif action == "throttle":
                try:
                    value = int(speed)
                except (TypeError, ValueError):
                    raise TrainControllerError("Speed must be an integer")
                if not -127 <= value <= 127:
                    raise TrainControllerError("Speed must be between -127 and 127")
                commands = [f"<t {cab} {abs(value)} {1 if value >= 0 else 0}>"]
            else:
                raise TrainControllerError("Unsupported train action")
        response = self._send(controller["ip"], commands)
        def record(current):
            self._complete(current, required_step)
            current["history"].insert(0, {"at": _now(), "controller": controller_id, "engine": engine_id, "action": action, "status": "success"})
            del current["history"][100:]
        self._mutate(record)
        return {"action": action, "response": response}

    def scan_engines(self, controller_id, maximum=127, progress=None, cancelled=None):
        if not self.enabled:
            raise TrainControllerError(self.capability()["reason"])
        data = self.state()
        controller = self._controller(data, controller_id)
        maximum = int(maximum)
        if not 1 <= maximum <= 127:
            raise TrainControllerError("Scan maximum must be between 1 and 127")
        found = []
        for cab in range(1, maximum + 1):
            if cancelled and cancelled():
                raise TrainControllerError("Engine scan was cancelled")
            reply = self._send(controller["ip"], [f"<s {cab} 1 128 0>"])
            if f"<l {cab} " in reply:
                found.append(cab)
            if progress:
                progress(cab, maximum, list(found))
        self._mutate(lambda current: current["history"].insert(0, {"at": _now(), "controller": controller_id, "action": "scan", "status": "success", "engines": found}))
        return found

    def _send(self, ip, commands):
        try:
            connection = self.socket_factory((ip, self.port), self.timeout)
            with connection:
                connection.settimeout(self.timeout)
                connection.sendall("".join(command + "\n" for command in commands).encode("ascii"))
                try:
                    return connection.recv(4096).decode("ascii", "replace")
                except socket.timeout:
                    return ""
        except OSError as error:
            raise TrainControllerError(f"Controller connection failed: {error}")

    def _load(self):
        if not self.data_path.exists():
            return self._default()
        try:
            data = json.loads(self.data_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise TrainControllerError(f"Train controller data could not be loaded: {error}")
        default = self._default()
        for key, value in default.items():
            data.setdefault(key, value)
        return data

    def _mutate(self, callback):
        with self._lock:
            data = self._load()
            callback(data)
            self.data_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.data_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
            temporary.replace(self.data_path)
            return deepcopy(data)

    @staticmethod
    def _default():
        return {"version": 1, "layout_name": "", "mode": "full", "controllers": [], "history": [], "training": {"completed": [], "trophies": []}}

    @staticmethod
    def _controller(data, controller_id):
        controller = next((item for item in data["controllers"] if item["id"] == controller_id), None)
        if not controller:
            raise TrainControllerError("Controller not found")
        return controller

    @staticmethod
    def _engine(controller, engine_id):
        engine = next((item for item in controller["engines"] if item["id"] == engine_id), None)
        if not engine:
            raise TrainControllerError("Engine not found on this controller")
        return engine

    @staticmethod
    def _complete(data, step):
        if not step:
            return
        completed = data["training"]["completed"]
        if step not in completed:
            completed.append(step)
        trophy = {"add_controller": "Dispatcher", "setup": "Track Online", "add_engine": "Roster Builder", "lights": "First Lights", "throttle": "Qualified Driver"}.get(step)
        if trophy and trophy not in data["training"]["trophies"]:
            data["training"]["trophies"].append(trophy)

    @staticmethod
    def _step_unlocked(data, step):
        names = [item[0] for item in TRAINING_STEPS]
        index = names.index(step)
        return index == 0 or names[index - 1] in data["training"]["completed"]


def _env_enabled(name):
    """Default the supported TCP integration on, while retaining an admin kill switch."""
    value = os.getenv(name)
    if value is None or not value.strip():
        return True
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _valid_ip(value):
    try:
        return str(ipaddress.ip_address(str(value).strip()))
    except ValueError:
        raise TrainControllerError("A valid IPv4 or IPv6 controller address is required")


def _cab(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise TrainControllerError("Engine address must be an integer")
    if not 1 <= value <= 10239:
        raise TrainControllerError("Engine address must be between 1 and 10239")
    return value


def _short_text(value, label):
    value = str(value or "").strip()
    if len(value) > 80:
        raise TrainControllerError(f"{label} must be 80 characters or fewer")
    return value


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
