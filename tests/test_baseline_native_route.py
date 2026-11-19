"""Regression checks for baseline native forwarding and timeout evidence."""

import json
import queue
import threading
from types import SimpleNamespace

import httpx
import openai

from backends.openai_backend import OpenAIBackend
from benchmarks import runner
from core.agent import Agent
from debugging.tracer import Tracer
from memory.memory_manager import MemoryManager
from planner.react_planner import ReActPlanner
from tools.packs.utils.calculator_tool import CalculatorTool
from tools.tool_registry import ToolRegistry


def test_metered_backend_forwards_native_calls_results_and_usage(tmp_path):
    calls = []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        assert body["tools"][0]["function"]["name"] == "calculator"
        if len(calls) == 1:
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "native1",
                        "type": "function",
                        "function": {
                            "name": "calculator",
                            "arguments": '{"expression":"6*7"}',
                        },
                    }
                ],
            }
        else:
            assert any(
                m.get("role") == "tool"
                and m.get("tool_call_id") == "native1"
                and m.get("content") == "42"
                for m in body["messages"]
            )
            message = {"role": "assistant", "content": "42"}
        return httpx.Response(
            200,
            json={
                "id": "fixture",
                "object": "chat.completion",
                "created": 1,
                "model": "fixture",
                "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            },
        )

    backend = object.__new__(OpenAIBackend)
    backend.client = openai.OpenAI(
        api_key="synthetic",
        base_url="http://127.0.0.1:9/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    backend.model = "fixture"
    backend.temperature = 0
    backend.max_tokens = 128
    backend.tool_calling_mode = "native"
    budget = runner.Budget(runner.ExperimentConfig())
    metered = runner.MeteredBackend(backend, budget, "agent-1")
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    try:
        agent = Agent(
            metered,
            ReActPlanner(metered),
            registry,
            MemoryManager({"enabled_stores": []}),
            Tracer(str(tmp_path)),
            max_iterations=3,
        )
        assert agent.run("Calculate 6*7") == "42"
        assert len(budget.model_calls) == 2
        assert sum(c["actual_tokens"] for c in budget.model_calls) == 30
        assert all(c["tool_calling_mode"] == "native" for c in budget.model_calls)
        assert all(c["request_profile"]["settlement_mode"] == "autonomous" for c in budget.model_calls)
        assert all(c["request_profile"]["temperature"]["effective"] == "unknown" for c in budget.model_calls)
    finally:
        backend.client.close()


def test_forced_worker_timeout_retains_partial_events(monkeypatch):
    activity = [
        {"type": "model_request", "content": "Step 1: waiting"},
        {"type": "tool_succeeded", "content": "read_fixture succeeded"},
        {"type": "model_request", "content": "Step 2: waiting"},
    ]

    class FakeQueue:
        def __init__(self, items=()):
            self.items = list(items)

        def get(self, **kwargs):
            raise queue.Empty

        def get_nowait(self):
            if not self.items:
                raise queue.Empty
            return self.items.pop(0)

        def close(self):
            pass

    class Process:
        alive = True

        def start(self):
            pass

        def is_alive(self):
            return self.alive

        def join(self, **kwargs):
            pass

        def terminate(self):
            self.alive = False

        def kill(self):
            self.alive = False

    queues = iter([FakeQueue(), FakeQueue(activity)])
    context = SimpleNamespace(
        Queue=lambda size: next(queues),
        Event=threading.Event,
        Process=lambda **kwargs: Process(),
    )
    monkeypatch.setattr(runner.multiprocessing, "get_context", lambda mode: context)
    clock = iter(n * 0.25 for n in range(1000))
    monkeypatch.setattr(runner.time, "monotonic", lambda: next(clock))
    result = runner.isolated_attempt(
        runner.ExperimentConfig(timeout_seconds=1), "B01", 1
    )
    assert result["status"] == "timeout" and result["partial_events"] == activity
    assert (
        result["usage"]["usage_incomplete"] and result["usage"]["tool_requests"] is None
    )
    assert result["evaluation"]["passed"] is False


def test_missing_member_call_mode_preserves_legacy_prompt():
    assert runner.Member().tool_calling_mode == "prompt"
    assert runner.Member(tool_calling_mode="auto").tool_calling_mode == "auto"


def test_incomplete_legacy_usage_is_unknown_not_zero():
    record = {
        "configs": [runner.ExperimentConfig().model_dump()],
        "repeats": 1,
        "selected_tasks": ["B01"],
        "attempts": [
            {
                "task": "B01",
                "config_index": 0,
                "elapsed_seconds": 190,
                "evaluation": {"passed": False, "score": 0},
                "usage": {
                    "estimated_reserved_usd": None,
                    "actual_tokens": None,
                    "reserved_tokens": 0,
                    "tool_requests": 0,
                    "usage_incomplete": True,
                },
                "tool_events": [],
            }
        ],
    }
    summary = runner.summaries(record)[0]
    assert summary["tool_requests"] is None and summary["reserved_tokens"] is None
    assert record["attempts"][0]["usage"]["tool_requests"] == 0


def test_saved_activity_sidecar_survives_server_job_loss(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from debugging.dashboard import server, experiments

    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(experiments, "JOBS", {})
    job_id = "a" * 32
    folder = tmp_path / "benchmark-results" / job_id
    folder.mkdir(parents=True)
    record = {
        "configs": [runner.ExperimentConfig().model_dump()],
        "status": "completed",
        "attempts": [],
        "scheduled": 1,
        "repeats": 1,
        "selected_tasks": ["B01"],
    }
    (folder / "experiment.json").write_text(json.dumps(record), encoding="utf-8")
    events = [
        {"type": "model_request", "content": "Step 4: waiting for the model response."}
    ]
    (folder / "activity.json").write_text(
        json.dumps({"events": events}), encoding="utf-8"
    )
    client = TestClient(
        server.app,
        base_url="http://127.0.0.1",
        headers={"X-Playpen-Token": server.API_TOKEN},
    )
    assert client.get("/api/benchmarks/" + job_id).json()["events"] == events
