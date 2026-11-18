# Qalculate scientific calculator tool

Open **Menu → Scientific calculator & graphs**, or select **scientific_calculator** in the Agent Workspace Tools list. ReAct is the appropriate planner for tool use. The tool is available to every existing model provider through the same tool registry; whether a model successfully calls it is measured separately from numerical correctness.

The tool accepts operation evaluate/plot, a Qalculate expression, exact string-valued variables, precision (10–200 significant digits), and radians/degrees. Evaluation also accepts exact/approximate/try exact mode. Plotting accepts variable x/y/z/t, decimal-string bounds and 3–501 sample points. Results contain actual engine version, submitted formula, values, precision, result text, and diagnostics. Graph results link to a preview and downloadable SVG/CSV/JSON records. No API key or paid web tool is involved.

Example tool arguments:

```json
{"operation":"evaluate","expression":"distance/duration","variables":{"distance":"120 km","duration":"2 h"},"precision":80}
```

Expected result: `60 km/h`. The model must still infer the correct equation, units and inputs. A calculator cannot repair an incorrect translation of the question.

Install the external CLI from the official Qalculate downloads page. Configure QALCULATE_QALC, QALCULATE_WORK_DIR and QALCULATE_OUTPUT_DIR, or copy config/qalculate.example.json to the ignored config/qalculate.json. Use absolute local paths. If qalc is on PATH, executable can be null. The standalone package and contract are documented in playpen_qalculate/README.md. The dashboard does not accept executable or filesystem paths from tool/API arguments. Download routes require the local session token and only serve the three known artifacts inside the configured output root.

This computer uses D:/AI-Runtimes/Qalculate/5.13.2/qalculate/qalc.exe and stores plots/work files under D:/Agent-Playpen-Results to avoid the nearly full C drive. The official Windows bundle is 5.13.2, but its qalc executable reports **5.13.0**; records report that actual engine version. Download asset: https://github.com/Qalculate/libqalculate/releases/download/v5.13.2/qalculate-5.13.2-x64.zip. Its SHA256 matched the GitHub release asset digest: 6e8a39df926d6eae4e9139472b550a8e72a359888fd2f5ab6f060acc73fa677a.

The Python bridge lives entirely in playpen_qalculate/ and builds its own dependency-free wheel. The Playpen adapter is tools/packs/utils/scientific_calculator_tool.py; dashboard integration is debugging/dashboard/scientific.py. Copy the bridge folder into a separate repository and install/build it independently; retain or replace the thin adapter. The original bounded calculator and B01–B05 fixtures/scorers are unchanged, preserving historical study comparisons. A future calculator-assisted baseline must explicitly identify which tool was used.

The next finding from the five-task study is tool interaction and result handoff: GPT-OSS-20B answered 49/50 direct cases, but its tool arm had zero strict passes and provider tool-protocol rejections. Local Qwen produced valid calculator calls yet failed final output contracts. Therefore the next experiment should isolate one tool call, an observed result, and a correctly formatted final answer before adding harder mathematics. See docs/studies/2026-11-17-five-task-matched.md. A second issue is grading equivalence: documented semantic-format observations must be addressed in a new scorer version without rewriting historical scores.

Validation on 2026-11-17: all 495 host tests passed with the real qalc executable enabled, including a scripted production-agent roundtrip (an application integration check, not a new LLM benchmark). Separate DOM tests verified running acknowledgement, completion, graph preview/download controls, error feedback and existing workspace/inventory behavior. Real engine checks covered 80-digit sqrt(2), exact integration, derivatives, matrices, complex numbers, unit conversion, zero-division diagnostics, graph precision and undefined-sample gaps. Standalone source and wheel builds were checked separately.
