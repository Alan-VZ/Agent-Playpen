"""Credential inventory: presence is distinct from authenticated access."""
import json
import threading
import re
from datetime import date, datetime, timezone
from pathlib import Path
import requests

from config import credentials
from debugging.dashboard import maintenance

LOCK = threading.RLock()
STATUSES = {"verified", "unchecked", "missing", "authentication_rejected", "permission_denied",
            "quota", "rate_limited", "connection_failed", "unsupported", "storage_unavailable"}
MODEL_CHECKS = {"openai": "https://api.openai.com/v1/models",
                "anthropic": "https://api.anthropic.com/v1/models",
                "groq": "https://api.groq.com/openai/v1/models"}


def model_access(provider):
    key = credentials.get_credential(credentials.BACKEND_KEYS[provider])
    if not key:
        return {"status": "missing", "message": "Save this provider's key first."}
    headers = {"Authorization": f"Bearer {key}"}
    if provider == "anthropic":
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    with requests.Session() as session:
        session.trust_env = False
        with session.get(MODEL_CHECKS[provider], headers=headers, timeout=10, allow_redirects=False, stream=True) as response:
            if not 200 <= response.status_code < 300:
                raise maintenance.MaintenanceError(f"Provider returned HTTP {response.status_code}.")
            content = bytearray()
            for chunk in response.iter_content(16384):
                content.extend(chunk)
                if len(content) > 1024 * 1024:
                    raise maintenance.MaintenanceError("Model-list response exceeded the check limit.")
            payload = json.loads(content)
            if not isinstance(payload, dict) or not isinstance(payload.get("data"), list) or payload.get("error"):
                raise maintenance.MaintenanceError("Provider returned an unexpected model-list response.")
    return {"status": "verified", "message": "Authenticated model-list endpoint accepted this key. This does not verify selected-model inference, quota, or billing."}


def classify(code=None):
    return {401: "authentication_rejected", 402: "quota", 403: "permission_denied",
            429: "rate_limited"}.get(code, "connection_failed")


def requirements(config):
    """Return deduplicated provider -> consumer names, including team members."""
    result = {}
    for index, selected in enumerate(config.get("agents") or config.get("model_slots") or [config]):
        agent = {**config, **{key: value for key, value in selected.items() if value is not None}}
        backend = agent.get("backend", "lm_studio")
        if backend in credentials.BACKEND_KEYS:
            result.setdefault(backend, []).append(f"agent-{index + 1}: model")
        for tool in agent.get("tools", []):
            provider = "nimble" if tool == "nimble_extract" else agent.get("search_provider", "auto")
            if tool in {"web_search", "nimble_extract"} and provider in credentials.SEARCH_KEYS:
                result.setdefault(provider, []).append(f"agent-{index + 1}: {tool}")
        for provider in agent.get("fallback_providers", []):
            if provider in credentials.SEARCH_KEYS:
                result.setdefault(provider, []).append(f"agent-{index + 1}: allowed fallback")
    return result


class Inventory:
    def __init__(self, root):
        self.path = Path(root) / "traces" / "credential-inventory.json"

    def read(self):
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def update(self, provider, **fields):
        if provider not in maintenance.CATALOG:
            raise ValueError("Unknown provider")
        with LOCK:
            data = self.read()
            record = data.setdefault(provider, {})
            if not isinstance(record, dict):
                record = {}
                data[provider] = record
            record.update(fields)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
            temporary.replace(self.path)

    def invalidate(self, provider):
        self.update(provider, status="unchecked", checked_at=None, scope=None)

    def rows(self, config=None):
        required = requirements(config or {})
        records = self.read()
        rows = []
        for provider, entry in maintenance.CATALOG.items():
            previous = records.get(provider, {})
            if not isinstance(previous, dict):
                previous = {}
            status = previous.get("status", "unchecked")
            if status not in STATUSES:
                status = "unchecked"
            try:
                native_present = bool(credentials.store.get(entry["key_name"]))
                present = bool(credentials.get_credential(entry["key_name"]))
                if not present:
                    status = "missing"
            except credentials.CredentialError:
                present, native_present, status = False, False, "storage_unavailable"
            extra_missing = provider == "google" and present and not credentials.get_credential("GOOGLE_CSE_ID")
            checked = previous.get("checked_at")
            if not isinstance(checked, str):
                checked = None
            try:
                stale = not checked or (datetime.now(timezone.utc) - datetime.fromisoformat(checked)).total_seconds() > 86400
            except (ValueError, TypeError):
                checked, stale = None, True
            review = previous.get("next_review")
            if not isinstance(review, str):
                review = None
            try:
                due = bool(review and date.fromisoformat(review) <= date.today())
            except (ValueError, TypeError):
                review, due = None, False
            rows.append({"provider": provider, "name": entry["name"], "key_name": entry["key_name"],
                         "portal": entry["portal"], "required_by": required.get(provider, []),
                         "present": present, "status": status, "checked_at": checked,
                         "storage": "native encrypted vault" if native_present else "legacy/environment" if present else "not saved",
                         "stale": stale, "next_review": review, "review_due": due,
                         "extra_missing": extra_missing, "scope": previous.get("scope") if isinstance(previous.get("scope"), str) and previous.get("scope") in {"account endpoint", "operation test", "authenticated model listing"} else None,
                         "readonly_check": entry["readonly_check"] or provider in MODEL_CHECKS, "search_test": entry["search_test"]})
        return rows

    def check(self, provider, allow_billable=False):
        if provider not in maintenance.CATALOG:
            raise ValueError("Unknown provider")
        billable_attempted = False
        test_result = None
        scope = "account endpoint"
        try:
            credentials.store.get(maintenance.CATALOG[provider]["key_name"])
            if allow_billable and maintenance.CATALOG[provider]["search_test"] and credentials.get_credential(maintenance.CATALOG[provider]["key_name"]):
                billable_attempted = True
                scope = "operation test"
                returned = maintenance.WebSearchTool(provider).run(query="API access check", num_results=1)
                if isinstance(returned,str):
                    test_result = credentials.redact(returned)[:2500]
                    if returned.strip().lower().startswith(("[error]", "search error")):
                        raise maintenance.MaintenanceError("The provider returned a search error. Review its configuration before testing again.")
                response = {"status": "verified", "message": "One search request completed. It may consume credits; this does not verify other operations or remaining balance."}
            elif provider in MODEL_CHECKS:
                scope = "authenticated model listing"
                response = model_access(provider)
            else:
                response = maintenance.verify_access(provider, False)
            status = {"manual": "unsupported"}.get(response["status"], response["status"])
            message = response["message"]
        except credentials.CredentialError:
            status, message = "storage_unavailable", "Native encrypted storage is unavailable."
        except maintenance.MaintenanceError as exc:
            # Only locally constructed MaintenanceError messages are inspected.
            status = next((classify(code) for code in (401, 402, 403, 429) if f"HTTP {code}" in str(exc)), "connection_failed")
            message = str(exc)
        except Exception as exc:
            response = getattr(exc, "response", None)
            code = getattr(response, "status_code", None)
            # The built-in direct adapters construct these HTTP messages locally.
            match = re.search(r"HTTP (401|402|403|429)\b", str(exc)) if isinstance(exc, RuntimeError) else None
            if code is None and match:
                code = int(match.group(1))
            status = classify(code)
            message = {"authentication_rejected": "The provider rejected authentication. Replace or review this key.",
                       "permission_denied": "The provider denied this operation. Review account or resource permissions.",
                       "quota": "The provider requires credits or a billing change.",
                       "rate_limited": "The provider rate-limited this request; retry later."}.get(status, "Provider check failed; retry or inspect the provider portal.")
        stamp = datetime.now(timezone.utc).isoformat()
        self.update(provider, status=status, checked_at=stamp, scope=scope)
        if billable_attempted:
            # Separate opt-in verification ledger; no raw query, response, key, or account identifiers.
            with LOCK:
                data = self.read()
                record = data.get(provider, {})
                history = record.get("verification_usage", [])
                if not isinstance(history, list):
                    history = []
                history.append({"at": stamp, "operation": "search_test", "attempts": 1,
                                "status": status, "actual_cost": None})
                self.update(provider, verification_usage=history[-100:])
        return {"provider": provider, "status": status, "message": message, "checked_at": stamp,
                "scope": scope, "billable_test_requested": allow_billable,
                "test_result":test_result if status == "verified" else None}


def preflight(root, config):
    rows = Inventory(root).rows(config)
    blocking = [row for row in rows if row["required_by"] and
                (row["status"] in {"missing", "storage_unavailable", "authentication_rejected"} or row["extra_missing"])]
    return {"ready": not blocking, "providers": rows, "blocking": [row["provider"] for row in blocking]}
