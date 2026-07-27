import json
import time

import pytest

from app import app
from scripts.train_controller import TrainControllerError, TrainControllerService


class FakeSocket:
    def __init__(self, response=b""):
        self.response, self.sent = response, b""
    def __enter__(self): return self
    def __exit__(self, *_): return None
    def settimeout(self, _): return None
    def sendall(self, value): self.sent += value
    def recv(self, _): return self.response


def service(tmp_path, enabled=True, response=b""):
    connection = FakeSocket(response)
    instance = TrainControllerService(tmp_path / "trains.json", enabled=enabled, socket_factory=lambda *_: connection)
    return instance, connection


def test_capability_detection_explains_disabled_hardware(tmp_path):
    capability = service(tmp_path, enabled=False)[0].capability()
    assert capability["available"] is False
    assert "TRAIN_CONTROLLER_ENABLED=0" in capability["reason"]


def test_capability_is_enabled_by_default_without_claiming_reachability(tmp_path, monkeypatch):
    monkeypatch.delenv("TRAIN_CONTROLLER_ENABLED", raising=False)
    capability = TrainControllerService(tmp_path / "trains.json").capability()
    assert capability["available"] is True
    assert capability["reason"] is None
    assert capability["reachability"] == "checked_on_action"


def test_service_persists_roster_sends_generated_command_and_history(tmp_path):
    instance, connection = service(tmp_path)
    controller = instance.add_controller("192.0.2.10", "Yard")["controllers"][0]
    engine = instance.add_engine(controller["id"], 3, "Switcher")["controllers"][0]["engines"][0]
    assert instance.run_action(controller["id"], "lights", engine["id"])["action"] == "lights"
    assert connection.sent == b"<f 3 0 1>\n"
    assert instance.state()["history"][0]["status"] == "success"
    assert json.loads((tmp_path / "trains.json").read_text())["controllers"][0]["name"] == "Yard"


def test_service_updates_layout_roster_and_imports_discovered_engines(tmp_path):
    instance, _ = service(tmp_path)
    instance.set_layout_name("Branch Line")
    controller = instance.add_controller("192.0.2.10", "Old")["controllers"][0]
    state = instance.update_controller(controller["id"], "192.0.2.11", "Main")
    assert state["layout_name"] == "Branch Line"
    assert state["controllers"][0]["ip"] == "192.0.2.11"
    engine = instance.add_engine(controller["id"], 3, "Old engine")["controllers"][0]["engines"][0]
    state = instance.update_engine(controller["id"], engine["id"], 4, "Switcher")
    assert state["controllers"][0]["engines"][0]["name"] == "Switcher"
    state = instance.import_engines(controller["id"], [4, 5, 5, 6])
    assert [item["address"] for item in state["controllers"][0]["engines"]] == [4, 5, 6]


def test_service_rejects_invalid_values_duplicates_and_unavailable_hardware(tmp_path):
    instance, _ = service(tmp_path, enabled=False)
    with pytest.raises(TrainControllerError, match="valid IPv4"):
        instance.add_controller("not a host")
    controller = instance.add_controller("192.0.2.10")["controllers"][0]
    with pytest.raises(TrainControllerError, match="already exists"):
        instance.add_controller("192.0.2.10")
    with pytest.raises(TrainControllerError, match="TRAIN_CONTROLLER_ENABLED=0"):
        instance.run_action(controller["id"], "setup")


def test_connection_failure_is_not_reported_as_success(tmp_path):
    instance = TrainControllerService(tmp_path / "trains.json", enabled=True, socket_factory=lambda *_: (_ for _ in ()).throw(OSError("offline")))
    controller = instance.add_controller("192.0.2.10")["controllers"][0]
    with pytest.raises(TrainControllerError, match="offline"):
        instance.run_action(controller["id"], "setup")
    assert instance.state()["history"] == []


def test_training_progression_persists_and_locks_later_steps(tmp_path):
    instance, _ = service(tmp_path)
    instance.set_mode("training")
    controller = instance.add_controller("192.0.2.10")["controllers"][0]
    with pytest.raises(TrainControllerError, match="current Training Guide"):
        instance.run_action(controller["id"], "lights", "missing")
    with pytest.raises(TrainControllerError, match="before adding an engine"):
        instance.add_engine(controller["id"], 4)
    instance.run_action(controller["id"], "setup")
    engine = instance.add_engine(controller["id"], 4)["controllers"][0]["engines"][0]
    instance.run_action(controller["id"], "lights", engine["id"])
    assert instance.state()["training"]["completed"] == ["add_controller", "setup", "add_engine", "lights"]
    assert "First Lights" in instance.state()["training"]["trophies"]


@pytest.fixture
def train_client(tmp_path):
    instance, _ = service(tmp_path)
    app.config.update(TESTING=True, TRAIN_CONTROLLER_SERVICE=instance)
    yield app.test_client(), instance
    app.config.pop("TRAIN_CONTROLLER_SERVICE", None)


def test_page_renders_tabs_controls_empty_state_and_navigation(train_client):
    client, _ = train_client
    response = client.get("/train-controller")
    assert response.status_code == 200
    for value in (b"Overview", b"Controllers", b"Controls", b"Discovery", b"Diagnostics", b"History", b"Training Guide", b"No controllers configured"):
        assert value in response.data
    assert b"Train Controller" in client.get("/").data
    assert b'id="layout-name-form"' in response.data
    assert b"Save to Evidence Vault" in response.data


def test_routes_validate_authorization_input_and_success(train_client):
    client, _ = train_client
    assert client.post("/api/train-controller/controllers", json={"ip": "bad"}).status_code == 400
    created = client.post("/api/train-controller/controllers", json={"ip": "192.0.2.20", "name": "Lab"})
    controller_id = created.get_json()["state"]["controllers"][0]["id"]
    assert created.status_code == 201
    unauthorized = client.post(f"/api/train-controller/controllers/{controller_id}/actions", json={"action": "setup"})
    assert unauthorized.status_code == 400
    assert "Authorization" in unauthorized.get_json()["message"]
    success = client.post(f"/api/train-controller/controllers/{controller_id}/actions", json={"action": "setup", "authorized": True})
    assert success.status_code == 200
    assert success.get_json()["result"]["action"] == "setup"


def test_update_import_background_scan_and_evidence_routes(train_client):
    client, instance = train_client
    instance.socket_factory = lambda *_: FakeSocket(b"<l 1 0 0 0>")
    created = client.post("/api/train-controller/controllers", json={"ip": "192.0.2.30", "name": "Old"}).get_json()
    controller_id = created["state"]["controllers"][0]["id"]
    assert client.put("/api/train-controller/layout", json={"name": "Test Layout"}).status_code == 200
    assert client.put(f"/api/train-controller/controllers/{controller_id}", json={"ip": "192.0.2.31", "name": "New"}).status_code == 200
    started = client.post(f"/api/train-controller/controllers/{controller_id}/scan-jobs", json={"maximum": 2, "authorized": True})
    assert started.status_code == 202
    job_id = started.get_json()["job"]["id"]
    for _ in range(50):
        job = client.get(f"/api/train-controller/scan-jobs/{job_id}").get_json()["job"]
        if job["status"] == "completed":
            break
        time.sleep(.01)
    assert job["engines"] == [1]
    imported = client.post(f"/api/train-controller/controllers/{controller_id}/engines/import", json={"addresses": job["engines"]})
    engine = imported.get_json()["state"]["controllers"][0]["engines"][0]
    assert client.put(f"/api/train-controller/controllers/{controller_id}/engines/{engine['id']}", json={"address": 2, "name": "Edited"}).status_code == 200
    assert client.post("/api/train-controller/evidence", json={}).status_code == 201


def test_route_reports_unavailable_hardware(tmp_path):
    instance, _ = service(tmp_path, enabled=False)
    controller = instance.add_controller("192.0.2.21")["controllers"][0]
    app.config["TRAIN_CONTROLLER_SERVICE"] = instance
    try:
        response = app.test_client().post(f"/api/train-controller/controllers/{controller['id']}/actions", json={"action": "setup", "authorized": True})
        assert response.status_code == 503
        assert "TRAIN_CONTROLLER_ENABLED=0" in response.get_json()["message"]
    finally:
        app.config.pop("TRAIN_CONTROLLER_SERVICE", None)
