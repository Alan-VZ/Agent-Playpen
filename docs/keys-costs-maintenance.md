# Keys, costs, and maintenance

Reviewed: 2026-10-29. Next suggested review: 2026-11-29. USD, before tax. Confirm checkout terms before purchasing.

Start with two keys total: your existing OpenRouter key and one search key, such as Tavily. DDGS, Crossref, and the app's fetch tool need no search key. Add Serper as an optional third key only when you want to compare Google results.

## How many keys?

| Setup | Keys total | Meaning |
| --- | --- | --- |
| Local model + DDGS/Crossref | 0 | No cloud model or search key; local hardware/electricity still cost money. |
| OpenRouter + DDGS/Crossref | 1 | Reuse OPENROUTER_API_KEY; model usage is billed separately. |
| OpenRouter + Tavily (recommended start) | 2 | One model key and one search key. Only one new key if OpenRouter is already saved. |
| OpenRouter + Tavily + Serper | 3 | An optional comparison setup; choose a search provider explicitly. |

Keys belong to services/projects, not to individual agents. A future 10-agent run can share the same two or three keys, subject to provider rate limits and account terms. More agents increase requests and tokens. The current dashboard still runs one agent per task. Normal OpenRouter routing does not require a separate model-vendor key for each model; direct backends and BYOK are separate setups.

## Recommended starting plan

1. Keep your existing OpenRouter key. Set a provider-side limit for the Playpen key where available; a suggested initial model budget is $10/month, not a forecast of usage.
2. Create one Tavily Free key and save it using Web search provider → tavily → Set search API key → Save. Search costs can stay $0 within its basic-search allowance.
3. Choose tavily explicitly for predictable account selection. Use ddgs or crossref explicitly for keyless searches. Keep fetch enabled to check original sources.
4. Optionally try Serper's signup allowance with a third key. Delay purchasing the $50 pack until its results and your volume justify it.
5. Use Max iterations around 5 for early smoke tests. Review actual provider usage before longer runs. A step limit is not a dollar limit.

## Provider accounts and current prices

### OpenRouter (models)

Credential: `OPENROUTER_API_KEY`.
Get the key/account: [Provider portal](https://openrouter.ai/workspaces/default/keys).

- Free allowance: Free-model access is limited; paid model usage draws from your balance.
- Upfront: Existing balance: no new purchase needed. Paid top-ups start at $5 credits; Standard card fee is 5.5%, minimum $0.80 (about $5.80 for $5 credits, before tax).
- Recurring/usage cost: No required Standard subscription. Pay for model input/output tokens; rates vary by model.
- Check: Track model spending separately from search. Check auto-recharge and key limits; unused credits may expire after 365 days.

Source: [Official pricing/documentation](https://openrouter.ai/pricing).
Additional source: [Top-up fees](https://openrouter.ai/blog/simplifying-our-platform-fee/).
Additional source: [Credit terms](https://openrouter.ai/terms).

### DDGS / DuckDuckGo

Credential: `None`.

- Free allowance: No search API subscription or credits in this adapter.
- Upfront: $0
- Recurring/usage cost: $0 search-provider charge.
- Check: Public engines can block requests or return weak results. This is a best-effort option.

Source: [Official pricing/documentation](https://github.com/deedy5/ddgs).

### Crossref

Credential: `None`.

- Free allowance: Public scholarly metadata API.
- Upfront: $0
- Recurring/usage cost: $0 for the public endpoint used here.
- Check: Titles, authors, and DOIs; metadata does not replace reading the paper.

Source: [Official pricing/documentation](https://www.crossref.org/documentation/retrieve-metadata/rest-api/).

### Tavily

Credential: `TAVILY_API_KEY`.
Get the key/account: [Provider portal](https://app.tavily.com/).

- Free allowance: 1,000 credits every month; no card required.
- Upfront: $0 on Free.
- Recurring/usage cost: $0 within Free. Optional PAYG: $0.008/credit. Project: $30/month for 4,000 credits.
- Check: Basic search costs 1 credit; advanced costs 2. The app uses the API's basic default. The monthly budget examples assume basic search.

Source: [Official pricing/documentation](https://docs.tavily.com/documentation/api-credits).

### Serper

Credential: `SERPER_API_KEY`.
Get the key/account: [Provider portal](https://serper.dev/).

- Free allowance: 2,500 signup queries; no monthly refill advertised. No card required for the trial.
- Upfront: $0 trial; smallest advertised paid pack is $50 for 50,000 credits.
- Recurring/usage cost: No subscription. $1/1,000 is the pack's usage rate, not a $1 monthly bill. Credits expire after 6 months.
- Check: Buy only after testing. A $50 pack used for just 6,000 searches before expiry costs $8.33 per 1,000 actually used.

Source: [Official pricing/documentation](https://serper.dev/).

### Brave Search API

Credential: `BRAVE_API_KEY`.
Get the key/account: [Provider portal](https://api-dashboard.search.brave.com/).

- Free allowance: Search plan lists $5 free credits/month, equivalent to 1,000 Search requests.
- Upfront: Card required for verification; prepaid usage. Confirm paid top-up minimum at checkout.
- Recurring/usage cost: No subscription. Search: $5/1,000 requests before available free credits.
- Check: This is the authenticated Search API, separate from the free Brave engine accessed by DDGS.

Source: [Official pricing/documentation](https://brave.com/search/api/).

### Exa

Credential: `EXA_API_KEY`.
Get the key/account: [Provider portal](https://dashboard.exa.ai/).

- Free allowance: $10 credits/month; first-team onboarding can earn a one-time $10 bonus. No payment method required.
- Upfront: $0 Free; paid usage uses credits with no subscription/minimum spend advertised.
- Recurring/usage cost: The app's Auto search is $7/1,000 requests, up to 10 results, before credits.
- Check: The advertised $4/1,000 Lite rate is a different mode. This app requests Auto with highlights, without page summaries.

Source: [Official pricing/documentation](https://exa.ai/docs/admin/pricing).

### Firecrawl Search

Credential: `FIRECRAWL_API_KEY`.
Get the key/account: [Provider portal](https://www.firecrawl.dev/).

- Free allowance: 1,000 credits/month, advertised as 500 searches; no card required.
- Upfront: $0 Free; Hobby monthly billing starts at $19. Annual checkout charges a full year upfront.
- Recurring/usage cost: Hobby: $19/month for 5,000 credits. $16/month is an advertised annual equivalent, not monthly billing.
- Check: Search costs 2 credits per 10 results. Paid plans can enable extra credits; scraping/crawling costs are separate from this app's search-only adapter.

Source: [Official pricing/documentation](https://www.firecrawl.dev/pricing).

### SerpAPI

Credential: `SERPAPI_API_KEY`.
Get the key/account: [Provider portal](https://serpapi.com/).

- Free allowance: 250 searches/month.
- Upfront: $0 Free; $25 for the first Starter month.
- Recurring/usage cost: Starter $25/month for 1,000 searches; Developer $75/month for 5,000.
- Check: Different company/key from Serper. Check Automatic Early Renewal before enabling a paid plan.

Source: [Official pricing/documentation](https://serpapi.com/pricing).

### OpenWeb Ninja

Credential: `OPENWEBNINJA_API_KEY`.
Get the key/account: [Provider portal](https://app.openwebninja.com/).

- Free allowance: 100 request units/month, hard limit, no card required.
- Upfront: $0 Free. PAYG funding requirements must be confirmed in the account portal.
- Recurring/usage cost: PAYG $0.005/billed unit with no monthly fee; Pro $25/month for 10,000 units, then $0.003/unit.
- Check: Standard/full search can consume different units (full is advertised as 2). Verify the app's /search usage meter before assuming $5 per 1,000 calls. Use a direct key, not RapidAPI.

Source: [Official pricing/documentation](https://www.openwebninja.com/api/real-time-web-search).

### Google Custom Search (legacy)

Credential: `GOOGLE_API_KEY + GOOGLE_CSE_ID`.

- Free allowance: Existing customers: 100 queries/day.
- Upfront: Closed to new customers; do not set up a new account for this adapter.
- Recurring/usage cost: Existing accounts: $5/1,000 extra queries until discontinuation on January 1, 2027.
- Check: Plan migration before that date. CSE ID is a search-engine identifier, not a second API key.

Source: [Official pricing/documentation](https://developers.google.com/custom-search/v1/overview).

## Estimate your usage

Monthly requests ≈ runs/day × active days × search calls/run × agents/run. Add fallback attempts and reruns; subtract actual cache hits. The current dashboard has one agent per run.

Example: 20 runs/day × 30 days × 3 searches × 1 agent = 1,800 calls/month. A hypothetical 10-agent version doing the same work per agent would make 18,000 calls, using the same service keys.

For Tavily basic search, up to 1,000 calls/month can fit the Free allowance. If all 1,000 credits remain available and PAYG is enabled, 1,800 basic calls imply 800 paid credits × $0.008 = $6.40 in search usage. Model costs are additional; other API activity reduces the available free allowance.

Model usage is separate: sum input tokens × input price plus output tokens × output price across every model call, using the model's billing units. Tool observations can increase later input-token usage. Add top-up fees and taxes separately.

The table below is gross search usage value before trials, monthly free credits, taxes, purchase minimums, and expiry. It is not a bill. Firecrawl, SerpAPI, and OpenWeb Ninja need their plan/unit rules applied separately.

| Mode | 1,000 calls | 10,000 calls | Cash-flow caveat |
| --- | --- | --- | --- |
| Serper Starter pack rate | $1 | $10 | $50 minimum paid pack; 6-month expiry. |
| Tavily basic PAYG | $8 | $80 | Apply available monthly credits; advanced search doubles credit usage. |
| Brave Search API | $5 | $50 | Apply eligible Search-plan free credits. |
| Exa Auto, up to 10 results | $7 | $70 | Apply available monthly credits; not Lite pricing. |

## Maintenance checklist

| When | Action |
| --- | --- |
| Once at setup · 20–30 min | Record account owner, key label (not value), provider portal, plan, renewal/reset date, credit expiry, and spending cap. Disable unwanted auto-top-ups/early renewals. Run one search and inspect its usage meter. |
| Weekly · 10 min | Review provider request/credit counts and OpenRouter model spend. Check 401/402/429 errors, repeated searches, and source quality. Pause paid runs if usage exceeds the agreed budget. |
| Monthly · 20 min | Recheck the official price links and this snapshot; reconcile invoices with the manual ledger. Review resets, renewals, prepaid expiry, and unused subscriptions. Run the same five representative research tasks to compare useful answers per dollar. |
| Quarterly · 30–45 min | Review who can use each account, remove unused keys, and check provider/dependency changes. Test upgrades in a separate environment. Confirm you can recreate credentials on a replacement computer without placing keys in the repository. |
| Before expiry or after suspected exposure | Replace/revoke the key in the provider portal, save the new key in the encrypted manager, and smoke-test. Review usage for unexpected charges. Review key ownership quarterly; rotate according to provider requirements or an incident, not an arbitrary timer alone. |
| When retiring a service | Cancel the subscription and auto-renewal at the provider, revoke the remote key, then clear the local saved credential. Clearing a key in Playpen does not cancel billing. |

## Current controls and planned accounting

This guide and its budget examples do not activate subscriptions, create keys, set account limits, or schedule maintenance jobs. The maintenance plan is a manual checklist.

Current auto mode tries configured paid APIs before free fallbacks; saving more keys can make more services eligible. It is not a free-first or cheapest-first policy. Select a provider explicitly when controlling cost.

Playpen currently has live activity and repeat-call protection, but no complete per-provider search billing ledger or enforced search-dollar budget. Provider billing dashboards are the source of truth.

Proposed accounting fields: provider, endpoint/mode, requests, billable units, confirmed/estimated cost, pricing date, and remaining budget. Future free_only/cheap/best_search/deep_research policies need explicit provider allowlists and budget enforcement; they are not implemented by this guide.

Store only key labels and account metadata in a maintenance inventory. Keep actual keys in the encrypted credential manager. Follow provider storage/retention terms when keeping source content or traces.

See [search setup](search-providers.md) and [credential storage](credentials-and-openrouter.md).

Use the [Maintenance screen](maintenance-screen.md) for provider onboarding, encrypted saves, access checks, and review dates. OpenRouter has a direct authorization flow; other portals require guided human steps.

For input/output model token rates across backends, see [model pricing](model-pricing.md) and the dashboard's comparison screen.

Maintainers: edit `debugging/dashboard/setup_guide.py`, recheck primary sources, and run `python -m debugging.dashboard.setup_guide --write-docs` to refresh this document. The dashboard uses the same snapshot.
