# Nimble integration

Implemented: explicit Search Lite and basic extraction. No generic MCP client,
Map, Crawl, rendering, templates, or managed research is enabled by this integration.

- Save NIMBLE_API_KEY through Maintenance (native encrypted OS credential store).
- Choose nimble explicitly for web_search. Auto excludes Nimble even with a saved key.
- Enable nimble_extract separately; try ordinary fetch first.
- Search POSTs only to https://sdk.nimbleway.com/v2/search with Lite depth, no full content, and general focus.
- Extraction POSTs only to https://sdk.nimbleway.com/v2/extract, requests Markdown, render=false and driver=vx6.
- No credential is an agent-facing argument, no authenticated redirects are followed, and provider response errors are not echoed.
- Each tool instance caches repeated completed results and permits at most five request attempts. Extraction returns at most 12,000 content characters. Caches reset with each new run/instance and are not shared between agents.
- Failed requests count against the local attempt cap even if Nimble does not bill them. No automatic retries or higher-cost fallback.
- Extraction accepts public HTTPS destinations without embedded credentials and rejects literal private addresses/local hostnames. Hostname-to-private DNS rebinding and provider-side redirects remain provider-side concerns; this is not a browser sandbox.
- Request counts and provider output appear in existing traces/live activity. No account balance API or exact invoice reconciliation is claimed.

## Costs and account status

Rates reviewed 2026-11-01: Search Lite $1.10/1,000 inputs; basic extraction
$1/1,000 URLs. Rendering, parsed files, full-content search, and agent research
have different costs and are outside this implementation. Trial renewal and
credit unit mapping remain unverified. User-provided screens showed Trial,
no payment method, auto-recharge off, 5,000 API credits and 30 agent runs unused.
These observations are not a guarantee about account terms or future charges.
The Maintenance search test is an explicit real request if a real key is present.

Sources:
- [Search contract](https://docs.nimbleway.com/nimble-sdk/web-tools/search)
- [Extract contract](https://docs.nimbleway.com/nimble-sdk/web-tools/extract/quickstart)
- [Pricing](https://docs.nimbleway.com/nimble-sdk/admin/pricing)
- [API keys portal](https://online.nimbleway.com/settings/api-keys)

See [todo.md](../todo.md) for live verification, usage accounting, shared budgets,
parallel-agent coordination, and additional tool phases.
