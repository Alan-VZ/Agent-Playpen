# Changelog

## v0.1.0

### Added

- Initial public release of Agent Playpen
- Support for local and cloud LLM backends
- ReAct planner loop and planner abstractions
- Tool registry and callable tool execution model
- Memory, tracing, and observability helpers
- Browser-based dashboard for configuration and task execution
- Full README documentation and project onboarding guidance

### Changed

- Standardized the default local backend to LM Studio
- Cleaned up backend registration and optional dependency loading
- Improved project structure and documentation for easier exploration

### Fixed

- Repaired runtime bugs in backend initialization, tool invocation, and dashboard flow
- Aligned tool implementations with the shared BaseTool contract
- Restored path and config hygiene for local project usage

## Unreleased

- Added baseline fixture-name JSON-Schema enums with executable unknown-name
  denial, separately labeled autonomous/guided settlement modes, conservative
  exact-expression repetition guards, native-tool capability states, and
  requested/effective/default/unknown request-profile evidence. Historical
  baseline-v1 fixtures, scorers, and results remain unchanged.
- Fixed guided settlement so failed tool operations do not advance evidence,
  terminal reports cannot bypass readiness, B02/B05 require observed report
  evidence, native error-only paths do not count as working tool calls, and
  whitespace-preserving repetition keys distinguish invalid and valid expressions.
- Fixed saved model-slot restoration: `/api/defaults` now loads
  `config/web_agent_config.json` model_slots after **Save Config**.

- Let model requests use the remaining shared task deadline instead of an
  unconditional 60-second cap; record each request’s timeout in its ledger.
- Publish the baseline calculator’s arithmetic-only contract and explain invalid
  JSON/program inputs instead of reporting all such errors as calculation size.

- Reject malformed ReAct action inputs, invented observations, multi-action
  responses, and missing required tool arguments before tool execution. Added
  bounded corrective feedback and a visible stop reason after repeated invalid
  responses. Preserve actual arguments in history and expose JSON tool contracts.

- Run Agent now starts checked baseline tasks directly and opens the new run’s
  live results. Added workspace repetition selection and protected the results
  handoff before a new experiment appears in saved history.
- Removed recurring model-inventory polling. Cache each page’s model catalog
  and update its active selection after a verified switch.

- Added immediate baseline launch acknowledgement, setup/running/error states,
  progress and explicit pass/fail outcomes. Restore saved results automatically,
  show answers and failed checks, retry lost status connections, and preserve
  run links and recorded activity across refreshes/restarts.
- API search checks now show a bounded redacted result preview and distinguish
  provider verification from baseline execution; previews are not persisted.

- Replaced separate model discovery/status/load controls with one shared Choose
  model picker across every provider and the baseline builder. Single-model local
  fields follow the actual active model; local selection unloads and verifies before
  loading. Added equivalent Ollama lifecycle handling.
- Added 1–10 model slots to ordinary workspace tasks, including mixed providers,
  ordered individual answers/traces, and transfer of all slots to baseline tests.
  Whole-task local server leases prevent slots from unloading each other's models;
  shared local engines run in turn while independent sources may run concurrently.

- Model switching now defaults to unloading previous text-model instances and
  verifying their removal before loading the selection, following ComfyUI's
  release-before-allocation lifecycle. Added explicit coexistence override,
  serialized switches, active-benchmark guard, and clearer load-failure outcomes.

- Separated model discovery from LM Studio memory loading: explicit load/status
  controls verify the exact native model instance and report load failures.
- Automatically select the baseline ReAct planner and required fixture tools,
  restore custom workspace settings on clear, and provide an explicit comparison
  override. Reject placeholder model IDs before real benchmark execution and
  retain provider-reported model identity in model-call evidence.

- Added baseline-task checkboxes beside the workspace Task field and on the
  comparison page, with fixed task previews, workspace-model transfer, selected
  task scheduling, saved selections/reruns, CLI --tasks, and explicit Not selected
  report cells. A subset pass does not claim full-suite qualification.

- Added a hamburger-menu Secrets/API inventory dialog with provider accordions,
  secure entry and replacement, required-credential preflight, dated access checks,
  review dates, explicit search verification, and distinct authentication/quota/network states.
- Added five versioned objective baseline tasks, seeded repetitions, bounded
  1–10-agent teams with critique/synthesis, shared usage reservations, spawned
  attempt workers, live attributed activity, resumable CLI experiments, comparison
  dashboard, and escaped HTML/CSV/JSON reports. Live provider/model qualification
  remains distinct from offline scripted harness validation.
- Record available non-streaming provider token usage without inventing missing data;
  clarify ordinary tool-timeout and Python-tool isolation limitations.

- Added token prices to model choices and a cross-backend comparison screen:
  provider catalog/official-page rates, labeled reference fallback, cache rates,
  source/freshness, cost sorting, base text estimates, and explicit unknown prices.
- Added a Maintenance screen with guided provider onboarding, OpenRouter S256
  PKCE authorization and direct vault saving, account/usage access checks,
  opt-in search tests, review dates, and secret-free maintenance history.
- Added a dashboard keys/costs/maintenance guide and matching generated document:
  dated primary-source prices, account links, key-count scenarios, cash-flow
  distinctions, review reminders, and a manual account-maintenance plan.
- Added Serper, Brave Search API, Exa, Firecrawl Search, and OpenWeb Ninja direct
  API adapters, encrypted credential support, automatic fallback, and a dedicated
  dashboard search-key shortcut. Documented API versus MCP integration scope.
- Replaced the deprecated search wrapper with pinned DDGS engines, conservative
  unrelated-batch screening, and free Crossref fallback for scholarly queries.
- Added PDF text/font extraction, duplicate search/fetch loop prevention, readable
  final-answer envelopes, and explicit finished-with-tool-warnings UI state.

- Live dashboard activity stream, elapsed timer, Stop Run, retained failed traces,
  redacted actionable errors, and explicit incomplete outcomes.
- Search source URLs, recoverable ReAct action formats, and OpenRouter response
  metadata/empty-output diagnostics. Added stream lifecycle and DOM smoke tests.

- Encrypted native OS credential manager for all cloud backends and search keys,
  hidden CLI entry, legacy migration, presence-only status, and export filtering.
- OpenRouter dashboard/CLI setup, model selection and discovery, trusted endpoint
  routing, and provider presets.
- Local session/origin/host protections, no-store/CSP headers, sanitized errors,
  credential-path restrictions, and dashboard arbitrary-Python removal.
- Regression suite and repaired package/CLI startup, planner execution, memory,
  dashboard validation, provider construction, and evaluator parsing.
- Updated setup, dashboard, extension, testing, and credential-security guides.

- Repository polish, asset cleanup, and documentation improvements
- GitHub metadata and release preparation work
- Optional refinements for production hardening and packaging
