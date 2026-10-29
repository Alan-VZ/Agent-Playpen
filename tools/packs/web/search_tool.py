# search_tool.py
import os
import re
from config.credentials import get_credential, SEARCH_KEYS, redact
from typing import Callable

from tools.base_tool import BaseTool
from tools.packs.web.api_search import API_PROVIDERS, search_api


class WebSearchTool(BaseTool):
    """
    Web search tool with pluggable providers.
    Supports free engines, Crossref, and the APIs listed in config.credentials.SEARCH_KEYS.
    Set WEB_SEARCH_PROVIDER in .env to select.
    """

    name = "web_search"
    description = "Search the web and return top N results as text."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "num_results": {
                "type": "integer",
                "default": 5,
                "description": "Number of results to return",
            },
        },
        "required": ["query"],
    }

    def __init__(self, provider: str | None = None, api_key: str | None = None, cse_id: str | None = None):
        self.provider = (provider if provider is not None else os.getenv("WEB_SEARCH_PROVIDER") or "auto").lower()
        self.api_key = api_key
        self.cse_id = cse_id

    def run(self, **kwargs) -> str:
        query = kwargs["query"].strip()
        if not query:
            raise ValueError("Search query cannot be empty.")
        num_results = min(max(int(kwargs.get("num_results", 5)), 1), 10)

        if self.provider == "auto":
            return self._auto(query, num_results)
        if self.provider in API_PROVIDERS:
            return self._api_search(self.provider, query, num_results)
        if self.provider == "duckduckgo":
            return self._duckduckgo(query, num_results)
        if self.provider == "ddgs":
            return self._ddgs(query, num_results)
        if self.provider == "crossref":
            return self._crossref(query, num_results)
        if self.provider == "google":
            return self._google(query, num_results)
        if self.provider == "tavily":
            return self._tavily(query, num_results)
        if self.provider == "serpapi":
            return self._serpapi(query, num_results)
        return f"Unknown provider: {self.provider}"

    def _auto(self, query: str, n: int) -> str:
        attempts: list[tuple[str, Callable[[str, int], str]]] = []

        if self._has_google_credentials():
            attempts.append(("google", self._google))
        if self._has_tavily_credentials():
            attempts.append(("tavily", self._tavily))
        if self._has_serpapi_credentials():
            attempts.append(("serpapi", self._serpapi))
        for provider in API_PROVIDERS:
            if self._search_key(provider):
                attempts.append((provider, lambda q, n, name=provider: self._api_search(name, q, n)))
        attempts.append(("ddgs", self._ddgs))
        if re.search(r"\b(paper|journal|doi|scholarly|preprint|article|research)\b", query, re.IGNORECASE):
            attempts.append(("crossref", self._crossref))

        failures: list[str] = []
        for name, fn in attempts:
            try:
                result = fn(query, n)
            except Exception as exc:
                failures.append(redact(f"{name}: {exc}"))
                continue

            if self._has_results(result) and self._matches_query(query, result):
                return result
            failures.append(f"{name}: no usable results (empty or no query-term overlap)")

        if failures:
            return "No results found. Tried: " + "; ".join(failures) + ". Try a different query/provider or fetch a known source URL; this does not establish that the source does not exist."
        return "No results found."

    def _has_results(self, text: str) -> bool:
        stripped = text.strip()
        return bool(stripped) and not stripped.lower().startswith(("no results", "search error", "[error]"))

    @staticmethod
    def _matches_query(query: str, text: str) -> bool:
        # A deliberately conservative batch-level relevance heuristic. It does
        # not rank truth, validate facts, or reject short/ambiguous queries.
        stopwords = {"the", "and", "for", "from", "with", "that", "this", "find", "paper", "original", "source"}
        terms = {word for word in re.findall(r"[^\W_]+", query.casefold()) if len(word) > 2 and word not in stopwords}
        if len(terms) < 3:
            return True
        words = set(re.findall(r"[^\W_]+", text.casefold()))
        return bool(terms & words)

    def _search_key(self, provider: str) -> str:
        env_key = get_credential(SEARCH_KEYS[provider])
        if self.provider == "auto":
            return env_key
        return self.api_key or env_key

    def _api_search(self, provider: str, query: str, n: int) -> str:
        return search_api(provider, query, n, self._search_key(provider))

    def _search_cse_id(self) -> str:
        env_value = get_credential("GOOGLE_CSE_ID")
        if self.provider == "auto":
            return env_value
        return self.cse_id or env_value

    def _has_google_credentials(self) -> bool:
        return bool(self._search_key("google") and self._search_cse_id())

    def _has_tavily_credentials(self) -> bool:
        return bool(self._search_key("tavily"))

    def _has_serpapi_credentials(self) -> bool:
        return bool(self._search_key("serpapi"))

    def _duckduckgo(self, query: str, n: int) -> str:
        return self._free_search(query, n, ("duckduckgo",))

    def _ddgs(self, query: str, n: int) -> str:
        return self._free_search(query, n, ("duckduckgo", "yahoo", "brave"))

    def _free_search(self, query: str, n: int, engines: tuple[str, ...]) -> str:
        from ddgs import DDGS
        failures = []
        for engine in engines:
            try:
                with DDGS(timeout=5) as search:
                    items = search.text(query, max_results=n, backend=engine)
                lines = [f"- {r.get('title', '')}: {r.get('body', '')}\n  URL: {r.get('href') or r.get('url', '')}" for r in items]
                text = "\n".join(lines)
                if text and self._matches_query(query, text):
                    return f"Search engine: {engine}\n" + text
                failures.append(f"{engine}: empty or no query-term overlap")
            except Exception as exc:
                failures.append(f"{engine}: {type(exc).__name__}")
        return "No results found. Tried: " + "; ".join(failures)

    def _google(self, query: str, n: int) -> str:
        import requests

        api_key = self._search_key("google")
        cse_id = self._search_cse_id()
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY is required for google search.")
        if not cse_id:
            raise RuntimeError("GOOGLE_CSE_ID is required for google search.")

        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": api_key,
                "cx": cse_id,
                "q": query,
                "num": min(max(n, 1), 10),
            },
            timeout=15,
            allow_redirects=False,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        lines = [
            f"- {item.get('title')}: {item.get('snippet')}\n  URL: {item.get('link', '')}"
            for item in items[:n]
            if item.get("title") or item.get("snippet")
        ]
        return "\n".join(lines) if lines else "No results."

    def _crossref(self, query: str, n: int) -> str:
        """Locate scholarly metadata/DOIs; this is not full-text retrieval."""
        import requests
        response = requests.get(
            "https://api.crossref.org/works",
            params={"query.bibliographic": query, "rows": n}, timeout=8,
        )
        response.raise_for_status()
        lines = []
        for item in response.json().get("message", {}).get("items", []):
            titles = item.get("title") or []
            title = titles[0] if titles else "Untitled record"
            authors = ", ".join(" ".join(filter(None, [author.get("given"), author.get("family")])) for author in item.get("author", []))
            doi = item.get("DOI", "")
            url = "https://doi.org/" + doi if doi else item.get("URL", "")
            lines.append(f"- {title}\n  Authors: {authors}\n  DOI: {doi}\n  URL: {url}")
        return "Crossref scholarly metadata (not full text):\n" + "\n".join(lines) if lines else "No results found."

    def _tavily(self, query: str, n: int) -> str:
        import requests

        api_key = self._search_key("tavily")
        if not api_key:
            raise RuntimeError("TAVILY_API_KEY is required for tavily search.")

        resp = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": api_key, "query": query, "max_results": n},
            timeout=15,
            allow_redirects=False,
        )
        resp.raise_for_status()
        data = resp.json()
        lines = [f"- {r['title']}: {r['content']}\n  URL: {r.get('url', '')}" for r in data.get("results", [])]
        return "\n".join(lines) if lines else "No results."

    def _serpapi(self, query: str, n: int) -> str:
        import requests

        api_key = self._search_key("serpapi")
        if not api_key:
            raise RuntimeError("SERPAPI_API_KEY is required for serpapi search.")

        resp = requests.get(
            "https://serpapi.com/search",
            params={"q": query, "api_key": api_key, "num": n},
            timeout=15,
            allow_redirects=False,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("organic_results", [])
        lines = [f"- {r.get('title')}: {r.get('snippet')}\n  URL: {r.get('link', '')}" for r in results[:n]]
        return "\n".join(lines) if lines else "No results."
