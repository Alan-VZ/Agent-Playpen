"""Local calculator endpoints, using the dashboard's existing session boundary."""

import re

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from playpen_qalculate import CalculationError
from tools.packs.utils.scientific_calculator_tool import (
    calculate_request,
    configured_engine,
)


class CalculationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expression: str = Field(min_length=1, max_length=2000)
    operation: str = "evaluate"
    variables: dict[str, str] | None = None
    precision: int = Field(default=50, ge=10, le=200)
    mode: str | None = None
    angle_unit: str = "radians"
    variable: str | None = None
    x_min: str | None = None
    x_max: str | None = None
    points: int | None = Field(default=None, ge=3, le=501)


def install(server):
    @server.app.get("/scientific-calculator")
    def page(request: Request):
        return server.templates.TemplateResponse(
            request=request,
            name="scientific_calculator.html",
            context={"session_token": server.API_TOKEN},
        )

    @server.app.get("/api/scientific-calculator/status")
    def status():
        try:
            engine, _ = configured_engine()
            return {
                "available": engine.available(),
                "message": "Qalculate is ready locally."
                if engine.available()
                else "Install Qalculate's qalc CLI and configure QALCULATE_QALC or config/qalculate.json. No API key is needed.",
            }
        except (ValueError, OSError):
            return {
                "available": False,
                "message": "Check config/qalculate.json: the local runtime configuration is invalid.",
            }

    @server.app.post("/api/scientific-calculator")
    def calculate(payload: CalculationRequest):
        try:
            return calculate_request(**payload.model_dump(exclude_none=True))
        except (CalculationError, ValueError, TypeError, OSError) as exc:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "code": getattr(exc, "code", "calculation_failed"),
                        "message": str(exc)[:2000],
                    },
                },
            )

    @server.app.get("/api/scientific-calculator/artifacts/{plot_id}/{filename}")
    def artifact(plot_id: str, filename: str):
        types = {
            "plot.svg": "image/svg+xml",
            "samples.csv": "text/csv",
            "calculation.json": "application/json",
        }
        if not re.fullmatch(r"[a-f0-9]{32}", plot_id) or filename not in types:
            raise HTTPException(404, "Unknown plot artifact")
        _, root = configured_engine()
        path = (root / plot_id / filename).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise HTTPException(404, "Plot artifact is unavailable")
        return FileResponse(path, media_type=types[filename], filename=filename)
