"""Direct search APIs with fixed destinations and bounded, source-linked output.

These adapters use provider APIs, not MCP transport. Credentials never enter
agent arguments; authenticated requests must not follow redirects.
"""

from config.credentials import SEARCH_KEYS, remember_secret, redact

API_PROVIDERS = ("serper", "brave", "exa", "firecrawl", "openwebninja")


def search_api(provider: str, query: str, count: int, key: str) -> str:
    import requests

    if provider not in API_PROVIDERS:
        raise ValueError("Unsupported search API provider")
    if not key:
        raise RuntimeError(f"{SEARCH_KEYS[provider]} is required for {provider} search. Save it in Credential manager.")
    remember_secret(key)
    headers = {"Accept": "application/json"}
    if provider == "serper":
        method, url = "POST", "https://google.serper.dev/search"
        headers["X-API-KEY"] = key
        payload = {"json": {"q": query, "num": count}}
    elif provider == "brave":
        method, url = "GET", "https://api.search.brave.com/res/v1/web/search"
        headers["X-Subscription-Token"] = key
        payload = {"params": {"q": query, "count": count}}
    elif provider == "exa":
        method, url = "POST", "https://api.exa.ai/search"
        headers["x-api-key"] = key
        payload = {"json": {"query": query, "numResults": count, "type": "auto", "contents": {"highlights": True}}}
    elif provider == "firecrawl":
        method, url = "POST", "https://api.firecrawl.dev/v2/search"
        headers["Authorization"] = f"Bearer {key}"
        # Search only: do not implicitly start crawls or scrape every result.
        payload = {"json": {"query": query, "limit": count, "sources": [{"type": "web"}]}}
    else:
        method, url = "GET", "https://api.openwebninja.com/realtime-web-search/search"
        headers["x-api-key"] = key
        payload = {"params": {"q": query, "num": count}}

    try:
        response = requests.request(method, url, headers=headers, timeout=15, allow_redirects=False, **payload)
    except requests.Timeout:
        raise RuntimeError(f"{provider} search timed out. Try again later or select another provider.") from None
    except requests.RequestException:
        # A raw exception can contain headers, response bodies, or key-bearing URLs.
        raise RuntimeError(f"{provider} search connection failed. Check connectivity or select another provider.") from None
    if not 200 <= response.status_code < 300:
        hint = {
            401: "Check the saved API key.", 403: "Check the key and account permissions.",
            402: "Check account credits.", 429: "Rate limit or quota reached; retry later.",
        }.get(response.status_code, "Try again later or select another provider.")
        raise RuntimeError(f"{provider} search returned HTTP {response.status_code}. {hint}")
    try:
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError()
        if data.get("success") is False or data.get("error") or (
            provider == "openwebninja" and data.get("status", "OK") != "OK"
        ):
            raise RuntimeError(f"{provider} reported an unsuccessful search. Check your account and provider status.")
        if provider == "serper":
            items = data.get("organic", [])
        elif provider == "brave":
            items = data.get("web", {}).get("results", [])
        elif provider == "exa":
            items = data.get("results", [])
        elif provider == "firecrawl":
            items = data.get("data", {}).get("web", [])
        else:
            items = data.get("data", {}).get("organic_results", [])
        if not isinstance(items, list):
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise RuntimeError(f"{provider} returned an unexpected search response.") from None

    lines = []
    for item in items:
        if not isinstance(item, dict):
            continue
        url = item.get("url") or item.get("link")
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            continue
        title = item.get("title") or "Untitled source"
        snippet = item.get("snippet") or item.get("description") or ""
        if provider == "exa":
            highlights = item.get("highlights") or []
            snippet = " ".join(value for value in highlights if isinstance(value, str)) if isinstance(highlights, list) else ""
        lines.append(f"- {str(title)[:300]}: {str(snippet)[:1200]}\n  URL: {url[:2048]}")
        if len(lines) >= count:
            break
    if not lines:
        return f"No results found from {provider}."
    return redact(f"Search provider: {provider}\n" + "\n".join(lines))
