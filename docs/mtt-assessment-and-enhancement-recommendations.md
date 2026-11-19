# MTT Assessment and Code-Enhancement Recommendations

Date: 2026-11-19

Status: independent assessment; documentation only; no implementation, dependency,
model run, or runtime configuration is authorized by this document.

Scope:

- [MTT requirements and build specification](mtt-model-testing-tool-requirements.md)
- [MTT reference review and application-fit decisions](mtt-reference-review-and-application-fit.md)
- The [November 19 verification report](verification-baseline-spec-2026-11-19.md)
- The existing Playpen benchmark, diagnostics, evidence, model-picker and dashboard
  implementation
- The supplied framework/reference links summarized in the user's project scope

## Executive assessment

MTT is a sound and necessary product direction for Playpen. The current local and
cloud model evidence demonstrates that model usefulness is configuration- and
application-specific:

- Groq Qwen3.8 passed all D01-D06 diagnostics and all five B04 recovery seeds,
  but failed all five independent B01 reconciliation cases.
- Local Qwen3.5 completed several tool and arithmetic workflows and passed B04,
  but B01 timed out after successful calculations and repeated calls.
- Local Qwen2.5 passed five of six diagnostics, but failed longer B01/B04
  workflows because of mixed protocol output and missing evidence.
- Successful tool transport and arithmetic do not establish finalization or
  whole-task correctness.

The existing MTT specification correctly avoids turning these observations into
permanent labels about every possible use of a model. It separates availability,
route, capability, operating point and application fit. That is the central
design principle MTT should retain.

The specification is not yet an implementation-ready first milestone. It is broad
and internally sophisticated, but it combines:

- Historical evidence import
- Live Quick Screens
- Deep qualification
- Reference cohort calibration
- Application-fit scoring
- Commercial judge orchestration
- External benchmark adapters
- Selection and comparison UI
- Partial timeout replay
- Context, coding, RAG, safety and modality testing

Those are different products and dependencies. The first MTT release should
implement a small evidence-led core and defer the remaining dimensions until the
core has real usage.

## What is already strong

### 1. Configuration, not model name, is the tested entity

The specification requires provider, model revision, quantization, chat template,
route, tools, controller, prompts, hardware, inference settings and budgets to
be represented or marked unknown.

This matches the actual Playpen evidence. It also prevents a test of one server
configuration from becoming an unsupported statement about every deployment of
the model.

**Recommendation:** keep this requirement as a hard invariant. A qualification
decision must carry an immutable configuration fingerprint and cannot be inferred
only from a model display name.

### 2. Availability is not model ability

Missing credentials, provider quota, load failure, timeout and request rejection
are operational outcomes, not ability failures.

This is necessary and already implemented conceptually in the benchmark outcome
categories. MTT should retain this distinction for every profile and every export.

### 3. Whole-task completion is distinct from tool success

The MTT requirements correctly require result handoff, evidence, finalization,
end state and strict whole-task pass. The November 19 evidence is strong support
for keeping these as separate checks.

### 4. A global score cannot override a failed hard capability

The dual `Q`/`R` proposal is useful for a later maturity stage, but its current
design is too ambitious for the initial implementation.

MTT should initially show:

- absolute profile score
- hard-gate status
- coverage
- confidence/interval
- cost and latency
- concrete strengths and limitations

It should not publish `R` until there is a real, balanced reference cohort.

### 5. Limited useful roles must survive a failed broad role

The application-fit matrix is directionally correct. One model should be able to
be unusable for autonomous tools while remaining useful for extraction or writing.

This is not an exception to the evaluation. It is the product's central use case:
match models to jobs rather than ranking only one universal average.

## Material gaps and code-enhancement needs

### Enhancement 1: Make MTT a profile and evidence product, not a benchmark runner

MTT should not begin by implementing 200 cases and a universal scoring package.

Create the following MVP:

1. A profile registry.
2. A canonical attempt/evidence schema.
3. Historical evidence import.
4. A bounded Quick Screen.
5. Application-fit records.
6. A recommendation filter.
7. A read-only evidence and replay UI.

Qualification and reference scoring should follow only after this evidence core
is stable.

**Likely code reuse**

- `benchmarks/runner.py` for configuration, attempt, budget and summary concepts
- `benchmarks/diagnostics.py` for the first capability-probe pack
- `benchmarks/evidence.py` for bounded redacted evidence and replay
- `benchmarks/tasks.py` for deterministic baseline fixtures and scorers
- `debugging/dashboard/model_sources.py` for local model lease coordination
- `backends/base_backend.py` for route and native-call metadata
- `tools/gateway.py` and `tools/tool_executor.py` for execution outcomes

MTT should build on these surfaces. It should not create a parallel agent loop or
bypass the existing UACP gateway.

### Enhancement 2: Add application and profile schemas

The MTT requirements mention application packs but do not yet define a compact
machine-readable profile record.

Add a schema equivalent to:

```text
ApplicationProfile
  id
  version
  application
  required_capabilities
  optional_capabilities
  required_tools
  allowed_tool_routes
  context_requirement
  required_schema
  evidence_requirements
  latency_bound
  token_budget
  cost_budget
  repeatability_policy
  rubric_version
  hard_gates
  fixture_manifest
```

Store profiles independently from models. This enables the same model to be:

- qualified for extraction
- provisional for writing
- not usable for autonomous tools
- untested for coding

without collapsing these states into a total score.

### Enhancement 3: Upgrade the historical importer before building new runs

The existing Playpen records are the best initial training corpus, but they are
not one clean comparable dataset.

The importer must preserve:

- study ID
- attempt ID
- arm
- task
- fixture seed
- repetition
- model/provider
- route
- settings
- source commit
- runtime source hashes
- transport capture
- partial events
- quota and timeout outcome
- strict score
- original rubric version

Never calculate MTT scores by pooling:

- different arms
- diagnostic and baseline runs
- historical and repaired adapters
- paced and unpaced settings
- output-token 512 versus 2048 runs
- one-case diagnostics and repeated fixtures

The importer should emit `historical_evidence_available`, `compatible_evidence`,
`not_comparable`, or `current_score_not_established`.

### Enhancement 4: Canonicalize timeout and partial replay

The November 19 timeout finding is a serious evidence problem, and MTT will reuse
the same evidence pipeline.

The existing `isolated_attempt` timeout result already retains `partial_events`.
The normal replay helper reads only `interactions`. MTT and existing evidence
views need one canonical conversion step:

```text
partial_events
  -> normalized request/response/intermediate event
  -> replay event
  -> outcome category
  -> canonical attempt record
```

The canonical record must distinguish:

- complete response
- provider response present but worker terminated later
- unfinished request
- truncated response
- provider error
- local timeout
- cancellation

It must remain read-only. Missing usage is unknown.

### Enhancement 5: Separate model capability from route compatibility

The MTT matrix needs at least these independent fields:

- native-call support
- explicit JSON-call support
- prompt-adapter support
- one-call-per-turn policy
- parallel-call policy
- mixed-output handling
- finalization behavior
- result handoff behavior
- structured-output support

`tool_calling_mode=auto` is not proof of native capability. Provider advertisement,
observed working and observed failing are separate states.

This prevents a model from being labeled incapable of tool use merely because the
old adapter misclassified its response.

### Enhancement 6: Add a job-fit recommendation engine

The recommendation endpoint should not return a single model unless the user has
a preference or service objective.

For each application/profile, return:

- qualified candidates
- provisional candidates
- blocked candidates
- untested candidates
- explicit exclusions
- matched evidence
- coverage
- latency/cost trade-offs
- non-dominated alternatives
- recommended missing test

If no candidate qualifies, MTT should say none qualified. It must not choose the
largest or cheapest model as a default winner.

### Enhancement 7: Define the first absolute score without overengineering R

Use a provisional profile score in the MVP:

- deterministic subchecks
- task pass
- first-try success
- corrected-within-budget success
- hard-gate status
- confidence/coverage
- no-complete-score state for insufficient evidence

Defer `R` until there is a frozen, balanced reference cohort. A 50-centered rating
cannot be invented from the current three or four tested configurations.

The implementation should store a future `R`, but not display a misleading
calibrated value before:

- enough distinct configurations
- at least three model families
- at least two serving/provider environments
- comparable profile and suite
- comparable operating-point policy

### Enhancement 8: Use paired and hierarchical uncertainty

Do not turn a small 5/5 result into a 100% claimed reliability score.

The UI and data model should show:

- number of trials
- Wilson interval for independent opportunities
- cluster or template uncertainty for related fixtures
- best, worst and median family behavior
- one model versus another with matched cases
- confidence/corrected-for-selection label

The live Groq B04 5/5 result is promising evidence, not proof of 95% reliability.

### Enhancement 9: Separate finalization from problem solving

The live November 19 evidence shows B01 arithmetic can be correct while
finalization fails.

MTT needs a finalization dimension and first-finalization report phase:

- evidence complete
- structured final request
- tool calls prohibited once state is complete
- one allowed format correction
- exact final artifact
- first-try versus corrected success
- repeated calculation after sufficient evidence

Guided and autonomous finalization must remain separate profiles.

No guided feedback may expose target totals or use expected-answer constants.

### Enhancement 10: Add a malformed-tool protocol pack

MTT should test and classify:

- complete one-tool JSON
- JSON plus prose
- multiple tool requests
- unknown tool
- missing required argument
- wrong type
- invented observation
- partial/truncated call
- non-object arguments
- tool result not used in final answer

The first two categories need route-specific strictness. Mixed and multiple calls
must not be silently extracted unless an explicitly documented compatibility
adapter applies.

### Enhancement 11: Make framework adapters trial-only

Pydantic Evals and DeepEval are the strongest initial optional evaluation-layer
trials.

Pydantic Evals is attractive because it is a Python data/evaluator/reporting
library and does not require the Pydantic agent framework.

DeepEval is attractive for trajectory/tool metrics and pytest-style workflows.
It must be pinned and run against canonical Playpen traces. It cannot become the
qualification authority simply because a metric exists.

Recommended trial order:

1. Pydantic Evals
2. DeepEval
3. Promptfoo for matrix/provider comparisons
4. Inspect AI for isolated environment/coding qualification
5. Ragas for retrieval/RAG only
6. Evidently or Langfuse/Opik for monitoring only
7. LightEval for external benchmark import only

No framework should:

- replace the Agent/UACP execution path
- add hidden model calls
- load `.env` unexpectedly
- export secrets or telemetry
- execute another agent implementation and claim it tested Playpen
- treat tool-name mention as tool execution

### Enhancement 12: Add application-specific reference packs

MTT should extend beyond tool tasks to:

- extraction/classification
- summarization
- writing and rewriting
- retrieval/RAG
- coding/project inspection
- translation/multilingual
- long-document analysis
- calculator/scientific workflows
- autonomous tools

Each pack needs:

- held-out cases
- allowed tools
- expected evidence
- alternative-answer policy
- hard gates
- calibrated judge/human data if subjective
- separate context and cost requirements

No pack should be inferred from a model name or small benchmark.

## Recommended MVP scope

### MVP 1: Source onboarding, persistent model pool and bounded pre-testing

Deliverables:

- Connect/discover one source and cache a paginated catalog
- Run an explicitly approved autonomous bounded pre-test campaign under a standing policy
- Resume paused campaigns without repeating completed cases
- Pre-test a bounded eligible subset and persist results across restart
- Import existing `diagnostic-results`, `benchmark-results`, `controlled-results` and study summaries
- Preserve original settings and denominators
- Parse partial timeout events
- Add model/configuration fingerprints
- Search/filter model, application, status and route
- Export evidence and recommendations

Exit condition:

- Normal task selection queries the stored model pool without re-discovery or re-screening
- Quota failures are not ability failures
- Historical arms are not pooled
- Partial responses replay
- No inference occurs during import

### MVP 2: Quick Screen

Deliverables:

- Profile registry
- 12-24 probe plan
- 80-request/20-minute budget
- early stop
- application-fit matrix
- retest and override decisions

Exit condition:

- a bad model can be stopped for a profile
- a bad route can be diagnosed instead of blamed on weights
- useful limited roles remain visible

### MVP 3: Current qualification

Deliverables:

- Frozen task packs
- hard gates
- deterministic scoring
- Wilson/cluster uncertainty
- matched configuration retry
- finalization and protocol diagnostics

Exit condition:

- MTT does not qualify an arbitrary model from diagnostics alone
- a current positive control must pass a repeated live run
- every result is linked to evidence

### Deferred

- 240-attempt general qualification
- R calibration
- commercial judge
- coding/modality packs
- broad live benchmark import
- parallel-agent qualification
- external hosted observability

## Concrete code changes recommended

The following implementation modules are recommended for a later implementation
turn:

```text
model_testing/
  profiles.py
  manifests.py
  registry.py
  importer.py
  runner.py
  evidence.py
  replay.py
  scorers/
  uncertainty.py
  qualification.py
  application_fit.py
  recommendations.py
  adapters/
```

The first code changes should be enhancements to shared surfaces:

- Add partial-event normalization to `benchmarks/evidence.py`.
- Add schema-validated profile and model configuration entities.
- Add profile and application status to benchmark result summaries.
- Preserve settlement mode and result provenance in export/API shapes.
- Add a read-only `/api/mtt/recommendations` or equivalent UI result.
- Add a task-minimal-tool diagnostic comparator.
- Add a framework-adapter interface that never executes a second agent.

No MTT framework dependency should be selected before the replay and canonical
evidence fixes are validated.

## Reference and framework assessment

The supplied references support application-centric evaluation but not every
project as a primary MTT authority.

| Reference | Assessment |
|---|---|
| Reddit LocalLLaMA list | Discovery source only; treat list content as unverified |
| DeepEval | High-priority trial for agent/tool trajectory metrics |
| Cognee article | Useful layer taxonomy, not a product-ranking authority |
| Evidently | Useful lifecycle/monitoring concepts, optional integration |
| LangChain/LangSmith | Useful experiment/tracing concepts, hosted/retention decisions separate |
| Pydantic Evals | High-priority code-first trial |
| Promptfoo | High-priority matrix/regression adapter trial |
| Inspect AI | Strong later controlled-environment/coding candidate |
| Ragas | Optional RAG/retrieval pack |
| LightEval | Optional broad benchmark import, not core qualification |
| Opik/Langfuse/Langtrace | Optional observability, avoid overlapping mandatory stores |

The [existing MTT reference review](mtt-reference-review-and-application-fit.md)
already captures these distinctions. It should be tightened with exact pinned
versions and license/review dates before any framework is adopted.

## Final recommendation

MTT should be approved as a product specification and Phase 0/1 core, but not for
automatic model qualification yet.

Approve the following scope:

- canonical evidence and historical import
- profile/application model
- Quick Screen
- application-fit matrix
- read-only recommendations
- finite rescue budgets
- partial-event replay
- framework-adapter trial harness

Defer:

- calibrated `R`
- 240-attempt general qualification
- commercial judge
- broad coding/modality packs
- hosted observability
- broad benchmark imports

The first live acceptance gate should be a small, repeated positive-control pilot
plus a weak and unavailable candidate. It should prove MTT can save evaluations,
not merely produce a plausible 0-100 number.
