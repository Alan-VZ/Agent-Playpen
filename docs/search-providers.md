# Search APIs and MCP

Start with [Keys, costs, and maintenance](keys-costs-maintenance.md) before
creating accounts or buying credits. The same reviewed snapshot is available
from the dashboard's **Keys, costs & maintenance guide** link at `/setup`.

For account setup and verification, use [Maintenance](maintenance-screen.md).
Its search tests require explicit opt-in to possible credit use.

Agent Playpen's `web_search` tool supports direct search APIs. An LLM backend
(for example OpenRouter) and a search service have separate credentials and
usage charges. The same search tool works with every supported model backend.

## Choose a provider

| Dashboard value | Integration in this app | Credential |
| --- | --- | --- |
| `serper` | Google organic results: title, URL, snippet | `SERPER_API_KEY` |
| `brave` | Brave Search API web results | `BRAVE_API_KEY` |
| `exa` | Exa auto search with source highlights | `EXA_API_KEY` |
| `firecrawl` | Firecrawl v2 web search, without automatic scraping or crawling | `FIRECRAWL_API_KEY` |
| `openwebninja` | OpenWeb Ninja direct Real-Time Web Search API, organic results | `OPENWEBNINJA_API_KEY` |
| `tavily` | Tavily Search (existing integration) | `TAVILY_API_KEY` |
| `serpapi` | SerpAPI Google results (existing integration) | `SERPAPI_API_KEY` |
| `google` | Google Programmable Search (existing integration) | `GOOGLE_API_KEY` and `GOOGLE_CSE_ID` |
| `ddgs`, `duckduckgo` | Public search engines; availability can vary | None |
| `crossref` | Scholarly titles, authors, and DOIs; metadata only | None |

Serper and SerpAPI are separate services with different keys. `brave` uses the
authenticated Brave Search API; DDGS's Brave engine uses a different public
search interface. OpenWeb Ninja uses a direct OpenWeb Ninja key, not a RapidAPI
key. These distinctions matter when saving credentials.

For an initial comparison, select one provider explicitly and run the same task
against it. Record whether the source was relevant, whether `fetch` could read
it, whether the answer cited the evidence, and the provider's usage/latency.
Marketing rankings, a few sample queries, or the number of returned links do not
establish which service will be best for your tasks. Check the provider's current
account terms for trial allowances, rates, and prices.

## Dashboard setup

1. Restart the dashboard after updating the code, then hard-refresh the browser.
2. Enable **web_search** and, for reading sources, **fetch**.
3. Choose a **Web search provider** and click **Set search API key**.
4. The credential selector switches to that provider's key name. Enter the key
   in the password field and press **Save**. The field clears after saving.
5. Run a task. Tool responses name the new API provider and include source URLs.
6. **Save Settings** preserves the provider choice. Credentials are saved
   separately in the existing native encrypted OS store.

No new dependencies are needed beyond the dashboard/web extras already used by
the app. CLI users can set a key through the hidden credential prompt:

```powershell
python -m config.credentials set SERPER_API_KEY
$env:WEB_SEARCH_PROVIDER = "serper"
```

Do not paste a key into the task prompt. The search tool receives the query and
requested result count; the server resolves the credential separately. See
[credential storage and limits](credentials-and-openrouter.md).

## Automatic fallback and cost

`auto` tries configured APIs in this order: Google, Tavily, SerpAPI, Serper,
Brave, Exa, Firecrawl, OpenWeb Ninja. It skips missing keys and stops at the first
usable response. It then tries DDGS and, for scholarly queries, Crossref if the
configured APIs did not yield usable results. The existing conservative lexical
screen can reject a batch with no query-term overlap; this is not semantic
validation and may reject relevant synonyms. An explicit provider bypasses that
auto screen.

One `web_search` call can therefore make multiple provider requests and consume
multiple credits. Select one provider explicitly to compare services or control
which account is used. There are no automatic HTTP retries in the new adapters.
Each API attempt has a 15-second request timeout; a fallback chain can take
longer. The run's tool timeout and cancellation behavior still apply.

The new API adapters use fixed HTTPS destinations, keys in headers, and disabled
redirects. They return safe status messages for authentication, credit, quota,
connection, and malformed-response failures. They do not expose raw error bodies
or exception details. Result counts are limited to 1–10, and snippets/highlights
are bounded to keep provider output manageable. Fetch remains a separate action.
Search snippets are evidence to investigate, not verified full-text conclusions.

Existing duplicate-call prevention, trace redaction, and warning states apply;
see [search reliability](search-reliability.md).

## How MCP fits

MCP is a protocol for discovering and invoking tools. A search MCP server often
wraps the same provider API and still needs that provider's account and key.
Using MCP does not by itself improve the provider's search results or make its
usage free.

This release adds **direct API adapters**, not a generic MCP client or a screen
for importing arbitrary MCP servers. There is no separate MCP process to start.
Firecrawl's crawling/browser tools, Exa's other endpoints, and external servers'
additional tools are not exposed by these search adapters. A future MCP client
would need explicit server configuration, transport/session handling, tool
selection, credential isolation, and cancellation integration.

## Provider references

- [Serper](https://serper.dev/) — Google Search API and account setup.
- [Brave Search API](https://api-dashboard.search.brave.com/api-reference/web/search/get)
  — web search request and response contract.
- [Exa Search](https://exa.ai/docs/reference/search) — search with highlights.
- [Firecrawl Search](https://docs.firecrawl.dev/api-reference/endpoint/search)
  — v2 search contract.
- [OpenWeb Ninja Real-Time Web Search](https://www.openwebninja.com/api/real-time-web-search)
  — direct API and account setup. This adapter follows its documented
  `/realtime-web-search/search` endpoint and `data.organic_results` response.

Automated tests use mocked provider responses and isolated test credentials.
They validate request contracts, result normalization, fallback, quota and
authentication errors, redirects, and redaction. They do not establish that an
individual account has credit or that live search quality meets a task's needs.
