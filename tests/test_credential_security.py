import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from config import credentials
from config.credentials import CredentialError
from config.security import azure_endpoint, openrouter_endpoint
from debugging.dashboard import server
from debugging.tracer import Tracer
from tools.packs.filesystem.read_file import ReadFileTool
from tools.packs.filesystem.write_file import WriteFileTool
from backends.openrouter import OpenRouterBackend


@pytest.fixture
def secure_client(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "ENV_PATH", tmp_path / ".env")
    return TestClient(server.app, base_url="http://127.0.0.1", headers={"X-Playpen-Token": server.API_TOKEN})


@pytest.mark.parametrize("name", sorted(credentials.MANAGED_KEYS))
def test_each_provider_can_save_reuse_and_delete(secure_client, name):
    secret = "test-credential-value-123456789"
    response = secure_client.post("/api/save-key", json={"name": name, "value": secret})
    assert response.status_code == 200
    assert secret not in response.text
    assert credentials.get_credential(name) == secret
    assert secret not in server.ENV_PATH.read_text()
    status = secure_client.get("/api/keys")
    assert secret not in status.text and secret[-4:] not in status.text
    assert status.json()[name]["encrypted"]
    assert secure_client.post("/api/save-key", json={"name": name, "value": ""}).status_code == 200
    assert not credentials.get_credential(name)


def test_no_key_retrieval_route(secure_client):
    assert secure_client.get("/api/export-keys").status_code == 404


@pytest.mark.parametrize("route", ["/api/keys", "/api/defaults", "/api/models"])
def test_api_rejects_missing_session_token(route):
    client = TestClient(server.app, base_url="http://127.0.0.1")
    assert client.get(route).status_code == 403


def test_cross_origin_and_dns_rebinding_rejected(secure_client):
    assert secure_client.get("/api/keys", headers={"Origin": "https://attacker.invalid"}).status_code == 403
    assert secure_client.get("/", headers={"Host": "attacker.invalid"}).status_code == 400


def test_key_not_accepted_in_url(secure_client):
    assert secure_client.get("/api/models?api_key=never-put-keys-in-urls").status_code == 400


def test_storage_failure_never_falls_back_to_plaintext(secure_client, monkeypatch):
    monkeypatch.setattr(credentials.store, "set", Mock(side_effect=CredentialError("fail")))
    result = secure_client.post("/api/save-key", json={"name": "OPENROUTER_API_KEY", "value": "test-key-123456"})
    assert result.status_code == 503
    assert not server.ENV_PATH.exists()


def test_keyring_error_is_not_exported():
    backend = Mock(get_password=Mock(side_effect=RuntimeError("sensitive-detail")))
    with pytest.raises(CredentialError) as error:
        credentials.CredentialStore(backend).get("OPENROUTER_API_KEY")
    assert "sensitive-detail" not in str(error.value)


def test_encrypted_key_has_precedence_over_legacy(monkeypatch):
    credentials.store.set("OPENROUTER_API_KEY", "encrypted-test-value")
    monkeypatch.setenv("OPENROUTER_API_KEY", "old-env-value")
    assert credentials.get_credential("OPENROUTER_API_KEY") == "encrypted-test-value"


@pytest.mark.parametrize("bom", ["", "\ufeff"])
def test_legacy_migration_removes_duplicate_plaintext_entries(secure_client, bom):
    server.ENV_PATH.write_text(bom + '# keep\nOPENROUTER_API_KEY="legacy-test-key"\nexport OPENROUTER_API_KEY="legacy-test-key"\nMODEL=example\n', encoding="utf-8")
    result = secure_client.post("/api/migrate-keys")
    assert result.status_code == 200
    assert credentials.store.get("OPENROUTER_API_KEY") == "legacy-test-key"
    content = server.ENV_PATH.read_text()
    assert "legacy-test-key" not in content
    assert "# keep" in content and "MODEL=example" in content


def test_failed_migration_keeps_plaintext_for_recovery(secure_client, monkeypatch):
    server.ENV_PATH.write_text("OPENROUTER_API_KEY=legacy-test-key\n")
    monkeypatch.setattr(credentials.store, "set", Mock(side_effect=CredentialError("fail")))
    assert secure_client.post("/api/migrate-keys").status_code == 503
    assert "legacy-test-key" in server.ENV_PATH.read_text()


def test_exports_ignore_arbitrary_fields_and_redact_known_secrets(secure_client):
    secret = "saved-test-key-123456789"
    credentials.store.set("OPENROUTER_API_KEY", secret)
    response = secure_client.post("/api/save-config", json={
        "api_key": secret, "nested": {"password": secret}, "model": secret,
        "task": secret, "OPENROUTER_API_KEY": secret,
    })
    assert response.status_code == 200
    content = (server.ROOT / "config" / "web_agent_config.json").read_text()
    assert secret not in content
    assert "nested" not in content and "api_key" not in content
    assert secure_client.post("/api/save-env", json={"api_key": secret}).status_code == 200
    assert secret not in server.ENV_PATH.read_text()


def test_trace_and_api_failure_redaction(secure_client, monkeypatch, tmp_path):
    secret = "trace-test-secret-123456789"
    credentials.store.set("OPENROUTER_API_KEY", secret)
    trace = Tracer(str(tmp_path / "traces"))
    trace.on_observe(secret)
    assert secret not in json.dumps(json.loads(__import__('pathlib').Path(trace.save()).read_text()))
    monkeypatch.setattr(server, "_build_backend", Mock(side_effect=RuntimeError(secret)))
    result = secure_client.post("/api/run", json={"task": "test"})
    assert secret not in result.text and "traceback" not in result.text


@pytest.mark.parametrize("path", [".env", ".env.backup", ".ssh/id_rsa", "vault/data", ".aws/credentials"])
@pytest.mark.parametrize("tool", [ReadFileTool, WriteFileTool])
def test_agent_file_tools_cannot_read_or_modify_secret_paths(tmp_path, path, tool):
    with pytest.raises(PermissionError):
        tool([str(tmp_path)]).run(path=str(tmp_path / path), content="x")


def test_dashboard_disallows_arbitrary_python(secure_client):
    assert secure_client.post("/api/run", json={"task": "test", "tools": ["python_repl"]}).status_code == 400


@pytest.mark.parametrize("url", ["http://openrouter.ai/api/v1", "https://attacker.invalid/api/v1", "https://openrouter.ai.attacker.invalid/api/v1"])
def test_openrouter_refuses_key_exfiltration_endpoints(url):
    with pytest.raises(ValueError):
        openrouter_endpoint(url)


def test_openrouter_default_endpoint_with_saved_key(monkeypatch):
    credentials.store.set("OPENROUTER_API_KEY", "router-test-key-123456789")
    client = Mock()
    constructor = Mock(return_value=client)
    monkeypatch.setattr("backends.openrouter.openai.OpenAI", constructor)
    OpenRouterBackend()
    assert constructor.call_args.kwargs["base_url"] == "https://openrouter.ai/api/v1"
    assert constructor.call_args.kwargs["api_key"] == "router-test-key-123456789"


@pytest.mark.parametrize("url", ["http://unit.openai.azure.com", "https://unit.openai.azure.com.attacker.invalid", "https://unit.openai.azure.com@attacker.invalid"])
def test_azure_refuses_key_exfiltration_endpoints(url):
    with pytest.raises(ValueError):
        azure_endpoint(url)


def test_dashboard_headers_and_template_session(secure_client):
    response = secure_client.get("/")
    assert response.status_code == 200
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"
    assert "X-Playpen-Token" in response.text


@pytest.mark.parametrize("suffix", [".py", ".html", ".pth", ".ps1", ".dll", ".toml"])
def test_dashboard_cannot_write_executable_artifacts(tmp_path, suffix):
    writer = WriteFileTool([str(tmp_path)], safe_mode=True)
    with pytest.raises(PermissionError):
        writer.run(path=str(tmp_path / ("payload" + suffix)), content="test")


def test_subprocess_does_not_inherit_provider_keys(monkeypatch):
    from tools.packs.code.python_repl import PythonReplTool
    monkeypatch.setenv("OPENROUTER_API_KEY", "parent-test-key")
    result = PythonReplTool().run(code="import os; print(os.getenv('OPENROUTER_API_KEY', 'absent'))")
    assert result.strip() == "absent"


def test_redaction_happens_before_trace_truncation(tmp_path):
    secret = "prefix-test-" + "x" * 600
    credentials.remember_secret(secret)
    tracer = Tracer(str(tmp_path))
    tracer.on_observe(secret)
    assert tracer.events[-1].content == "[REDACTED]"


@pytest.mark.parametrize("backend_name", ["openrouter", "anthropic", "azure_openai"])
def test_actual_sdk_constructor_without_network(backend_name):
    from backends.backend_factory import BackendFactory
    options = {"api_key": "synthetic-not-a-real-api-key"}
    if backend_name == "azure_openai":
        options.update(azure_endpoint="https://unit.openai.azure.com", deployment_name="test")
    backend = BackendFactory.create(backend_name, **options)
    try:
        assert backend.client is not None
    finally:
        backend.client.close()


def test_settings_cannot_inject_plaintext_credential_assignments(secure_client):
    response = secure_client.post("/api/save-env", json={"model": "model\nOPENROUTER_API_KEY=injected"})
    assert response.status_code == 200
    assert "OPENROUTER_API_KEY" not in server._read_env_file()


def test_validation_does_not_echo_secret_input(secure_client):
    response = secure_client.post("/api/save-key", json={"name": "OPENROUTER_API_KEY", "value": {"secret": "validation-test-key"}})
    assert response.status_code == 422
    assert "validation-test-key" not in response.text
