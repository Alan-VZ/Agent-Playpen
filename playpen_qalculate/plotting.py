"""Precision-preserving Qalculate samples and a static SVG presentation."""

import csv
from decimal import Decimal, DecimalException, localcontext
from html import escape
import json
from pathlib import Path
import re
import uuid
import time

from .engine import (
    CalculationError,
    NUMBER,
    checked_bindings,
    checked_expression,
    decimal_value,
)


def vector_values(text, count):
    text = text.strip()
    if not text.startswith("[") or not text.endswith("]"):
        raise CalculationError(
            "plot_result", "Qalculate did not return a sample vector."
        )
    values = re.split(r"\s{2,}", text[1:-1].strip())
    if len(values) != count:
        raise CalculationError(
            "plot_result", "Qalculate returned an unexpected number of samples."
        )
    return [
        v if NUMBER.fullmatch(v) and Decimal(v).is_finite() else None for v in values
    ]


def render_svg(expression, xs, ys, precision, variable):
    with localcontext() as context:
        context.prec = precision + 30
        pairs = [
            (Decimal(x), Decimal(y)) if x is not None and y is not None else None
            for x, y in zip(xs, ys)
        ]
        valid = [p for p in pairs if p is not None]
        if not valid:
            raise CalculationError(
                "plot_domain",
                "No finite real samples. Plot a scalar real-valued expression; normalize units explicitly before plotting.",
            )
        xmin, xmax = min(p[0] for p in valid), max(p[0] for p in valid)
        ymin, ymax = min(p[1] for p in valid), max(p[1] for p in valid)
        if xmin == xmax:
            raise CalculationError(
                "plot_domain", "The plot has no distinct x coordinates."
            )
        padding = (
            (ymax - ymin) / 20 if ymax != ymin else max(abs(ymin) / 10, Decimal(1))
        )
        ymin -= padding
        ymax += padding

        def px(x):
            return 80 + (x - xmin) * 760 / (xmax - xmin)

        def py(y):
            return 430 - (y - ymin) * 330 / (ymax - ymin)

        segments, current = [], []
        for pair in pairs:
            if pair is None:
                if current:
                    segments.append(current)
                current = []
            else:
                current.append(f"{px(pair[0]):.3f},{py(pair[1]):.3f}")
        if current:
            segments.append(current)
        paths = "".join(
            f'<polyline points="{" ".join(s)}" fill="none" stroke="#1674b8" stroke-width="2"/>'
            for s in segments
        )
        axes = ""
        if xmin <= 0 <= xmax:
            axes += f'<line x1="{px(Decimal(0)):.3f}" x2="{px(Decimal(0)):.3f}" y1="100" y2="430" stroke="#8898a8"/>'
        if ymin <= 0 <= ymax:
            axes += f'<line x1="80" x2="840" y1="{py(Decimal(0)):.3f}" y2="{py(Decimal(0)):.3f}" stroke="#8898a8"/>'
        title = escape(expression[:120])
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="920" height="530" viewBox="0 0 920 530" role="img" aria-labelledby="title desc">
<title id="title">{title}</title><desc id="desc">Qalculate samples at {precision} significant digits. Screen coordinates are rounded for display; CSV and JSON preserve result strings. Unsampled discontinuities may remain.</desc>
<rect width="920" height="530" fill="white"/><g font-family="sans-serif" fill="#16324a"><text x="40" y="35" font-size="20">{title}</text><text x="40" y="65" font-size="13">Qalculate · {precision} significant digits · {len(valid)}/{len(xs)} finite samples</text>
<rect x="80" y="100" width="760" height="330" fill="none" stroke="#b1bcc6"/>{axes}{paths}
<text x="80" y="455">{escape(format(xmin, ".8g"))}</text><text x="840" y="455" text-anchor="end">{escape(format(xmax, ".8g"))}</text>
<text x="75" y="100" text-anchor="end" font-size="11">{escape(format(ymax, ".6g"))}</text><text x="75" y="430" text-anchor="end" font-size="11">{escape(format(ymin, ".6g"))}</text>
<text x="460" y="485" text-anchor="middle">{escape(variable)}</text><text x="40" y="515" font-size="12">Sampled curve; gaps mark undefined/non-real samples. Download CSV/JSON for precise values.</text></g></svg>"""


def make_plot(
    engine,
    expression,
    *,
    output_dir,
    variable,
    x_min,
    x_max,
    points,
    precision,
    variables,
    angle_unit,
):
    expression = checked_expression(expression, limit=1000)
    if variable not in {"x", "y", "z", "t"}:
        raise CalculationError(
            "invalid_variable", "Plot variable must be x, y, z or t."
        )
    bindings = checked_bindings(variables)
    if variable in bindings:
        raise CalculationError(
            "invalid_variable",
            "Do not bind the plot's independent variable to a fixed value.",
        )
    lo, hi = decimal_value(x_min), decimal_value(x_max)
    if lo >= hi or type(points) is not int or not 3 <= points <= 501:
        raise CalculationError(
            "invalid_range", "Use increasing bounds and 3–501 sample points."
        )
    deadline = time.monotonic() + engine.timeout
    x_result = engine.evaluate(
        f"genvector({variable}, {x_min}, {x_max}, {points}, {variable})",
        precision=precision,
        angle_unit=angle_unit,
        _deadline=deadline,
    )
    y_result = engine.evaluate(
        f"genvector(({expression}), {x_min}, {x_max}, {points}, {variable})",
        variables=bindings,
        precision=precision,
        angle_unit=angle_unit,
        _allow_diagnostics=True,
        _deadline=deadline,
    )
    xs, ys = (
        vector_values(x_result["result"], points),
        vector_values(y_result["result"], points),
    )
    try:
        svg = render_svg(expression, xs, ys, precision, variable)
    except DecimalException:
        raise CalculationError(
            "plot_range",
            "Sample magnitudes exceeded display coordinate limits; narrow the range.",
        ) from None
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    plot_id = uuid.uuid4().hex
    target = root / plot_id
    target.mkdir()
    metadata = {
        "ok": True,
        "operation": "plot",
        "plot_id": plot_id,
        "engine": y_result["engine"],
        "engine_version": y_result["engine_version"],
        "expression": expression,
        "variables": bindings,
        "precision_digits": precision,
        "angle_unit": angle_unit,
        "variable": variable,
        "x_min": x_min,
        "x_max": x_max,
        "points": points,
        "finite_samples": sum(y is not None for y in ys),
        "warnings": y_result["warnings"],
        "sampling_note": "Scalar real 2D samples; not a proof of continuity. Undefined/complex samples are gaps. SVG coordinates are display-rounded; data strings preserve qalc precision.",
        "samples": [{"x": x, "y": y} for x, y in zip(xs, ys)],
    }
    try:
        (target / "plot.svg").write_text(svg, encoding="utf-8")
        with (target / "samples.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow([variable, "value"])
            writer.writerows(zip(xs, ys))
        (target / "calculation.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )
    except OSError:
        for name in ("plot.svg", "samples.csv", "calculation.json"):
            (target / name).unlink(missing_ok=True)
        target.rmdir()
        raise
    return {k: v for k, v in metadata.items() if k != "samples"} | {
        "artifacts": {
            "svg": str(target / "plot.svg"),
            "csv": str(target / "samples.csv"),
            "json": str(target / "calculation.json"),
        }
    }
