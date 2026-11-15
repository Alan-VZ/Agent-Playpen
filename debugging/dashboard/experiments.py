"""Local authenticated routes for credential inventory and benchmark jobs."""
import json
import threading
import uuid

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from benchmarks.runner import ExperimentConfig, run_experiment, summaries, atomic_json
from benchmarks.report import render_report
from debugging.dashboard.readiness import Inventory, preflight

JOBS = {}
LOCK = threading.RLock()


class ReadinessRequest(BaseModel):
    config: dict = Field(default_factory=dict)


class CheckRequest(BaseModel):
    provider: str
    allow_billable: bool = False


class ReviewRequest(BaseModel):
    provider: str
    next_review: str | None = None


class LaunchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    configs: list[ExperimentConfig] = Field(min_length=1, max_length=8)
    repeats: int = 5


def install(server):
    app = server.app

    @app.get("/api-inventory")
    def inventory_page(request: Request):
        return server.templates.TemplateResponse(request=request, name="api_inventory.html", context={"session_token": server.API_TOKEN})

    @app.post("/api/readiness")
    def readiness(payload: ReadinessRequest):
        return preflight(server.ROOT, payload.config)

    @app.post("/api/readiness/check")
    def check(payload: CheckRequest):
        if payload.provider not in server.maintenance.CATALOG:
            raise HTTPException(400, "Unknown provider")
        return Inventory(server.ROOT).check(payload.provider, payload.allow_billable)

    @app.post("/api/readiness/review")
    def review(payload: ReviewRequest):
        from datetime import date
        try:
            if payload.next_review:
                date.fromisoformat(payload.next_review)
            Inventory(server.ROOT).update(payload.provider, next_review=payload.next_review)
        except ValueError:
            raise HTTPException(400, "Invalid provider or date") from None
        return {"status": "saved"}

    @app.get("/baselines")
    def baselines_page(request: Request):
        return server.templates.TemplateResponse(request=request, name="baselines.html", context={"session_token": server.API_TOKEN})

    @app.get("/api/benchmarks")
    def list_experiments():
        root = server.ROOT / "benchmark-results"
        items = []
        for path in sorted(root.glob("*/experiment.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:100]:
            if not valid_id(path.parent.name):
                continue
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                state = record["status"]
                if state == "running" and path.parent.name not in JOBS:
                    state = "interrupted"
                items.append({"id": path.parent.name, "created_at": record["created_at"], "status": state, "scheduled": record["scheduled"], "completed": len(record["attempts"])})
            except (OSError, ValueError, KeyError):
                continue
        return items

    def experiment_path(job_id):
        if not valid_id(job_id):
            raise HTTPException(404, "Unknown experiment")
        return server.ROOT / "benchmark-results" / job_id

    def worker(job_id, configs, repeats, output, stop):
        try:
            def progress(value):
                with LOCK:
                    if "type" in value:
                        JOBS[job_id]["events"].append(value)
                        JOBS[job_id]["events"] = JOBS[job_id]["events"][-200:]
                    else:
                        JOBS[job_id]["progress"] = value
            record = run_experiment(configs, output, repeats, stopped=stop, on_progress=progress)
            render_report(record, output)
            with LOCK:
                JOBS[job_id]["status"] = record["status"]
        except Exception:
            try:
                path = output / "experiment.json"
                record = json.loads(path.read_text(encoding="utf-8"))
                record["status"] = "failed"
                atomic_json(path, record)
            except (OSError, ValueError):
                pass
            with LOCK:
                JOBS[job_id]["status"] = "failed"

    @app.post("/api/benchmarks")
    def launch(payload: LaunchRequest):
        if payload.repeats not in {1, 5, 20}:
            raise HTTPException(400, "Select 1, 5, or 20 repeats")
        for config in payload.configs:
            result = preflight(server.ROOT, config.model_dump())
            if not result["ready"]:
                raise HTTPException(409, {"message": "Required APIs need setup", "readiness": result})
            for member in config.agents:
                if member.backend not in server.BackendFactory.REGISTRY or member.planner not in server.PLANNER_MAP:
                    raise HTTPException(400, "Unsupported backend or planner")
            if config.dollar_limit is not None and (config.usd_per_million_input is None or config.usd_per_million_output is None or not config.rate_source):
                raise HTTPException(400, "Dollar reservations require declared rates and source")
        with LOCK:
            if any(j["status"] == "running" for j in JOBS.values()):
                raise HTTPException(409, "Stop or finish the active experiment first")
            # Retain bounded in-memory metadata; evidence lives in files.
            while len(JOBS) >= 100:
                JOBS.pop(next(iter(JOBS)))
            job_id = uuid.uuid4().hex
            stop = threading.Event()
            JOBS[job_id] = {"status": "running", "stop": stop, "events": [], "progress": {"completed": 0, "scheduled": len(payload.configs) * payload.repeats * 5}}
            output = experiment_path(job_id)
            threading.Thread(target=worker, args=(job_id, payload.configs, payload.repeats, output, stop), daemon=True).start()
        return {"id": job_id, "status": "running"}

    @app.get("/api/benchmarks/{job_id}")
    def status(job_id: str):
        path = experiment_path(job_id)
        record = None
        try:
            record = json.loads((path / "experiment.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        with LOCK:
            job = JOBS.get(job_id)
            if not record and not job:
                raise HTTPException(404, "Unknown experiment")
            state = job["status"] if job else record["status"]
            if not job and state == "running":
                state = "interrupted"
            return {"id": job_id, "status": state, "progress": job["progress"] if job else {"completed": len(record["attempts"]), "scheduled": record["scheduled"]},
                    "summaries": summaries(record) if record else [], "configs": record["configs"] if record else [], "repeats": record["repeats"] if record else 5, "attempts": record["attempts"] if record else [], "events": list(job["events"]) if job else []}

    @app.post("/api/benchmarks/{job_id}/stop")
    def stop(job_id: str):
        experiment_path(job_id)
        with LOCK:
            if job_id not in JOBS:
                raise HTTPException(404, "No active job")
            JOBS[job_id]["stop"].set()
        return {"status": "stopping"}

    @app.get("/api/benchmarks/{job_id}/export/{kind}")
    def export(job_id: str, kind: str):
        names = {"html": ("comparison.html", "text/html"), "csv": ("comparison.csv", "text/csv"), "json": ("experiment.json", "application/json")}
        if kind not in names:
            raise HTTPException(404, "Unknown export")
        path = experiment_path(job_id)
        try:
            record = json.loads((path / "experiment.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise HTTPException(404, "No results yet") from None
        # Render exports into memory-isolated output directory only after worker completion.
        with LOCK:
            if JOBS.get(job_id, {}).get("status") == "running":
                raise HTTPException(409, "Wait for the experiment to finish before exporting")
        render_report(record, path)
        name, mime = names[kind]
        content = server.redact((path / name).read_text(encoding="utf-8"))
        if kind == "html":
            return HTMLResponse(content)
        return Response(content, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{name}"'})


def valid_id(value):
    return len(value) == 32 and all(c in "0123456789abcdef" for c in value)
