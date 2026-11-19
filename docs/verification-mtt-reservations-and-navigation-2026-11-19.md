# MTT reservations and shared navigation: independent verification

Date: 2026-11-19. Review of the latest corrective package, including shared menu middleware, registered diagnostic profiles and attempt reservations.

## Follow-up corrective status

The two blocking findings were corrected and re-tested:

- Completed attempt reservations now replace pre-dispatch upper bounds with observed model-request, reserved-token and elapsed-time usage.
- Unresolved reservations are marked `uncertain`; recovery quarantines them rather than dispatching the same task again.
- The ledger now reconciles every stable reservation row, including completed and uncertain outcomes.
- A 1,200-second fast six-case control is covered and completes using measured elapsed time rather than full timeout reservations.
- Exact multi-attempt accounting is covered with a 4-request/20,000-token campaign.

Focused MTT validation: 17 passed.

Full Python validation: 576 passed, 9 skipped.

## Verdict

Navigation and several prior corrections are verified. **Autonomous MTT budget/recovery acceptance is still blocked.** The new per-call request guard works inside an attempt, but the campaign ledger counts fixed attempt reservations instead of the resources that the attempt is allowed to consume. Recovery also redispatches an unresolved reserved attempt under the same reservation.

No implementation or existing tests were modified. All campaign probes used fresh temporary SQLite databases and substituted inference. The multi-call probe uses the real `benchmarks.runner.Budget.reserve_model` for every simulated call; each individual attempt obeyed its actual configured request/token limits. No provider calls, live inference, production database writes or paid requests were made.

Evidence: [machine-readable results](studies/2026-11-19-mtt-reservations-and-navigation-verification.json).

## Verified improvements

- Independent full Python suite: **573 passed, 9 skipped in 79.71 seconds**, using `.venv-test/Scripts/python.exe -m pytest -q` with an isolated `AGENT_PLAYPEN_MTT_DB`. This reproduces the reported suite count; the negative probes below expose gaps outside those tests.
- The standalone test syntax error is gone; focused Ruff check of `model_testing` and `tests/test_mtt.py` passes.
- Read-only live checks of `/mtt`, `/setup`, `/baselines`, `/model-prices` and `/tools` return HTTP 200 and exactly one `id="pp-menu-toggle"` each. This verifies menu markup delivery, not every interactive menu action.
- `qualification-anything` is rejected by campaign creation. Diagnostic profiles do not create full qualification.
- The runner's per-attempt request limit is checked in `Budget.reserve_model` before accepting another call.
- Attempt timeouts and token/request limits are now derived from the campaign's reported remaining allowance.
- Deferred restart admission remains queued rather than being marked failed, and unavailable-source exits update shared job status.
- Cancellation retains the shared job's running status while signalling the stop event, which is an improvement over releasing admission immediately.

## Blocking finding 1: attempt limits and campaign ledger do not agree

Locations: `model_testing/campaign.py`, `_reconcile_attempt_ledger` and the task dispatch block; `model_testing/store.py`, `reserve_campaign_attempt` and `complete_campaign_attempt`.

Each attempt durably reserves **one request** and at most `max_output + 1024` tokens. The actual worker is permitted to use **all remaining campaign requests and tokens**. Completion stores observed usage in the result but leaves the reservation amounts unchanged. Ledger reconstruction sums those unchanged reservation columns.

Reproduction using the real per-call Budget implementation:

| Quantity | Campaign limit | Simulated calls actually reserved | Reported campaign ledger |
|---|---:|---:|---:|
| Model requests | 4 | 9 | 4 |
| Tokens | 20,000 | 27,954 | 12,288 |

The four attempts accepted 3, 3, 2 and 1 calls. No attempt exceeded its own configured limit. The campaign nevertheless exceeded both caps because later attempts were authorized using understated prior consumption.

Required: the durable authorization must cover the resources dispatched to the worker. Either reserve the full authorized allowance before dispatch and safely reconcile unused allowance after conclusive completion, or implement durable per-call reservations. On completion, reconcile recorded request/token usage without ever silently dropping uncertain consumption. Add this exact multi-attempt negative test; merely checking config values or asserting a fixed ledger does not establish enforcement.

## Blocking finding 2: an in-flight reservation is executed again on recovery

The reservation insert uses a stable unique key and `ON CONFLICT ... DO NOTHING`, but dispatch skips only reservations whose status is completed. An existing reserved row falls through to a fresh `isolated_attempt` call. A previous process may already have sent provider requests before stopping.

Reproduction: create an unresolved D01 reservation, then invoke campaign recovery with remaining allowance. D01 is dispatched again, followed by D02–D06. Its reservation is reused rather than creating/accounting for an explicitly authorized retry. The existing recovery test uses an already-exhausted one-attempt budget; that stops before reaching this defective branch.

Required: treat unresolved in-flight reservations as uncertain consumption, not permission to reissue the same work. Recover completed results where conclusive evidence exists; otherwise mark interrupted/needs-reconciliation or reserve a separately identified bounded retry without refunding the uncertain first execution. Exact once provider execution cannot be inferred from a stable local row ID.

## Functional issue: full timeout reservations remain consumed after fast completion

Ledger reconstruction always sums `reserved_wall_seconds`, even for completed attempts that took much less time. With default standing campaign allowance 1,200 seconds and 400-second case timeouts, three quick attempts consume the full ledger allowance and prevent finishing D01–D06. This is conservative rather than a time-budget overspend, but it prevents the intended complete screen under those defaults.

Required: distinguish active timeout reservation from measured campaign elapsed time and reconcile conclusive completion. Use a monotonic campaign deadline during execution, define downtime/restart policy explicitly, and retain conservative treatment only for uncertain in-flight work.

## Remaining limitations to keep explicit

The standing worker still needs revision/configuration-aware freshness and outcome-specific retry/continuation rules. A fixed expiry is not evidence that a model or its adapter is unchanged. Calibrated scores, broader application profiles and full qualification remain separate unfinished scope. Passing diagnostic rates should not be presented as complete Q scores when coverage is insufficient.

## Acceptance recommendation

Accept the navigation correction and the verified profile/syntax/per-attempt guard fixes. Do not declare campaign budget and restart correctness complete until the two reproductions above fail safely, a quick six-case positive control can complete within policy, and a live local trial confirms database-first selection makes no additional inventory or inference calls.
