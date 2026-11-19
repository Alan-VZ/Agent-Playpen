# Baseline Failure Findings and Corrective Actions

Date: 2026-11-18
Scope: `README.md`, all files under `docs/`, all files under `docs/studies/`, the baseline implementation, recent live saved runs, and the available automated test suite.

## Executive summary

Recent failures involve several layers: application protocol and orchestration, provider limits, model/template behavior, and task evaluation. Offline tests validate the mechanics that were tested; recorded live interactions are needed to assign individual failures to those layers.

Verification passed:

- **548 Python tests passed, 9 skipped**
- **113 focused baseline/diagnostic tests passed**
- Browser checks passed for independent model cards, numeric settings, model launch, baseline task transfer, diagnostics, and live activity
- The LM Studio API is reachable and exposes the installed model catalog

The live baselines fail because the system is now exercising real model behavior and exposes several difficult-to-hide stages:

1. Models can complete a tool operation but fail to produce the required final JSON.
2. Models can repeatedly read or calculate after obtaining useful information.
3. Local reasoning models can spend much of their token/time budget on reasoning before the final action.
4. Prompt/numeric protocols can still differ by model and provider despite native tool support.
5. Baseline-v1 has known semantic/wording ambiguities in B02 and B05 that can reject factually equivalent answers.
6. The evidence and documentation clearly separate historical scores and new runtime routes, but the baseline plan and implementation still need a live-quality qualification gate.

The baseline should not be described as an application success until repeated live runs pass. Passing offline tests and live tool transport establishes only that the harness and gateway work in the tested conditions.

## Evidence summary

| Evidence | Result | Interpretation |
|---|---|---|
| Full Python suite | 548 passed, 9 skipped | Application regressions are largely covered and currently passing |
| Focused baseline/diagnostic suite | 113 passed | Baseline runner, native-route forwarding, recovery, and diagnostics mechanics pass in mocked/scripted tests |
| Matched capability study | 7/24 strict diagnostic passes | Seven passes; four Groq cases were quota-blocked, so they are not model-failure evidence |
| Qwen2.5 JSON-call follow-up | 1/6 before, 3/6 after | A separate protocol follow-up improved two tool/recovery cases; no retroactive B01-B05 score change |
| Groq 512-token paced follow-up | 6/6 | Separate 512-token, paced conditions passed all six diagnostics; not directly matched to the 2048-token run |
| Saved LM Studio B01 comparison, run `e40dbdbca42544399d6aa0057b1cc1c4` | 0/4 strict passes | Distinct format, arithmetic, loop, and timeout failures; not one universal application defect |
| Five-model B01/B02 recovery run, `6ec7f70828b648568b85133fdba48faa` | 0/10 strict passes | Tool execution, finalization, source coverage, and protocol failures remain model-dependent |
| Qwen3.5 B01 follow-up, `8f2abebf514d4d8490f1a51156832320` | 1 attempted case, 0 pass | Four tool calls succeeded, but the model did not return a final report before timeout |
| Historical five-task matched study | 59 strict B passes out of 801 attempted cases across available models | Model/tool/finalization reliability is weak and provider availability/quotas are separate outcomes |
| Groq/B01 and four-model studies | Mixed passes and protocol failures | Stronger models demonstrate that transport/scoring can work; weak cases are not evidence of a universal infrastructure failure |
| Capability diagnostics | D01-D06 improve under explicit protocol/recovery changes | Narrow capability work is useful, but it must not be used to claim B01-B05 qualification |

Application protocol evidence has also established two concrete integration defects:

- Qwen2.5 produced identical first requests and first responses before and after the JSON-call adapter. Playpen's previous interpretation treated the complete JSON tool envelope as a final-report candidate; the adapter now dispatches exactly one explicitly advertised call and contributed to a separate 1/6-to-3/6 diagnostic result.
- Groq could return parallel native calls while Playpen executes one action per turn. Native Groq requests now send `parallel_tool_calls=false`; a one-request probe changed the response from two calls to one.

These findings establish application compatibility gaps, not the full cause of every baseline failure.

## Scope of B06 and B07

B06 and B07 are currently proposals, not implemented baselines. The existing diagnostics provide narrow coverage:

- D02 reads one fixture.
- D03 performs one calculation.
- D04 formulates a word equation and calculates it.
- D05 resolves conflicting evidence.
- D06 recovers from a controlled failure.

- These diagnostics are candidate building blocks for future tool handoff baselines, but they are separate one-case observations and do not establish repeated B01-B05 reliability.
- A future **B06** should promote or extend these cases into a versioned baseline that requires one allowed tool call, the observed result, and a correctly formatted final answer.
- A future **B07** should isolate calculation stages: operand selection, expression formation, calculator result, and final propagation.
- Do not refer to B06 or B07 as ready to run until their manifests, scorers, fixtures, and alternative-answer tests are implemented and frozen.

## Implementation status

| Area | Status | Evidence and limits |
|---|---|---|
| Temperature and max-tokens forwarding | Implemented | Verified for ordinary, streaming, and native LM Studio requests |
| Keyboard-editable numeric settings | Implemented | Direct text entry and validation are implemented; real-browser layout/keyboard behavior still needs verification |
| Independent 1-10 model slots | Implemented | Browser tests cover slot count, add/remove, preserved edits, and independent baseline payloads |
| Configuration-first scheduling and per-config task subsets | Implemented | Browser/API tests cover the scheduler; live qualification remains separate |
| Request/response transport capture | Implemented | Bounded, redacted HTTP evidence is captured; streaming bodies are not consumed |
| Rejected-response retention | Implemented | Rejected model/text responses are retained in attempt data where workers complete |
| Offline replay | Implemented | Replay uses captured native shapes or the current normalizer/parser without model/tool execution |
| JSON-call compatibility bridge | Implemented | It accepts exactly one complete, explicitly advertised Auto-mode call; Qwen2.5 follow-up evidence exists |
| Groq single-call request policy | Implemented | Groq native requests send `parallel_tool_calls=false`; it was verified by a one-request probe |
| Calculator repetition guards | Implemented | Exact repeated calculator calls stop after bounded recovery feedback |
| Fixture-read caching and repetition guards | Implemented | Identified as exact repeated-read handling, not semantic operation detection |
| B02/B05 rubric-v2 | Pending | Baseline-v1 remains unchanged; alternative-answer and deliberate-failure tests are not yet a published pilot |
| Fixture-name JSON-Schema enum | Implemented | ReadFixture advertises only task fixture names and still rejects unknown executable names |
| Task-state and settlement modes | Partially implemented | Experiment state and guided/autonomous identity exist; task-specific automated settlement conditions are pending full validation |
| Complete inference/load profile | Partially implemented | Playpen request values exist; effective provider/model and LM Studio load state are not one complete profile |
| Conservative semantic loop detection | Partially implemented | Exact reads/calculations, normalized exact expressions, and consecutive format errors are guarded; semantic equivalence is not established |
| Cross-browser UI verification | Pending | DOM tests do not prove real-browser keyboard or layout behavior |

## Principal findings

### P0-1: Tool completion is being mistaken for task completion

Several saved live runs recorded successful fixture reads and successful calculator executions but ended with:

- invalid JSON
- no final report
- timeout
- iteration exhaustion
- repeated tool calls
- unsatisfied source/evidence checks

Examples include:

- Gemma 4 returned explanatory prose instead of the required JSON after reading the fixture.
- NeuralDareDevil reached 87.5/100 but omitted the `B`-refund category adjustment.
- Qwen2.5 performed one correct calculator call but repeated reads and never finalized.
- Qwen3.5 obtained correct-looking arithmetic but did not finish within the task budget.
- Two B02 reports completed, but strict evidence failed because required sources were missing or quotations were fabricated/unsupported.

The runner correctly keeps strict pass separate from operational tool success in [`benchmarks/runner.py`](../benchmarks/runner.py) and [`benchmarks/tasks.py`](../benchmarks/tasks.py). This is a finding, not a scorer bug for B01: successful execution does not imply a correct answer.

**Corrective action**

1. Add a first-class baseline stage classification:
   setup/preparation, protocol, tool execution, evidence assembly, finalization, and scorer result.
2. Stop presenting a run as “completed” when no valid terminal report exists; retain `completed` only for execution completion and keep `strict_pass` independent.
3. Keep the existing autonomous mode unchanged in the next small pilot. It should continue to let the model decide when evidence is sufficient and when to finish, subject to safety and repetition guards.
4. Add a separately labeled guided-settlement mode only after it has explicit task-state rules. It should track task-specific requirements without consulting the scorer’s expected answers:
   - B01: record the fixture read and sufficient distinct category/grand-total calculations before requesting finalization
   - B02: record required source reads and actual observed quotations before requesting finalization
   - B03: record required file/line inspection and report artifact state before requesting finalization
   - B04: record primary failure, backup result, and empty-result handling before requesting finalization
   - B05: record all sources and the authoritative constraint before requesting finalization
5. A reading or one calculator call must not prove that every required calculation or citation is complete. A settlement controller must define the state fully and reserve a bounded finalization budget.
6. Guided-settlement passes must not be presented as improved autonomous-agent performance. Publish the autonomous and guided modes as separate experiment types.

### P0-2: Repeated operations consume iterations and live time

The agent already blocks repeated fixture reads and exact repeated calculator expressions, but observed runs still spent many turns on different or semantically redundant calculations.

Examples:

- Qwen3.5 calculated `37+12-5`, `37-5`, and `37+5` in separate turns instead of committing to the first correct result.
- Qwen2.5 repeatedly read the same fixture before the guard stopped further reads.
- Qwen3.5 B02 repeatedly calculated `10+0`.
- NeuralDareDevil/Mradermacher emitted malformed action/recovery cycles.

The loop guards are in [`core/agent.py`](../core/agent.py), and the `B01` execution guidance is in [`benchmarks/runner.py`](../benchmarks/runner.py).

**Corrective action**

1. Expand loop recovery from exact repeated operations to:
   - repeated calculations with unchanged inputs
   - explicitly defined operation duplicates, such as the same expression or the same normalized operands and operator structure
   - repeated malformed actions
   - repeated reads within the same evidence set
2. Do not group different calculations solely by shared operands or a shared final number. For example, `37 + 12 - 5`, `37 - 5`, and `37 + 5` perform different operations and may represent legitimate intermediate category and total calculations.
3. A precise semantic rule requires a model-facing normalized operation, such as canonicalized decimal expression and exact operand sequence, plus the task state in which it was submitted. It must also distinguish a category subtotal from the grand total.
4. Preserve the first verified observation and every original observation/decision in the audit record. If history compression is added, make it model-facing only and retain the full trace separately.
5. Make the correction prompt explicitly say “use the result already observed; do not call an operation that is a duplicate under the configured rule.”
6. Introduce a maximum number of evidence-gathering turns for small fixed baselines. Reserve the remaining iterations for finalization and correction.
7. Keep write and live/stateful operations uncached.

### P0-3: Local reasoning models can exhaust the live budget before finalization

The `8f2abeb...` B01 follow-up returned four successful model responses with tool calls and no final report. Across the four completed responses, 2,011 reasoning tokens were reported against 2,288 completed-response output tokens; this was aggregate evidence, not one response.

This is related to:

- model/template reasoning behavior
- LM Studio server/model load configuration
- the `max_tokens` request setting
- task wording and repeated planning
- request latency and the remaining shared task deadline

It is not established that a higher timeout alone is the fix.

**Corrective action**

1. Expose a per-model reasoning preset/profile only when the backend and model support it; do not invent provider parameters.
2. Distinguish and record:
   - Playpen request value
   - provider acknowledgement or effective response metadata
   - LM Studio server/load value
   - server default
3. Add a bounded “reasoning budget probe” that changes only one supported setting and reruns D01-D03 or B01.
4. Improve finalization prompts for reasoning-heavy models; do not rely on more iterations.
5. Continue to use five-repeat live qualification; one slow run proves latency, not reliability.

### P0-4: Provider/model presets are not yet a complete reproducible model profile

The implementation currently sends `temperature` and `max_tokens` explicitly on:

- ordinary chat
- streaming chat
- OpenAI-compatible native tool calls

The LM Studio backend is in [`backends/lm_studio.py`](../backends/lm_studio.py), and native forwarding is in [`backends/base_backend.py`](../backends/base_backend.py). Request tests verify this in [`tests/test_lm_studio_request_settings.py`](../tests/test_lm_studio_request_settings.py).

`Max iterations` belongs to the Playpen agent loop, not LM Studio. It is enforced in [`core/agent.py`](../core/agent.py).

Provider reasoning controls, LM Studio GUI presets, context length, GPU offload, KV-cache placement, and other load settings are not represented as one saved Playpen profile.

**Corrective action**

1. Add a per-model **Inference profile** containing every Playpen-supported request setting:
   `temperature`, `max_tokens`, `max_iterations`, `tool_calling_mode`, and supported provider reasoning fields.
2. Add an optional **Model load profile** for LM Studio fields exposed by its load API. Leave unsupported fields explicitly unavailable.
3. Before a run, record requested, effective/confirmed, default, and unknown states separately. Do not represent an unconfirmed GUI value as an applied default.
4. Record server defaults and the configured model identity without exposing credentials.
5. Never claim a GUI preset was reproduced unless the corresponding request/load values were actually sent or verified.

### P1-1: Native, JSON-call, and textual protocols still require model-specific recovery

The base adapter recognizes native calls and the narrow Auto-mode JSON-call bridge in [`backends/tool_protocol.py`](../backends/tool_protocol.py). It deliberately does not extract calls from arbitrary prose or execute unknown/multiple calls.

This behavior fixed the Qwen2.5 calculator/recovery examples in a focused follow-up, but text protocol compliance remains weak in several local models.

**Corrective action**

1. Record provider/model native-tool capability separately from the execution policy:
   `untested`, `advertised by provider`, `observed working`, or `observed failing`, with the provider, model, tested settings, and route attached.
2. Treat `Auto` as an execution policy only; it does not prove native model capability or that a provider returned native calls.
3. Add provider/model capability detection and explicit route labels:
   native required, native supported with Auto, or prompt only.
4. Retry only bounded format correction within existing budgets; do not silently switch providers or routes.
5. Preserve and report rejected raw text for one protocol failure sample.
6. Continue to separate native call transport success from:
   argument correctness, tool-result handoff, finalization, and factual correctness.
7. Keep the Groq `parallel_tool_calls=false` request explicit for a single-action loop.

### P1-2: Fixture source names should be constrained by the task

The baseline `ReadFixture` implementation now advertises task-specific fixture names and executable unknown-name denial. This reduces avoidable grounding and wrong-name failures while preserving rejection of arguments outside the fixture set.

**Corrective action**

1. Add fixture-name enum/`const` constraints near the front of implementation.
2. Keep the unknown-name denial in the executable tool; never silently rename or alias a model's argument.
3. Add wrong-name diagnostics to the live evidence and category counts.
4. Add targeted tests for guesses such as `catalog.json`, `notice.txt`, or another non-existent name.

### P1-3: B02 and B05 baseline-v1 contracts need explicit ambiguity fixes

The live evidence identifies two rubric/wording issues:

- B02 accepts `Sunday` but the fixture contains `Closed on Sundays.`; factually equivalent wording can be rejected if the model uses a plural or sentence form.
- B05 requires the literal numbers `12` and `10` in `rejected_reason`, although the task prompt does not explicitly instruct the model to include both values.

These limitations are already documented in the five-task study and issue register, but they remain active baseline-v1 rules.

**Corrective action**

1. Create `baseline-v2` only after publishing the revised contract and fixtures.
2. B02:
   - allow a canonical closed-day enum plus equivalent aliases
   - require the exact quotation from an observed source
   - require source coverage separately from quotation correctness
3. B05:
   - explicitly require both `12 A` and `10 A` in the prompt and rubric, or remove that unstated wording requirement
   - keep the fact, constraint, source, and unknown-warranty checks visible separately
4. Retain baseline-v1 scores unchanged; do not silently pool or retroactively improve historical results.
5. Add deliberate alternative-answer tests before launching another ranking.

### P1-4: The UI now supports independent cards, but a final cross-browser gate is still needed

The independent model-card implementation exists and the automated browser tests cover:

- 1-10 model slots
- independent model selections
- preserved edits after count changes
- add/remove behavior
- per-slot temperature, iterations, tokens, time limit, tools, and endpoint
- baseline launch payloads

`temperature=0` is preserved and direct keyboard entry is implemented in [`debugging/dashboard/templates/index.html`](../debugging/dashboard/templates/index.html) and [`debugging/dashboard/templates/workspace_models.html`](../debugging/dashboard/templates/workspace_models.html).

**Corrective action**

1. Run a real browser test at 1024px and 1920px widths with ten cards.
2. Verify Enter/Tab, clearing fields, replacing values, invalid-entry blocking, and Apply Defaults behavior.
3. Verify changing/removing a model does not change another model's endpoint or temperature.
4. Verify saved slots restore after refresh and that legacy slots inherit main defaults only once.

## Documentation drift and missing information

| Priority | File | Finding | Required documentation action |
|---|---|---|---|
| P1 | [`baseline-evaluation-plan.md`](baseline-evaluation-plan.md) | It still says live model/provider qualification is pending even though multiple live studies now exist | Add a dated implementation/live-status section that distinguishes harness completion, offline tests, protocol diagnostics, and qualification |
| P1 | [`baseline-tests.md`](baseline-tests.md) | It includes long dated appendices and duplicate integration updates | Keep a short current workflow and move dated results to a linked study index |
| P1 | [`issues-and-resolutions.md`](issues-and-resolutions.md) | It has become a cumulative issue register and mixes completed fixes, limits, and dated live observations | Add explicit status labels: implemented, verified offline, live-observed, pending, or superseded |
| P1 | [`local-model-troubleshooting.md`](local-model-troubleshooting.md) | It contains correct historical point-in-time observations but could be mistaken for current model scores | Add a visible snapshot date and forbid ranking or generalizing one-run outcomes |
| P1 | [`controlled-study.md`](controlled-study.md) | It clearly identifies 1,200-case scheduling and 240-case B01, but not a direct link to the latest baseline state | Add links to latest report/attempt index and state that historical scheduling is not live revalidation |
| P1 | [`model-comparisons.md`](model-comparisons.md) | It explains independent Playpen parameters but not server-effective LM Studio values | Add requested/effective/server-default provenance and a link to the per-model profile |
| P2 | [`README.md`](../README.md) | The main overview links setup and architecture but does not lead directly to baseline/finding status | Add a short current-status section with baseline status, diagnostic status, and a link to this report |
| P2 | [`diagnostics.md`](diagnostics.md) | It separates diagnostics from baseline qualification, as it should | Add the latest live pass/fail status and explicit “do not qualify B01-B05” badge |
| P2 | [`keys-costs-maintenance.md`](keys-costs-maintenance.md) | Some review and allowance dates are dated snapshots | Add next-review automation or a more visible snapshot-expiry label |

## Required implementation sequence

### Phase 1: Add schema guards and instrument, before broadening the model sweep

1. Reproduce one captured defect in B01 before broadening the sweep.
2. Add fixture-name enum/`const` constraints for each baseline task, retain executable unknown-name denial, and add targeted wrong-name tests.
3. Use temperature `0`, an explicitly recorded supported max-token budget, 10 iterations, and a known server/load state.
   - Use each configuration's supported budget; do not assume that 2048 or 4096 is valid or safe for every provider.
   - Keep the proven Groq 512-token paced configuration as a positive-control option.
   - Label comparisons between 512, 2048, and 4096 tokens as different conditions.
4. Keep a small multi-model pilot panel for the regression strategy:
   - one positive control with native-tool support
   - Qwen2.5 Coder for protocol/JSON-call comparison
   - one local reasoning model for timeout/finalization evidence
5. Record:
   - outgoing request body
   - provider/native mode
   - finish reason
   - reasoning and output token counts
   - selected tool calls
   - accepted/rejected calls
   - actual tool observations
   - final candidate
   - validation result
   - elapsed time
6. Do not rerun a failed case silently. Preserve the original attempt and assign it a new rerun ID.

### Phase 2: Fix settle-and-finalize behavior

1. Add per-task required-evidence state.
2. Autonomous mode keeps its existing behavior and identity: the model decides when to finish within iteration/time and repetition guards.
3. Apply forced concise finalization only in the separately labeled guided-settlement mode, after its explicit task-state conditions are met.
4. Add conservative repeated-read/calculation guards with precise operation rules.
5. Preserve the current unchanged baseline scorer and baseline-v1 results.

### Phase 3: Add model/request/load provenance

1. Persist explicit Playpen request values.
2. Capture response-reported model and usage metadata.
3. Query/record LM Studio load state when supported.
4. Show requested, confirmed, and server-default values separately.
5. Add a profile diff view for comparing models.

### Phase 4: Add rubric-v2 pilot

1. Build a separate baseline-v2 evaluator for B02/B05 ambiguity fixes.
2. Run alternative-answer and deliberate-failure tests.
3. Keep baseline-v1 comparison artifacts immutable.
4. Do not compare or pool v1 and v2 aggregate scores as if they used the same contract.

### Phase 5: Qualify live baselines

1. Start with B01 and B04 as protocol/evidence controls.
2. Use the existing D02-D06 capability diagnostics for bounded one-operation handoff, evidence, and recovery checks until B06/B07 are implemented, tested, versioned, and frozen.
3. Add B02/B05 only after their contracts are versioned.
4. Run repeated live comparisons only after setup, request policy, and evidence gates are stable.
5. Do not refer to proposed B06/B07 as accepted live baselines before they exist as frozen, scored implementations.

## Acceptance criteria

### Change-level acceptance

Apply only to the code change being verified:

- The focused offline suite remains green or the delta is explicitly explained.
- The changed behavior has a regression test that fails without the change.
- A timeout or truncation cannot be recorded as a successful answer for the changed execution path.
- A successful tool call is separately reported from final-answer correctness.
- Rejected actions and actual observations remain attributable to the changed path.
- A fixture-schema fix passes wrong-name and allowed-name tests without silently rewriting model arguments.
- A settlement-mode change is tested separately for autonomous and guided behavior.
- Request/load provenance reflects requested, confirmed, default, and unknown states accurately.
- Groq native requests explicitly send a serial one-call policy where covered.

### Live baseline qualification

This gate is separate from change-level acceptance:

- At least a small repeated multi-model pilot has completed under recorded, supported settings.
- A five-repeat positive-control model passes repeatedly before broader qualification is claimed.
- Qwen2.5 JSON-call and native/text protocol recovery remain measured under the applicable settings.
- A timeout, quota block, provider rejection, or unavailable evidence is reported separately from wrong or incorrect answers.
- D02-D06 or a later frozen baseline provide the narrow handoff/evidence checks agreed for the pilot.
- B02/B05 alternative-answer tests are added before rubric-v2 results are published.
- A repeated live result reports pass count, attempt count, quality, elapsed time, usage, and unavailable evidence separately.

## Suggested priority order

| Priority | Change | Expected effect |
|---|---|---|
| P1 | Reconcile implementation/evidence status | Makes implemented, partial, and pending work unambiguous |
| P1 | Fixture-name enum and wrong-name tests | Small, testable reduction in grounding failures |
| P0 | Explicit task-state tracking and settlement modes | Prevents correct tool results from dying before finalization while separating guided from autonomous runs |
| P0 | Conservative repeated-read/calculation guards and audit-preserving history compression | Cuts wasted iterations and local latency without conflating different calculations |
| P0 | Requested/effective/load-value provenance | Makes model comparisons reproducible |
| P1 | Native vs prompt capability metadata | Separates protocol support from model intelligence |
| P1 | Baseline-v2 pilot | Repairs known B02/B05 ambiguity without rewriting v1 |
| P1 | Real cross-browser/model-card verification | Proves layout and keyboard behavior beyond DOM tests |
| P2 | Documentation/status cleanup | Keeps live evidence, plans, and implementation state understandable |

## Bottom line

The baseline failures are real live-model results, not an artifact of the offline suite. The highest-value next work is not to increase every timeout or make the scorer looser. It is to:

1. make tool evidence and finalization explicit,
2. stop repeated work deterministically,
3. send and record the complete reproducible request/load profile,
4. version known rubric ambiguities rather than silently changing scores,
5. run small repeated live pilots before declaring B01-B05 reliable.
