# Baseline tests and API inventory

Implemented November 15, 2026. Start the existing local dashboard, then use **☰ Menu → Secrets & API inventory** or **☰ Menu → Baseline tests**. Restart an already-running dashboard after updating the code and refresh the browser.

## Secrets and API inventory

`/api-inventory` lists every built-in model/search service even when no key has been saved. The menu opens an accordion dialog inspired by the supplied reference: expand a provider, open its key website in a new tab, create the key there, and paste it into the masked field in Playpen. **Save securely** uses the existing native encrypted OS credential store. Select replacement explicitly before overwriting a saved key. Saved keys are never loaded back into the field. Closing the window clears unsaved key inputs.

Each provider shows presence, required consumers, access status, last check, stale-check indication, and an optional next-review date. Missing unused services do not block a task. Google legacy search also requires its CSE ID. Local models and key-free retrieval services are described separately. Dates are maintenance metadata, not autonomous reminders or guarantees that a key has expired.

**Check required APIs** and **Check all saved APIs** perform explicit non-inference checks where supported. Startup and key saving make no paid verification calls. Search providers have an additional explicitly authorized single-search test; its request/status is recorded in a separate bounded verification ledger with unknown actual cost. No automatic retries, subscription changes, or key purchases occur. Authentication, permission, credit/billing, rate-limit, connectivity, unsupported verification, and secure-storage failures have different statuses.

An authenticated listing/account check proves acceptance by that endpoint at that time; it does not prove inference permission for a selected model or remaining credit. Together and Azure lack a configured general credential check and remain explicitly unverified until actual operation or manual portal review. The existing OpenRouter authorization flow remains available through Maintenance. Do not paste keys into chat, configuration JSON, model prompts, or benchmark reports.

On ordinary agent launch, required missing/rejected credentials open the dialog and preserve the task configuration. A runtime model authentication rejection records the status and reopens setup. After repair, launch again explicitly; the app does not silently replay a task. For `auto` search, the existing adapter may try saved paid providers: explicitly choose a key-free provider when desired. Inventory does not silently change that established policy.

Provider check contracts reviewed against official references on November 15, 2026:

- [OpenRouter current-key information](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-api-key).
- [Tavily account/key usage](https://docs.tavily.com/documentation/api-reference/endpoint/usage).
- [Firecrawl credit usage](https://docs.firecrawl.dev/api-reference/endpoint/credit-usage).
- [OpenAI authenticated models listing](https://developers.openai.com/api/reference/resources/models/methods/list).
- [Anthropic models listing](https://platform.claude.com/docs/en/api/models/list).
- [Groq models API](https://console.groq.com/docs/api-reference).

Provider portals, account entitlements, and billing can change. Refresh checks when troubleshooting. A dated result is not continuous monitoring. Credentials changed outside the app require a fresh check; a CLI/external change is not reliably detected from metadata alone. Native-vault persistence must be verified in the actual user's desktop session, which may differ from a development sandbox.

## Five fixed tasks

| Task | Work | Mandatory evidence |
| --- | --- | --- |
| B01 | Deduplicate orders, subtract refunds, exclude cancellations, total categories. | Correct amounts/counts and a recorded input read. |
| B02 | Resolve dated source claims and supply three factual answers. | Correct facts and exact supporting sentences from the designated authoritative sources. |
| B03 | Inspect a synthetic project for two known defects and avoid a false positive. | Correct file/line findings and matching report.json artifact. |
| B04 | Recover from an injected first-read failure and recognize an empty response. | Correct backup answer, observed failure, bounded reads, and no false absence claim. |
| B05 | Resolve a majority-supported wrong choice using authoritative constraints. | Correct constrained choice, decisive citation, rejected-option explanation, and explicit unknown warranty. |

These tasks run against synthetic frozen document collections, not the live web or the user's filesystem. Every attempt records the fixture seed and hash; B01/B04 vary numeric content across repetitions. Source IDs replace live URLs in this frozen track. The evaluator's expected answers are never exposed through the registered tools. Reports reveal expected values after scoring so failures are reviewable.

Correctness comes from deterministic validators, not an LLM judge. The rubric is deliberately strict about required JSON fields and citation sentences; a semantically reasonable answer can fail the stated output contract. Quality is the percentage of checks met; a strict pass requires every mandatory check and successful execution. A partial answer, failed model call, timeout, denied tool operation, or missing artifact remains visible.

## Run from the dashboard

Open `/baselines`. Use the form to name a configuration, select 1–10 agents, set each provider/model/planner/role, and set shared time, token-reservation, and tool-request limits. **Load available models** is an explicit provider request, not proof of inference access. Use **Add comparison configuration** or the single-versus-team preset. The last member of a team is the critic/synthesizer; preceding members work independently before synthesis. Two agents mean one researcher and one synthesizer. The ordinary workspace remains a single-agent workspace.

Choose one repeat for a smoke run, five for the baseline, or twenty for extended evidence. Five repeats give 25 attempts per configuration. Team configurations share the same aggregate limits as single agents when comparing matched budgets. Critic and synthesis calls count too. Requests and reports carry agent IDs; team memory and tool state are separate. The concurrency setting limits active agents independently of team size.

The comparison table links to expandable attempt evidence and exports HTML, CSV, and JSON. It shows passes over scheduled attempts, minimum/mean quality in stored summaries, median/p95 time, reported actual tokens, conservative token reservations, tool requests, cost reservations when rates are supplied, and violations. `summary.json` includes per-task Wilson 95% intervals. Small-sample percentiles and success rates are only initial evidence. A configuration qualifies only after all tasks pass every repetition with at least five repeats.

Unknown tokens or costs stay unknown. Estimated costs require declared input/output rates; heterogeneous teams should use conservative aggregate rates. A dollar reservation limit additionally requires a rate source. These are local estimates, not provider-enforced billing caps or account balances. Provider-reported cache charges, reasoning, and other billable units may differ. A backend that omits usage cannot supply measured token totals.

## CLI and saved evidence

From the project root, with the usual environment installed:

```powershell
python -m benchmarks run --config benchmarks/configs/single-local.json --repeats 5
python -m benchmarks compare --config benchmarks/configs/single-local.json benchmarks/configs/team-local.json --repeats 5
python -m benchmarks report --experiment benchmark-results/EXPERIMENT_DIRECTORY
```

Edit model IDs in these non-secret configurations to match installed/available models. Optional `base_url` supports HTTP loopback local servers or a validated Azure resource endpoint. Each member may restrict `tools` to `read_fixture`, `write_artifact`, and `calculator`. Configuring a member without the tools needed to satisfy a task will be reflected in its results.

Use `--output` to choose a CLI results directory. Use the same arguments plus `--resume` to continue its unattempted slots. Resume preserves original failed attempts; it does not turn them into unrecorded retries. Changed configurations or fixtures are rejected for resume. For an explicit rerun, create a new experiment. The dashboard stores UUID-named experiments under git-ignored `benchmark-results/` and lists prior results. An interrupted dashboard job is shown as interrupted after restart; CLI resume remains available with its matching configurations.

Evidence includes canonical configurations/hashes, suite/rubric version, source fixture hashes, commit/dirty state, selected dependency versions, agent-tagged public event traces, outputs, artifacts/hashes, failed checks, expected values, usage provenance, and failure outcomes. These files may contain task output, so share intentionally; saved keys are excluded and known credentials redacted. CSV names are protected from spreadsheet formula injection and HTML is escaped.

## Execution boundaries and validation

Each real-model benchmark attempt runs in a spawned worker process. A shared deadline/cancellation flag stops new actions; the supervisor terminates a local worker that fails to exit. Fixture reads come from a fixed in-memory mapping; report writes go only to a bounded per-agent artifact collection. Late model replies cannot schedule writes after the attempt closes. The bounded calculator disallows exponentiation and arbitrary code. This is capability restriction for these trusted benchmark tools, not a general-purpose OS security sandbox. It does not cancel remote provider computation or undo provider charges.

The ordinary ToolExecutor still has its documented thread-timeout limitation. Benchmark isolation does not make arbitrary Python or shell execution safe, and those tools are not registered in this suite. Account-wide budgets, live-web comparisons, generic MCP, and Bayesian pooling remain future extensions from the original plan.

Regression tests cover objective rejection, fresh seeded fixtures, 1/2/4/10-agent attribution, concurrency ceilings, failed-worker isolation, atomic reservations, cancellation and late writes, resume, credential statuses, vault failure, redaction, explicit billable tests, and authenticated model-list request boundaries. A loopback fake model also exercises the real SDK and Windows spawn path without a real API account. Scripted reference runs validate the harness, never model competence.

```powershell
python -m pytest -q
ruff check .
python tests/render_baseline_ui.py
node tests/baseline_ui.cjs
python -m build --no-isolation
```

The Node check uses the existing optional `.test-tmp/ui-test/node_modules/jsdom` dependency. Live model accuracy, live tool-provider access/billing, and real-user native-vault persistence require separate runs. No real keys or paid model/search calls were used to implement this feature. At implementation time neither local model service was reachable from the development session, so no real-model baseline qualification is claimed.

## Implementation verification record

November 15, 2026: 360 offline tests passed; Ruff passed; inventory/baseline, ordinary dashboard, Maintenance, and pricing DOM checks passed; wheel/source builds passed. A fresh virtual environment installed the wheel without dependencies and verified packaged fixtures/templates outside the source checkout; this was a packaging check, not a full clean runtime installation. The actual SDK/process transport test used a loopback fake model. A five-repeat scripted reference compared one and three agents: 25/25 strict passes each. The earlier scripted comparison that exposed the team read-limit rubric defect was retained as separate evidence. Neither result is a real-model evaluation.
