# Testing Agent Playpen

Use Python 3.11 or newer and a fresh virtual environment. The automated suite
uses fake backend clients and temporary files. It does not require API keys,
download embedding models, or call live model/search services.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev,web-tools,dashboard]"
python -m pytest -q
python -m pytest --cov=core --cov=planner --cov=memory --cov=tools --cov=advanced --cov=debugging --cov=backends --cov-report=term-missing
ruff check .
python core/runner.py --help
python -m core.runner --help
```

To verify distributable packages:

```bash
python -m pip install build
python -m build
```

The suite covers the agent's tool/observation feedback loop and budget, planner
selection and fallback behavior, local memory, filesystem boundaries, calculator,
network tools with mocked transports, dashboard requests, backend adapters,
ten-agent routing, message-bus fanout, execution timeouts, and observability.
External network connections are blocked during tests; loopback is allowed for
Windows asyncio internals. TestClient exercises the dashboard in process.

Live provider compatibility, model output quality, browser interactions, and
optional Chroma/FAISS embedding integrations require separate integration runs
with their dependencies and services. Passing offline tests does not certify
those paths. The documented Bayesian consensus coordinator remains a proposal;
the ten-agent routing test verifies the existing manager, not that future engine.

Credential tests use a fresh in-memory keyring per test; they do not create or
read real saved keys. Dashboard tests send a local session token and include
cross-origin/host checks, plaintext-fallback refusal, legacy migration,
credential-path denial, redaction, export allowlists, and provider endpoint
restrictions. Native Windows/macOS/Linux credential persistence still requires
an integration check in the user's desktop session. OpenRouter chat/stream tests
use mocked clients; the provider is not charged during tests.

Live-activity tests additionally verify ordered model/tool events, actual event
delivery while a fake model is blocked, failure-trace persistence, redaction,
incomplete outcomes, cancellation scheduling, empty model replies, OpenRouter
usage metadata, source URLs, and fenced/non-object action inputs.

An optional DOM test executes the real dashboard JavaScript against a fake
stream, including UTF-8 chunk boundaries, early progress, final/error states,
escaped tool output, and Stop Run:

```bash
npm install --prefix .test-tmp/ui-test --no-audit --no-fund --ignore-scripts jsdom
node tests/dashboard_ui.cjs
```

The DOM check does not replace a full browser/layout test or call a live provider.
See [live activity and troubleshooting](live-activity.md).

Search-reliability tests cover explicit free-engine fallback, conservative
query-term screening, Crossref metadata, PDF extraction, duplicate-read loop
prevention, and unwrapping simple final-answer JSON envelopes. Free web engines
are best effort; offline passing tests do not establish search availability.

## Search API integration coverage

Model-pricing coverage is in `tests/test_model_pricing.py`: normalization,
provider identity, official source parsing, reference fallback, cache behavior,
unknown/zero prices, pagination, and credential isolation. UI checks:

```powershell
python tests/render_pricing_ui.py
node tests/model_prices_ui.cjs
node tests/dashboard_ui.cjs
```

Maintenance coverage is in `tests/test_maintenance.py`: browser-bound PKCE,
replay/expiry, key replacement, vault failure, non-billable checks versus opt-in
search tests, and safe history. Optional UI checks:

```powershell
python tests/render_maintenance_ui.py
node tests/maintenance_ui.cjs
```

`tests/test_search_apis.py` validates the five added APIs with isolated credentials
and mocked HTTP: provider-specific request/response contracts, bounded output,
missing keys, quota/authentication failures, disabled redirects, and fallback.
The dashboard DOM smoke also checks selecting and saving each search key.
These tests make no paid API calls and do not measure live retrieval quality.
