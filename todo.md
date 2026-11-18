# November 17: universal tools follow-through

- [x] Portable Qalculate scientific engine and sampled 2D graph artifacts.
- [x] Shared UACP tool gateway for all selected tools; typed validation, status, records and restricted replay.
- [x] Official SDK MCP tool server and persistent connections to explicit external allowlists.
- [x] Native OpenAI-compatible provider normalization and explicit prompt/native modes.
- [x] Universal tool console, preserved verified outputs and regression/contract tests.
- [x] Issue register, architecture/setup updates and upstream creator acknowledgements.
- [ ] New matched live-model study of gateway/native calling, separate from historical runtime results.
- [ ] Versioned semantic evaluator pilot for documented B02/B05 grading limitations.
- [ ] Authenticated HTTP/OAuth MCP onboarding and stronger isolation of arbitrary third-party handlers.

See [implemented behavior and limits](docs/universal-tools.md).

# Upgrade roadmap

## November 15: baseline evaluation and credential inventory

- [x] Provider inventory with hamburger-menu accordions, key-site links, masked
  secure entry, required-key preflight, distinct failure states, and review dates.
- [x] Five frozen synthetic tasks with objective scoring and 1/5/20-repeat modes.
- [x] Benchmark-only 1–10-agent teams with independent research, critique/synthesis,
  concurrency control, shared reservations, attributed evidence, and worker supervision.
- [x] Dashboard configuration builder, comparison/evidence views, CLI resume, and
  HTML/CSV/JSON exports. See [usage and boundaries](docs/baseline-tests.md).
- [x] Completed matched five-seed/two-round studies and published results/limitations; this does not qualify every model.
- [ ] Real-user credential-vault persistence and opt-in live provider/billing checks.

The older sections below remain the broader roadmap. Benchmark-only team support
does not complete general-purpose parallel task execution or account-wide budgets.

Updated: 2026-11-01. Checked items are implemented. Unchecked items are future work;
research proposals and provider marketing are not runtime capabilities.

## Completed in the current upgrade

- [x] Direct Nimble Search Lite adapter, explicit provider selection, bounded results.
- [x] Native encrypted NIMBLE_API_KEY storage and Maintenance onboarding/search test.
- [x] Explicit basic nimble_extract tool in dashboard, CLI, and YAML registry.
- [x] Per-instance Nimble caching and five-attempt limits for each tool; no automatic retries or paid upgrades.
- [x] Retain provider-specific model selections; use current Together endpoint.
- [x] Explain missing keys, rejected access, quota, and local service failures separately.
- [x] Use Azure form resource endpoint and deployment name; reject literal placeholder URLs.
- [x] README, provider setup guide, Nimble guide, and regression coverage.

## Next: account verification and usage controls

- [ ] Confirm Nimble trial renewal, credit conversion, supported options, and exhaustion behavior with Nimble; record verified terms without account identifiers.
- [ ] User-run live smoke test with a securely saved key: one Lite search and one basic extraction; compare counters before/after. Do not mark billing verified from HTTP success alone.
- [ ] Shared per-run usage ledger: provider, operation, attempts, successes, cached hits, estimated gross cost, rate source/date, and unknown actual cost.
- [ ] Enforce configurable account-wide and per-run request/dollar reservations, atomic under concurrency; distinguish local estimates from provider-enforced limits.
- [ ] Opt-in fallback policies free_only / inexpensive / research. Never silently enable paid providers.
- [ ] Shared bounded TTL cache with source timestamps and explicit freshness control; exclude secrets and private content from cache keys and exports.
- [ ] Provider health and rate-limit backoff with bounded retry budgets; do not retry non-idempotent research/job creation blindly.

## Parallel agents: 1-10 agents, staged implementation

Dependencies: shared usage reservations, cancellation ownership, stable event schema,
and bounded source/cache access. Agent count and concurrency must be separate settings.

- [ ] Add coordinator configuration: agent_count 1-10, max_concurrency, per-agent backend/model/tools, timeout, iteration and token limits.
- [ ] Add independent researcher roles plus source verifier, critic, and synthesizer presets; allow custom roles without hard-coding a 2-4-agent limit.
- [ ] Implement bounded asynchronous scheduling with per-agent memory and tool instances, unique IDs, failure isolation, and deterministic result collection.
- [ ] Propagate Stop Run and timeout cancellation to active agents and queued work; prevent orphaned jobs and late output after completion.
- [ ] Stream agent-tagged lifecycle, model, tool, evidence, usage, error, and final events into separate expandable dashboard panels.
- [ ] Define structured public work reports: answer/claim IDs, assumptions, evidence URLs and excerpts, calculations, counterarguments, confidence, and unresolved questions. Request concise justifications and verifiable work products, not hidden chain-of-thought.
- [ ] Gather independent first-round reports before peer critique to reduce anchoring; use a bounded number of review rounds and preserve dissent.
- [ ] Add simple majority and explicit rubric baselines before Bayesian aggregation. Never apply arithmetic to token IDs as semantic scores.
- [ ] Add calibrated numeric/categorical predictions for Bayesian pooling; account for shared models/sources and correlated errors. Separate confidence from measured reliability.
- [ ] Use Kalman filtering only for justified time-series numeric state estimates with explicit noise assumptions, not arbitrary text consensus.
- [ ] Acceptance: run 1, 2, 4, and 10 mocked agents; verify concurrency ceilings, budget reservations, cancellation, one failing agent, stable attribution, and no credential leaks.
- [ ] Evaluation: factual accuracy and citation validity, calibration, dissent, latency, cost, source overlap, and comparison against a single-agent baseline.

## Additional providers and Nimble tools

- [ ] You.com free MCP search: deferred by user; implement explicit free profile, tools/list negotiation, SSE/JSON-RPC handling, session lifecycle, quota reporting, and existing fetch pairing.
- [ ] Common MCP adapter with fixed approved endpoints, tool allowlists, no dynamic code installation, bounded output, and auth isolation.
- [ ] Nimble Map: bounded URL discovery before extraction, domain/path controls, cost display.
- [ ] Nimble Crawl: page/depth/concurrency limits, job lifecycle, cancellation, usage reconciliation.
- [ ] Nimble maintained extraction templates for concrete product/reference tasks; verify billing per run/item first.
- [ ] Explicit optional rendering and file parsing; visible price changes and page limits, no silent upgrades.
- [ ] Optional Nimble research tool with effort explicitly selected, never defaulted to expensive high; cite claim reports and preserve provider provenance.
- [ ] Compare providers on the same paper, coding, current-information, and dynamic-page tasks; record relevance and extraction success, not vendor rankings.

## Maintenance and release

- [x] Build wheel/source distribution and verify new tool modules, README, and roadmap packaging.
- [ ] Perform a clean-environment installation smoke test on supported platforms.
- [ ] Review provider prices monthly and on plan changes; date each source independently rather than implying all rates were refreshed.
- [ ] Add optional reminders only when the user requests scheduling; no autonomous billing changes.
- [ ] Complete PR review/merge and release notes after checking current branch and remote status.
- [ ] Revisit native credential-store availability and limitations on Windows/macOS/Linux; encryption does not protect against arbitrary same-user malware.
