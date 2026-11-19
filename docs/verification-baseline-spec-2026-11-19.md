# Independent Playpen verification — November 19, 2026

Reviewed commit: `80c701716e54bb624f3dbdf11326264f75c303ed`. The three valid live studies all recorded this commit and a clean working tree. No implementation files changed during verification. This report and its supporting artifacts were written after the studies finished.

**Verdict:** regression mechanics and several live tool paths work, but the entire corrective plan is not ready to be described as complete or qualified. Guided B01 exposes target answers; forced-timeout evidence is not consumed by the standard replay helper; complete inference/load profiles and rubric-v2 remain unfinished. Autonomous baseline reliability is reported below, independently of offline test success.

## Verification performed

- Full Python suite: **559 passed, 9 skipped**, 69.11 seconds, Python 3.12.14.
- Enabled the installed Qalculate binary and ran the nine skipped real-engine checks: **9 passed**, 9.44 seconds. Coverage includes high-precision arithmetic, units, integration, differentiation, algebra, complex numbers, matrices, graph files/discontinuities, and an Agent/tool round trip.
- Rendered production templates and ran **all 11 UI scripts**, all passed: baseline feedback, tasks, baseline/inventory, controlled studies, dashboard, diagnostics, local model picker, maintenance, model prices, scientific calculator, universal tools.
- Real browser: ten model slots; apply defaults to all; keyboard replacement of Model 10 temperature independently of Model 1; reload persistence; layout at 1024 and 1920 pixels. At 1920, document width was 1905, summary width 1160, and table width 1134. Restored the temporary viewport override, original single-slot count and temperature 0.7. This was one real browser engine, not a claim of Firefox/Edge coverage.
- Live OpenAPI exposes `settlement_mode` with autonomous/guided and autonomous as default; stale-server schema is resolved.
- Ruff: **one failure**, unused local `rows` in `tests/test_baselines.py:413`; no runtime source finding from this lint check.
- `benchmarks/tasks.py` remains unchanged from `d83f954`; original baseline-v1 scoring was preserved.

## Live study design and results

There are **34 valid new live cases**: 18 diagnostics (D01–D06 for three independent models), six autonomous B01/B04 pilot cases, and ten autonomous Groq candidate-positive-control cases (five fixture seeds, two tasks). All use ReAct, Auto tool calling, temperature 0, maximum 10 iterations and a 400-second task limit. Groq uses 512 output tokens and 60-second model-request pacing; local models use 2048 output tokens. All tools are local fixture/calculator operations; no paid web-search tests were invoked. Baseline-v1 continues to use its bounded basic arithmetic calculator; the real Qalculate scientific-engine checks are reported separately above. Live workers used Python 3.13.5.

Baseline automatic setup was enabled and the server-confirmed tool list was `read_fixture, calculator` for every pilot/control configuration. This is the union for B01/B04, not a per-attempt minimal tool set. Models sharing LM Studio ran sequentially. Diagnostics and baselines use separate contracts and must not be combined into one accuracy percentage.

| Model | D01–D06 | Pilot B01 | Pilot B04 |
|---|---:|---|---|
| qwen/qwen3.8-27b | 6/6 | FAIL (repeated_action) | PASS (passed) |
| qwen3.5-9b-uncensored-hauhaucs-aggressive@q6_k | 4/6 | FAIL (timeout) | PASS (passed) |
| qwen2.5-coder-7b-instruct | 5/6 | FAIL (final_report_validation) | FAIL (missing_or_unsupported_evidence) |

The five-seed Groq follow-up is a candidate qualification check, not an assumption that the model is already a reliable positive control. Seeds vary the fixtures; this is not five identical prompts. Seed 1 also repeats the earlier pilot conditions.

| Fixture seed | B01 | B04 |
|---|---|---|
| 1 | FAIL (repeated_action; 241.3 s) | PASS (passed; 241.0 s) |
| 2 | FAIL (repeated_action; 301.8 s) | PASS (passed; 241.4 s) |
| 3 | FAIL (repeated_action; 362.2 s) | PASS (passed; 241.4 s) |
| 4 | FAIL (repeated_action; 301.5 s) | PASS (passed; 241.3 s) |
| 5 | FAIL (repeated_action; 361.4 s) | PASS (passed; 241.2 s) |

Per-case quality, elapsed seconds, known actual token counts, tool requests, failed checks, categories, and retained transport counts are in [the case CSV](studies/2026-11-19-verification-case-results.csv) and [case JSON](studies/2026-11-19-verification-case-results.json). Timings include deliberate Groq pacing and local model preparation, so they are not a direct inference-speed ranking. Timeout usage remains unknown/incomplete, never zero.

Live views:

- Diagnostics: http://127.0.0.1:8765/diagnostics?run=4d07847036c34e52becf91e5c23e2f4e
- Valid pilot: http://127.0.0.1:8765/baselines?run=87a21b5c9502488abd42efca54d5eee5
- Five-seed follow-up: http://127.0.0.1:8765/baselines?run=592a2a1cbdc54983a4fcfb5a687d2d13

## Findings established by the evidence

### 1. Guided B01 leaks target answers — approval blocker

`benchmarks/settlement.py:123` computes the target totals from the CSV. `remaining()` at line 184 includes the exact missing values in feedback. `core/agent.py:132` forwards this as “Missing guided evidence.” A seed-1 reproduction, after a successful fixture read, returns `verified calculation result 12`, `32`, and `44`. Calling the calculator on the constants `12`, `32`, and `44` makes `ready()` true. This does not establish that the agent derived the required operations, and it supplies the main numerical answers to a premature finalizer.

Keep grading targets out of model-visible feedback. Track successful, task-relevant named operations and evidence provenance without revealing target values. Test premature finals, unrelated constants, equal-valued distinct operations, and legitimate remaining operations. Guided and autonomous results must retain separate identities. **No live guided qualification is claimed here**; spending generations on oracle-assisted guided passes would not provide the agreed evidence. See [the reproduction](studies/2026-11-19-verification-guided-answer-leak.json).

### 2. Successful arithmetic is not reliable finalization

Groq's pilot B01 (`385d5a6e47d84ea6bed48b9021e06132`) read the correct CSV, calculated `37 + 12 - 5 = 44` and `37 - 5 = 32`, then repeated the grand-total calculation. The complete request history retained those observations, and `tool_choice` was auto. Responses ended with `tool_calls`, not token-length truncation. This was not a calculator error, bad server address, or quota rejection.

Qwen3.5 diagnostic D02 (`874534bd76054668aa8debc3350e7d35`) had the actual `amber-47` observation in a role=tool message, then repeatedly requested the same fixture. D03 similarly repeated a successful calculator operation. The other four diagnostics passed. This is why a broad provider/model failure label is inadequate.

Qwen3.5 pilot B01 (`3028726663514644a3e69df38de80f4d`) hit the 410-second worker bound, including supervision. Partial timestamps show approximately 95 seconds preparing the model, followed by tool calls with substantial reasoning time and a repeated-calculation warning. Four provider responses survived; the fifth request had no captured response. Preparation, generation, looping and deadline effects must be distinguished.

The next controlled improvement should be an explicit finalization phase with a supported structured-output contract and bounded budget, activated from observed operation state rather than expected answers. Preserve the current autonomous scores and evaluate this as a separately identified guided/assisted policy.

### 3. Tool-request protocol errors need their own recovery feedback

Qwen2.5 pilot B01 (`c00f9a20f20945d1bfb0b41ed2bfc9a9`) produced a fenced `read_fixture` envelope plus explanatory prose. The strict adapter did not dispatch that mixed response, and it reached final-report validation instead. In B04 (`ef64aa4b7a804e96aabefbac5fa6617c`) it emitted multiple concatenated tool requests and a report, then returned the literal release placeholder “version” without executing the reads. The scorer rejected missing evidence.

The narrow JSON-call bridge works on supported shapes (several diagnostics passed) but does not make arbitrary mixed output a valid tool call. Add a bounded malformed-tool-intent classification and explicit “one complete advertised tool object, no prose or multiple actions” feedback. Do not silently extract and execute ambiguous embedded requests. Keep the original transport evidence.

### 4. Timeout raw evidence survives, but standard replay misses it

The Qwen3.5 timeout has 57 `partial_events`, including four complete `transport_response` events. `benchmarks/evidence.py:124` only reads `interactions`, so `replay_attempt(original_timeout)` returns an empty list. A read-only normalization from partial event `type` to interaction `kind` replays all four captured responses successfully. No models or tools were called by this replay. See [the reproduction](studies/2026-11-19-verification-timeout-replay-gap.json).

Normalize retained partial events into the standard evidence/replay envelope, and assign outcome categories on the forced-timeout path. Missing usage for the unfinished worker must remain unknown. Add a regression that forces worker termination and proves replay of the captured responses, not merely retention of raw events.

### 5. Extra tool availability and output formatting deserve separate trials

Groq B04 seed 1 passed but unnecessarily sent the version label `1.7` to the calculator. The configuration exposed the B01/B04 tool union. A future controlled comparison should hold model/fixture/settings fixed and vary union versus task-minimal tools; this run alone does not prove causation. Several recovery outputs required a bounded correction from prose-wrapped JSON to a bare report. Tool execution, evidence use, formatting, and final correctness need separate metrics.

## Resolved mechanics and remaining scope

The reviewed changes have passing regression coverage for failed operations not advancing guided state, guided terminal gating, error-only native handoff not being marked working, and preserving the distinction between invalid `1 2` and valid `12`. Live Groq requests confirmed temperature 0, 512 max output tokens, and `parallel_tool_calls=false` on native requests. Model IDs were recorded in returned metadata. The real calculator checks and cross-model tool successes show working transport and arithmetic paths; they do not establish end-to-end baseline reliability.

Complete inference/load profiles remain **partial**: request profile records requested values, while effective/default values and load profile remain unknown (`benchmarks/runner.py:306`). Supported reasoning/load controls, apply/query and profile diff are not completed by this review. B02/B05 rubric-v2 and proposed B06/B07 are still pending; no invented or unversioned qualification results are reported for them.

One reviewer-launcher setup run (`90aa6a0888514810bd723ccea0b8196d`) inherited the diagnostic empty tool list with auto setup disabled. It was cancelled and replaced with the correctly prepared pilot. Its single attempt is preserved and explicitly excluded from the 34 valid cases and all model scores. The source implementation was not changed to correct this launcher error.

## Artifacts

- [Summary and outcome counts](studies/2026-11-19-verification-summary.json)
- [Run manifest, including the excluded setup run](studies/2026-11-19-verification-manifest.json)
- [Per-case CSV](studies/2026-11-19-verification-case-results.csv)
- [Per-case JSON](studies/2026-11-19-verification-case-results.json)
- [Standard offline replays](studies/2026-11-19-verification-offline-replays.json)
- Raw individual attempts and experiments remain under their existing `diagnostic-results/<run>` and `benchmark-results/<run>` folders. Historical studies were not rewritten.

## Final evidence and service audit

The 34 valid cases retained **127 transport requests and 126 responses**. The one unmatched request is the unfinished fifth request in the forced Qwen3.5 timeout. All captured requests sent the recorded temperature and output-token limits. All **80 native Groq requests** explicitly sent the serial-call policy. The diagnostic study's 16 source fingerprints match the reviewed files; baseline records use commit/clean-tree provenance without that diagnostic fingerprint map. Report artifact links were verified. The dashboard returned HTTP 200, and both benchmark and diagnostic APIs reported no active jobs after completion.
