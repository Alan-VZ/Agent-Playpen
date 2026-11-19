# Independent MTT implementation verification — 2026-11-19

## Decision

**Do not approve the autonomous MTT release yet.** The implementation supplies useful persistence, API and dashboard foundations, but the accepted source-to-database-to-task-selection workflow is not correctly enforced. Successful smoke tests do not establish qualification correctness, budget enforcement or autonomous resume behavior.

This review changes no implementation, configuration or existing requirements. Live inference and paid requests were deliberately not started: the isolated checks below demonstrate that accepted campaign limits are not enforced.

## Verification method and evidence

- Read the supplied VS Code completion transcript and the main MTT specification; inspected `model_testing/store.py`, `campaign.py`, `dashboard.py`, the MTT template and the six new tests.
- Read-only live check: `GET http://127.0.0.1:8765/mtt` returned HTTP 200 with the Model Testing Tool title. This establishes page delivery, not an end-to-end autonomous campaign.
- Executed isolated reproductions using temporary SQLite databases and a substituted diagnostic runner. No real model, provider account, production database or vault was used by these reproductions.
- Machine-readable reproduction results: [MTT verification evidence](studies/2026-11-19-mtt-verification.json).
- Independent full-suite run: **565 passed, 9 skipped in 66.85 seconds**, using `.venv-test/Scripts/python.exe -m pytest -q`. Tests require `AGENT_PLAYPEN_MTT_DB` to point to a writable isolated database in this sandbox: dashboard import otherwise attempts to create the default AppData database, which is outside writable roots. That initial permission failure is an environment limitation, not evidence of a normal-user application failure. The successful suite includes the six new MTT tests; those tests do not cover the negative cases reproduced below.

## Blocking findings

### 1. Campaign budgets are accepted and persisted but not enforced — critical

`model_testing/dashboard.py` accepts attempt, request, wall-clock, token and dollar limits. `model_testing/campaign.py` uses the per-case timeout, but does not enforce the other campaign limits or pass the declared token/dollar limits to the diagnostic configuration.

Reproduction: a two-model campaign declaring one maximum attempt, one request, 1,000 tokens and a $0 limit ran both simulated diagnostic batches: twelve attempts. Each effective configuration retained a 300,000-token reservation limit and no dollar limit. This proves the limit propagation/enforcement defect without making actual requests; it is not a measurement of real token consumption.

Required: enforce a durable campaign/standing-policy ledger before every reserved request, account for retries and load attempts, stop/defer at limits, and preserve reservations across restart. Do not enable unattended cloud screening before this passes negative tests. Relevant: AUTO-AC-04.

### 2. Partial or diagnostic-only success creates false qualification — high

`model_testing/campaign.py:125` onward computes qualification from returned attempts without validating completed status or required coverage. One passing attempt in a cancelled six-case diagnostic run becomes `qualified`, Q=100, coverage=1.0 and is immediately selectable. A complete six-case diagnostic pass also becomes qualified, although the specification says a Quick Screen pass is provisional and does not create current qualification.

The reported coverage is pass rate, not coverage of the required evaluation suite. A six-case quota-only result is correctly tagged blocked but incorrectly receives Q=0 rather than unknown capability.

Required: distinguish execution completeness, coverage, pass rate, access/environment outcomes and qualification; apply versioned profile gates; leave complete Q unknown where required evidence is missing. Preserve cancelled evidence as partial. Update the existing test that currently expects six diagnostic passes to certify qualification. Relevant: AC-34 and the main scoring requirements.

### 3. Database-first recommendations do not enforce current suitability — high

`model_testing/store.py:593` queries stored qualification decisions but does not reject removed sources, unlisted models, expired decisions or deadline violations. The deadline is echoed rather than applied. The latest decision is grouped by fingerprint, so an old qualified fingerprint remains selectable alongside a newer failed fingerprint without establishing which configuration is current.

Separate reproductions selected (a) expired evidence with a 500-second result for a one-second requirement and (b) a model from a removed source. Another returned the old qualified fingerprint after a newer failing configuration was stored.

Required: resolve exact current source/model/configuration identity, enforce source/catalog status, validity and application hard constraints, and return an explicit evidence gap when these cannot be established. Historical evidence should remain viewable without automatically remaining eligible. Relevant: AC-27 and AUTO-AC-06.

### 4. Standing campaigns do not implement incremental screening or recovery — high

Code inspection: `model_testing/dashboard.py:175` always slices the first N catalog entries on a due refresh and starts a new campaign. It does not consult completed evidence to select only new/changed/stale candidates. An unchanged catalog can repeatedly test its first ten models while later candidates never advance.

`model_testing/campaign.py:28` returns immediately for a persisted running campaign even if a newly created manager has no corresponding thread. There is no recovery/resume endpoint or completed-case checkpoint reconciliation. Storing campaign rows is not equivalent to resumable execution. The existing cancellation test manually updates database rows; it does not exercise worker cancellation/restart.

Required: durable candidate queue and leases, policy-aware eligibility/freshness, case-level checkpoints, restart reconciliation, pause/disable behavior and tests proving unchanged evidence causes no inference. Relevant: AC-28, AC-30, AUTO-AC-02 and AUTO-AC-05. These scheduler/restart findings are from code inspection, not a live long-duration scheduler trial.

### 5. Model identifiers can escape the evidence directory on Windows — high

`model_testing/campaign.py:122` replaces forward slashes and colons but leaves backslashes and `..` intact. Campaign model IDs are accepted as arbitrary strings rather than requiring a catalog match. A read-only path calculation with `..\\..\\outside-campaign` resolves outside the campaign directory.

Required: opaque generated directory IDs, store the external model ID as metadata, and verify resolved containment. Validate model membership independently. The reproduction did not write outside the campaign directory.

### 6. Failed discovery is treated as model removal — high

`model_testing/store.py:235` processes an empty failed catalog refresh by marking prior entries unlisted. Reproduction: a successful one-model catalog followed by a failed empty refresh left zero listed models.

Required: retain the last successful catalog on retrieval failure; record source health and failed snapshot separately. Only an authoritative successful snapshot should establish removal. Relevant: AC-28.

### 7. Autonomous work is not coordinated with other model jobs — high

Code inspection: MTT calls the diagnostic runner directly without the existing dashboard job/study admission controls. The lock protects updates to in-memory thread dictionaries, but does not atomically claim a campaign or coordinate ownership of a shared local model server. Concurrent starts and other Playpen work can interfere with loading/inference.

Required: shared admission and per-server model ownership, atomic campaign claims and bounded concurrency. Verify with controlled competing jobs before live multi-model testing. No competing live inference was launched during this review.

## Remaining product scope

The current runner is a fixed D01–D06 diagnostic wrapper, not the specified balanced Quick Screen or application capability profile system. Requested profile IDs are not implemented as executable profile definitions; qualification storage uses `diagnostics-v1`. Historical controlled-study imports, task-specific skill matching, calibrated complete scores and confidence gates are not established by this implementation.

The UI provides source/catalog/campaign/recommendation views, but does not expose the full policy/budget controls, pause/resume or live campaign polling needed to operate the autonomous service. Free-only handling excludes cloud providers wholesale rather than identifying eligible free models; the UI's standing-screen action instead sets cloud free-only false. These are unfinished requirements, not reasons to classify a model as incapable.

## What is verified and worth retaining

The SQLite schema, source/catalog persistence, retained historical records, dashboard route and database-backed recommendation surface are useful foundations. They warrant continued development. They do not yet justify the main specification's “Implemented MVP” status or approval of unattended qualification/selection.

## Corrective verification order

1. Enforce budgets, safe evidence paths and shared job admission.
2. Prevent cancelled, incomplete, blocked and Quick Screen-only evidence from creating current qualification.
3. Apply current identity, validity, access and task hard filters to selection.
4. Implement and test incremental scheduling, source-outage semantics and restart/resume.
5. Implement the declared screen/profile registry and historical import requirements, then verify UI operation.
6. Run a bounded local campaign with a known positive control and a known negative control, restart mid-campaign, and prove later database selection makes no discovery/inference calls. Only then broaden to providers under an enforced standing policy.

Add negative tests for every reproduction in the evidence file; retain the originals as regression evidence. Do not substitute a passing broad unit suite for these acceptance checks.
