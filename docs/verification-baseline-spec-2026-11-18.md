# Independent verification of baseline specification implementation

Reviewed commit: `212a0fc22c2110b1d514e9320a4f4b399605983a` on baseline-spec-implementation. Date: November 18, 2026. Verdict: **not ready to approve as a completed implementation**.

## Follow-up implementation status

The following P1/P2 findings have targeted source and regression coverage after
the original review:

| Finding | Current status |
|---|---|
| Failed operations counted as evidence | Fixed: settlement records only successful tool outcomes; error results and failed calculator operations do not advance state |
| Terminal report bypassed guided readiness | Fixed: guided terminal reports are withheld until required observed state is reached, with bounded correction feedback |
| Task-state proxies | Improved: B01 derives required fixture values and requires matching successful calculator results; B02/B05 require exact observed report evidence |
| Native capability promotion | Fixed: successful native handoff marks working only after an acknowledged successful execution; error-only and missing-argument paths mark failing |
| Whitespace repetition canonicalization | Fixed: calculator repetition keys preserve internal whitespace and only successful, valid calls advance state |
| Saved model-slot refresh persistence | Fixed: `/api/defaults` now restores saved `model_slots` from `config/web_agent_config.json`; real-browser refresh verification follows |

Current verification:

- Full Python suite: **558 passed, 9 skipped** after the follow-up fixes.
- Focused settlement/native regressions: **101 passed**.
- Remaining verification gaps: real-browser layout/keyboard/persistence checks,
  complete supported reasoning/load-profile functionality, and repeated live
  autonomous/guided positive-control qualification.

## Checks performed

- Full Python suite independently rerun: **552 passed, 9 skipped**.
- Production templates rendered; baseline_tasks_ui.cjs, baseline_feedback_ui.cjs and local_models_ui.cjs passed.
- baseline-v1 tasks.py is unchanged from d83f954.
- Targeted scripted reproductions below exercise actual controller/Agent code; they are not live-model performance results.
- Live loopback OpenAPI inspection: ExperimentConfig does **not** expose settlement_mode, indicating the running dashboard has not loaded the reviewed backend version.
- No implementation files changed during this review; no new live model generations, merge, or deployment performed.

## Blocking findings

### P1 — Failed operations count as settlement evidence

benchmarks/settlement.py record() records reads based on name, calculations based on expression and writes based on filename without verifying successful results. Reproduction: B01 record orders.csv with an Error result, then 1/0, 2/0 and 3/0 with Error results. ready() returns True. B02 also returns True after every source read returns Error. Failed writes can similarly mark report_artifact.

Use structured execution outcomes and operation evidence, distinguishing expected B04 source failure from a successful read. Do not infer success merely from attempted arguments. Add negative tests for failed reads, calculations and writes.

### P1 — Terminal responses bypass guided readiness

core/agent.py accepts terminal thoughts before the guided readiness gate. Reproduction: empty B01 settlement state, guided Agent, one syntactically valid B01 terminal report. state.ready() is False but agent completion_status is success. The independent scorer can still reject missing evidence; this does not satisfy the guided controller contract.

Validate required guided state before terminal acceptance, with bounded feedback/correction. Preserve autonomous behavior and separate identities.

### P1 — Task state uses proxies rather than agreed requirements

B01 readiness is any three different expression strings, not verified category/grand-total operations; even unrelated successful expressions qualify. B02/B05 readiness is source-name coverage only, omitting the agreed observed-quotation/constraint state. B03 artifact state does not establish successful valid report persistence. Guided gating sends feedback but does not define a distinct reserved finalization budget or provider final-only policy.

Define task-specific observed state without using expected answers. Three arbitrary calculator requests must not stand in for sufficient B01 computation. Prove that guided settlement neither triggers early nor blocks legitimate remaining operations.

### P1 — Native capability can be falsely promoted

backends/base_backend.py accept_tool_result() marks observed working whenever a native call is pending. Reproduction: pending unexecuted call followed by Error: missing required arguments; no tool was executed sets native_tool_capability to observed working.

Separate envelope/protocol observation, validation, execution and handoff evidence. Do not label an error-only path as verified successful tool operation; record capability scope and outcomes explicitly.

### P2 — Whitespace canonicalization suppresses a valid correction

core/agent.py removes all whitespace before checking duplicate calculator operations. This conflates invalid `1 2` with valid `12`. Reproduction: first expression fails, second expression is blocked as a repeat; only `1 2` reaches the calculator.

Canonicalize only validated syntax using a conservative representation. Preserve token boundaries and do not treat an invalid expression as a prior verified calculation.

## Completion gaps

- request_profile adds useful requested/unknown fields, but effective/default values and load_profile are hardcoded unknown. There is no complete supported reasoning/load profile editor, apply/query workflow or profile diff in this change. Unknown is honest; it is not completion of the planned profile functionality.
- Real-browser keyboard/layout verification at 1024/1920 widths and ten cards has not been established by the submitted DOM checks.
- New repeated live positive-control qualification is not included. Existing historical diagnostic results are not evidence for the new settlement implementation.
- The running service lacks the new settlement schema. Reload/deployment and a smoke check are needed after source blockers are resolved; do not test a new template against a stale backend.

## Positive findings

Fixture-name enums are advertised and executable unknown-name denial remains. Autonomous mode is the default, guided mode has a distinct serialized configuration/summary/export field, original baseline-v1 scoring is preserved, and requested values are not falsely described as confirmed load settings. These are useful changes, but green tests do not cover the reproduced negative paths above.

## Required re-verification

Fix the P1/P2 paths with regression tests, rerun suite/DOM checks, reconcile implemented/partial/pending documentation, load the reviewed backend, perform real-browser checks, then run the agreed small multi-model pilot and repeated positive control. Keep autonomous/guided modes and historical/new results separate.
