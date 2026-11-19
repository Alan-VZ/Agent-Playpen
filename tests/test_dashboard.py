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


def test_saved_model_slots_restore_from_defaults(client):
    response = client.post("/api/save-config", json={
        "backend": "lm_studio",
        "model": "qwen2.5-coder-7b-instruct",
        "model_slots": [
            {"backend": "lm_studio", "model": "qwen2.5-coder-7b-instruct", "temperature": 0},
            {"backend": "lm_studio", "model": "qwen3.5-9b-uncensored-hauhaucs-aggressive@q6_k", "temperature": 0.2},
        ],
    })
    assert response.status_code == 200
    defaults = client.get("/api/defaults").json()
    assert len(defaults["model_slots"]) == 2
    assert defaults["model_slots"][1]["temperature"] == 0.2


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

@pytest.mark.parametrize('backend', ['openai', 'anthropic', 'groq', 'together'])
def test_model_catalog_explains_missing_provider_key(client, monkeypatch, backend):
    monkeypatch.setattr(server, 'get_credential', lambda *args: '')
    monkeypatch.setattr(server.model_pricing, 'model_details', lambda *args: [])
    monkeypatch.setattr(server, '_fetch_models', lambda *args: pytest.fail('Must not request models without a key'))
    data = client.get('/api/models', params={'backend': backend}).json()
    assert data['reason'] == 'missing_key'
    assert data['status'] == 'configuration_required'
    assert server.BACKEND_KEY_VAR[backend] in data['message']


def test_azure_catalog_requests_actual_deployment(client, monkeypatch):
    monkeypatch.setattr(server.model_pricing, 'model_details', lambda *args: [])
    data = client.get('/api/models', params={'backend': 'azure_openai'}).json()
    assert data['reason'] == 'manual_deployment'
    assert 'placeholder' in data['message']


def test_local_catalog_connection_failure_has_actionable_message(client, monkeypatch):
    import requests
    monkeypatch.setattr(server.model_pricing, 'model_details', lambda *args: [])
    def unavailable(*args):
        raise requests.ConnectionError('private diagnostic')
    monkeypatch.setattr(server, '_fetch_models', unavailable)
    data = client.get('/api/models', params={'backend': 'ollama'}).json()
    assert data['reason'] == 'local_service_unavailable'
    assert 'ollama serve' in data['message']
    assert 'private diagnostic' not in str(data)


def test_azure_backend_uses_form_endpoint_and_deployment(monkeypatch):
    monkeypatch.setattr(server, 'get_credential', lambda *args: 'test-only')
    create = Mock()
    monkeypatch.setattr(server.BackendFactory, 'create', create)
    server._build_backend(server.AgentConfig(task='test', backend='azure_openai',
        base_url='https://my-resource.openai.azure.com', model='my-deployment'))
    assert create.call_args.kwargs['azure_endpoint'] == 'https://my-resource.openai.azure.com'
    assert create.call_args.kwargs['deployment_name'] == 'my-deployment'


def test_azure_placeholder_is_not_a_resource_address():
    with pytest.raises(ValueError):
        server.azure_endpoint('https://<your-resource>.openai.azure.com')
