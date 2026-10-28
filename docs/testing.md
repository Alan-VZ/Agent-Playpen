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
