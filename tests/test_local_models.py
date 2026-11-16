import json
from unittest.mock import Mock

import pytest
import requests
from fastapi.testclient import TestClient

from debugging.dashboard import local_models, server
from benchmarks.tasks import baseline_setup
from benchmarks.runner import ExperimentConfig, Member, prepare_baseline_configs


def response(payload, status=200):
    result = Mock(status_code=status)
    result.iter_content.return_value = [json.dumps(payload).encode()]
    result.__enter__ = Mock(return_value=result)
    result.__exit__ = Mock(return_value=False)
    return result


def session_with(monkeypatch, *responses):
    session = Mock()
    session.request.side_effect = list(responses)
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(local_models.requests, "Session", Mock(return_value=session))
    return session


def catalog(loaded=False, kind="llm"):
    return {"models": [{"key": "chosen-model", "type": kind,
                        "loaded_instances": [{"id": "chosen-instance"}] if loaded else []},
                       {"key": "other-model", "type": "llm", "loaded_instances": [{"id":"other-instance"}]}]}


def test_status_does_not_load_or_unload(monkeypatch):
    session = session_with(monkeypatch, response(catalog()))
    result = local_models.manage("http://localhost:1234/v1", "chosen-model")
    assert result["status"] == "not_loaded"
    assert session.request.call_count == 1
    assert session.request.call_args.args == ("GET", "http://localhost:1234/api/v1/models")
    assert session.trust_env is False
    assert session.request.call_args.kwargs["allow_redirects"] is False


def test_loading_verifies_exact_instance_and_preserves_other_models(monkeypatch):
    session = session_with(monkeypatch, response(catalog()),
                           response({"status":"loaded","instance_id":"chosen-instance"}), response(catalog(True)))
    result = local_models.manage("http://127.0.0.1:1234/v1", "chosen-model", load=True)
    assert result["loaded"] and result["model"] == "chosen-instance"
    assert [call.args[0] for call in session.request.call_args_list] == ["GET", "POST", "GET"]
    assert session.request.call_args_list[1].kwargs["json"] == {"model": "chosen-model"}
    assert session.request.call_args_list[1].args[1].endswith("/api/v1/models/load")
    assert not any("unload" in call.args[1] or "download" in call.args[1] for call in session.request.call_args_list)


def test_already_loaded_does_not_create_duplicate_instance(monkeypatch):
    session = session_with(monkeypatch, response(catalog(True)))
    result = local_models.manage("http://localhost:1234/v1", "chosen-instance", load=True)
    assert result["model"] == "chosen-instance"
    assert session.request.call_count == 1


@pytest.mark.parametrize("url", ["https://localhost:1234/v1", "http://example.com:1234/v1", "http://localhost:1234/v1?api_key=secret", "http://user:secret@localhost:1234/v1", "http://127.0.0.1:1234/other"])
def test_management_rejects_nonlocal_or_credential_bearing_urls(url):
    with pytest.raises(local_models.ModelManagementError):
        local_models.server_root(url)


@pytest.mark.parametrize("model,kind", [("local-model","llm"),("missing","llm"),("chosen-model","embedding")])
def test_placeholder_unknown_and_embedding_models_cannot_be_loaded(monkeypatch, model, kind):
    session = session_with(monkeypatch, response(catalog(kind=kind)))
    with pytest.raises(local_models.ModelManagementError):
        local_models.manage("http://localhost:1234/v1", model, load=True)
    assert session.request.call_count == 1


def test_load_response_alone_does_not_prove_loaded_state(monkeypatch):
    session_with(monkeypatch, response(catalog()), response({"status":"loaded","instance_id":"chosen-instance"}), response(catalog()))
    with pytest.raises(local_models.ModelManagementError, match="not listed as loaded"):
        local_models.manage("http://localhost:1234/v1", "chosen-model", load=True)


def test_timeout_has_no_automatic_load_retry(monkeypatch):
    session = session_with(monkeypatch, response(catalog()), requests.Timeout())
    with pytest.raises(local_models.ModelManagementError, match="No automatic load retry"):
        local_models.manage("http://localhost:1234/v1", "chosen-model", load=True)
    assert session.request.call_count == 2


@pytest.mark.parametrize("status", [401, 403, 404, 500])
def test_native_api_errors_are_actionable_without_raw_provider_data(monkeypatch, status):
    session_with(monkeypatch, response({"private":"must not appear"}, status))
    with pytest.raises(local_models.ModelManagementError) as exc:
        local_models.manage("http://localhost:1234/v1", "chosen-model")
    assert "must not appear" not in str(exc.value)


def test_management_routes_require_local_session(monkeypatch):
    client = TestClient(server.app, base_url="http://127.0.0.1")
    for route in ["/api/local-models/status", "/api/local-models/load"]:
        assert client.post(route, json={"model":"chosen-model"}).status_code == 403
    client.headers["X-Playpen-Token"] = server.API_TOKEN
    operation = Mock(return_value={"status":"loaded","model":"chosen-instance","loaded":True})
    monkeypatch.setattr(local_models, "manage", operation)
    assert client.post("/api/local-models/load", json={"model":"chosen-model"}).status_code == 200
    assert operation.call_args.kwargs == {"load":True}


def test_baseline_recommendations_depend_on_selected_tasks_and_are_enforced_without_mutation():
    assert baseline_setup(["B02"]) == {"planner":"react","tools":["read_fixture"]}
    assert baseline_setup(["B01"])["tools"] == ["read_fixture","calculator"]
    assert baseline_setup(["B03"])["tools"] == ["read_fixture","write_artifact"]
    original = ExperimentConfig(agents=[Member(planner="cot", tools=[]), Member(planner="tree", tools=[])])
    prepared = prepare_baseline_configs([original], ["B01","B03"])[0]
    assert all(m.planner == "react" and set(m.tools) == {"read_fixture","calculator","write_artifact"} for m in prepared.agents)
    assert original.agents[0].planner == "cot" and original.agents[0].tools == []
    original.auto_baseline_setup = False
    manual = prepare_baseline_configs([original], ["B01"])[0]
    assert manual.agents[0].planner == "cot" and manual.agents[0].tools == []


def test_placeholder_is_rejected_before_starting_an_experiment(tmp_path):
    client = TestClient(server.app, base_url="http://127.0.0.1", headers={"X-Playpen-Token":server.API_TOKEN})
    response = client.post("/api/benchmarks", json={"configs":[{}],"tasks":["B01"],"repeats":1})
    assert response.status_code == 400
    assert "placeholder" in response.json()["detail"]
    from benchmarks.runner import run_experiment
    with pytest.raises(ValueError, match="explicit model"):
        run_experiment([ExperimentConfig()], tmp_path / "invalid", repeats=1)
    assert not (tmp_path / "invalid").exists()
