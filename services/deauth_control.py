"""Bounded, supervised controller for authorized deauthentication lab runs."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Callable, Optional

DEFAULT_MAX_RUN_SECONDS = 15.0
DEFAULT_HEARTBEAT_GRACE_SECONDS = 5.0
DEFAULT_SEND_INTERVAL_SECONDS = 0.1
_MAX_ERROR_LENGTH = 500

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_STATE_DIR = _REPO_ROOT / "instance"
_DEFAULT_ACTIVE_MARKER = _DEFAULT_STATE_DIR / "deauth_active.json"
_DEFAULT_EMERGENCY_FLAG = _DEFAULT_STATE_DIR / "deauth_emergency_stop.flag"


def _bounded_error(value: object) -> str:
    return str(value or "").strip()[:_MAX_ERROR_LENGTH]


def validate_start_request(data, normalize_mac):
    """Validate the bounded Start/Stop controller inputs."""
    ap_mac = normalize_mac(data.get("ap"))
    target_mac = normalize_mac(data.get("target") or "ff:ff:ff:ff:ff:ff")
    if not ap_mac:
        raise ValueError("Enter a valid lab AP MAC address")
    if not target_mac:
        raise ValueError("Enter a valid target MAC address")
    if ap_mac == "ff:ff:ff:ff:ff:ff":
        raise ValueError("AP MAC must be a specific lab access point, not broadcast")
    if data.get("authorized") != "on":
        raise ValueError(
            "Confirm this is an authorized isolated lab network before starting deauth"
        )
    return ap_mac, target_mac


class BoundedDeauthController:
    """Manage one short-lived deauthentication sender with fail-closed leases."""

    def __init__(
        self,
        *,
        max_run_seconds: float = DEFAULT_MAX_RUN_SECONDS,
        heartbeat_grace_seconds: float = DEFAULT_HEARTBEAT_GRACE_SECONDS,
        send_interval_seconds: float = DEFAULT_SEND_INTERVAL_SECONDS,
        active_marker: Path | str = _DEFAULT_ACTIVE_MARKER,
        emergency_flag: Path | str = _DEFAULT_EMERGENCY_FLAG,
        time_fn: Callable[[], float] = time.time,
    ):
        self.max_run_seconds = float(max_run_seconds)
        self.heartbeat_grace_seconds = float(heartbeat_grace_seconds)
        self.send_interval_seconds = float(send_interval_seconds)
        if self.max_run_seconds <= 0:
            raise ValueError("Maximum run time must be greater than zero")
        if self.heartbeat_grace_seconds <= 0:
            raise ValueError("Heartbeat grace must be greater than zero")
        if self.send_interval_seconds <= 0:
            raise ValueError("Send interval must be greater than zero")

        self.active_marker = Path(active_marker)
        self.emergency_flag = Path(emergency_flag)
        self._time = time_fn
        self._lock = threading.Lock()
        self._active = None
        self._last = None
        self.startup_cleanup()

    def startup_cleanup(self) -> bool:
        """Fail closed after restart and remove any stale active-job marker."""
        self.emergency_flag.parent.mkdir(parents=True, exist_ok=True)
        stale = self.active_marker.exists()
        self.emergency_flag.write_text(
            f"startup-cleanup {os.getpid()} {self._time():.6f}\n",
            encoding="utf-8",
        )
        try:
            self.active_marker.unlink()
        except FileNotFoundError:
            pass
        return stale

    def _write_marker(self, job: dict) -> None:
        self.active_marker.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "id": job["id"],
            "pid": os.getpid(),
            "interface": job["interface"],
            "ap": job["ap"],
            "target": job["target"],
            "operator": job["operator"],
            "started_at": job["started_at"],
            "hard_deadline": job["hard_deadline"],
        }
        temporary = self.active_marker.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        temporary.replace(self.active_marker)

    def _clear_marker(self) -> None:
        try:
            self.active_marker.unlink()
        except FileNotFoundError:
            pass

    def _public(self, job: Optional[dict]) -> dict:
        if not job:
            return {
                "active": False,
                "max_run_seconds": self.max_run_seconds,
                "heartbeat_grace_seconds": self.heartbeat_grace_seconds,
            }
        now = self._time()
        status = job.get("status", "stopped")
        return {
            "active": status in {"starting", "running", "stopping"},
            "id": job["id"],
            "status": status,
            "interface": job["interface"],
            "ap": job["ap"],
            "target": job["target"],
            "operator": job["operator"],
            "started_at": job["started_at"],
            "stopped_at": job.get("stopped_at"),
            "hard_deadline": job["hard_deadline"],
            "heartbeat_deadline": job["heartbeat_deadline"],
            "remaining_seconds": max(0.0, job["hard_deadline"] - now),
            "frames_sent": job.get("frames_sent", 0),
            "stop_reason": job.get("stop_reason"),
            "error": job.get("error"),
            "max_run_seconds": self.max_run_seconds,
            "heartbeat_grace_seconds": self.heartbeat_grace_seconds,
        }

    def status(self) -> dict:
        with self._lock:
            return self._public(self._active or self._last)

    def start(
        self,
        *,
        ap_mac: str,
        target_mac: str,
        interface: str,
        operator: str,
        send_frame: Callable[[], None],
    ) -> dict:
        now = self._time()
        with self._lock:
            if self._active and self._active.get("status") in {
                "starting",
                "running",
                "stopping",
            }:
                raise ValueError("A bounded deauth lab run is already active")

            try:
                self.emergency_flag.unlink()
            except FileNotFoundError:
                pass

            job = {
                "id": uuid.uuid4().hex,
                "status": "starting",
                "interface": interface,
                "ap": ap_mac,
                "target": target_mac,
                "operator": operator or "unknown",
                "started_at": now,
                "hard_deadline": now + self.max_run_seconds,
                "heartbeat_deadline": min(
                    now + self.heartbeat_grace_seconds,
                    now + self.max_run_seconds,
                ),
                "frames_sent": 0,
                "stop_reason": None,
                "error": None,
                "_stop_event": threading.Event(),
            }
            self._active = job
            self._write_marker(job)
            thread = threading.Thread(
                target=self._worker,
                args=(job["id"], send_frame),
                name=f"bounded-deauth-{job['id'][:8]}",
                daemon=True,
            )
            job["_thread"] = thread
            job["status"] = "running"
            thread.start()
            return self._public(job)

    def heartbeat(self, job_id: str) -> dict:
        now = self._time()
        with self._lock:
            job = self._active
            if not job or job.get("id") != job_id:
                raise ValueError("The bounded deauth job is not active")
            if job.get("status") not in {"starting", "running"}:
                raise ValueError("The bounded deauth job is stopping")
            if now >= job["hard_deadline"]:
                job["stop_reason"] = "hard_timeout"
                job["_stop_event"].set()
            else:
                job["heartbeat_deadline"] = min(
                    now + self.heartbeat_grace_seconds,
                    job["hard_deadline"],
                )
            return self._public(job)

    def stop(self, job_id: Optional[str] = None, reason: str = "manual_stop") -> dict:
        with self._lock:
            job = self._active
            if not job:
                return self._public(self._last)
            if job_id and job.get("id") != job_id:
                raise ValueError("The bounded deauth job ID does not match")
            job["status"] = "stopping"
            job["stop_reason"] = reason
            job["_stop_event"].set()
            return self._public(job)

    def emergency_stop(self, reason: str = "emergency_stop") -> dict:
        request_emergency_stop(self.emergency_flag, reason=reason)
        return self.stop(reason=reason)

    def _worker(self, job_id: str, send_frame: Callable[[], None]) -> None:
        reason = "completed"
        error = None
        while True:
            with self._lock:
                job = self._active
                if not job or job.get("id") != job_id:
                    return
                now = self._time()
                stop_event = job["_stop_event"]
                explicit_reason = job.get("stop_reason")
                heartbeat_deadline = job["heartbeat_deadline"]
                hard_deadline = job["hard_deadline"]

            if stop_event.is_set():
                reason = explicit_reason or "manual_stop"
                break
            if self.emergency_flag.exists():
                reason = "emergency_stop"
                break
            if now >= hard_deadline:
                reason = "hard_timeout"
                break
            if now >= heartbeat_deadline:
                reason = "heartbeat_timeout"
                break

            try:
                send_frame()
            except Exception as exc:  # pragma: no cover - hardware/runtime specific
                reason = "sender_error"
                error = _bounded_error(exc)
                break

            with self._lock:
                current = self._active
                if current and current.get("id") == job_id:
                    current["frames_sent"] += 1

            stop_event.wait(self.send_interval_seconds)

        self._finish(job_id, reason, error)

    def _finish(self, job_id: str, reason: str, error: Optional[str]) -> None:
        with self._lock:
            job = self._active
            if not job or job.get("id") != job_id:
                return
            job["status"] = "failed" if error else "stopped"
            job["stop_reason"] = reason
            job["error"] = error
            job["stopped_at"] = self._time()
            self._last = job
            self._active = None
            self._clear_marker()


def request_emergency_stop(
    path: Path | str = _DEFAULT_EMERGENCY_FLAG,
    *,
    reason: str = "local-emergency-stop",
) -> Path:
    """Create the filesystem kill flag checked by the active worker."""
    flag = Path(path)
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.write_text(
        f"{reason} {os.getpid()} {time.time():.6f}\n",
        encoding="utf-8",
    )
    return flag


_controller = BoundedDeauthController()


def start_deauth(**kwargs) -> dict:
    return _controller.start(**kwargs)


def heartbeat_deauth(job_id: str) -> dict:
    return _controller.heartbeat(job_id)


def stop_deauth(job_id: Optional[str] = None, reason: str = "manual_stop") -> dict:
    return _controller.stop(job_id, reason)


def emergency_stop_deauth(reason: str = "emergency_stop") -> dict:
    return _controller.emergency_stop(reason)


def deauth_status() -> dict:
    return _controller.status()


def emergency_stop_path() -> str:
    return str(_controller.emergency_flag)
