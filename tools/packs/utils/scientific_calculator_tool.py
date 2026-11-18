"""Thin Playpen adapter; the engine package has no dependency on Playpen."""

import json
import os
from pathlib import Path

from playpen_qalculate import CalculationError, QalculateEngine
from tools.base_tool import BaseTool

ROOT = Path(__file__).resolve().parents[3]
LOCAL_CONFIG = ROOT / "config" / "qalculate.json"


def tool_settings():
    values = {}
    if LOCAL_CONFIG.exists():
        values = json.loads(LOCAL_CONFIG.read_text(encoding="utf-8-sig"))
        if not isinstance(values, dict) or set(values) - {
            "executable",
            "work_dir",
            "output_dir",
            "timeout",
        }:
            raise ValueError("Invalid local Qalculate configuration")
    return {
        "executable": os.environ.get("QALCULATE_QALC") or values.get("executable"),
        "work_dir": os.environ.get("QALCULATE_WORK_DIR") or values.get("work_dir"),
        "output_dir": os.environ.get("QALCULATE_OUTPUT_DIR")
        or values.get("output_dir")
        or str(ROOT / "qalculate-output"),
        "timeout": values.get("timeout", 15),
    }


def configured_engine():
    values = tool_settings()
    return QalculateEngine(
        values["executable"], work_dir=values["work_dir"], timeout=values["timeout"]
    ), Path(values["output_dir"]).resolve()


def calculate_request(**kwargs):
    operation = kwargs.pop("operation", "evaluate")
    expression = kwargs.pop("expression", None)
    if set(kwargs) - {
        "variables",
        "precision",
        "mode",
        "angle_unit",
        "variable",
        "x_min",
        "x_max",
        "points",
    }:
        raise CalculationError("invalid_request", "Unknown calculation field")
    engine, output_dir = configured_engine()
    if operation == "evaluate":
        if set(kwargs) & {"variable", "x_min", "x_max", "points"}:
            raise CalculationError(
                "invalid_request", "Plot settings require operation=plot."
            )
        return engine.evaluate(expression, **kwargs)
    if operation != "plot":
        raise CalculationError("invalid_request", "Operation must be evaluate or plot.")
    if "mode" in kwargs:
        raise CalculationError(
            "invalid_request",
            "Plots always use approximate numeric samples; omit mode.",
        )
    result = engine.plot(expression, output_dir=output_dir, **kwargs)
    result["view_url"] = "/scientific-calculator?plot=" + result["plot_id"]
    result["artifact_urls"] = {
        kind: f"/api/scientific-calculator/artifacts/{result['plot_id']}/{name}"
        for kind, name in {
            "svg": "plot.svg",
            "csv": "samples.csv",
            "json": "calculation.json",
        }.items()
    }
    return result


class ScientificCalculatorTool(BaseTool):
    name = "scientific_calculator"
    description = "Use the local Qalculate engine for high-precision scientific math, exact algebra/equation solving, calculus, units, matrices and scalar 2D plots. Infer the formula from the question, then submit mathematics and exact string-valued variables. Return the engine's result string with units/precision; never replace it with mental arithmetic. No Python, report JSON or shell commands. Plot returns an SVG and full-precision CSV/JSON."
    parameters = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["evaluate", "plot"],
                "default": "evaluate",
            },
            "expression": {
                "type": "string",
                "maxLength": 2000,
                "description": "Qalculate mathematics, e.g. sqrt(2), solve(x^2=4,x), 50 ohm*2 A to V, or distance/duration. Use explicit multiplication.",
            },
            "variables": {
                "type": "object",
                "maxProperties": 20,
                "additionalProperties": {"type": "string"},
                "description": "Exact values with optional units, e.g. distance='120 km', duration='2 h'.",
            },
            "precision": {
                "type": "integer",
                "minimum": 10,
                "maximum": 200,
                "default": 50,
            },
            "mode": {
                "type": "string",
                "enum": ["approximate", "exact", "try exact"],
                "description": "Evaluation only. Omit for plots.",
            },
            "angle_unit": {"type": "string", "enum": ["radians", "degrees"]},
            "variable": {
                "type": "string",
                "enum": ["x", "y", "z", "t"],
                "description": "Independent plot variable.",
            },
            "x_min": {
                "type": "string",
                "description": "Plot lower decimal bound, e.g. '-10'.",
            },
            "x_max": {
                "type": "string",
                "description": "Plot upper decimal bound, e.g. '10'.",
            },
            "points": {"type": "integer", "minimum": 3, "maximum": 501},
        },
        "required": ["expression"],
    }

    def run(self, **kwargs):
        try:
            result = calculate_request(**kwargs)
        except (CalculationError, ValueError, TypeError, OSError) as exc:
            result = {
                "ok": False,
                "error": {
                    "code": getattr(exc, "code", "calculation_failed"),
                    "message": str(exc)[:2000],
                },
            }
        return json.dumps(result, ensure_ascii=False)
