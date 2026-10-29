# Search reliability and research tasks

An LLM backend and a search provider are independent. A working OpenRouter key
allows model calls; it does not provide Google, Tavily, or SerpAPI search access.
The live feed distinguishes model responses, tool results, and retrieval errors.

## Search providers

- `auto`: tries configured Google/Tavily/SerpAPI services, then DDGS free engines.
  Queries containing paper/journal/DOI/research-related words may subsequently
  fall back to Crossref metadata.
- `ddgs`: explicitly tries DuckDuckGo, Yahoo, then Brave. The successful engine is
  named in the observation. These are public search services, not guaranteed APIs;
  rate limits, blocking, empty results, and poor matches can still occur.
- `duckduckgo`: only that engine, without secretly substituting another one.
- `crossref`: free scholarly title/author/DOI metadata from Crossref. This locates
  publications; it does not read or verify their full text.
- `google`, `tavily`, `serpapi`: the corresponding service with its separately
  saved credentials. Availability depends on that account and provider.

The deprecated `duckduckgo_search` adapter could force queries through Bing while
appearing to use DuckDuckGo. It is replaced with the pinned `ddgs==9.16.1` package
and explicit supported engines. An old copy of `duckduckgo-search` may remain in
an existing environment, but this application's adapter no longer imports it.
See the upstream [DDGS project](https://github.com/deedy5/ddgs) and
[Crossref REST API documentation](https://github.com/CrossRef/rest-api-doc).

For detailed queries with at least three substantive terms, a batch with no word
overlap is treated as suspect and another provider/engine is tried. Short queries
are not filtered this way. This conservative lexical heuristic can miss relevant
synonyms or accept weak matches: it is not a semantic verifier or a truth score.
Inspect the result titles, authors, URLs, and fetched source before relying on it.

## Repeated calls and outcomes

Identical search/fetch requests are cached for the current run. Search query case
and whitespace are normalized for this comparison. A second request reuses the
cached result and warns the model to change approach; a third identical attempt
ends the run as incomplete. Different result counts or fetch limits are distinct
requests. Start another run to retry the same operation against the network.

The guard also applies to unsuccessful reads. It prevents unproductive loops but
can delay recovery from a transient outage until the next run. It does not cache
file writes or all tools, and it does not prove that a source is unavailable.

`Run finished` means a final model response was produced, not that its claims
were independently verified. Tool failures, empty results, and cached retries
produce warning events; a final reply after such warnings is labeled `Run
finished with tool warnings`. Review the log and evidence. A model saying that it
could not locate a paper does not establish that the paper does not exist.

## PDF and answer handling

Fetch detects PDF bytes and extracts text from up to ten pages, with a ten MB
PDF size limit and the configured character cap. Font decoding support is
installed with web/dashboard extras. Scanned PDFs may require OCR, which this
tool does not implement; publisher access controls can still prevent fetching.
This is not a general untrusted-file sandbox or a complete document reader.

Simple final response envelopes such as `{"answer": "..."}` are displayed as
their text. Objects with extra fields are preserved to avoid silently discarding
sources or other data. Retrieved content and answers are rendered as text.

## A direct-source check

For the Prelec paper used in the initial research example, Crossref identifies
the DOI as `10.1126/science.1102081`. An institution-hosted copy is available at
[MIT's paper PDF](https://nel.mit.edu/wp-content/uploads/2016/10/bts.pdf).
Use this task to test fetching independently of search:

```text
Use fetch to read https://nel.mit.edu/wp-content/uploads/2016/10/bts.pdf.
Explain what participants report and what the scoring mechanism rewards.
Cite that source. Distinguish what you actually retrieved from interpretation.
If the retrieved excerpt is insufficient, say so rather than inventing details.
```

After changing dependencies, install `.[dashboard,web-tools,dev]` in the active
environment. Restart the server and hard-refresh the page to load new routes,
UI behavior, and search-provider choices. The local working environment may
already have been updated by the repair; these are reproducible setup steps.
