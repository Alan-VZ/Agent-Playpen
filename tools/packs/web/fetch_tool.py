# fetch_tool.py
from copy import deepcopy

import requests
from markdownify import markdownify as md
from tools.base_tool import BaseTool


class FetchTool(BaseTool):
    """Fetch a URL and return its content converted to Markdown."""

    name = "fetch"
    description = "Fetch a URL and return its readable text content as Markdown."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
            "max_chars": {
                "type": "integer",
                "default": 4000,
                "description": "Maximum characters to return",
            },
        },
        "required": ["url"],
    }

    def __init__(self, max_chars: int = 4000):
        self.max_chars = max_chars
        self.parameters = deepcopy(self.parameters)
        self.parameters["properties"]["max_chars"]["default"] = max_chars

    def run(self, **kwargs) -> str:
        url = kwargs["url"]
        max_chars = kwargs.get("max_chars", self.max_chars)
        headers = {"User-Agent": "AgentPlaypen/1.0"}
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            return f"Fetch error: {e}"
        markdown = md(resp.text, heading_style="ATX")
        return markdown[:max_chars]
    