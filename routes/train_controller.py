import os
import json
import threading
import uuid

from flask import Blueprint, current_app, jsonify, render_template, request

from scripts.train_controller import TRAINING_STEPS, TrainControllerError, TrainControllerService


def create_train_controller_blueprint(context_provider):
    blueprint = Blueprint("train_controller", __name__)
    scan_jobs = {}
    scan_jobs_lock = threading.Lock()

    def service():
        configured = current_app.config.get("TRAIN_CONTROLLER_SERVICE")
        if configured:
            return configured
        return TrainControllerService(os.path.join(current_app.instance_path, "train_controller.json"))

    def payload():
        return request.get_json(silent=True) or request.form

    def error_response(error, unavailable=False):
        return jsonify({"status": "error", "message": str(error)}), 503 if unavailable else 400

    @blueprint.get("/train-controller")
    def page():
        train_service = service()
        return render_template(
            "train_controller.html", title="Train Controller", train_state=train_service.state(),
            train_capability=train_service.capability(), training_steps=TRAINING_STEPS, **context_provider()
        )

    @blueprint.get("/api/train-controller")
    def get_state():
        train_service = service()
        return jsonify({"status": "success", "state": train_service.state(), "capability": train_service.capability()})

    @blueprint.post("/api/train-controller/mode")
    def mode():
        try:
            state = service().set_mode(payload().get("mode"))
            return jsonify({"status": "success", "state": state})
        except TrainControllerError as error:
            return error_response(error)

    @blueprint.put("/api/train-controller/layout")
    def update_layout():
        try:
            return jsonify({"status": "success", "state": service().set_layout_name(payload().get("name", ""))})
        except TrainControllerError as error:
            return error_response(error)

    @blueprint.post("/api/train-controller/controllers")
    def add_controller():
        data = payload()
        try:
            state = service().add_controller(data.get("ip"), data.get("name", ""))
            return jsonify({"status": "success", "state": state}), 201
        except TrainControllerError as error:
            return error_response(error)

    @blueprint.delete("/api/train-controller/controllers/<controller_id>")
    def delete_controller(controller_id):
        try:
            return jsonify({"status": "success", "state": service().delete_controller(controller_id)})
        except TrainControllerError as error:
            return error_response(error)

    @blueprint.put("/api/train-controller/controllers/<controller_id>")
    def update_controller(controller_id):
        data = payload()
        try:
            state = service().update_controller(controller_id, data.get("ip"), data.get("name", ""))
            return jsonify({"status": "success", "state": state})
        except TrainControllerError as error:
            return error_response(error)

    @blueprint.post("/api/train-controller/controllers/<controller_id>/engines")
    def add_engine(controller_id):
        data = payload()
        try:
            state = service().add_engine(controller_id, data.get("address"), data.get("name", ""))
            return jsonify({"status": "success", "state": state}), 201
        except TrainControllerError as error:
            return error_response(error)

    @blueprint.delete("/api/train-controller/controllers/<controller_id>/engines/<engine_id>")
    def delete_engine(controller_id, engine_id):
        try:
            return jsonify({"status": "success", "state": service().delete_engine(controller_id, engine_id)})
        except TrainControllerError as error:
            return error_response(error)

    @blueprint.put("/api/train-controller/controllers/<controller_id>/engines/<engine_id>")
    def update_engine(controller_id, engine_id):
        data = payload()
        try:
            state = service().update_engine(controller_id, engine_id, data.get("address"), data.get("name", ""))
            return jsonify({"status": "success", "state": state})
        except TrainControllerError as error:
            return error_response(error)

    @blueprint.post("/api/train-controller/controllers/<controller_id>/engines/import")
    def import_engines(controller_id):
        try:
            state = service().import_engines(controller_id, payload().get("addresses"))
            return jsonify({"status": "success", "state": state})
        except TrainControllerError as error:
            return error_response(error)

    @blueprint.post("/api/train-controller/controllers/<controller_id>/actions")
    def action(controller_id):
        data = payload()
        if str(data.get("authorized", "")).lower() != "true":
            return error_response(TrainControllerError("Authorization confirmation is required for hardware commands"))
        train_service = service()
        try:
            result = train_service.run_action(controller_id, data.get("action"), data.get("engine_id"), data.get("speed"))
            return jsonify({"status": "success", "result": result, "state": train_service.state()})
        except TrainControllerError as error:
            return error_response(error, unavailable=not train_service.capability()["available"])

    @blueprint.post("/api/train-controller/controllers/<controller_id>/scan-jobs")
    def start_scan(controller_id):
        data = payload()
        if str(data.get("authorized", "")).lower() != "true":
            return error_response(TrainControllerError("Authorization confirmation is required for network scanning"))
        train_service = service()
        try:
            if not train_service.capability()["available"]:
                raise TrainControllerError(train_service.capability()["reason"])
            maximum = int(data.get("maximum", 127))
            if not 1 <= maximum <= 127:
                raise TrainControllerError("Scan maximum must be between 1 and 127")
            train_service._controller(train_service.state(), controller_id)
        except (TrainControllerError, ValueError) as error:
            return error_response(error, unavailable=not train_service.capability()["available"])

        job_id = uuid.uuid4().hex
        with scan_jobs_lock:
            scan_jobs[job_id] = {"id": job_id, "controller_id": controller_id, "status": "queued", "current": 0, "maximum": maximum, "progress": 0, "engines": [], "cancel_requested": False, "error": None}

        def run_scan():
            def progress(current, total, engines):
                with scan_jobs_lock:
                    job = scan_jobs[job_id]
                    job.update(status="running", current=current, progress=round(current * 100 / total), engines=engines)

            def cancelled():
                with scan_jobs_lock:
                    return scan_jobs[job_id]["cancel_requested"]

            try:
                engines = train_service.scan_engines(controller_id, maximum, progress, cancelled)
                with scan_jobs_lock:
                    scan_jobs[job_id].update(status="completed", current=maximum, progress=100, engines=engines)
            except TrainControllerError as error:
                with scan_jobs_lock:
                    status = "cancelled" if scan_jobs[job_id]["cancel_requested"] else "failed"
                    scan_jobs[job_id].update(status=status, error=str(error))

        threading.Thread(target=run_scan, daemon=True, name=f"train-scan-{job_id[:8]}").start()
        return jsonify({"status": "success", "job": dict(scan_jobs[job_id])}), 202

    @blueprint.get("/api/train-controller/scan-jobs/<job_id>")
    def scan_status(job_id):
        with scan_jobs_lock:
            job = scan_jobs.get(job_id)
            if not job:
                return jsonify({"status": "error", "message": "Engine scan job not found"}), 404
            return jsonify({"status": "success", "job": dict(job)})

    @blueprint.post("/api/train-controller/scan-jobs/<job_id>/cancel")
    def cancel_scan(job_id):
        with scan_jobs_lock:
            job = scan_jobs.get(job_id)
            if not job:
                return jsonify({"status": "error", "message": "Engine scan job not found"}), 404
            if job["status"] not in {"queued", "running"}:
                return error_response(TrainControllerError("Only queued or running scans can be cancelled"))
            job["cancel_requested"] = True
            return jsonify({"status": "success", "job": dict(job)})

    @blueprint.post("/api/train-controller/evidence")
    def save_evidence():
        recorder = current_app.config.get("TRAIN_CONTROLLER_EVIDENCE_RECORDER")
        if not recorder:
            return jsonify({"status": "error", "message": "Evidence integration is unavailable"}), 503
        state = service().state()
        record = recorder(
            title=f"Train Controller history — {state['layout_name'] or 'Layout'}",
            category="scan-output", source="Train Controller",
            notes="Validated DCC-EX hardware action and discovery history.",
            content=json.dumps(state["history"], indent=2),
        )
        return jsonify({"status": "success", "record": record}), 201

    return blueprint
