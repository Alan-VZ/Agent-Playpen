"""Explicit, bounded basic Nimble extraction; no rendering or paid add-ons."""
import ipaddress
from urllib.parse import urlsplit

import requests

from config.credentials import get_credential, redact
from tools.base_tool import BaseTool


class NimbleExtractTool(BaseTool):
    name = "nimble_extract"
    description = "Read a public HTTPS page through Nimble basic extraction. Consumes API credits. Use fetch first."
    parameters = {
        "type": "object", "properties": {
            "url": {"type": "string", "description": "Public HTTPS page URL"},
        }, "required": ["url"], "additionalProperties": False,
    }

    def __init__(self):
        self._cache = {}
        self._attempts = 0

    def run(self, **kwargs):
        url = kwargs["url"]
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if (parsed.scheme != "https" or not host or parsed.username or parsed.password
                or parsed.port not in (None, 443) or "." not in host
                or host.endswith((".localhost", ".local", ".internal"))):
            raise ValueError("Use a public HTTPS URL without credentials.")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError("Private network addresses are unavailable.")
        if url in self._cache:
            return self._cache[url] + "\nCache hit: no additional API request."
        if self._attempts >= 5:
            raise RuntimeError("Nimble Extract limit reached: 5 requests per tool instance/run.")
        key = get_credential("NIMBLE_API_KEY")
        if not key:
            raise RuntimeError("Save NIMBLE_API_KEY in Maintenance before using Nimble Extract.")
        self._attempts += 1
        try:
            response = requests.post(
                "https://sdk.nimbleway.com/v2/extract",
                headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
                json={"url": url, "formats": ["markdown"], "render": False, "driver": "vx6"},
                timeout=25, allow_redirects=False,
            )
        except requests.RequestException:
            raise RuntimeError("Nimble extraction connection failed; no automatic retry.") from None
        if not 200 <= response.status_code < 300:
            raise RuntimeError(f"Nimble extraction HTTP {response.status_code}. Check key, credits, and provider status.")
        try:
            data = response.json()
            if data.get("status") != "success":
                raise ValueError()
            text = data["data"]["markdown"]
            if not isinstance(text, str) or not text.strip():
                raise ValueError()
        except (ValueError, KeyError, TypeError, AttributeError):
            raise RuntimeError("Nimble returned no usable Markdown; no automatic upgrade to rendering.") from None
        result = redact(f"Source: {url}\nProvider: nimble; basic extraction; 1 request.\n" + text[:12000])
        self._cache[url] = result
        return result
