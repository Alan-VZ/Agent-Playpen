# Agent Playpen dashboard

Start with `python -m debugging.dashboard.server` or the Windows launcher, then
open `http://127.0.0.1:8765`. The server is a local development application.

## Backends and credentials

Choose LM Studio, Ollama, OpenRouter, OpenAI, Anthropic, Azure OpenAI, Groq, or
Together AI. Use the Credential manager selector to save or clear each cloud or
search key independently. New values go to native encrypted OS storage; the input
clears after Save. Status reports presence without revealing a prefix or suffix.
Use Migrate Legacy Keys to move existing `.env` entries and remove their plaintext
assignments. Save Settings writes non-secret settings only; Save Config exports
an allowlisted configuration without credentials or task text.

See [OpenRouter and encrypted credentials](../../docs/credentials-and-openrouter.md)
for setup, migration, endpoint restrictions, storage availability, and limitations.
OpenRouter uses `https://openrouter.ai/api/v1`; its workspaces/files page is not an
inference endpoint. Load retrieves available model IDs, with fallback suggestions
when providers are unreachable. The public OpenRouter catalog needs no key.

## Local API

All `/api/*` requests require `X-Playpen-Token` from the locally served page.
The browser adds it automatically. Cross-origin access and untrusted hosts are
rejected. Never put credentials in query strings. Responses disable caching;
errors omit raw exception tracebacks and request input values.

| Route | Behavior |
| --- | --- |
| `GET /api/defaults` | Non-secret defaults |
| `GET /api/models` | Model discovery; accepts backend/base_url, never API keys |
| `GET /api/keys` | Presence, encrypted/legacy state, storage availability only |
| `POST /api/save-key` | `{name, value}` saves in encrypted OS storage; empty value deletes |
| `POST /api/migrate-keys` | Moves legacy `.env` credentials into encrypted storage |
| `POST /api/save-config` | Saves allowlisted non-secret configuration |
| `POST /api/save-env` | Saves non-secret settings to `.env`; ignores credential fields |
| `POST /api/run` | Executes with saved credentials; validates task/planner/budgets |
| `POST /api/run/stream` | Live NDJSON activity and terminal result; same token/config validation |

There is no key-retrieval/export endpoint. No `/api/clear-key` endpoint is needed;
use an empty value with `/api/save-key`. API documentation endpoints are disabled;
`/openapi.json` contains schema metadata only.

## Agent tools and results

The dashboard offers web search, fetch, read/write file, calculator, and datetime.
File tools deny credential paths even inside allowed directories. Dashboard writes
are limited to text, Markdown, CSV, and JSON artifacts. Unrestricted
Python execution is disabled here because same-user code can access the native
credential store. CLI/library users may still enable it for trusted workloads.
Results and saved traces redact known credential values; encoded or transformed
secrets are not comprehensively detected. This is not an OS sandbox.

The prior regression fixes preserve planner steps, tool observation feedback,
and working-memory entries, validate malformed requests, and repair backend
construction and evaluator parsing. See [the testing guide](../../docs/testing.md)
for offline coverage and the remaining live-integration checks.

The workspace now shows live tool requests/results and model status, elapsed
time, and Stop Run. Both successful and failed traces are saved; budget exhaustion
is labeled incomplete. This is a single-agent page. See
[live activity and troubleshooting](../../docs/live-activity.md) for restart
instructions, empty-response diagnostics, and cancellation limits.

Search providers now include `ddgs` (explicit free-engine fallback) and `crossref`
(scholarly metadata, no key required). Auto uses Crossref for scholarly queries
when earlier providers fail. PDFs are extracted as text. Finished runs with tool
warnings receive a warning label; they do not certify research success. See
[search reliability](../../docs/search-reliability.md).

## Additional search services

Open **Maintenance: connect accounts & manage keys** at `/maintenance` for
provider portal setup, encrypted saving, access checks, and review tracking.
OpenRouter supports a direct browser authorization flow; human account/email,
MFA, and billing steps remain on the provider's portal. Other search-provider
tests explicitly identify possible credit use. See the
[Maintenance guide](../../docs/maintenance-screen.md).

Before registering for services, open **Keys, costs & maintenance guide** at the
top of the dashboard (`/setup`). It lists official account/pricing URLs, key
counts, upfront versus recurring payments, and a maintenance checklist. The
page shows its review date and flags overdue pricing reviews. It is a planning
guide; it does not activate subscriptions or enforce a search-dollar budget.

The Web search provider selector also includes Serper, Brave Search API, Exa,
Firecrawl Search, and OpenWeb Ninja. **Set search API key** selects the correct
credential in the existing encrypted manager. Model keys and search keys are
separate. Auto mode can try multiple configured APIs and consume their credits;
select an explicit provider to compare services. These connections use direct
APIs. See [Search APIs and MCP](../../docs/search-providers.md) for full details.
