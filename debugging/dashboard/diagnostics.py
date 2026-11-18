"""Local diagnostic study launch/status, sharing benchmark run exclusion."""

import json
import threading
import uuid
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from benchmarks.runner import ExperimentConfig
from benchmarks.diagnostics import run
from debugging.dashboard.experiments import JOBS, LOCK, active_study


class DiagnosticRequest(BaseModel):
    configs: list[ExperimentConfig] = Field(min_length=1, max_length=10)


def install(server):
    app = server.app

    def path_for(identity):
        if len(identity) != 32 or any(c not in "0123456789abcdef" for c in identity):
            raise HTTPException(404, "Unknown diagnostic run")
        return server.ROOT / "diagnostic-results" / identity

    @app.get("/diagnostics")
    def page(request: Request):
        return server.templates.TemplateResponse(
            request=request,
            name="diagnostics.html",
            context={"session_token": server.API_TOKEN},
        )

    @app.get("/api/diagnostics")
    def history():
        result = []
        for path in sorted(
            (server.ROOT / "diagnostic-results").glob("*/experiment.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:50]:
            try:
                d = json.loads(path.read_text(encoding="utf-8"))
                result.append(
                    {
                        "id": path.parent.name,
                        "status": d["status"],
                        "completed": len(d["attempts"]),
                        "scheduled": d["scheduled"],
                    }
                )
            except (OSError, ValueError, KeyError):
                pass
        return result

    @app.get("/api/diagnostics/{identity}")
    def status(identity: str):
        root = path_for(identity)
        try:
            record = json.loads((root / "experiment.json").read_text(encoding="utf-8"))
        except OSError:
            raise HTTPException(404, "Diagnostic record not ready") from None
        # Full evidence is downloaded separately rather than repeatedly polled.
        record["attempts"] = [
            {
                k: v
                for k, v in a.items()
                if k not in {"interactions", "partial_events", "agents"}
            }
            for a in record["attempts"]
        ]
        if (root / "progress.json").exists():
            record["progress"] = json.loads(
                (root / "progress.json").read_text(encoding="utf-8")
            )
        return record

    @app.get("/api/diagnostics/{identity}/evidence/{attempt_id}")
    def evidence(identity: str, attempt_id: str):
        from benchmarks.evidence import replay_attempt

        if len(attempt_id) != 32 or any(
            c not in "0123456789abcdef" for c in attempt_id
        ):
            raise HTTPException(404, "Unknown attempt")
        try:
            data = json.loads(
                (path_for(identity) / (attempt_id + ".json")).read_text(
                    encoding="utf-8"
                )
            )
        except OSError:
            raise HTTPException(404, "Unknown attempt") from None
        data["offline_replay"] = replay_attempt(data)
        return data

    @app.post("/api/diagnostics/{identity}/stop")
    def stop(identity: str):
        path_for(identity)
        with LOCK:
            if identity in JOBS:
                JOBS[identity]["stop"].set()
        return {"status": "stop_requested"}

    @app.post("/api/diagnostics")
    def launch(payload: DiagnosticRequest):
        from debugging.dashboard.readiness import preflight

        if active_study(server.ROOT):
            raise HTTPException(409, "A controlled study is active")
        for config in payload.configs:
            if len(config.agents) != 1:
                raise HTTPException(400, "Use one independent model per configuration")
            member = config.agents[0]
            if (
                member.backend not in server.BackendFactory.REGISTRY
                or member.model.strip() in {"", "local-model"}
            ):
                raise HTTPException(400, "Choose an explicit supported provider/model")
            if not preflight(
                server.ROOT, {"agents": [member.model_dump()], "tools": []}
            )["ready"]:
                raise HTTPException(409, "Model provider needs credential setup")
        with LOCK:
            if any(j["status"] == "running" for j in JOBS.values()):
                raise HTTPException(409, "Finish the active experiment first")
            identity = uuid.uuid4().hex
            stop = threading.Event()
            JOBS[identity] = {"status": "running", "stop": stop, "events": []}

        def worker():
            try:
                state = run(payload.configs, path_for(identity), stop)["status"]
            except Exception:
                state = "failed"
            with LOCK:
                JOBS[identity]["status"] = state

        threading.Thread(target=worker, daemon=True).start()
        return {"id": identity, "status": "running"}
