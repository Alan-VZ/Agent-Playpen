import json
import threading
from types import SimpleNamespace

import httpx
import openai
import pytest

from backends.lm_studio import LMStudioBackend
from benchmarks import runner
from benchmarks.diagnostics import fixture, score, expected
from benchmarks.evidence import install_transport_capture, replay_response
from config.credentials import remember_secret
from planner.react_planner import ReActPlanner
from core.context import AgentContext
from planner.base_planner import Step


def test_transport_capture_redacts_and_replays_without_execution():
    entries = []
    secret = "synthetic-secret-not-a-real-key"
    remember_secret(secret)
    payload = {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "x",
                            "type": "function",
                            "function": {
                                "name": "calculator",
                                "arguments": '{"expression":"6*7"}',
                            },
                        }
                    ],
                },
            }
        ]
    }
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    client = httpx.Client(transport=transport)
    backend = SimpleNamespace(client=SimpleNamespace(_client=client))
    assert install_transport_capture(
        backend, lambda kind, data: entries.append({"kind": kind, **data})
    )
    client.post(
        "https://example.org/v1/chat/completions",
        headers={"Authorization": "Bearer " + secret},
        json={"messages": [{"role": "user", "content": secret}], "temperature": 0},
    )
    text = json.dumps(entries)
    assert secret not in text and "Authorization" not in text
    assert entries[0]["payload"]["temperature"] == 0
    assert replay_response(entries[1]["payload"], ["calculator"])["arguments"] == {
        "expression": "6*7"
    }
    client.close()


def test_native_prompt_no_duplicate_text_protocol_and_text_fallback_observation():
    backend = object.__new__(LMStudioBackend)
    backend.client = openai.OpenAI(
        api_key="synthetic", base_url="http://127.0.0.1:9/v1"
    )
    backend.tool_calling_mode = "auto"
    backend.reset_tool_session()
    planner = ReActPlanner(backend)
    planner.available_tool_names = {"calculator"}
    prompt = planner.format_thought_prompt(
        Step(index=0, description="test"), AgentContext(session_id="x", task="test")
    )
    assert "Thought:" not in prompt[0]["content"]
    backend.accept_tool_result("42")
    assert backend._native_history[-1] == {
        "role": "user",
        "content": "Runtime observation/feedback: 42",
    }
    backend.client.close()


def fake_attempt(config, task, seed, **kwargs):
    return {
        "id": task + config.name,
        "task": task,
        "seed": seed,
        "status": "completed",
        "elapsed_seconds": 1,
        "evaluation": {"passed": True, "score": 100},
        "agents": [],
        "tool_events": [],
        "usage": {
            "actual_tokens": 1,
            "estimated_reserved_usd": None,
            "reserved_tokens": 1,
            "tool_requests": 0,
        },
    }


def test_configuration_first_subsets_and_resume(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "isolated_attempt", fake_attempt)
    configs = [
        runner.ExperimentConfig(
            name="a", agents=[runner.Member(model="one")], selected_tasks=["B01", "B04"]
        ),
        runner.ExperimentConfig(
            name="b", agents=[runner.Member(model="two")], selected_tasks=["B02"]
        ),
    ]
    record = runner.run_experiment(configs, tmp_path, repeats=1, tasks=["B01"])
    assert [(r["config_index"], r["task"]) for r in record["attempts"]] == [
        (0, "B01"),
        (0, "B04"),
        (1, "B02"),
    ]
    assert record["scheduled"] == 3
    rows = runner.summaries(record)
    assert rows[0]["tasks"]["B02"]["selected"] is False and rows[1]["scheduled"] == 1
    resumed = runner.run_experiment(
        configs, tmp_path, repeats=1, tasks=["B01"], resume=True
    )
    assert len(resumed["attempts"]) == 3
    with pytest.raises(ValueError, match="Resume"):
        runner.run_experiment(
            configs,
            tmp_path,
            repeats=1,
            tasks=["B01"],
            resume=True,
            scheduling="task_first",
        )


def test_schedule_cancellation_before_work(monkeypatch, tmp_path):
    monkeypatch.setattr(
        runner, "isolated_attempt", lambda *a, **k: pytest.fail("cancelled work ran")
    )
    stop = threading.Event()
    stop.set()
    record = runner.run_experiment(
        [runner.ExperimentConfig(agents=[runner.Member(model="one")])],
        tmp_path,
        repeats=1,
        stopped=stop,
        tasks=["B01"],
    )
    assert record["status"] == "cancelled" and record["attempts"] == []


@pytest.mark.parametrize("task", ["D01", "D02", "D03", "D04", "D05", "D06"])
def test_diagnostic_scorers_need_evidence(task):
    data = fixture(task, 1)
    answer = expected(task, 1)
    if task == "D05":
        answer = {**answer, "quote": data["documents"]["notice"]}
    result = score(data, json.dumps(answer), [])
    assert result["passed"] is (task == "D01")


def test_b02_pre_final_requires_observed_sources_and_quotes():
    from benchmarks.tasks import (
        fixture as baseline_fixture,
        expected as baseline_expected,
    )

    data = baseline_fixture("B02", 1)
    answer = baseline_expected("B02", 1)
    assert "required sources" in runner.validate_final_report(
        "B02", json.dumps(answer), data["documents"], {"notice"}
    )
    assert (
        runner.validate_final_report(
            "B02", json.dumps(answer), data["documents"], set(data["documents"])
        )
        is None
    )
    answer["citations"]["loan_days"]["quote"] = "fabricated quote"
    assert "quote exact" in runner.validate_final_report(
        "B02", json.dumps(answer), data["documents"], set(data["documents"])
    )


def test_diagnostic_resume_fingerprints_and_pacing_cancel(monkeypatch, tmp_path):
    from benchmarks import diagnostics

    stop = threading.Event()
    seen = []

    def finish_one(config, task, seed, **kwargs):
        seen.append(task)
        stop.set()
        return fake_attempt(config, task, seed)

    monkeypatch.setattr(runner, "isolated_attempt", finish_one)
    config = runner.ExperimentConfig(
        name="paced", agents=[runner.Member(model="one")], model_min_interval_seconds=60
    )
    record = diagnostics.run([config], tmp_path, stop)
    assert record["status"] == "cancelled" and seen == ["D01"]
    assert record["source_hashes"] and record["fixture_hashes"]

    def finish_rest(config, task, seed, **kwargs):
        return fake_attempt(config, task, seed)

    monkeypatch.setattr(runner, "isolated_attempt", finish_rest)
    # A changed fixture must never be silently pooled into the saved study.
    original = diagnostics.fixture
    monkeypatch.setattr(
        diagnostics,
        "fixture",
        lambda task, seed: {**original(task, seed), "prompt": "changed"},
    )
    with pytest.raises(ValueError, match="resume"):
        diagnostics.run([config], tmp_path, resume=True)


def test_evidence_call_index_survives_other_agent_reservation(monkeypatch):
    from benchmarks import evidence

    callbacks = []
    monkeypatch.setattr(
        evidence,
        "install_transport_capture",
        lambda backend, emit: callbacks.append(emit) or True,
    )
    budget = runner.Budget(runner.ExperimentConfig())

    class Backend:
        tool_calling_mode = "prompt"
        last_usage = {"total_tokens": 1}

        def chat(self, messages):
            budget.reserve_model([{"role": "user", "content": "other"}], "agent-2")
            callbacks[0]("transport_request", {"payload": {"messages": messages}})
            return "done"

    metered = runner.MeteredBackend(Backend(), budget, "agent-1")
    assert metered.chat([{"role": "user", "content": "own"}]) == "done"
    entry = next(e for e in budget.interactions if e["kind"] == "transport_request")
    assert entry["call_index"] == 0 and len(budget.model_calls) == 2


def test_in_case_pacing_is_visible():
    import time

    events = []
    budget = runner.Budget(
        runner.ExperimentConfig(model_min_interval_seconds=0.02), on_event=events.append
    )
    budget.last_request_at = time.monotonic()

    class Backend:
        last_usage = {"total_tokens": 1}

        def chat(self, messages):
            return "done"

    assert (
        runner.MeteredBackend(Backend(), budget, "agent-1").chat(
            [{"role": "user", "content": "test"}]
        )
        == "done"
    )
    assert any(e["type"] == "provider_pacing" for e in events)


def test_groq_single_action_policy_is_explicit_on_wire():
    from backends.groq_backend import GroqBackend

    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "fixture",
                "object": "chat.completion",
                "created": 1,
                "model": "fixture",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": '{"result":63}'},
                    }
                ],
            },
        )

    backend = object.__new__(GroqBackend)
    backend.client = openai.OpenAI(
        api_key="synthetic",
        base_url="http://127.0.0.1:9/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    backend.model = "fixture"
    backend.temperature = 0
    backend.max_tokens = 512
    backend.tool_calling_mode = "auto"
    try:
        backend.chat_with_tools(
            [{"role": "user", "content": "calculate"}],
            [
                {
                    "type": "function",
                    "function": {
                        "name": "calculator",
                        "parameters": {"type": "object"},
                    },
                }
            ],
        )
        assert requests[0]["parallel_tool_calls"] is False
    finally:
        backend.client.close()
