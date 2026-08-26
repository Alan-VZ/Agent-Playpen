# search_tool.py
import os
from typing import Callable

from tools.base_tool import BaseTool


class WebSearchTool(BaseTool):
    """
    Web search tool with pluggable providers.
    Supported providers: auto, google, serpapi, tavily, duckduckgo.
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
        query = kwargs["query"]
        num_results = kwargs.get("num_results", 5)

        if self.provider == "auto":
            return self._auto(query, num_results)
        if self.provider == "duckduckgo":
            return self._duckduckgo(query, num_results)
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
        attempts.append(("duckduckgo", self._duckduckgo))

        failures: list[str] = []
        for name, fn in attempts:
            try:
                result = fn(query, n)
            except Exception as exc:
                failures.append(f"{name}: {exc}")
                continue

            if self._has_results(result):
                return result
            failures.append(f"{name}: no results")

        if failures:
            return "No results found. Tried: " + "; ".join(failures)
        return "No results found."

    def _has_results(self, text: str) -> bool:
        stripped = text.strip()
        return stripped and stripped not in {"No results.", "No results found."}

    def _search_key(self, provider: str) -> str:
        env_map = {
            "google": "GOOGLE_API_KEY",
            "tavily": "TAVILY_API_KEY",
            "serpapi": "SERPAPI_API_KEY",
        }
        env_key = os.getenv(env_map[provider], "")
        if self.provider == "auto":
            return env_key
        return self.api_key or env_key

    def _search_cse_id(self) -> str:
        env_value = os.getenv("GOOGLE_CSE_ID", "")
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
        from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=n):
                results.append(f"- {r['title']}: {r['body']}")
        return "\n".join(results) if results else "No results found."

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
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        lines = [
            f"- {item.get('title')}: {item.get('snippet')}"
            for item in items[:n]
            if item.get("title") or item.get("snippet")
        ]
        return "\n".join(lines) if lines else "No results."

    def _tavily(self, query: str, n: int) -> str:
        import requests

        api_key = self._search_key("tavily")
        if not api_key:
            raise RuntimeError("TAVILY_API_KEY is required for tavily search.")

        resp = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": api_key, "query": query, "max_results": n},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        lines = [f"- {r['title']}: {r['content']}" for r in data.get("results", [])]
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
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("organic_results", [])
        lines = [f"- {r.get('title')}: {r.get('snippet')}" for r in results[:n]]
        return "\n".join(lines) if lines else "No results."
