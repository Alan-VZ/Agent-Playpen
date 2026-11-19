# MTT Assessment and Implementation Clarifications

Date: November 19, 2026

Status: documentation assessment; no implementation or runtime changes are authorized
by this document.

Evidence sources:

- [MTT requirements and build specification](mtt-model-testing-tool-requirements.md)
- [MTT reference review and application-fit decisions](mtt-reference-review-and-application-fit.md)
- [VS Code MTT assessment review](mtt-assessment-review-2026-11-19.md)
- [November 19 independent verification](verification-baseline-spec-2026-11-19.md)
- [November 19 verification case results](studies/2026-11-19-verification-case-results.csv)
- [Baseline finalization corrective plan](baseline-finalization-corrective-plan.md)

## 1. Decision

Proceed with MTT only as an evidence-led, staged implementation:

1. canonical evidence and historical import
2. profiles and configuration identity
3. bounded Quick Screen
4. profile-specific exclusions and application-fit reporting
5. narrow, explicitly qualified releases
6. framework adapters and larger qualification packs

Defer calibrated reference ratings, commercial judges, broad coding/modality
packs, context sweeps and general leaderboard ranking until a real Playpen cohort
and versioned policy exist.

MTT should answer both primary questions separately:

- is this exact model configuration worth further testing for this application?
- what can it demonstrate for this application, and what alternative should be
  tested instead?

It must not convert a single overall score into a universal statement that a
model is useful or useless.

## 2. Timeout and deadline rules

The existing MTT requirements sometimes treat availability failures and candidate
deadline failures together. These must be independent fields:

| Field | Meaning |
|---|---|
| Observed outcome | provider quota, missing key, provider rejection, load failure, local timeout, provider timeout, completed or cancelled |
| Attribution | candidate behavior, provider/configuration, harness defect, host contention or unresolved |
| Profile effect | eligible, failed runtime fitness, inconclusive, not usable for this deadline, or test not run |

A verified timeout for a healthy host is a failure of the exact deadline and
operating profile. It can exclude a model from a profile with that deadline even
when a longer-budget test might establish task competence.

The evidence must record whether the timeout occurred during:

- model preparation or loading
- provider queue or pacing
- generation
- tool execution
- finalization
- worker supervision

A provider timeout or quota does not establish model inability.

The existing outcome categories in `benchmarks/outcomes.py` are useful for
initial attribution, but MTT should add the separate eligibility effect and
retained partial-event evidence.

## 3. Historical corpus scope

`HIST-01` must include `controlled-results` with `benchmark-results`,
`diagnostic-results` and `docs/studies`.

The imported corpus is an **evaluation and regression corpus**, not a training
corpus. No model training is required or implied.

The importer must preserve:

- 240-case B01 controlled study records
- 1200-scheduled-case matched five-task results
- direct-answer and real-tool arms
- two rounds and matched fixture seeds
- quota-blocked and unavailable cases
- diagnostic D01-D06 records
- Qwen2.5 protocol follow-up results
- Groq paced follow-up results
- November 19 autonomous pilots
- November 19 Groq five-seed follow-up
- excluded setup runs and their invalidation reason

Do not import only prose summaries. Preserve raw attempts where available and
deduplicate by study/attempt identity. Summaries are views, not duplicate trials.

If a selected failure is later used to tune an adapter or prompt, label it as a
development case. Qualification must use separate held-out cases.

## 4. Quick Screen standard

The current 12-template, two-trial screen must be stated exactly:

- 12 probe templates
- two identical-input trials per template
- up to 24 attempts
- separate model-request count
- separate provider/model load attempts
- explicit whole-screen model-request, wall-time and cost ceilings

The Quick Screen is:

- provisional
- profile-specific
- bounded
- not a qualification
- not a universal model ranking

An application-specific screen may have a different template count, but it must
publish the count and denominators. It must not label a writing/extraction pass
as a tool-agent pass.

The early-stop rule remains:

- three attributable failures spanning at least two fixtures
- valid harness controls
- route/settings verified
- profile applicability documented

An unresolved protocol or environment issue is inconclusive, not a model-failure
score.

## 5. Smaller qualification release

The full 240-attempt default is not required for every MVP profile.

A narrow qualification release must publish:

- exact profile ID and rubric version
- required capabilities
- fixture count and family count
- identical-input repeat count
- held-out case count
- required first-try pass
- required corrected-within-budget pass
- required whole-task pass
- confidence/interval policy
- hard-gate list
- route and tool requirements
- deadline, token and cost operating point

The Quick Screen remains a triage state. It cannot become qualification by adding
an aggregate score.

Five identical successes do not establish broad reliability. They produce a real
small-sample interval and a repeatability observation. General qualification
requires independent fixtures and enough coverage for the declared claim.

### Proposed narrower first profile

A first current-configuration profile could cover one delivered application:

- instruction and structured output
- one allowed tool call
- one returned observation
- result handoff
- one final report
- bounded correction
- repeated identical fixture

It should require a small held-out fixture set, explicit hard gates and a visible
coverage statement. It should not claim B01, B02 or five-task baseline
qualification by analogy.

## 6. Forced finalization arm

Forced finalization, whether it disables tools or reserves a final-only request,
must be a separately identified guided policy.

Record:

- autonomous profile
- guided profile
- model/tool/controller versions
- readiness rule
- observed operations
- final-only request shape
- first-try versus corrected completion
- whether target values entered model-visible feedback

The guided profile may improve completion, but it must not be published as an
unchanged autonomous result.

The implementation also needs a bounded structured finalization request and must
not use hidden expected totals or target answers in model-facing feedback.

## 7. Positive-control scope

No model is a positive control for every application.

A positive-control label must name:

- the capability
- the profile
- the route
- the fixture and model settings
- the repeated trial count
- the latest evidence date
- whether it is still current

Groq Qwen3.8 is useful as a control for D01-D06 and B04 evidence under the
recorded configuration. It is not a B01 positive control after the 0/5 repeated
B01 result. Historical successful controls require current rerun evidence before
being used for a repaired runtime.

## 8. Timeout and partial replay

The evidence package must normalize partial timeout events into replayable
records.

Add this canonical conversion:

```text
partial_events
  -> transport_request
  -> transport_response
  -> request_diagnostic
  -> response_diagnostic
  -> incomplete pending request
  -> outcome category
```

Replay remains read-only:

- no model request
- no tool execution
- no fixture or calculator execution
- no synthesized response

The replay UI must show complete recorded responses and unmatched pending
requests separately.

## 9. Compatibility adapter boundary

A compatibility adapter may accept:

- exactly one complete advertised tool object
- exactly one complete object in an explicitly tested whole-response fence
- object arguments only

It must reject:

- concatenated requests
- object-plus-prose
- multiple objects
- unknown tools
- missing or wrong-typed arguments
- invented observations

The rejected response remains in the evidence record. A new accepted dialect
requires a version, positive tests and negative tests.

## 10. Framework adoption

Pydantic Evals and DeepEval are the first two reasonable adapter trials.

The trial must run against canonical Playpen evidence without launching another
agent implementation:

- successful read/calculate/final sequence
- correct net total with incorrect category subtotal
- no-tool or wrong-tool response
- mixed and multiple tool requests
- repeated call with no final answer
- injected source failure with successful fallback
- forced timeout with one pending request
- quota block
- alternative contract-valid final wording

The result must state which metrics are deterministic, judged or hybrid and which
external calls or dependencies occur. Tool-name matching without actual execution
is insufficient.

Promptfoo can be a matrix/comparison adapter. Inspect AI is better suited to
later isolated environment/coding work. Ragas is an optional RAG pack.
Langfuse/Opik/Langtrace/Evidently are observability or monitoring candidates,
not qualification authorities.

## 11. Recommended implementation sequence

### Phase 1: Source onboarding and evidence foundation

- source connection and catalog discovery
- persistent local model database
- controlled/diagnostic/baseline result importer
- timeout/partial-event replay
- configuration fingerprints
- complete/partial/unknown usage
- profile and application entities

### Phase 2: Autonomous bounded pre-testing and Quick Screen

- profile registry
- 12-template/24-attempt policy
- separate model-request budget
- finite rescue budget
- profile-specific exclusions
- application-fit report
- standing screening policy and resumable campaign queue
- normal task selection that reads the local database without discovery or benchmarking

### Phase 3: Narrow qualification

- versioned profile policy
- held-out fixtures
- hard gates
- small-sample uncertainty
- matched current control
- separate autonomous/guided modes

### Phase 4: Framework adapters

- Pydantic Evals trial
- DeepEval trial
- canonical trace adapter
- no hidden calls or alternate execution

### Phase 5: Larger packs

- coding and modality packs
- context sweeps
- reference cohorts
- `R` calibration
- broad live qualification

## 12. Acceptance additions

The MTT specification already reserves AC-26 through AC-30 for source discovery,
catalog persistence, database selection, campaign resume and access states. Keep
those existing IDs and add genuinely new policy tests as AC-31 onward:

| ID | Required behavior |
|---|---|
| AC-31 | Timeout by valid deadline is a profile failure or inconclusive host condition; missing key/quota is availability failure and never zero ability. |
| AC-32 | Groq B01 0/5 does not become a positive B01 control even if diagnostics and B04 pass. |
| AC-33 | Quick Screen reports templates, attempts, model requests and load attempts as separate counts. |
| AC-34 | A Quick Screen pass is provisional and does not create current qualification. |
| AC-35 | A guided-only success and an autonomous success receive distinct profile and result identities. |
| AC-36 | Historical records are named evaluation/regression corpus entries, and tuning exposure prevents held-out qualification. |
| AC-37 | Partial timeout responses replay in canonical evidence form; one pending request remains pending. |
| AC-38 | Mixed/concatenated tool output is rejected without extraction and receives explicit protocol feedback. |
| AC-39 | A model useful for extraction can remain unsuitable for autonomous tools and receives no universal-use label. |
| AC-40 | A framework adapter cannot add hidden retries, execute an alternate agent or override deterministic failures. |
| AUTO-AC-01 | With a standing policy enabled, MTT discovers and pre-tests eligible candidates without per-model approval, within configured budgets. |
| AUTO-AC-02 | Scheduled rediscovery queues only new, changed or stale work; unchanged catalog entries and completed tests are not redundantly rerun. |
| AUTO-AC-03 | A failed model and an inaccessible model produce distinct outcomes while the campaign continues with eligible candidates. |
| AUTO-AC-04 | Quota, token, cost or host limits stop or defer the campaign without paid fallback or duplicate reservations. |
| AUTO-AC-05 | Pause/restart preserves partial and completed evidence and accurately reports campaign lifetime. |
| AUTO-AC-06 | Later task selection uses the autonomous database population without discovery or benchmark calls. |

## 13. Final recommendation

Support the smaller MTT MVP with the following corrections:

- add controlled-results to historical import
- split timeout and quota outcomes from ability
- define narrow screen and qualification policies
- separate autonomous and guided finalization
- call the historical data an evaluation/regression corpus
- preserve partial replay
- defer reference-centered `R` and broad qualification
- use current, application-specific controls
- make framework adoption an adapter trial

This scope will let Playpen stop repeated wasted tests sooner, retain useful
limited model roles and avoid turning a small live sample into a broad model
competence claim.
