# Model prices in the picker and comparison screen

The model picker shows input and output rates under model names. Selecting a
model shows its source, retrieval time, and any listed cached-input/cache-write
rates. Only the model ID goes into execution settings; price labels do not
change the selected ID.

Open **Compare model prices across backends** below the picker, or visit
`http://127.0.0.1:8765/model-prices`. Filter by backend, model ID, or source and
sort by input/output price or a base text estimate. Public comparison requires
no additional API keys. **Load selected backend's model list** uses that backend's
existing credentials and replaces its public comparison rows with the discovered
model list. An unavailable account can still return fallback names, labeled as
such; a public price is not proof that the model is available to your account.

## Units and meaning

All numeric token rates are **USD per 1 million text tokens**. Input is what the
model reads; output is what it generates. Repeated agent iterations can each
incur input/output usage. The same text can tokenize differently on different
models, so equal per-token rates do not guarantee equal task cost.

The comparison estimate is:

```text
base text estimate = input_tokens × input_rate / 1,000,000
                   + output_tokens × output_rate / 1,000,000
```

It is a planning calculation, not an invoice or an enforced budget. It excludes
long-context tier adjustments, cache effects, extra reasoning tokens not included
in your entered count, tool/search/media fees, top-up fees, tax, discounts, and
account contracts. Cache writes can have different retention windows: official
source notes identify the displayed base duration where applicable.

Missing, malformed, negative/variable, and non-finite rates are **Unavailable**,
never zero. Genuine advertised zero token rates remain `$0`, without promising
that every other charge is zero. Hourly and other advertised charges are called
out in notes. Non-token audio/image/video charges are not converted into text
token rates. Unknown models are not assigned a similarly named model's price.

## Coverage and source priority

| Backend | Price source and limits |
| --- | --- |
| OpenRouter | Its public paginated model catalog. Per-token prices are multiplied by 1,000,000 for display. Routing/upstream provider, tools, and media can affect the bill. |
| Together | Token prices in the authenticated model catalog where supplied; otherwise the official serverless model table, then exact-ID reference estimates. Input/output catalog prices are already per million. Image/hourly prices are not mistaken for text rates. |
| OpenAI | Official standard text-token pricing data on the pricing page; other processing tiers are not substituted. Exact-ID reference fallback covers unmatched entries. Context-qualified rates retain their applicability notes. |
| Anthropic | Explicit model links/rates in the official pricing table; reference fallback for unmatched snapshots/IDs. Model IDs are not guessed from similar names. Prompt-length and cache-window notes remain relevant. |
| Groq | Official token-rate rows and Contact Sales requirements, then exact-ID reference fallback where no official row matches. Contact Sales overrides historical numeric estimates. Audio/character rates are not text-token prices. |
| Azure OpenAI | Account/deployment-specific. A deployment name alone cannot establish the model version, region, contract, or price; obtain an account quote. |
| LM Studio / Ollama | Local/self-hosted pricing status. No token tariff is assumed; hardware, electricity, hosting, or any separate service plan are outside these figures. Installed models can be loaded from the selected backend. |

Official pricing page parsers recognize specific table/data structures and
explicit units/IDs. They do not execute website scripts. If a layout changes,
unrecognized rates are not fabricated: a previously retrieved source can be
shown as stale, a reference estimate can be shown, or the price is unavailable.

LiteLLM's public community registry is a fallback, **not a provider quote**.
Reference rows are labeled **Reference estimate** and keep separate source links.
Provider and model IDs must both match exactly. Aggregate model-size categories
and non-chat billing modes are excluded from the reference comparison. Reference
catalogs can include aliases, legacy models, or models your account cannot use.
A retrieval timestamp is not the underlying rate's last review date.

## Refresh, caching, and privacy

The server caches public OpenRouter data for five minutes and official/reference
pricing data for one hour in memory. **Load** in the workspace refreshes the
OpenRouter model catalog. **Refresh public prices** in the comparison screen
requests fresh public sources. On a failed refresh, older data remains explicitly
stale with its original retrieval time. A first failure has no fake price/date.
Brief failure caching avoids repeatedly hammering an unavailable source.

Public retrieval uses fixed HTTPS destinations, disabled redirects, response
size limits, and fresh HTTP sessions without `.netrc`, environment/proxy
credentials, or saved provider keys. Private model IDs, prompts, and tasks are
not sent to the public reference service. Networks requiring an authenticated
proxy may be unable to retrieve prices; official links remain available.
Authenticated model discovery retains its existing endpoint/key protections.

Pricing endpoints share the local dashboard session/host/origin protections.
No model completion or search is issued by loading prices. The comparison data
does not replace a provider invoice, the application's runtime cost utilities,
or a complete per-provider spending ledger.

## Primary sources and reference registry

- [OpenRouter models API](https://openrouter.ai/docs/api/api-reference/models/list-all-models-and-their-properties)
- [OpenAI API pricing](https://developers.openai.com/api/docs/pricing)
- [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [Groq model rates](https://console.groq.com/docs/models)
- [Together serverless model rates](https://docs.together.ai/docs/serverless/models)
- [Together model-price schema](https://github.com/togethercomputer/together-python/blob/main/src/together/types/models.py)
- [Azure OpenAI pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/)
- [LiteLLM reference registry](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json)

These are data sources, not a new inference backend or a promise of universal
account-specific price coverage. Review official terms before spending money.

## Verification

`tests/test_model_pricing.py` covers unit conversions, exact matches, published
versus reference rates, zero/missing/variable values, official table contracts,
cache staleness, pagination, public-request credential isolation, and API session
protection. Browser DOM tests cover the picker (including late responses after
backend switching) and the comparison screen's filters, estimates, safe text,
and model-list loading.

```powershell
python tests/render_pricing_ui.py
node tests/model_prices_ui.cjs
node tests/dashboard_ui.cjs
```

Use the optional jsdom setup in [testing](testing.md). Tests use synthetic data
and fake credentials; separate public-source smoke checks verify current layout
compatibility without signing in or issuing model/search requests.
