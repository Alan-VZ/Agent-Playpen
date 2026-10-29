import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from debugging.dashboard import server


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "ENV_PATH", tmp_path / ".env")
    for key in server.MANAGED_KEYS:
        monkeypatch.delenv(key, raising=False)
    return TestClient(server.app, base_url="http://127.0.0.1", headers={"X-Playpen-Token": server.API_TOKEN}, raise_server_exceptions=False)


@pytest.mark.parametrize("path", ["/", "/setup", "/api/defaults", "/api/keys", "/openapi.json"])
def test_dashboard_startup_routes(client, path):
    assert client.get(path).status_code == 200


def test_setup_guide_shows_key_names_without_saved_values(client):
    from config import credentials
    credentials.store.set("TAVILY_API_KEY", "private-guide-test-credential")
    response = client.get("/setup")
    assert response.status_code == 200
    assert "TAVILY_API_KEY" in response.text
    assert "private-guide-test-credential" not in response.text
    assert "built-in method" not in response.text
    assert "https://app.tavily.com/" in response.text
    assert "2026-10-29" in response.text
    assert "does not cancel billing" in response.text


@pytest.mark.parametrize("payload", [
    {"task": ""}, {"task": "   "}, {"task": "x", "max_iterations": 0},
    {"task": "x", "max_tokens": -1}, {"task": "x", "planner": "invalid"},
])
def test_invalid_run_request_is_client_error(client, payload):
    assert client.post("/api/run", json=payload).status_code in (400, 422)


def test_dashboard_runs_real_agent_loop(client, monkeypatch):
    backend = Mock()
    backend.chat.side_effect = [
        'Thought: calculate\nAction: calculator\nAction Input: {"expression":"6*7"}',
        'Thought: done\nAction: FINISH\nAction Input: 42',
    ]
    monkeypatch.setattr(server, "_build_backend", lambda config: backend)
    response = client.post("/api/run", json={"task": "six times seven", "tools": ["calculator"]})
    assert response.status_code == 200
    assert response.json()["result"] == "42"
    from pathlib import Path
    assert Path(response.json()["trace_path"]).is_file()


def test_backend_failure_is_reported(client, monkeypatch):
    def fail(config):
        raise RuntimeError("Backend unavailable")
    monkeypatch.setattr(server, "_build_backend", fail)
    response = client.post("/api/run", json={"task": "task"})
    assert response.status_code == 500
    assert "execution failed" in response.json()["message"]


def test_config_does_not_save_credentials(client):
    response = client.post("/api/save-config", json={"task": "x", "api_key": "fake-secret", "search_cse_id": "private"})
    assert response.status_code == 200
    saved = json.loads((server.ROOT / "config" / "web_agent_config.json").read_text())
    assert "api_key" not in saved and "search_cse_id" not in saved


@pytest.mark.parametrize("route", ["/api/save-config", "/api/save-env"])
@pytest.mark.parametrize("payload", [[], None, "text"])
def test_save_routes_reject_non_objects(client, route, payload):
    assert client.post(route, json=payload).status_code in (400, 422)


def test_env_merge_preserves_comments_and_removes_key(client):
    server.ENV_PATH.write_text("# settings\nKEEP=yes\nTEST_KEY=old\n")
    server._write_env_file({"TEST_KEY": None, "NEW": "value"})
    assert server._read_env_file() == {"KEEP": "yes", "NEW": "value"}
    assert "# settings" in server.ENV_PATH.read_text()


def test_models_offline_fallback(client, monkeypatch):
    def fail(*args):
        raise RuntimeError("offline")
    monkeypatch.setattr(server, "_fetch_models", fail)
    response = client.get("/api/models?backend=lm_studio")
    assert response.status_code == 200
