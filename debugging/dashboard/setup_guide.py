"""Reviewed setup/pricing snapshot shared by the dashboard and generated guide.

Edit this module when reviewing prices, then regenerate the checked-in document:
    python -m debugging.dashboard.setup_guide --write-docs
This is planning information, not a billing engine or an enforced spending limit.
"""
from pathlib import Path

REVIEWED = "2026-10-29"
NEXT_REVIEW = "2026-11-29"
INTRO = (
    "Start with two keys total: your existing OpenRouter key and one search key, "
    "such as Tavily. DDGS, Crossref, and the app's fetch tool need no search key. "
    "Add Serper as an optional third key only when you want to compare Google results."
)
KEY_COUNTS = [
    ("Local model + DDGS/Crossref", "0", "No cloud model or search key; local hardware/electricity still cost money."),
    ("OpenRouter + DDGS/Crossref", "1", "Reuse OPENROUTER_API_KEY; model usage is billed separately."),
    ("OpenRouter + Tavily (recommended start)", "2", "One model key and one search key. Only one new key if OpenRouter is already saved."),
    ("OpenRouter + Tavily + Serper", "3", "An optional comparison setup; choose a search provider explicitly."),
]
KEY_NOTE = (
    "Keys belong to services/projects, not to individual agents. A future 10-agent "
    "run can share the same two or three keys, subject to provider rate limits and "
    "account terms. More agents increase requests and tokens. The current dashboard "
    "still runs one agent per task. Normal OpenRouter routing does not require a "
    "separate model-vendor key for each model; direct backends and BYOK are separate setups."
)

# Monetary figures below are USD, excluding tax. Do not silently replace these
# with third-party comparisons or mix rates from modes this app does not call.
PROVIDERS = [
    {
        "name": "OpenRouter (models)", "keys": "OPENROUTER_API_KEY",
        "signup": "https://openrouter.ai/workspaces/default/keys",
        "pricing": "https://openrouter.ai/pricing",
        "free": "Free-model access is limited; paid model usage draws from your balance.",
        "upfront": "Existing balance: no new purchase needed. Paid top-ups start at $5 credits; Standard card fee is 5.5%, minimum $0.80 (about $5.80 for $5 credits, before tax).",
        "monthly": "No required Standard subscription. Pay for model input/output tokens; rates vary by model.",
        "note": "Track model spending separately from search. Check auto-recharge and key limits; unused credits may expire after 365 days.",
        "sources": [("Top-up fees", "https://openrouter.ai/blog/simplifying-our-platform-fee/"), ("Credit terms", "https://openrouter.ai/terms")],
    },
    {
        "name": "DDGS / DuckDuckGo", "keys": "None", "signup": None,
        "pricing": "https://github.com/deedy5/ddgs",
        "free": "No search API subscription or credits in this adapter.",
        "upfront": "$0", "monthly": "$0 search-provider charge.",
        "note": "Public engines can block requests or return weak results. This is a best-effort option.", "sources": [],
    },
    {
        "name": "Crossref", "keys": "None", "signup": None,
        "pricing": "https://www.crossref.org/documentation/retrieve-metadata/rest-api/",
        "free": "Public scholarly metadata API.", "upfront": "$0",
        "monthly": "$0 for the public endpoint used here.",
        "note": "Titles, authors, and DOIs; metadata does not replace reading the paper.", "sources": [],
    },
    {
        "name": "Tavily", "keys": "TAVILY_API_KEY", "signup": "https://app.tavily.com/",
        "pricing": "https://docs.tavily.com/documentation/api-credits",
        "free": "1,000 credits every month; no card required.", "upfront": "$0 on Free.",
        "monthly": "$0 within Free. Optional PAYG: $0.008/credit. Project: $30/month for 4,000 credits.",
        "note": "Basic search costs 1 credit; advanced costs 2. The app uses the API's basic default. The monthly budget examples assume basic search.", "sources": [],
    },
    {
        "name": "Serper", "keys": "SERPER_API_KEY", "signup": "https://serper.dev/",
        "pricing": "https://serper.dev/",
        "free": "2,500 signup queries; no monthly refill advertised. No card required for the trial.",
        "upfront": "$0 trial; smallest advertised paid pack is $50 for 50,000 credits.",
        "monthly": "No subscription. $1/1,000 is the pack's usage rate, not a $1 monthly bill. Credits expire after 6 months.",
        "note": "Buy only after testing. A $50 pack used for just 6,000 searches before expiry costs $8.33 per 1,000 actually used.", "sources": [],
    },
    {
        "name": "Brave Search API", "keys": "BRAVE_API_KEY",
        "signup": "https://api-dashboard.search.brave.com/",
        "pricing": "https://brave.com/search/api/",
        "free": "Search plan lists $5 free credits/month, equivalent to 1,000 Search requests.",
        "upfront": "Card required for verification; prepaid usage. Confirm paid top-up minimum at checkout.",
        "monthly": "No subscription. Search: $5/1,000 requests before available free credits.",
        "note": "This is the authenticated Search API, separate from the free Brave engine accessed by DDGS.", "sources": [],
    },
    {
        "name": "Exa", "keys": "EXA_API_KEY", "signup": "https://dashboard.exa.ai/",
        "pricing": "https://exa.ai/docs/admin/pricing",
        "free": "$10 credits/month; first-team onboarding can earn a one-time $10 bonus. No payment method required.",
        "upfront": "$0 Free; paid usage uses credits with no subscription/minimum spend advertised.",
        "monthly": "The app's Auto search is $7/1,000 requests, up to 10 results, before credits.",
        "note": "The advertised $4/1,000 Lite rate is a different mode. This app requests Auto with highlights, without page summaries.", "sources": [],
    },
    {
        "name": "Firecrawl Search", "keys": "FIRECRAWL_API_KEY", "signup": "https://www.firecrawl.dev/",
        "pricing": "https://www.firecrawl.dev/pricing",
        "free": "1,000 credits/month, advertised as 500 searches; no card required.",
        "upfront": "$0 Free; Hobby monthly billing starts at $19. Annual checkout charges a full year upfront.",
        "monthly": "Hobby: $19/month for 5,000 credits. $16/month is an advertised annual equivalent, not monthly billing.",
        "note": "Search costs 2 credits per 10 results. Paid plans can enable extra credits; scraping/crawling costs are separate from this app's search-only adapter.", "sources": [],
    },
    {
        "name": "SerpAPI", "keys": "SERPAPI_API_KEY", "signup": "https://serpapi.com/",
        "pricing": "https://serpapi.com/pricing",
        "free": "250 searches/month.", "upfront": "$0 Free; $25 for the first Starter month.",
        "monthly": "Starter $25/month for 1,000 searches; Developer $75/month for 5,000.",
        "note": "Different company/key from Serper. Check Automatic Early Renewal before enabling a paid plan.", "sources": [],
    },
    {
        "name": "OpenWeb Ninja", "keys": "OPENWEBNINJA_API_KEY", "signup": "https://app.openwebninja.com/",
        "pricing": "https://www.openwebninja.com/api/real-time-web-search",
        "free": "100 request units/month, hard limit, no card required.",
        "upfront": "$0 Free. PAYG funding requirements must be confirmed in the account portal.",
        "monthly": "PAYG $0.005/billed unit with no monthly fee; Pro $25/month for 10,000 units, then $0.003/unit.",
        "note": "Standard/full search can consume different units (full is advertised as 2). Verify the app's /search usage meter before assuming $5 per 1,000 calls. Use a direct key, not RapidAPI.", "sources": [],
    },
    {
        "name": "Google Custom Search (legacy)", "keys": "GOOGLE_API_KEY + GOOGLE_CSE_ID",
        "signup": None, "pricing": "https://developers.google.com/custom-search/v1/overview",
        "free": "Existing customers: 100 queries/day.", "upfront": "Closed to new customers; do not set up a new account for this adapter.",
        "monthly": "Existing accounts: $5/1,000 extra queries until discontinuation on January 1, 2027.",
        "note": "Plan migration before that date. CSE ID is a search-engine identifier, not a second API key.", "sources": [],
    },
]

STARTER_STEPS = [
    "Keep your existing OpenRouter key. Set a provider-side limit for the Playpen key where available; a suggested initial model budget is $10/month, not a forecast of usage.",
    "Create one Tavily Free key and save it using Web search provider → tavily → Set search API key → Save. Search costs can stay $0 within its basic-search allowance.",
    "Choose tavily explicitly for predictable account selection. Use ddgs or crossref explicitly for keyless searches. Keep fetch enabled to check original sources.",
    "Optionally try Serper's signup allowance with a third key. Delay purchasing the $50 pack until its results and your volume justify it.",
    "Use Max iterations around 5 for early smoke tests. Review actual provider usage before longer runs. A step limit is not a dollar limit.",
]

BUDGET_NOTES = [
    "Monthly requests ≈ runs/day × active days × search calls/run × agents/run. Add fallback attempts and reruns; subtract actual cache hits. The current dashboard has one agent per run.",
    "Example: 20 runs/day × 30 days × 3 searches × 1 agent = 1,800 calls/month. A hypothetical 10-agent version doing the same work per agent would make 18,000 calls, using the same service keys.",
    "For Tavily basic search, up to 1,000 calls/month can fit the Free allowance. If all 1,000 credits remain available and PAYG is enabled, 1,800 basic calls imply 800 paid credits × $0.008 = $6.40 in search usage. Model costs are additional; other API activity reduces the available free allowance.",
    "Model usage is separate: sum input tokens × input price plus output tokens × output price across every model call, using the model's billing units. Tool observations can increase later input-token usage. Add top-up fees and taxes separately.",
    "The table below is gross search usage value before trials, monthly free credits, taxes, purchase minimums, and expiry. It is not a bill. Firecrawl, SerpAPI, and OpenWeb Ninja need their plan/unit rules applied separately.",
]
USAGE_EXAMPLES = [
    ("Serper Starter pack rate", "$1", "$10", "$50 minimum paid pack; 6-month expiry."),
    ("Tavily basic PAYG", "$8", "$80", "Apply available monthly credits; advanced search doubles credit usage."),
    ("Brave Search API", "$5", "$50", "Apply eligible Search-plan free credits."),
    ("Exa Auto, up to 10 results", "$7", "$70", "Apply available monthly credits; not Lite pricing."),
]

MAINTENANCE = [
    ("Once at setup · 20–30 min", "Record account owner, key label (not value), provider portal, plan, renewal/reset date, credit expiry, and spending cap. Disable unwanted auto-top-ups/early renewals. Run one search and inspect its usage meter."),
    ("Weekly · 10 min", "Review provider request/credit counts and OpenRouter model spend. Check 401/402/429 errors, repeated searches, and source quality. Pause paid runs if usage exceeds the agreed budget."),
    ("Monthly · 20 min", "Recheck the official price links and this snapshot; reconcile invoices with the manual ledger. Review resets, renewals, prepaid expiry, and unused subscriptions. Run the same five representative research tasks to compare useful answers per dollar."),
    ("Quarterly · 30–45 min", "Review who can use each account, remove unused keys, and check provider/dependency changes. Test upgrades in a separate environment. Confirm you can recreate credentials on a replacement computer without placing keys in the repository."),
    ("Before expiry or after suspected exposure", "Replace/revoke the key in the provider portal, save the new key in the encrypted manager, and smoke-test. Review usage for unexpected charges. Review key ownership quarterly; rotate according to provider requirements or an incident, not an arbitrary timer alone."),
    ("When retiring a service", "Cancel the subscription and auto-renewal at the provider, revoke the remote key, then clear the local saved credential. Clearing a key in Playpen does not cancel billing."),
]

LIMITS = [
    "This guide and its budget examples do not activate subscriptions, create keys, set account limits, or schedule maintenance jobs. The maintenance plan is a manual checklist.",
    "Current auto mode tries configured paid APIs before free fallbacks; saving more keys can make more services eligible. It is not a free-first or cheapest-first policy. Select a provider explicitly when controlling cost.",
    "Playpen currently has live activity and repeat-call protection, but no complete per-provider search billing ledger or enforced search-dollar budget. Provider billing dashboards are the source of truth.",
    "Proposed accounting fields: provider, endpoint/mode, requests, billable units, confirmed/estimated cost, pricing date, and remaining budget. Future free_only/cheap/best_search/deep_research policies need explicit provider allowlists and budget enforcement; they are not implemented by this guide.",
    "Store only key labels and account metadata in a maintenance inventory. Keep actual keys in the encrypted credential manager. Follow provider storage/retention terms when keeping source content or traces.",
]


def render_markdown() -> str:
    """Generate the companion document from the same reviewed page content."""
    lines = ["# Keys, costs, and maintenance", "",
             f"Reviewed: {REVIEWED}. Next suggested review: {NEXT_REVIEW}. USD, before tax. Confirm checkout terms before purchasing.",
             "", INTRO, "", "## How many keys?", "",
             "| Setup | Keys total | Meaning |", "| --- | --- | --- |"]
    lines += ["| " + " | ".join(row) + " |" for row in KEY_COUNTS]
    lines += ["", KEY_NOTE, "", "## Recommended starting plan", ""]
    lines += [f"{i}. {step}" for i, step in enumerate(STARTER_STEPS, 1)]
    lines += ["", "## Provider accounts and current prices", ""]
    for provider in PROVIDERS:
        lines += [f"### {provider['name']}", "", f"Credential: `{provider['keys']}`."]
        if provider["signup"]:
            lines += [f"Get the key/account: [Provider portal]({provider['signup']})."]
        lines += ["", f"- Free allowance: {provider['free']}", f"- Upfront: {provider['upfront']}",
                  f"- Recurring/usage cost: {provider['monthly']}", f"- Check: {provider['note']}", "",
                  f"Source: [Official pricing/documentation]({provider['pricing']})."]
        lines += [f"Additional source: [{label}]({url})." for label, url in provider["sources"]]
        lines += [""]
    lines += ["## Estimate your usage", ""]
    for paragraph in BUDGET_NOTES:
        lines += [paragraph, ""]
    lines += ["| Mode | 1,000 calls | 10,000 calls | Cash-flow caveat |", "| --- | --- | --- | --- |"]
    lines += ["| " + " | ".join(row) + " |" for row in USAGE_EXAMPLES]
    lines += ["", "## Maintenance checklist", "", "| When | Action |", "| --- | --- |"]
    lines += ["| " + " | ".join(row) + " |" for row in MAINTENANCE]
    lines += ["", "## Current controls and planned accounting", ""]
    for paragraph in LIMITS:
        lines += [paragraph, ""]
    lines += ["See [search setup](search-providers.md) and [credential storage](credentials-and-openrouter.md).", "",
              "Maintainers: edit `debugging/dashboard/setup_guide.py`, recheck primary sources, and run "
              "`python -m debugging.dashboard.setup_guide --write-docs` to refresh this document. The dashboard uses the same snapshot.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Render the reviewed setup guide.")
    parser.add_argument("--write-docs", action="store_true")
    args = parser.parse_args()
    if args.write_docs:
        target = Path(__file__).resolve().parents[2] / "docs" / "keys-costs-maintenance.md"
        target.write_text(render_markdown(), encoding="utf-8")
        print(f"Updated {target}")
    else:
        print(render_markdown())
