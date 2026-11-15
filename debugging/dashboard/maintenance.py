"""Provider onboarding, bounded verification, and secret-free maintenance history."""
import base64
import hashlib
import json
import logging
import math
import secrets
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import requests

from config import credentials
from debugging.dashboard import setup_guide
from tools.packs.web.search_tool import WebSearchTool

CALLBACK_PATH = "/maintenance/oauth-callback"
COOKIE_NAME = "playpen_maintenance"
LOCK = threading.RLock()


class MaintenanceError(RuntimeError):
    """A message constructed locally and safe for the maintenance UI."""


def provider_catalog():
    entries = []
    names = {**credentials.BACKEND_KEYS, **credentials.SEARCH_KEYS}
    for item in setup_guide.PROVIDERS:
        provider = next((name for name, key in names.items() if item["keys"].startswith(key)), None)
        if not provider:
            continue
        entries.append({"id": provider, "name": item["name"], "key_name": names[provider],
                        "portal": item["signup"] or item["pricing"], "pricing": item["pricing"],
                        "readonly_check": provider in {"openrouter", "tavily", "firecrawl"},
                        "search_test": provider in credentials.SEARCH_KEYS,
                        "automated_connection": provider == "openrouter"})
    for provider, portal in {
        "openai": "https://platform.openai.com/api-keys",
        "anthropic": "https://console.anthropic.com/settings/keys",
        "groq": "https://console.groq.com/keys",
        "together": "https://api.together.ai/settings/api-keys",
        "azure_openai": "https://portal.azure.com/",
    }.items():
        entries.append({"id": provider, "name": provider.replace("_", " ").title(),
                        "key_name": names[provider], "portal": portal, "pricing": portal,
                        "readonly_check": False, "search_test": False, "automated_connection": False})
    return entries


CATALOG = {item["id"]: item for item in provider_catalog()}


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class MaintenanceHistory:
    """Persist only approved statuses, timestamps, and checklist flags, never API data."""

    def __init__(self, root: Path):
        self.path = root / "traces" / "maintenance.json"

    def read(self):
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(value, dict) and isinstance(value.get("providers"), dict) and isinstance(value.get("events"), list):
                # Treat the local metadata file as data, not a source of arbitrary
                # strings to export. A malformed/edited file cannot expose extra fields.
                clean = {"providers": {}, "events": []}
                for provider, record in value["providers"].items():
                    if provider not in CATALOG or not isinstance(record, dict):
                        continue
                    selected = {name: record[name] for name in ("portal_ready", "billing_reviewed") if isinstance(record.get(name), bool)}
                    if isinstance(record.get("check_status"), str) and record["check_status"] in {"verified", "failed", "missing", "manual"}:
                        selected["check_status"] = record["check_status"]
                    for name in ("last_check", "reviewed_at", "next_review"):
                        text = record.get(name)
                        try:
                            if isinstance(text, str) and len(text) <= 40:
                                datetime.fromisoformat(text)
                                selected[name] = text
                        except ValueError:
                            pass
                    clean["providers"][provider] = selected
                for event in value["events"][-100:]:
                    if not isinstance(event, dict) or not isinstance(event.get("provider"), str) or event["provider"] not in CATALOG or not isinstance(event.get("event"), str) or event["event"] not in {"key_saved", "key_cleared", "access_checked", "review_updated", "connection_started", "connection_saved", "connection_failed"}:
                        continue
                    try:
                        stamp = event.get("at")
                        if not isinstance(stamp, str) or len(stamp) > 40:
                            continue
                        datetime.fromisoformat(stamp)
                    except ValueError:
                        continue
                    status = event.get("status")
                    clean["events"].append({"provider": event["provider"], "event": event["event"], "at": stamp,
                                            "status": status if isinstance(status, str) and status in {"verified", "failed", "missing", "manual"} else None})
                return clean
        except (OSError, ValueError):
            pass
        return {"providers": {}, "events": []}

    def update(self, provider, event, *, status=None, portal_ready=None, billing_reviewed=None, next_review=None):
        if provider not in CATALOG or event not in {"key_saved", "key_cleared", "access_checked", "review_updated", "connection_started", "connection_saved", "connection_failed"}:
            raise ValueError("Unknown maintenance event")
        if status not in {None, "verified", "failed", "missing", "manual"}:
            raise ValueError("Unknown maintenance status")
        with LOCK:
            data = self.read()
            record = data["providers"].setdefault(provider, {})
            if event in {"key_saved", "key_cleared", "connection_saved"}:
                record.pop("last_check", None)
                record.pop("check_status", None)
            if status:
                record.update(last_check=now_iso(), check_status=status)
            if portal_ready is not None:
                record["portal_ready"] = bool(portal_ready)
            if billing_reviewed is not None:
                record["billing_reviewed"] = bool(billing_reviewed)
            if event == "review_updated":
                record["next_review"] = next_review
                record["reviewed_at"] = now_iso()
            data["events"].append({"provider": provider, "event": event, "status": status, "at": now_iso()})
            data["events"] = data["events"][-100:]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
            temporary.replace(self.path)
            return data


def _json_request(method, url, **kwargs):
    try:
        response = requests.request(method, url, timeout=15, allow_redirects=False, **kwargs)
    except requests.RequestException:
        raise MaintenanceError("Provider connection failed or timed out. No automatic retry was made.") from None
    if not 200 <= response.status_code < 300:
        hint = {401: "Key rejected.", 402: "Credits required.", 403: "Access denied.", 429: "Rate limit or quota reached."}.get(response.status_code, "Try again later or use the provider portal.")
        raise MaintenanceError(f"Provider returned HTTP {response.status_code}. {hint}")
    try:
        data = response.json()
        if not isinstance(data, dict) or data.get("error") or data.get("success") is False:
            raise ValueError()
        return data
    except (ValueError, TypeError):
        raise MaintenanceError("Provider returned an unexpected response. Check its portal.") from None


def verify_access(provider: str, allow_billable=False):
    entry = CATALOG[provider]
    key = credentials.get_credential(entry["key_name"])
    if not key:
        return {"status": "missing", "message": "Save this provider's key first.", "usage": {}}
    if entry["readonly_check"]:
        urls = {"openrouter": "https://openrouter.ai/api/v1/key", "tavily": "https://api.tavily.com/usage",
                "firecrawl": "https://api.firecrawl.dev/v2/team/credit-usage"}
        data = _json_request("GET", urls[provider], headers={"Authorization": f"Bearer {key}"})
        fields = {
            "openrouter": ("data", ("usage", "usage_monthly", "limit", "limit_remaining")),
            "tavily": ("key", ("usage", "limit")),
            "firecrawl": ("data", ("remainingCredits", "planCredits")),
        }
        container, allowed = fields[provider]
        values = data.get(container)
        if not isinstance(values, dict):
            raise MaintenanceError("The provider did not return recognizable account usage information.")
        # Never return labels, key hashes, IDs, emails, or raw provider responses.
        usage = {name: value for name, value in values.items() if name in allowed and
                 isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)}
        if not usage:
            raise MaintenanceError("The provider did not return recognizable numeric usage information.")
        return {"status": "verified", "message": "Authenticated account/usage endpoint accepted the key. This does not verify email, identity, or model/search access beyond that endpoint.", "usage": usage}
    if entry["search_test"] and allow_billable:
        # Explicit, bounded smoke test; never run automatically on save or page load.
        WebSearchTool(provider).run(query="Drazen Prelec Bayesian truth serum", num_results=1)
        return {"status": "verified", "message": "Search API test completed. It may consume provider credits; it does not verify email or identity.", "usage": {}}
    return {"status": "manual", "message": "No non-billable account check is configured. Complete portal verification; a saved key alone does not prove API access.", "usage": {}}


class OpenRouterConnections:
    """Ephemeral, browser-bound S256 PKCE. No keys/codes/verifiers on disk."""

    def __init__(self):
        self.flows = {}

    def start(self, owner: str, origin: str, replace: bool):
        parsed = urlsplit(origin)
        if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
            raise ValueError("Open the dashboard on its local HTTP address.")
        # Check native storage before the provider can issue a new key.
        credentials.store.get("OPENROUTER_API_KEY")
        previous = credentials.get_credential("OPENROUTER_API_KEY")
        if previous and not replace:
            raise ValueError("An OpenRouter key is already saved. Select replacement explicitly before connecting.")
        with LOCK:
            self.flows = {key: value for key, value in self.flows.items() if value["expires"] > time.monotonic()}
            if len(self.flows) >= 20:
                raise ValueError("Too many pending connections; wait for them to expire.")
            verifier = secrets.token_urlsafe(48)
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            state = secrets.token_urlsafe(32)
            self.flows[state] = {"owner": owner, "expires": time.monotonic() + 600, "verifier": verifier,
                                 "previous": hashlib.sha256(previous.encode()).digest()}
        query = urlencode({"callback_url": origin.rstrip("/") + CALLBACK_PATH, "code_challenge": challenge,
                           "code_challenge_method": "S256", "state": state, "key_label": "Agent Playpen"})
        return {"authorization_url": "https://openrouter.ai/auth?" + query}

    def exchange(self, owner: str, state: str, code: str):
        with LOCK:
            pending = self.flows.get(state)
            if not pending or not secrets.compare_digest(pending["owner"], owner):
                raise ValueError("Connection not recognized in this browser. Start again from Maintenance.")
            self.flows.pop(state)  # Single use even when an exchange fails.
            if pending["expires"] <= time.monotonic():
                raise ValueError("Connection expired. Start again from Maintenance.")
            current = credentials.get_credential("OPENROUTER_API_KEY")
            if hashlib.sha256(current.encode()).digest() != pending["previous"]:
                raise ValueError("The saved key changed during sign-in. Start again to avoid overwriting it.")
            data = _json_request("POST", "https://openrouter.ai/api/v1/auth/keys", json={
                "code": code, "code_verifier": pending["verifier"], "code_challenge_method": "S256",
            })
            key = data.get("key")
            if not isinstance(key, str) or not key.strip() or len(key) > 8192 or any(char in key for char in "\r\n\x00"):
                raise RuntimeError("OpenRouter did not return a valid API key.")
            return credentials.remember_secret(key)


connections = OpenRouterConnections()


class CallbackAccessFilter(logging.Filter):
    """Remove callback query strings (authorization codes) from Uvicorn access logs."""

    def filter(self, record):
        if isinstance(record.args, tuple):
            record.args = tuple(CALLBACK_PATH if isinstance(arg, str) and arg.startswith(CALLBACK_PATH + "?") else arg for arg in record.args)
        return True
