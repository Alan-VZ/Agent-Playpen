# Independent re-verification of MTT corrective changes

Date: 2026-11-19. This review follows the VS Code report claiming 569 passing tests and completion of the original corrective actions.

## Follow-up implementation status

Date: 2026-11-19. The corrective implementation is now present for the reproducible review findings:

- The shared HTML shell injects the menu widget when a page does not already include it.
- Unknown MTT profile names are rejected; diagnostic screens remain provisional, never full qualification.
- The runner has a campaign-level model-request limit and enforces it before each model call.
- MTT campaign attempts clamp timeout, reserved-token and tool-request values to remaining campaign allowances.
- Campaign attempts use stable campaign/item/task reservations and are reconciled from SQLite after restart.
- Reconciliation leaves recoverable campaigns queued when shared model-server work is active, rather than marking them terminally failed.
- Incomplete, blocked and provisional evidence receive short validity periods rather than a 90-day default.

Validation: the complete suite now reports 573 passing tests and 9 skipped; the focused MTT suite reports 14 passing tests. Live browser checks confirmed `☰ Menu` on `/mtt` and `/setup`.

## Decision

**Corrections are substantial, but unattended MTT is not ready for approval.** Several original failures are addressed; hard budget enforcement, qualification boundaries and durable restart accounting still have reproducible defects. No implementation or existing test was edited during this review. No live inference, paid request or production database mutation was performed.

## Checks and evidence

The full test command with an isolated `AGENT_PLAYPEN_MTT_DB` failed collection: `tests/test_mtt.py:400` contains a standalone `=` and raises `SyntaxError`. The reported 569-pass result therefore does not describe the working tree inspected in this review. Do not remove or overlook that failure when reporting validation.

Ruff independently reports the same invalid syntax. A separate run explicitly excluding `tests/test_mtt.py` completed with **559 passed, 9 skipped in 91.96 seconds**. This verifies the remainder of the suite; it is not a successful full-suite or MTT-suite result. The source/test files were left unchanged.

Offline probes substituted `isolated_attempt` and used fresh temporary SQLite databases. They exercise the campaign logic and model the valid possibility of several calls within an attempt; their request/token/time values are simulated, not billed provider measurements. Results are preserved in [re-verification evidence](studies/2026-11-19-mtt-corrective-reverification.json).

## Confirmed improvements

- Successful diagnostic-only screens now default to provisional; partial coverage becomes incomplete rather than qualified.
- Campaign attempt count is checked between cases and persisted.
- Failed discovery preserves previously listed models; independently reproduced.
- Recommendation code now filters expiry, source/catalog availability and observed deadline. New decisions get an expiry; older failing/current decisions supersede older qualified results for the same source/model.
- Evidence directories use opaque item IDs, and the campaign API validates catalog membership.
- Shared job registration and restart reconciliation have been added. Their presence does not establish correct admission/restart semantics in all cases below.

## Remaining blockers

### 1. Hard request/time/token budgets still overshoot

Locations: `model_testing/campaign.py:263`, `:349`, `:385`–`:472`; `benchmarks/runner.py` budget reservation and isolated worker.

The outer loop checks counters before/after an entire attempt. It does not enforce the campaign request cap inside that attempt, or reduce its timeout to the remaining campaign wall time. An attempt may issue multiple model calls. Reproduction: max one model request and 60 seconds, but the simulated accepted attempt recorded three requests and 120 seconds; its effective timeout remained 400 seconds.

The remaining token allowance is calculated once per model, not per task. Reproduction: a 1,500-token campaign supplied 1,500 to each of two attempts, which recorded 1,000 each, leaving campaign reservations at 2,000. The runner can enforce each attempt's limit while the campaign still overshoots.

Required: enforce request/token reservations at each actual call against a campaign-wide allowance; rebuild or share the remaining token budget for each attempt; clamp each deadline to remaining campaign time; persist reservations before dispatch. Accounting after execution is not authorization before execution. Provider timeout/worker termination cannot guarantee cancellation of remote billing and should be described accurately.

### 2. An arbitrary profile name still enables full qualification

Locations: `model_testing/campaign.py:159`–`:202`; `model_testing/dashboard.py:46`–`:57` and campaign route.

`profile_id.startswith("qualification")` upgrades the same six diagnostic passes to qualified. The API accepts any profile string and runs the same D01–D06 suite. Reproduction: `qualification-anything` returned qualified. There is no registered versioned qualification profile behind that name. Separately, a completed six-attempt record explicitly marked cancelled also returned qualified when that prefix was used because the classifier ignores record status.

Required: reject unknown profiles, map registered profiles to actual required suites and gates, and never infer qualification policy from a name prefix. Check cancellation/completeness explicitly. Until full qualification is implemented, all diagnostic screens must remain provisional. Q also remains a pass percentage even for incomplete/blocked evidence; do not present it as a complete capability score.

### 3. Case checkpoints and budget ledger are not crash-consistent

Locations: `model_testing/campaign.py:362`–`:440`, `:471`; restart reconciliation at `:99`.

Attempt evidence is written before the SQLite ledger update. Restart reads completed attempts from the file but does not reconstruct/reconcile their resource usage with the stored ledger. Reproduction: with an attempt limit of one, a checkpoint containing D01 and a pre-update ledger of zero caused recovery to execute D02. The result contained two attempts while the durable ledger counted one.

Required: durable reservation/completion transactions or an idempotent attempt ledger keyed by stable attempt ID. Recovery must reconcile evidence and allowances before dispatch, including the opposite crash window and in-flight calls whose usage is unknown. Unknown usage must not restore allowance.

### 4. Restart admission can permanently fail other recoverable campaigns

Code inspection: `reconcile()` starts eligible campaigns in a loop; `start()` rejects a second campaign while the first shared job is running; the exception handler marks the second campaign failed/completed rather than deferred. Early returns for unavailable sources also omit shared-job cleanup. A failed/unavailable campaign can leave a running registry entry blocking later jobs.

Required: distinguish deferred admission from terminal failure and use guaranteed cleanup around every worker exit. Resume one recoverable job at a time and leave the rest queued. Cancellation must retain server ownership until the worker actually stops; currently it changes the shared job status immediately, permitting admission while cancellation is still in flight. These findings are from code inspection, not a live competing-model trial.

### 5. Freshness and autonomous model qualification remain underspecified

The standing worker now skips evidence with future expiry, but does not compare model revision, tool/runtime versions or requested configuration. All new decisions receive a 90-day expiry, including provisional, incomplete and blocked results. A changed candidate or transiently blocked/partial candidate may therefore be skipped for 90 days. This is a change from repeated first-batch screening, but does not satisfy new/changed/policy-stale screening.

Required: explicit freshness rules by outcome and profile, revision/configuration fingerprints, bounded retries for transient blocks and continuation for incomplete work. Keep permanent capability failures separate from source, quota and timeout limitations.

## Next acceptance gate

Fix the syntax error and add negative tests reproducing the evidence file, including multi-call attempts, second-task token depletion, cancellation, fabricated profile IDs and a crash between evidence and ledger writes. Add restart/admission tests with more than one queued campaign and an unavailable source. Then independently rerun the complete suite before starting a bounded live local-model trial. Broader profile packs and calibrated rankings remain unfinished product scope, as VS Code acknowledged.
