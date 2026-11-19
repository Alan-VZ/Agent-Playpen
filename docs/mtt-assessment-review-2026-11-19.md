# Review of VS Code's MTT assessment

Date: November 19, 2026. Scope: documentation review only. No implementation, tests, configuration, dependencies or running services were changed for this review.

Reviewed: [MTT assessment and enhancement recommendations](mtt-assessment-and-enhancement-recommendations.md), against the [MTT requirements](mtt-model-testing-tool-requirements.md), [reference review](mtt-reference-review-and-application-fit.md), [November 19 verification](verification-baseline-spec-2026-11-19.md), and the current evidence/outcome/runner surfaces.

## Decision

**Subsequent user clarification:** the intended product is source onboarding and pre-testing into a persistent local model database, followed by task-based selection from that database. A read-only historical registry is an internal step, not the completed first product. The first usable release must connect/discover a source, pre-test a bounded selection, persist across restart and answer later selection requests without repeating discovery or screening. The main MTT requirements now make this explicit in sections 1.2 and 14.3. This clarifies the delivery emphasis below; it does not remove the evidence-integrity or qualification rules.

**Support the proposed smaller MVP and implementation direction. Tighten the decision rules below before calling it an implementation-ready qualification policy.** The assessment is a useful prioritization of the existing requirements, not evidence that the implementation defects or live qualification gaps have been repaired.

The first delivery should make existing evidence usable and prevent repeated expenditure on a known-unsuitable configuration for a selected job. Calibrated reference ratings, large task packs and commercial judges can follow. Deferring them is consistent with the main requirements' staged design and uncalibrated-score state; it is not a reason to remove those eventual requirements.

## What I agree with

- Test exact configurations and applications; do not classify model names as universally useful or useless.
- Reuse the actual Playpen Agent, model leases, provider adapters and UACP gateway.
- Normalize complete/partial evidence and import history before adding evaluation-framework dependencies.
- Keep narrow successful capabilities visible even when a larger autonomous task fails.
- Show hard gates, coverage and evidence before a general number. Do not publish a 50-centered R without a real reference cohort.
- Use a finite Quick Screen and targeted diagnosis, not indefinite retries or parameter changes.
- Trial Pydantic Evals and DeepEval as adapters; no framework is automatically the qualification authority.
- Keep recommendations read-only and allow “none qualified” as a valid answer.

## Corrections and clarifications

### 1. Timeouts are not always excluded operational failures

The assessment's “Availability is not model ability” section groups all timeouts and request rejections with missing keys and quota, calling them operational outcomes rather than ability failures. That is too broad for a tool whose job is to decide whether a configuration meets a real deadline.

Use three separate fields: **observed outcome**, **supported cause/attribution**, and **effect on profile eligibility**.

| Situation | Required treatment |
|---|---|
| Missing key, quota exhaustion, unreachable provider, invalid test setup | Blocked/inconclusive ability evidence. Do not assign an inability score. |
| Verified interface defect or provider protocol incompatibility | Integration/route limitation; diagnose or exclude that route. Do not infer a universal model-weight defect. |
| Correctly configured candidate cannot finish within a valid application deadline on a healthy host | Failed runtime-fitness/whole-task opportunity for that operating profile. It may remain useful for a slower or simpler profile. |
| Host overload, uncontrolled queue delay, or invalid pacing assumption prevents the intended test | Inconclusive operating condition, with recorded evidence and the predeclared exclusion rule. |
| Provider rejects a genuinely malformed candidate-generated tool request | May be evidence of candidate protocol behavior under this interface, rather than an unrelated availability outage. Preserve the request and rejection before deciding. |

Do not use the ambiguous phrase “model ability” to erase a demonstrated inability to satisfy the user's constraints. Equally, a deadline failure does not prove the model cannot solve the task with a different budget. The main MTT attribution table already makes this distinction; retain it in the MVP.

### 2. Include controlled-results in the first historical importer

MVP 1 explicitly lists `diagnostic-results`, `benchmark-results` and summaries, but omits **`controlled-results`**. Include all three result roots, as required by HIST-01.

The 240-case and 1200-scheduled-case studies contain particularly important evidence: direct-answer versus real-tool arms, repeated rounds, quota skips, and correct answers alongside protocol rejections. Importing only their prose summaries would lose much of the attribution and repeatability evidence.

Preserve the original score and denominator; deduplicate summaries versus raw attempts. Never make current MTT Q/R values by pooling these historical contracts. The November 19 cancelled empty-tool setup run must remain explicitly excluded.

### 3. Smaller qualification still needs an explicit evidence threshold

It is reasonable to defer the full 240-attempt pack. However, MVP 3 is named “Current qualification” and needs a quantitative, versioned policy before anything is labeled qualified.

- MVP 1 can show historical observations, compatibility and unknowns.
- MVP 2 can issue a small-sample **screen-policy exclusion** or **provisional** result under the frozen early-stop rule. Passing the screen is not qualification.
- MVP 3 may qualify a narrow application with an explicitly adequate subset of fixtures, required capabilities, sample/interval gates, exact-input repeats and held-out whole-task checks.
- A narrower test pack must produce a narrower qualification. It cannot silently lower the main specification's evidence requirements for broad autonomous tools.

Use the MTT requirements as the canonical policy source, or explicitly version and review a replacement. “The positive control passed” and “every result links to evidence” are necessary but insufficient qualification criteria by themselves.

### 4. Forced finalization belongs to a separately identified guided arm

The assessment correctly says guided and autonomous profiles remain separate. Make that scope explicit on the preceding bullets for “structured final request” and “tool calls prohibited once state is complete.”

Observe autonomous finalization as behavior. A controller that disables tools or supplies a final-only request after a readiness rule is a different guided policy, even if it improves completion. Label its scores accordingly. Readiness must use valid observed operations and task contracts, never target-answer values or the independent scorer's hidden totals.

An ordinary autonomous parser/schema correction and hard safety/budget limits also need to be recorded, but should not be confused with introducing a new task-state-driven finalization policy. Preserve first-try, corrected and guided results separately.

### 5. Call the old results an evaluation/regression corpus

Enhancement 3 calls existing records the “best initial training corpus.” No training is required for this project. Rename this to **historical evaluation and regression corpus**.

If prompts/adapters are tuned from selected failures, designate those as development cases. Keep a separate held-out recommendation/qualification set and mark cases exposed during tuning. Do not train or tune against the same cases and then present the resulting performance as independent qualification.

### 6. Pin down the screen count and provisional-score display

“12–24 probe plan” could mean template families, cases, attempts or model requests. The current proposal is **12 probe templates × two identical-input trials = up to 24 attempts**, with a separate ceiling of 80 model requests and 20 minutes. Application-specific packs may differ, but must declare each count explicitly.

The assessment already includes a no-complete-score state for insufficient evidence. Preserve that rule: show provisional per-capability rates and coverage; do not manufacture an aggregate Q by renormalizing around untested hard cases. A future R field can be null. Reference calibration remains deferred until its actual cohort exists.

### 7. Keep compatibility adapters bounded and auditable

The phrase allowing mixed-output extraction when a documented adapter applies needs a strict contract. An adapter may support an explicitly tested grammar, but not blindly execute prose, concatenated actions or unknown functions because they resemble tool requests.

The initial supported envelope can remain exactly one advertised tool with object arguments, optionally in the documented whole-response fence. For other shapes, retain the response and give bounded protocol feedback. Any newly accepted dialect gets a version, negative tests, actual gateway validation and separate configuration identity. Native parallel-call support is also a declared policy, not silent multi-action extraction.

### 8. Make reference-control scope explicit

Use scripted canonical controls to establish harness mechanics. A live model serving as a positive control must have current evidence on the actual capability/application being checked.

Groq's 6/6 diagnostic result and 5/5 B04 result do not make it a positive control for B01: the recorded five-seed B01 result was 0/5. Historic stronger-model successes can help select new control candidates, but do not establish that they pass today's runtime. A successful control is also not sufficient to blame every other failure on model weights; candidate-specific routing and template issues remain possible.

## Suggested implementation contract

1. **Evidence foundation:** canonical complete/partial attempt schema; read-only replay; unknown usage; outcome plus attribution; regression against the captured timeout case.
2. **Source onboarding and local model pool:** connect/discover/cache sources and models, run an explicitly approved autonomous bounded pre-test campaign, persist results and resume without repeating completed work.
3. **Profile and history registry:** schema-validated profiles/configuration fingerprints; all historical result roots, including controlled-results; deduplication; original/current editions and compatibility markers.
4. **Bounded screen:** explicit attempts versus calls, finite rescue budget, profile-specific early exclusion, availability holds and cancellation.
5. **Application-fit UI:** supported uses, limitations, unknown capabilities and evidence-backed alternatives. No claim of writing/coding/translation competence from a tool test or model name.
6. **Database-first selection:** normal task selection filters stored evidence and does not refresh discovery or launch a benchmark. A lightweight selected-model readiness check and a targeted approved retest are separate operations.
7. **Narrow qualified recommendations:** enforce the declared gate/sample/repetition policy before offering unattended selection; keep all other recommendations experimental or provisional.
8. **Framework trial and later expansion:** compare saved/synthetic canonical traces before dependency adoption; add broad packs, judges and reference-centered R only when justified and validated.

This sequence can save evaluation time before the project has a large calibrated cohort. It keeps the longer-term capability/rating requirements intact while making the first deliverable smaller.

## Definition of done for this assessment follow-up

- A bounded source-onboarding and autonomous pre-test loop populates the persistent model database before normal task selection.
- Normal task selection uses stored evidence without repeating catalog discovery or screening.
- Source/campaign removal, outage and budget behavior preserve prior evidence and never fabricate qualification.
- Timeout and provider-rejection treatment is conditional and consistent with the main attribution policy.
- Autonomous source/campaign pre-testing is allowed only within an approved standing policy and budget; normal task selection remains database-first.
- Controlled-study raw records are explicitly included in MVP import.
- Each released profile defines what screen success, provisional status, exclusion and qualification mean.
- State-driven forced finalization cannot be reported as an unchanged autonomous result.
- Historical records are an evaluation/regression corpus; tuning and held-out cases are separated.
- Screen templates, attempts, model requests and budgets are unambiguous.
- Unknown Q/R and small-sample limits remain visible.
- Current, capability-specific controls and strict adapter boundaries are required.

The existing assessment's local document links and referenced reuse paths were checked. The runner still records timeout status and the standard replay helper still reads `interactions` rather than timeout `partial_events` at review time. This review did not repair those source paths or rerun models.
