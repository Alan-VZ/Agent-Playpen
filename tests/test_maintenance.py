import hashlib
import base64
import json
import logging
from unittest.mock import Mock
from urllib.parse import urlsplit, parse_qs

import pytest
import requests
from fastapi.testclient import TestClient

from config import credentials
from debugging.dashboard import maintenance, server


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "ENV_PATH", tmp_path / ".env")
    monkeypatch.setattr(maintenance, "connections", maintenance.OpenRouterConnections())
    client = TestClient(server.app, base_url="http://127.0.0.1", headers={"X-Playpen-Token": server.API_TOKEN})
    client.get("/maintenance")
    return client


def start(client, replace=False):
    response = client.post("/api/maintenance/openrouter/start", json={"replace_existing": replace})
    assert response.status_code == 200, response.text
    url = urlsplit(response.json()["authorization_url"])
    return parse_qs(url.query)


def test_maintenance_page_and_status_do_not_show_saved_keys(client):
    credentials.store.set("TAVILY_API_KEY", "private-test-key-value")
    response = client.get("/maintenance")
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    assert "private-test-key-value" not in response.text
    status = client.get("/api/maintenance")
    assert status.json()["keys"]["TAVILY_API_KEY"]["encrypted"]
    assert "private-test-key-value" not in status.text


@pytest.mark.parametrize("path", ["/api/maintenance", "/api/maintenance/check", "/api/maintenance/review", "/api/maintenance/openrouter/start", "/api/maintenance/openrouter/finish"])
def test_maintenance_requires_local_session(path):
    client = TestClient(server.app, base_url="http://127.0.0.1")
    response = client.get(path) if path == "/api/maintenance" else client.post(path, json={})
    assert response.status_code == 403


@pytest.mark.parametrize("provider,container,usage", [("openrouter", "data", {"usage": 2, "limit_remaining": 8}), ("tavily", "key", {"usage": 5, "limit": 1000}), ("firecrawl", "data", {"remainingCredits": 500})])
def test_readonly_verification_filters_raw_account_data(client, monkeypatch, provider, container, usage):
    secret = "private-credential-value"
    credentials.store.set(maintenance.CATALOG[provider]["key_name"], secret)
    data = {container: {**usage, "label": "private-key-prefix", "email": "private@example.org", "other": secret}}
    request = Mock(return_value=Mock(status_code=200, json=Mock(return_value=data)))
    monkeypatch.setattr(requests, "request", request)
    result = client.post("/api/maintenance/check", json={"provider": provider}).json()
    assert result["status"] == "verified" and result["usage"] == usage
    assert request.call_args.args[0] == "GET"
    assert request.call_args.kwargs["allow_redirects"] is False
    assert request.call_args.kwargs["headers"] == {"Authorization": f"Bearer {secret}"}
    assert "private" not in json.dumps(result)
    history = client.get("/api/maintenance").json()["history"]
    assert history["providers"][provider]["check_status"] == "verified"
    assert "private" not in json.dumps(history)
    assert "usage" not in (server.ROOT / "traces/maintenance.json").read_text()


def test_search_verification_requires_billable_opt_in(client, monkeypatch):
    credentials.store.set("SERPER_API_KEY", "test-search-key")
    request = Mock(return_value=Mock(status_code=200, json=Mock(return_value={"organic": []})))
    monkeypatch.setattr(requests, "request", request)
    assert client.post("/api/maintenance/check", json={"provider": "serper"}).json()["status"] == "manual"
    request.assert_not_called()
    result = client.post("/api/maintenance/check", json={"provider": "serper", "allow_billable": True})
    assert result.json()["status"] == "verified"
    assert request.call_count == 1
    assert request.call_args.kwargs["json"]["num"] == 1


def test_missing_key_never_calls_provider(client, monkeypatch):
    request = Mock()
    monkeypatch.setattr(requests, "request", request)
    assert client.post("/api/maintenance/check", json={"provider": "tavily"}).json()["status"] == "missing"
    request.assert_not_called()


@pytest.mark.parametrize("status", [302, 401, 402, 403, 429, 500])
def test_failed_checks_are_safe_and_not_marked_verified(client, monkeypatch, status):
    credentials.store.set("TAVILY_API_KEY", "private-key")
    monkeypatch.setattr(requests, "request", Mock(return_value=Mock(status_code=status, text="private-response")))
    result = client.post("/api/maintenance/check", json={"provider": "tavily"})
    assert result.json()["status"] == "failed"
    assert str(status) in result.json()["message"]
    assert "private" not in result.text


def test_review_checklist_is_distinct_from_access_verification(client):
    result = client.post("/api/maintenance/review", json={"provider": "exa", "portal_ready": True, "billing_reviewed": True, "next_review": "2026-11-29", "password": "ignored-private-value"})
    assert result.status_code == 200
    record = client.get("/api/maintenance").json()["history"]["providers"]["exa"]
    assert record["portal_ready"] and "check_status" not in record
    assert record["next_review"] == "2026-11-29"
    assert "ignored-private-value" not in (server.ROOT / "traces/maintenance.json").read_text()


def test_review_does_not_claim_save_when_metadata_storage_fails(client, monkeypatch):
    monkeypatch.setattr(maintenance.MaintenanceHistory, "update", Mock(side_effect=OSError("private-detail")))
    response = client.post("/api/maintenance/review", json={"provider": "exa"})
    assert response.status_code == 503 and "private-detail" not in response.text


def test_history_does_not_export_extra_or_malformed_fields(client):
    path = server.ROOT / "traces/maintenance.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({"providers": {"tavily": {"api_key": "unknown-private-value", "check_status": [], "next_review": "private-date"}},
                                "events": [{"provider": [], "event": "private-event"}], "password": "private-password"}))
    response = client.get("/api/maintenance")
    assert response.status_code == 200
    assert "private" not in response.text
    assert response.json()["history"] == {"providers": {"tavily": {}}, "events": []}


def test_empty_usage_response_is_not_verified(client, monkeypatch):
    credentials.store.set("TAVILY_API_KEY", "test-key")
    monkeypatch.setattr(requests, "request", Mock(return_value=Mock(status_code=200, json=Mock(return_value={"key": {}}))))
    response = client.post("/api/maintenance/check", json={"provider": "tavily"})
    assert response.json()["status"] == "failed"


def test_saving_or_clearing_key_invalidates_last_check(client):
    maintenance.MaintenanceHistory(server.ROOT).update("tavily", "access_checked", status="verified")
    for value in ("private-new-key", ""):
        assert client.post("/api/save-key", json={"name": "TAVILY_API_KEY", "value": value}).status_code == 200
        record = client.get("/api/maintenance").json()["history"]["providers"]["tavily"]
        assert "last_check" not in record
    assert "private-new-key" not in (server.ROOT / "traces/maintenance.json").read_text()


def test_legacy_cleanup_failure_does_not_leave_stale_verification(client, monkeypatch):
    maintenance.MaintenanceHistory(server.ROOT).update("tavily", "access_checked", status="verified")
    monkeypatch.setattr(server, "_write_env_file", Mock(side_effect=OSError("private-internal-detail")))
    response = client.post("/api/save-key", json={"name": "TAVILY_API_KEY", "value": "private-new-key"})
    assert response.status_code == 503
    assert "vault was updated" in response.json()["message"]
    assert "private" not in response.text
    assert credentials.store.get("TAVILY_API_KEY") == "private-new-key"
    assert "last_check" not in client.get("/api/maintenance").json()["history"]["providers"]["tavily"]


def test_oauth_uses_s256_and_keeps_key_out_of_browser(client, monkeypatch):
    params = start(client)
    state = params["state"][0]
    pending = maintenance.connections.flows[state]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(pending["verifier"].encode()).digest()).rstrip(b"=").decode()
    assert params["code_challenge"] == [challenge]
    assert params["code_challenge_method"] == ["S256"]
    assert params["callback_url"] == ["http://127.0.0.1/maintenance/oauth-callback"]
    request = Mock(return_value=Mock(status_code=200, json=Mock(return_value={"key": "private-new-openrouter-key"})))
    monkeypatch.setattr(requests, "request", request)
    result = client.post("/api/maintenance/openrouter/finish", json={"state": state, "code": "private-code"})
    assert result.status_code == 200
    assert credentials.store.get("OPENROUTER_API_KEY") == "private-new-openrouter-key"
    assert "private" not in result.text
    assert request.call_args.args == ("POST", "https://openrouter.ai/api/v1/auth/keys")
    assert request.call_args.kwargs["allow_redirects"] is False
    assert request.call_args.kwargs["json"]["code_verifier"] == pending["verifier"]
    for path in (server.ENV_PATH, server.ROOT / "traces/maintenance.json"):
        assert "private" not in path.read_text()
    replay = client.post("/api/maintenance/openrouter/finish", json={"state": state, "code": "private-code"})
    assert replay.status_code == 400 and request.call_count == 1


def test_oauth_requires_explicit_replacement(client):
    credentials.store.set("OPENROUTER_API_KEY", "existing-key")
    assert client.post("/api/maintenance/openrouter/start", json={}).status_code == 409
    assert start(client, replace=True)["state"]


def test_oauth_rejects_different_browser_without_burning_flow(client, monkeypatch):
    state = start(client)["state"][0]
    other = TestClient(server.app, base_url="http://127.0.0.1", headers={"X-Playpen-Token": server.API_TOKEN})
    other.get("/maintenance")
    request = Mock()
    monkeypatch.setattr(requests, "request", request)
    assert other.post("/api/maintenance/openrouter/finish", json={"state": state, "code": "code"}).status_code == 400
    assert state in maintenance.connections.flows
    request.assert_not_called()


@pytest.mark.parametrize("change", ["expire", "saved_key_changed"])
def test_oauth_rejects_stale_flow_before_exchange(client, monkeypatch, change):
    state = start(client)["state"][0]
    if change == "expire":
        maintenance.connections.flows[state]["expires"] = 0
    else:
        credentials.store.set("OPENROUTER_API_KEY", "changed-in-another-window")
    request = Mock()
    monkeypatch.setattr(requests, "request", request)
    assert client.post("/api/maintenance/openrouter/finish", json={"state": state, "code": "code"}).status_code == 400
    request.assert_not_called()


def test_oauth_fails_closed_when_vault_is_unavailable(client, monkeypatch):
    monkeypatch.setattr(credentials.store, "get", Mock(side_effect=credentials.CredentialError("unavailable")))
    response = client.post("/api/maintenance/openrouter/start", json={})
    assert response.status_code == 503
    assert not maintenance.connections.flows


def test_oauth_does_not_export_new_key_when_save_fails(client, monkeypatch):
    state = start(client)["state"][0]
    monkeypatch.setattr(requests, "request", Mock(return_value=Mock(status_code=200, json=Mock(return_value={"key": "private-issued-key"}))))
    monkeypatch.setattr(credentials.store, "set", Mock(side_effect=credentials.CredentialError("private-internal-detail")))
    response = client.post("/api/maintenance/openrouter/finish", json={"state": state, "code": "private-code"})
    assert response.status_code == 503 and "private" not in response.text
    assert "revoke" in response.json()["message"]


def test_callback_does_not_reflect_codes_and_access_log_filters_query(client):
    response = client.get("/maintenance/oauth-callback?code=private-code&state=private-state")
    assert "private-code" not in response.text and "private-state" not in response.text
    assert "history.replaceState" in response.text
    record = logging.LogRecord("uvicorn.access", 20, "", 0, '%s - "%s %s HTTP/%s" %d',
                               ("127.0.0.1", "GET", "/maintenance/oauth-callback?code=private-code", "1.1", 200), None)
    maintenance.CallbackAccessFilter().filter(record)
    assert "private-code" not in record.getMessage()


@pytest.mark.parametrize("provider", ["unknown", "auto", "ddgs"])
def test_maintenance_rejects_unknown_or_keyless_provider(client, provider):
    assert client.post("/api/maintenance/check", json={"provider": provider}).status_code == 400
