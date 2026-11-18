# Standalone Qalculate bridge

This directory is a self-contained, standard-library-only Python package. It has no imports from Agent Playpen. Copy this directory to a new repository, then build/install it with `python -m pip install .`. Its wheel installs the `playpen-qalculate` command. The external Qalculate executable remains a separate dependency.

The LLM translates a word problem into an expression and exact string-valued inputs. Qalculate, rather than the LLM, evaluates that expression. Numeric output remains text throughout the bridge so Python binary floats cannot truncate it.

```python
from playpen_qalculate import QalculateEngine

engine = QalculateEngine(executable="/path/to/qalc", work_dir="/path/to/scratch")
result = engine.evaluate(
    "distance/duration",
    variables={"distance": "120 km", "duration": "2 h"},
    precision=80,
)
assert result["result"] == "60 km/h"
plot = engine.plot(
    "sin(x)",
    output_dir="/path/to/plots",
    x_min="-10",
    x_max="10",
    points=201,
    precision=80,
)
```

When using the source directory from its parent, run `python -m playpen_qalculate evaluate "sqrt(2)" --precision 80 --binary /path/to/qalc`. Once installed, use `playpen-qalculate` with the same arguments. `--help` lists plotting, variables, angle and mode options. Errors return structured JSON and exit status 1.

Capabilities: 10–200 significant digits, exact/symbolic or approximate calculation, scientific functions, unit conversions, equation solving, differentiation/integration, matrices, and scalar real 2D graphs. Examples: `solve(x^2=4,x)`, `diff(x^3,x)`, `integrate(x^2,0,1)`, `det([1,2;3,4])`, `50 ohm*2 A to V`. Qalculate syntax applies; use explicit multiplication. Variable values must be strings or integers, never binary floats. Independent plot variable is x/y/z/t; normalize physical units before graphing.

Graphs sample the expression using Qalculate, retain all returned numeric digits in CSV/JSON, and render a static SVG with rounded pixel coordinates. Undefined or complex samples create gaps. Sampling does not prove continuity or detect every pole. Up to 501 samples are allowed. This bridge does not reproduce the GTK application's full UI, 3D plots, live currencies, user-defined functions or persistent history.

The executable is invoked without a shell. Each request uses a fresh QALCULATE_USER_DIR, preventing the user's local definitions/history from changing results. File, shell, network, random/time and persistent-state commands are blocked; named function calls use the allowlist in engine.py. The process receives no provider credentials, and has bounded time and output. This is a bounded interface to a trusted local executable, not an operating-system sandbox for arbitrary executables or modified global definitions. Diagnostics are checked separately because qalc's terse mode suppresses warnings, including division by zero. Evaluation errors are never converted to successful numeric results. Plot domain warnings are retained with gaps.

Install the official Qalculate CLI from https://qalculate.github.io/downloads.html and set QALCULATE_QALC or pass executable. See https://qalculate.github.io/manual/qalc.html for engine syntax. Qalculate is an independently distributed GPL-licensed project; the MIT license here covers this Python bridge, not that external engine. No Qalculate binaries or source are bundled.

Portable standard-library tests are included: after installing the package, run `python -m unittest discover -s tests` from this directory. Set QALCULATE_TEST_BINARY and optionally QALCULATE_WORK_DIR to include the real-engine check. Expanded integration tests live in ../tests/test_scientific_calculator.py in the host application. They cover validation, diagnostics, bounded execution, adapter/API boundaries, and optional real-engine checks. When extracting this directory, migrate that test file's standalone-engine tests into the new repository as well.
