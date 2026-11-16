"""Uniform provider selection and model-slot execution, without live provider calls."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from debugging.dashboard import model_sources, local_models, readiness, server
from debugging.dashboard.model_sources import _activate as real_activate


@pytest.fixture
def client():
    return TestClient(
        server.app,
        base_url="http://127.0.0.1",
        headers={"X-Playpen-Token": server.API_TOKEN},
    )


@pytest.mark.parametrize("backend", list(server.BackendFactory.REGISTRY))
def test_same_picker_contract_for_every_provider(client, monkeypatch, backend):
    monkeypatch.setattr(
        model_sources,
        "local_state",
        lambda *args: {
            "models": [{"id": "installed", "loaded": True}],
            "active_models": ["instance"],
            "source": "live",
        },
    )
    monkeypatch.setattr(
        server, "api_models", lambda *args: {"models": ["hosted"], "source": "live"}
    )
    get = client.get("/api/model-picker", params={"backend": backend})
    assert get.status_code == 200
    assert isinstance(get.json()["models"][0]["id"], str)
    operation = Mock(
        return_value={
            "model": "verified-instance",
            "loaded": backend in model_sources.LOCAL,
        }
    )
    monkeypatch.setattr(model_sources, "select_model", operation)
    chosen = client.post(
        "/api/model-picker", json={"backend": backend, "model": "installed"}
    )
    assert chosen.status_code == 200 and chosen.json()["model"] == "verified-instance"
    operation.assert_called_once_with(backend, "installed", None)


def test_picker_requires_session_and_refuses_unknown_provider():
    client = TestClient(server.app, base_url="http://127.0.0.1")
    assert client.get("/api/model-picker?backend=lm_studio").status_code == 403
    assert (
        client.post(
            "/api/model-picker", json={"backend": "lm_studio", "model": "x"}
        ).status_code
        == 403
    )
    client.headers["X-Playpen-Token"] = server.API_TOKEN
    assert (
        client.post(
            "/api/model-picker", json={"backend": "unknown", "model": "x"}
        ).status_code
        == 400
    )


def test_local_unavailable_does_not_fabricate_active_model(client, monkeypatch):
    def unavailable(*args):
        raise local_models.ModelManagementError("Start your local server.")

    monkeypatch.setattr(model_sources, "local_state", unavailable)
    data = client.get("/api/model-picker?backend=lm_studio").json()
    assert (
        data["models"] == []
        and data["active_models"] == []
        and data["source"] == "unavailable"
    )


def test_ollama_releases_verifies_then_loads(monkeypatch):
    states = iter(
        [
            {"models": [{"id": "new"}], "active_models": ["old"]},
            {"active_models": []},
            {"active_models": ["new"]},
        ]
    )
    monkeypatch.setattr(model_sources, "local_state", lambda *args: next(states))
    requests = Mock(return_value={})
    monkeypatch.setattr(model_sources, "_ollama_request", requests)
    assert real_activate("ollama", "new")["loaded"]
    calls = requests.call_args_list
    assert [c.args[3] for c in calls] == [
        {"model": "old", "keep_alive": 0, "stream": False},
        {"model": "new", "keep_alive": "10m", "stream": False},
    ]


def test_ollama_unconfirmed_unload_stops_load(monkeypatch):
    monkeypatch.setattr(
        model_sources,
        "local_state",
        lambda *args: {"models": [{"id": "new"}], "active_models": ["old"]},
    )
    requests = Mock(return_value={})
    monkeypatch.setattr(model_sources, "_ollama_request", requests)
    with pytest.raises(local_models.ModelManagementError, match="not released"):
        real_activate("ollama", "new")
    assert requests.call_count == 1 and requests.call_args.args[3]["keep_alive"] == 0


def test_lm_studio_activation_uses_verified_unload_first_manager(monkeypatch):
    manager = Mock(return_value={"model": "exact-instance", "loaded": True})
    monkeypatch.setattr(local_models, "manage", manager)
    assert real_activate("lm_studio", "catalog-model")["model"] == "exact-instance"
    manager.assert_called_once_with(
        "http://localhost:1234/v1", "catalog-model", load=True
    )


@pytest.mark.parametrize(
    "backend", sorted(set(server.BackendFactory.REGISTRY) - model_sources.LOCAL)
)
def test_hosted_selection_does_not_make_inference_request(monkeypatch, backend):
    session = Mock(side_effect=AssertionError("No HTTP request allowed"))
    monkeypatch.setattr(model_sources.requests, "Session", session)
    result = real_activate(backend, "chosen")
    assert (
        result["model"] == "chosen"
        and result["status"] == "selected"
        and not result["loaded"]
    )


def test_engine_lease_protects_whole_run_and_releases_on_error(monkeypatch):
    entered = threading.Event()
    activated = []
    monkeypatch.setattr(
        model_sources,
        "_activate",
        lambda backend, model, url=None: activated.append(model) or {"model": model},
    )

    def later():
        entered.set()
        with model_sources.model_lease(
            "lm_studio", "second", "http://127.0.0.1:1234/v1"
        ):
            return list(activated)

    with ThreadPoolExecutor(1) as pool:
        with pytest.raises(ValueError):
            with model_sources.model_lease(
                "lm_studio", "first", "http://localhost:1234/v1"
            ):
                future = pool.submit(later)
                assert entered.wait(2)
                with pytest.raises(local_models.ModelManagementError, match="in use"):
                    model_sources.select_model("lm_studio", "interrupt")
                assert activated == ["first"] and not future.done()
                # Hosted sources do not wait for a local GPU lease.
                assert (
                    model_sources.select_model("openrouter", "hosted")["model"]
                    == "hosted"
                )
                raise ValueError("release on failure")
        assert future.result(2) == ["first", "hosted", "second"]


def test_expired_or_cancelled_lease_never_loads(monkeypatch):
    operation = Mock()
    monkeypatch.setattr(model_sources, "_activate", operation)
    with pytest.raises(TimeoutError):
        with model_sources.model_lease("lm_studio", "x", deadline=time.monotonic() - 1):
            pytest.fail("Expired run started")
    stop = threading.Event()
    stop.set()
    with pytest.raises(RuntimeError):
        with model_sources.model_lease("lm_studio", "x", stopped=stop):
            pytest.fail("Stopped run started")
    operation.assert_not_called()


def test_ten_mixed_models_receive_same_task_and_keep_order(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "ROOT", tmp_path)
    seen = []

    def execute(config, on_event, cancel_event):
        seen.append((config.backend, config.model, config.task, config.tools))
        on_event({"type": "session", "session_id": config.model})
        return {
            "backend": config.backend,
            "model": config.model,
            "status": "success",
            "result": config.model,
            "warning_count": 0,
        }

    monkeypatch.setattr(server, "_execute_single_run", execute)
    sources = ["lm_studio", "openrouter"] * 5
    config = server.AgentConfig(
        task="Identical task",
        tools=["calculator"],
        model_slots=[{"backend": b, "model": str(i)} for i, b in enumerate(sources)],
    )
    events = []
    result = server._execute_run(config, events.append)
    assert result["status"] == "success" and len(seen) == 10
    assert all(
        task == "Identical task" and tools == ["calculator"]
        for _, _, task, tools in seen
    )
    assert [r["model"] for r in result["results"]] == list(map(str, range(10)))
    assert {e["agent_id"] for e in events} == {
        "group",
        *(f"agent-{i}" for i in range(1, 11)),
    }
    assert (tmp_path / "traces" / (result["session_id"] + ".json")).exists()
    with pytest.raises(ValidationError):
        server.AgentConfig(
            task="x", model_slots=config.model_slots + [config.model_slots[0]]
        )


def test_slot_failure_does_not_discard_other_answers(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "ROOT", tmp_path)

    def execute(config, *args):
        if config.model == "bad":
            raise RuntimeError("Unavailable model")
        return {
            "backend": config.backend,
            "model": config.model,
            "status": "success",
            "result": "answer",
            "warning_count": 0,
        }

    monkeypatch.setattr(server, "_execute_single_run", execute)
    result = server._execute_run(
        server.AgentConfig(
            task="x",
            model_slots=[
                {"backend": "openrouter", "model": m} for m in ["good", "bad"]
            ],
        )
    )
    assert result["status"] == "incomplete" and [
        r["status"] for r in result["results"]
    ] == ["success", "error"]
    assert "answer" in result["result"] and "Unavailable model" in result["result"]


def test_readiness_includes_all_model_slots_and_shared_search():
    required = readiness.requirements(
        {
            "model_slots": [{"backend": "openrouter"}, {"backend": "openai"}],
            "tools": ["web_search"],
            "search_provider": "brave",
        }
    )
    assert set(required) == {"openrouter", "openai", "brave"}
    assert required["brave"] == ["agent-1: web_search", "agent-2: web_search"]


def test_engine_lease_is_shared_with_worker_process_and_released_on_exit(monkeypatch, tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    monkeypatch.setattr(model_sources, "_LOCK_DIRECTORY", tmp_path / "leases")
    monkeypatch.setattr(model_sources, "_LOCKS", {})
    marker = tmp_path / "worker-ready"
    script = """
import sys
from pathlib import Path
from debugging.dashboard import model_sources
model_sources._LOCK_DIRECTORY = Path(sys.argv[1])
lock = model_sources.engine_lock('lm_studio', 'http://localhost:19184/v1')
assert lock.acquire(blocking=False)
Path(sys.argv[2]).write_text('ready')
input()
"""
    process = subprocess.Popen(
        [sys.executable, "-c", script, str(tmp_path / "leases"), str(marker)],
        cwd=Path(__file__).resolve().parents[1], stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    lock = model_sources.engine_lock("lm_studio", "http://127.0.0.1:19184/v1")
    try:
        deadline = time.monotonic() + 10
        while not marker.exists() and time.monotonic() < deadline and process.poll() is None:
            time.sleep(.02)
        assert marker.exists(), "Worker did not acquire its model lease"
        assert not lock.acquire(blocking=False)
        process.terminate()
        process.wait(5)
        assert lock.acquire(timeout=2), "OS did not release terminated worker's lease"
        lock.release()
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(5)
        process.stdin.close()
        process.stderr.close()
