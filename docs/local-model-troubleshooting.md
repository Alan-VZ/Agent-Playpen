# Local model and baseline troubleshooting

Evidence reviewed November 16, 2026. This document distinguishes observed
failures from suggested remedies; it does not claim that a proposed remedy has
been implemented or that a model will pass after a change.

## How the workflow fits together

1. Start the LM Studio local server. Its default inference address is
   `http://localhost:1234/v1`. Installing or listing a model is not the same
   as running a task.
2. Start the dashboard with `Start Agent Playpen.cmd` and open
   `http://127.0.0.1:8765/`. The launcher requires `.venv` and keeps the
   dashboard running in its console window. It tests whether port 8765 is open,
   not whether the listener is actually Agent Playpen.
3. Choose `lm_studio` and use **Choose model**. Selecting a local model asks
   Playpen to unload other text models, load the selection, and verify it.
   Wait for the active status. This prepares the model; it does not run a test.
4. Open **Baseline tests**, select the tasks, configure the agent and repeats,
   and click **Run baseline tests**. Alternatively, in the workspace select
   baseline tasks and use **Load selected tasks** followed by **Run Agent**.
   **Compare using this agent** opens the comparison page without running it.
5. Watch **Run status & results** and expand **Live agent activity** and the
   individual test result. A run can finish processing while its tests fail.
   A strict pass requires every required check. Baselines use fixed synthetic
   fixtures, not live web searches.

For a first check, select **B01** only, one agent, and **1 · smoke** repetition.
Leave automatic baseline setup enabled: it selects ReAct, **Read baseline
inputs**, and **Calculator**. Confirm the displayed model and local URL before
starting. A completed smoke run checks the path, not general model reliability.
The [baseline guide](baseline-tests.md) has the complete workflow.

## What was observed

At the time of this review, the dashboard `/baselines` and LM Studio
`/v1/models` endpoints both returned HTTP 200. LM Studio's native model list
reported `qwen2.5-coder-7b-instruct` loaded. These are point-in-time checks:
they do not prove inference or baseline success. No new inference was started
for this review.

| Issue | Evidence | Suggested next step |
| --- | --- | --- |
| Mistral run timed out | Run `c0d9bbb873014c05a1d437cc351722c0` read the same B01 input three times, then passed a calculation expression to `read_fixture`. Its fifth model request ended with `APITimeoutError`; no final answer was recorded. The attempt lasted 129.79 seconds. | Inspect LM Studio's log for that request and check resource pressure or inference speed. Try a smaller or different model and a single B01 smoke run. The trace does not establish why the server timed out. |
| Later Qwen run exhausted its steps | Run `59cb68075631407f8c1e08d509f641cf`, using Qwen2.5 Coder 7B at temperature 0.0, correctly calculated 44, then repeatedly issued empty fixture and calculator calls. It stopped without a final answer after the iteration budget ended. | Review the expanded trace and try another instruction-following model or configuration. Increasing iterations alone may merely repeat the loop; it is not a verified fix. |
| Latest Qwen run returned an incorrect answer | Run `e6fac942b6b84bfdb0928d5173ea5fc8`, using the same model at temperature 0.7, produced valid JSON but failed B01 with 37.5% of checks. It attempted an oversized calculator expression and empty tool calls; its final totals and count were wrong. | Compare the answer and failed checks with **Full recorded evidence**. Try a different model, then rerun the same smoke test. Changing temperature may affect output but has not been shown to fix this failure. |
| Model-list messages look like a stalled task | The earlier conversation reported repeated LM Studio model-list requests without inference requests during that particular log. Later saved Qwen traces show that inference requests did occur. Model discovery and readiness checks are not task execution. | Confirm a **new run ID**, progress, and model requests in **Live agent activity**. If the run never starts, inspect the setup or launch message; don't infer a model failure from list requests alone. |
| Saved results can be confused with current form settings | The supplied URL includes all five tasks and temperature 0.7, but its `run=c0d9...` opens the older saved B01-only Mistral run at temperature 0.0. Saved results are separate from the next run's form. | Read the displayed run ID and configuration. Use **Use these settings for a new run** only when intentionally copying a saved configuration; click **Run baseline tests** to start a new run. |
| Setup instructions disagree | The [quick-start guide](../Installation%20and%20Quick-Start%20Guide.md) describes separate refresh/load/status buttons; the current [model picker](../debugging/dashboard/templates/model_picker.html) uses **Choose model** and automatic switching. The baseline guide describes the newer workflow. | Follow the current picker and baseline guide. The quick-start guide should be updated separately so its instructions match the interface. |

The Qwen traces establish which tool calls Playpen attempted, but do not by
themselves establish whether malformed calls originated in model output or in
Playpen's response parsing. That distinction needs further investigation.

## Timeout and result interpretation

The baseline **Time limit per task** defaults to 180 seconds and covers the
overall attempt. Separately, the benchmark runner caps an individual SDK client
request timeout at the smaller of the task limit and 60 seconds, with SDK
retries disabled. Raising the task limit above 60 seconds therefore does not
raise that individual request timeout. Changing the request cap would require
a code change and should be considered only after checking the server and
model behavior.

For the saved B01 seed, the expected answer is a net total of 44, three valid
orders, duplicate ID `A`, and category totals of 32 for parts and 12 for
service. These values apply to these saved attempts; other repetitions may use
different fixture values. A `valid_json` failure with no final answer is an
output-contract failure, not evidence that an incorrect JSON answer was sent.

## Potential application improvements

These are proposals, not completed fixes:

- Make **model ready, no test started** and the active run ID more prominent.
- Explain repeated or malformed tool calls and iteration exhaustion alongside
  the failed checks, while preserving the original evidence.
- Investigate model responses and the planner's parsing together before
  attributing empty or incorrect tool arguments to either component. If needed,
  add appropriately redacted diagnostics and targeted regression tests.
- Clarify the two timeout limits in the interface and documentation; consider
  a configurable request timeout only with explicit validation and tests.
- Update the outdated quick-start picker instructions after agreeing on the
  documentation change.

Saved evidence is local and normally git-ignored; it may contain task outputs.
Review and redact it before sharing. The three run directories above are under
`benchmark-results`; each contains `experiment.json`, an attempt JSON file,
`summary.json`, and comparison exports.


## November 17 follow-through

The earlier evidence and suggestions above are retained as a dated record. Current model selection uses Choose model with automatic local switching/verification; the old separate refresh/load/status instructions are superseded. Progress/results and saved-run identity are documented in the baseline guide. Typed validation, provider call adapters, verified result records and the shared MCP-capable execution layer are implemented; live model improvement after these changes is not yet measured. See [the complete issue register](issues-and-resolutions.md), [universal tools](universal-tools.md), [calculator](scientific-calculator.md), and [credits](credits-and-sources.md).
