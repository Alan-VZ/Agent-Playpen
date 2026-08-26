# scraper_tool.py
import requests
from bs4 import BeautifulSoup
from tools.base_tool import BaseTool


class ScraperTool(BaseTool):
    """Extract text from elements matching a CSS selector on a URL."""

    name = "scraper"
    description = "Fetch a URL and extract text from elements matching a CSS selector."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to scrape"},
            "css_selector": {
                "type": "string",
                "description": "CSS selector e.g. 'h1', 'p.intro', '#main-content'",
            },
        },
        "required": ["url", "css_selector"],
    }

    def run(self, **kwargs) -> str:
        url = kwargs["url"]
        css_selector = kwargs["css_selector"]
        resp = requests.get(url, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        elements = soup.select(css_selector)
        if not elements:
            return f"No elements matched selector '{css_selector}' on {url}"
        return "\n".join(el.get_text(strip=True) for el in elements)
    