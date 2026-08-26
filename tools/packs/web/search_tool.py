# search_tool.py
import os
from tools.base_tool import BaseTool


class WebSearchTool(BaseTool):
    """
    Web search tool with pluggable providers.
    Supported providers: serpapi, tavily, duckduckgo (default).
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

    def __init__(self, provider: str | None = None, api_key: str | None = None):
        self.provider = provider if provider is not None else os.getenv("WEB_SEARCH_PROVIDER") or "duckduckgo"
        self.api_key = api_key

    def run(self, **kwargs) -> str:
        query = kwargs["query"]
        num_results = kwargs.get("num_results", 5)
        if self.provider == "duckduckgo":
            return self._duckduckgo(query, num_results)
        elif self.provider == "tavily":
            return self._tavily(query, num_results)
        elif self.provider == "serpapi":
            return self._serpapi(query, num_results)
        else:
            return f"Unknown provider: {self.provider}"

    def _duckduckgo(self, query: str, n: int) -> str:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=n):
                results.append(f"- {r['title']}: {r['body']}")
        return "\n".join(results) if results else "No results found."

    def _tavily(self, query: str, n: int) -> str:
        import requests
        resp = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": self.api_key, "query": query, "max_results": n},
            timeout=15,
        )
        data = resp.json()
        lines = [f"- {r['title']}: {r['content']}" for r in data.get("results", [])]
        return "\n".join(lines) if lines else "No results."

    def _serpapi(self, query: str, n: int) -> str:
        import requests
        resp = requests.get(
            "https://serpapi.com/search",
            params={"q": query, "api_key": self.api_key, "num": n},
            timeout=15,
        )
        data = resp.json()
        results = data.get("organic_results", [])
        lines = [f"- {r.get('title')}: {r.get('snippet')}" for r in results[:n]]
        return "\n".join(lines) if lines else "No results."
    