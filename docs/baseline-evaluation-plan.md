# Working plan: repeatable agent baselines

Date: 2026-11-15. Updated: 2026-11-18. Status: core implementation and protocol/scheduling evidence delivered; live model/provider qualification remains pending.

## Implementation status (November 15, 2026)

- **November 18 update:** fixture-name enums, autonomous/guided settlement identity, requested/effective/default/unknown request-profile fields, and native-capability states are implemented in the code and covered by focused tests. They do not retroactively qualify live baselines.
- Implemented: five synthetic tasks and deterministic scorers; fresh seeded repetitions; single-agent and bounded 1–10-agent benchmark adapters; independent research and critique/synthesis; shared reservations; process supervision; CLI/resume; comparison reports; dashboard builder and results; provider inventory, accordion setup window, encrypted entry, checks, and review dates.
- Verified offline: see the current regression suite and `docs/baseline-tests.md`; scripted results measure the harness, not model competence.
- Pending external validation: five-repeat real-model comparison, optional cloud/team qualification, real-user native-vault persistence, and provider billing reconciliation. No saved provider keys were found in this session and no local model server was reachable. No live model results are claimed.
- Deferred extensions from this plan: live-web track, account-wide budgets, generic MCP, and calibrated Bayesian pooling. The ordinary workspace remains single-agent; team execution is available inside baseline experiments.

## Objective

Make five baseline tasks easy to run against any supported single-agent configuration or supported agent team. Produce an inspectable table showing correctness, repeatability, tool behavior, runtime, and usage. Every score must link to the underlying run evidence.

A passing benchmark is evidence for the specified task, fixtures, configuration, and limits. It is not proof of general reliability. Repeatability means consistently meeting the task contract, not producing identical prose.

## Current foundation and gaps

The current working branch has an Agent runtime, tool registry, tracing, dashboard, provider adapters, and 311 passing offline tests as of this review. These regression tests validate application behavior; they are distinct from measuring a real model's performance. Existing tests mock providers and isolate credentials.

The dashboard currently runs one agent per task. AgentManager routes registered agents and broadcasts sequentially; it is not a parallel consensus coordinator. Cancellation checks between steps do not terminate every active call. ToolExecutor's thread deadline stops waiting but can leave work running. Existing model-judge evaluation must not be the source of benchmark pass/fail: subjective model scores and parse-failure fallback scores are unsuitable as objective evidence.

Review and reconcile existing local edits and pending PR #2 before implementation. Preserve unrelated changes. Keep work in reviewable commits; merging and releasing are separate steps.

## Five baseline tasks, suite version 1

Each task has a frozen fixture package, a public task contract, machine-checkable output fields, and evaluator-only expected results. Expected answers must not be exposed through the agent's workspace or tools. Task variants use recorded fixture seeds to discourage memorized answers.

| ID | Task and fixture | Required deliverable | Objective acceptance checks |
| --- | --- | --- | --- |
| B01 | Reconcile a small synthetic orders CSV with duplicate IDs, refunds, and excluded statuses. State all accounting rules in the prompt. | JSON with net total, valid-order count, duplicate IDs, and category totals; short Markdown explanation. | Exact expected IDs/counts; decimal arithmetic with declared rounding; all totals match; source file unchanged; evidence of reading the supplied input. Calculator or bounded data tools may be used. |
| B02 | Answer a question using a frozen collection of local web-style source documents with stable source IDs, dates, and one superseded statement. | Structured claims with source IDs and supporting excerpts, plus a short research brief. | All required facts correct; current and superseded sources distinguished; references exist; quotations match; claim-to-source support checked against curated fixture facts; no invented citations. Merely including a valid URL is insufficient. |
| B03 | Inspect a synthetic project folder containing known configuration inconsistencies and one intentional non-issue. | Findings with file/line evidence and proposed corrections; report written only to the assigned output directory. | Expected defects identified; non-issue not reported; evidence locations correct; input hashes unchanged; no writes outside output; report parses. Keep this read-only apart from its report. |
| B04 | Complete a bounded retrieval task where the first source fails once and a documented alternative succeeds; include an empty result and a duplicate URL. | Correct sourced answer and machine-readable recovery summary. | Correct fallback result; no false success from an empty/error response; retry/request limits honored; duplicate work bounded; final outcome reflects actual completion. Fault schedule resets for every attempt and is independent of wall-clock timing. |
| B05 | Resolve conflicting evidence in a synthetic scheduling or equipment-choice problem. Several documents favor an option that violates an explicit constraint; one authoritative document supplies the decisive fact. Include an unanswerable field. | Chosen option, decisive evidence, rejected alternative with reason, and explicit unknown field. | Correct option and constraint reasoning; decisive source cited; unsupported field marked unknown; no fabricated value. A team must preserve the decisive evidence even when a minority agent finds it. The same final task contract applies to a single agent. |

All five must be solvable by one agent. Teams receive the same inputs, tools available to their configuration, final output contract, and aggregate resource limits. B05 must not require a team-specific intermediate report to earn task-quality points; internal dissent visibility is an additional team diagnostic.

Start B02/B04 with deterministic local retrieval adapters. A later opt-in live-web track runs comparable tasks against real providers and records retrieval time and source snapshots. Live-web results are reported separately because changing pages and availability impair reproduction. Frozen retrieval tests orchestration and evidence use, not live search-provider quality.

## Experiment configuration and fairness

- A named configuration pins agent count, role prompts, backend and exact model identifier for each agent, planner, tool allowlist, generation settings, memory policy, coordinator/synthesis policy, concurrency, and limits.
- Single-agent and team adapters expose the same run contract. Adapters create fresh agents, tools, and memory per attempt. Team reports identify contributions and include all researcher, critic, coordinator, and synthesis usage.
- Store a canonical configuration hash, suite/rubric/fixture versions, fixture hashes and seed, code commit and dirty-state indicator, dependency versions, provider model/version metadata where available, and cache policy. Never include secrets or credential fingerprints.
- Default baseline is fresh memory and cold caches. Warm-cache or persistent-memory experiments are separate labeled tracks. Reinitialize fixtures and injected faults before every attempt.
- Use aggregate token, tool-request, elapsed-time, and estimated-cost limits per configuration. Include planning and judging/synthesis calls where applicable. Report unavailable usage as unknown, never zero. Price estimates include rate source/date and are separate from provider billing.
- Compare equal-budget configurations first. A separate equal-per-agent-budget track may be useful but must show that teams received larger total resources. Do not imply equal temperature or token settings make different providers deterministic.
- Record provider seed when supported, but promise reproducible setup rather than identical remote model responses. Run configurations in rotating/interleaved order for live comparisons.
- Preflight incompatible tools, unavailable model access, and missing adapters. Show unsupported, setup failed, or not run explicitly; exclude none silently. A configuration advertised as completing the full suite cannot qualify with missing tasks.

## Running and scoring

Proposed interface, to implement:

```text
python -m benchmarks run --suite baseline-v1 --config single-local --repeats 5
python -m benchmarks compare --suite baseline-v1 --configs single-local single-cloud team-research --repeats 5
python -m benchmarks report --experiment <id> --format html,csv,json
```

These commands are implemented through `benchmarks/__main__.py` and the dashboard
Baseline Tests page uses the same runner and scorer. The interface provides
configuration selection, preflight, repeat count, aggregate limits, progress,
stop, and exports. Live model/provider qualification remains separate from the
offline implementation and scripted harness validation.

Use deterministic validators as the primary scorer. Freeze checks and weights before running comparisons. Each task gets a 0-100 quality score from explicit checks, plus an independent strict pass flag requiring every mandatory check. Workspace violations and missing required artifacts prevent a pass regardless of answer score. An infrastructure failure is a distinct outcome and remains visible in scheduled-attempt completion statistics; never rerun failed attempts silently. Explicit reruns get new IDs and retain the original failures.

Do not use the existing LLM judge to decide correctness. Optional blinded human review can annotate presentation quality; optional model judging is separately labeled and cannot override objective failures. Document unsupported assertions and evaluator errors rather than assigning neutral points.

The default repeatability target is 5/5 strict passes for each of the five tasks with zero workspace violations. Label this “passed five-repeat baseline,” not “proven reliable.” Report per-task success counts with a 95% Wilson interval, quality mean/minimum, median/p95 elapsed time with sample count, and failure categories. Five samples are a small initial screen; p95 and confidence intervals must not imply precision the sample does not provide. The extended run increases evidence but still does not certify generalization.

## Comparison table and evidence

One summary row per configuration, expandable into task rows and individual attempts:

| Configuration | Agents / models | B01 | B02 | B03 | B04 | B05 | Strict passes / scheduled | Worst task quality | Median / p95 time | Tokens | Tool requests | Estimated cost / unknowns | Violations |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Example only; no results | 1 / model ID | — | — | — | — | — | — / 25 | — | — | — | — | — | — |

Task cells show strict passes/attempts, not opaque stars. Detail views distinguish task failure, timeout, cancellation, provider failure, setup failure, and evaluator error. Show expected-versus-actual fields and failed checks. Preserve structured tool events, final outputs, source snapshots, generated artifacts, artifact hashes, usage provenance, and concise public explanations. Do not request hidden chain-of-thought. Sanitize exported content and redact secrets using existing protections.

Report orchestration regression checks separately from model benchmark scores. A mocked backend passing the runner tests does not establish model competence; a live model passing a task does not establish isolation guarantees.

## API credential self-check and launch window

Added requirement, 2026-11-15: automatically identify missing or rejected credentials required by the selected agents and tools, and provide a launch/setup window with provider website links and secure key entry. Extend the existing Maintenance and credential-store implementation rather than building a second secret store.

### User experience

1. On dashboard startup, show a credential readiness summary using local presence checks and dated prior check results. Offer **Check required APIs** for the current configuration and **Check all configured APIs** for maintenance. Before an agent run or benchmark, resolve requirements across every agent, coordinator, synthesizer, enabled tool, and explicitly allowed fallback provider. Identify key-free local services separately and check their connection readiness.
2. When a required key is missing, confirmed rejected, or the credential store is unavailable, open one consolidated **API setup** window. List affected providers, the agents/tools that require them, status, last checked time, and the recommended action. Optional unselected services do not block launching a run. Unknown or temporarily unreachable services have an explicit warning and retry path, not an invalid-key label.
3. Each provider row includes **Open key website**, a masked key-entry field, **Save securely**, and **Check again**. The website opens in a separate browser tab/window while the setup window stays available for pasting the generated key. Supply an ordinary link if browser popup handling prevents opening it. Show the credential destination and account/project guidance without displaying saved keys.
4. The user creates or rotates the key on the provider website, then pastes it directly into the setup window. Store it in the existing native encrypted OS vault; clear the input after the save attempt. Preserve a working existing key until replacement is explicitly submitted and storage succeeds. Reuse the existing supported authorization flow, such as OpenRouter connect, as an alternative to manual paste. Portal login, MFA, and key creation remain provider-site actions.
5. Recheck the affected provider and refresh the readiness summary without restarting the app or losing the selected experiment. If only credential presence can be established, display **Saved; access not yet verified**. Model access checks are specific to the selected model/deployment. Let the user explicitly continue the pending run once required setup is resolved; never silently resume a paid run or retry an uncertain tool side effect.
6. If authentication fails during execution, stop affected scheduling, preserve partial results and pending configuration, and surface the same setup window. Do not automatically replay failed benchmark attempts after a replacement: new attempts retain provenance and the original failure remains visible. CLI users receive matching status codes and portal links and can use the existing hidden-input credential command; CLI execution does not depend on a graphical popup.

### Check semantics and provider registry

Maintain one registry linking each backend/tool to its required credentials, supplementary settings (for example deployment endpoint or search-engine ID), official key-management URL, optional usage/billing URL, and supported bounded verification method. Discover required secrets from configuration rather than a hard-coded list of LLM providers; tools and fallback services count too. Unknown third-party adapters declare requirements through the same contract, or explicitly report that verification is unsupported. Verify portal URLs and API check contracts against official provider documentation during implementation and date that review.

| Status | Meaning and action |
| --- | --- |
| Not required | The current configuration does not use this credential; no launch blocker. |
| Missing | No credential resolves; offer key website and secure entry. |
| Saved; unchecked / stale | Presence is known but remote access is unverified or the last result is old. |
| Access verified | The named endpoint/operation succeeded at the displayed time; this does not establish all model/tool permissions or remaining balance. |
| Authentication rejected | Provider evidence identifies a rejected/revoked/expired credential; offer replacement. Do not infer expiration unless reported. |
| Permission or model access denied | Authentication may work, but this resource is unavailable; offer account/project/model guidance. A generic HTTP 403 is not sufficient to call the key invalid. |
| Quota / billing / rate limit | Explain the resource restriction, usage link, and retry timing where provided; key replacement is not the default remedy. |
| Connection or provider failure | Timeout, DNS, TLS, local server, or provider outage; preserve the credential and offer retry. |
| Secure storage unavailable | Explain the vault problem; do not fall back to plaintext. |
| Verification unsupported | Provide manual portal guidance and record presence separately from validity. |

Use supported non-billable authenticated checks where available, with finite timeouts, bounded concurrency, deduplication across agents, and no unbounded retries. A public catalog response or locally plausible key format does not prove validity. Do not automatically issue model completions or search/extraction requests merely to validate keys. If operation-level verification requires a potentially billable request, display the operation and expected usage and require an explicit test action; include it in the usage ledger, separately from benchmark attempts. Saving a key never triggers a billable test.

Startup performs local checks automatically. Remote checks occur on explicit self-check/preflight actions, reuse fresh scoped results, and have a visible force-refresh control. Invalidate recorded verification on credential changes using a non-secret local generation counter, not an exported key hash. Runtime authentication failures immediately invalidate applicable readiness. Store only sanitized status, scope, timestamps, and expiry metadata actually supplied by the provider; validity cannot be guaranteed between checks. Clearing a local key does not revoke its remote counterpart.

Apply existing local session/origin protections, fixed approved credential destinations, redaction, and no-cache behavior to the window. Never return saved plaintext keys to the browser, put entered keys in URLs, browser persistent storage, traces, benchmark manifests, exports, or source control. Tools and agents must not receive arbitrary credential-store access. Verification requests attach credentials only to the provider's approved endpoint.

### Completion gates

- Mock tests cover missing, rejected, replaced, stale, permission-denied, quota, rate-limit, timeout, unsupported-check, key-free local backend, and unavailable-vault states.
- Verify requirements for mixed-provider teams and tools, shared-key deduplication, optional/disabled providers, and allowed paid fallback. Distinguish supplementary configuration errors from missing secrets.
- UI checks cover opening the correct portal, popup fallback, masked entry, replacement/save failure, input clearing, recheck, and preservation of the pending configuration. Assert that secrets are absent from responses, logs, exports, and browser persistence.
- Verify that no automatic startup/save check makes a paid request; opted-in verification usage is recorded separately. Ensure benchmark setup failures do not become task-quality scores and authentication failures do not cause silent replay.
- Perform a user-session native-vault smoke check on supported platforms and opt-in live access checks for selected providers. Mock success alone does not establish real credential persistence or provider compatibility.

## Implementation stages and completion gates

### 0. Extend credential readiness and setup

Build the requirement registry, structured status checks, and API setup window by extending Maintenance. Connect ordinary agent launch and benchmark preflight to the same service. This is a first-milestone deliverable; frozen fixtures and scorers can be developed independently while this work proceeds. Broader provider coverage follows the shared adapter contract, with unsupported verification clearly labeled rather than claiming universal validity checks.

Gate: a user can select a configuration with missing credentials, open the correct provider website from the setup window, securely save a key in that window, recheck readiness, and explicitly launch the preserved configuration. No unrelated missing provider blocks the run, and quota/connection failures are not mislabeled as invalid keys.

### 1. Freeze task contracts and fixtures

Create `benchmarks/fixtures/baseline_v1/`, task manifests, hand-verified answer keys in evaluator-only storage, and scoring documentation. Use synthetic content only. Add alternate seeded fixtures for numeric values, filenames, and distractors without changing task difficulty intentionally.

Gate: a reviewer can manually compute every expected result; deliberately incorrect sample outputs fail the appropriate checks; agents cannot read answer keys through provided tools. Validate variants before treating them as equivalent comparison tasks.

### 2. Build the single-agent runner and evidence schema

Add `benchmarks/` modules for manifests, configuration, adapters, run lifecycle, scoring, persistence, CLI, and reports. Wrap the existing Agent and Tracer rather than creating a competing reasoning loop. Store per-attempt records and a resumable experiment manifest under a git-ignored benchmark-results directory. Resume skips completed attempts and preserves partial/failure records.

Gate: all five tasks execute through one command with a scripted fake backend; scoring catches wrong answers, invented citations, missing artifacts, fixture mutation, timeouts, and usage gaps. Verify fresh state per repetition and no real credentials/network use in regression tests. Then run the suite manually against one selected real local model; record failures honestly.

### 3. Establish execution and resource controls

Use per-attempt workspaces and narrow tool allowlists; keep the fixture/answer-key boundary explicit. Add shared usage accounting and bounded execution needed by the suite. Harden execution termination before enabling tools whose side effects could survive a deadline. Treat process termination and filesystem permissions as distinct controls; subprocesses alone are not a security sandbox.

Gate: a timeout/cancelled test cannot write a late artifact or contaminate the next run; bounded retries terminate; aggregate counters include every backend/tool invocation; unsupported hard limits fail preflight rather than claiming enforcement. Account-wide limits are a later extension; per-experiment estimates cannot promise provider-enforced billing caps.

### 4. Add the dashboard and useful demonstrations

Implement configuration selection, run controls, comparison table, per-attempt evidence, rerun, and HTML/CSV/JSON export. Save example task instructions and real results with exact reproduction metadata. Add a capability/status table distinguishing implemented, offline-tested, live-tested, and planned features. Update misleading timeout/sandbox wording and release documentation.

Gate: the same stored experiment yields matching CLI/dashboard/export scores; a user can launch the five-task suite and inspect a failure without editing code. No secret-bearing configuration enters exports. Complete a clean-install smoke test and relevant UI checks.

### 5. Add bounded teams through the same adapter

Implement team execution only after cancellation ownership and shared usage reservations exist. Begin with a fixed three-agent pattern: two independent researchers and a critic/synthesizer, with synthesis usage included. Keep the adapter generic for later 1-10-agent configurations. Collect independent reports before critique, retain disagreements, and isolate each agent's memory/tool state. Bayesian pooling is deferred until measured calibration warrants it.

Gate: one-, two-, four-, and ten-agent scripted runs verify concurrency ceilings, aggregate reservations, agent attribution, one failed worker, and cancellation. Then benchmark the first real team on the same five tasks and equal aggregate budgets. Report whether it improves quality enough to justify its time and cost; do not assume that it does.

### 6. Publish an initial measured comparison

Run five repetitions per task for one local configuration, one optional cloud configuration selected by the user, and the first supported team. Live paid runs require an explicitly chosen provider and spending limit; implementation and offline validation do not need paid calls. Refresh stale account/pricing information before estimating paid experiments.

Gate: publish a dated comparison artifact with all scheduled attempts, failures, configuration hashes, rubric version, caveats, and links to redacted evidence. Select configurations for the 20-repeat extended run based on the initial results. Tag suite changes so future runs cannot silently mix different baselines.

## Recommended first milestone

Deliver credential readiness and the API setup window, the five frozen tasks, deterministic scorers, single-agent CLI, and an HTML/CSV comparison report. Demonstrate missing-key recovery with mocked providers and one real local-model configuration for five repeats per task. This provides useful evidence before the larger dashboard/team work and establishes the common contract every future agent combination must satisfy.

Later extensions: opt-in live web/provider comparisons, account-wide usage controls, bounded MCP integration, read-only Home Assistant export review, calibrated multi-agent aggregation, and longer-running stability tests. These do not block the first milestone.

## November 17 integration update

All selected agent tools now execute through the shared Universal Agent Control Plane gateway. The [universal tool guide](universal-tools.md) documents typed contracts, readiness, the direct console, native/prompt model adapters, MCP exposure/connections, execution records, replay and timeout limits. The [issue register](issues-and-resolutions.md) distinguishes observed problems, implemented resolutions and remaining limits; [credits and sources](credits-and-sources.md) acknowledges the upstream creators. Historical study outputs and baseline-v1 scoring remain unchanged. A successful tool operation does not establish final-answer faithfulness or general model reliability.
