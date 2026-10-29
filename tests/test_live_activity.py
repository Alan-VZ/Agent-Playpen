import asyncio
import json
from pathlib import Path
import threading
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from config import credentials
from debugging.dashboard import server
from planner.react_planner import ReActPlanner
from tools.packs.web.search_tool import WebSearchTool


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "ENV_PATH", tmp_path / ".env")
    return TestClient(server.app, base_url="http://127.0.0.1", headers={"X-Playpen-Token": server.API_TOKEN})


def records(response):
    assert response.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(line) for line in response.text.splitlines() if line]


def test_stream_orders_actions_before_results_and_includes_answer(client, monkeypatch):
    backend = Mock()
    backend.chat.side_effect = [
        'Thought: PRIVATE_MARKER\nAction: calculator\nAction Input: {"expression":"6*7"}',
        'Thought: done\nAction: FINISH\nAction Input: 42',
    ]
    monkeypatch.setattr(server, "_build_backend", lambda config: backend)
    response = client.post("/api/run/stream", json={"task": "calculate", "tools": ["calculator"]})
    events = records(response)
    types = [event["type"] for event in events]
    assert types[0] == "session"
    assert types.index("model_request") < types.index("model_response") < types.index("act") < types.index("observe")
    assert events[-1]["type"] == "complete"
    assert events[-1]["status"] == "success" and events[-1]["result"] == "42"
    assert "PRIVATE_MARKER" not in response.text
    trace = json.loads(Path(events[-1]["trace_path"]).read_text())
    action = next(event for event in trace if event["type"] == "act")
    observation = next(event for event in trace if event["type"] == "observe")
    assert action["iteration"] == observation["iteration"] == 0


def test_failed_stream_saves_trace_and_redacts_error(client, monkeypatch):
    secret = "live-test-credential-123456789"
    credentials.remember_secret(secret)
    monkeypatch.setattr(server, "_build_backend", Mock(side_effect=RuntimeError("Example failure " + secret)))
    response = client.post("/api/run/stream", json={"task": "research"})
    events = records(response)
    assert events[-1]["status"] == "error"
    assert "Example failure" in events[-1]["message"]
    assert secret not in response.text
    trace_path = Path(events[-1]["trace_path"])
    assert trace_path.is_file() and secret not in trace_path.read_text()
    assert any(event["type"] == "error" for event in events)


def test_provider_error_is_actionable_without_raw_body(client, monkeypatch):
    error = RuntimeError("raw provider body must not be exposed")
    error.status_code = 402
    monkeypatch.setattr(server, "_build_backend", Mock(side_effect=error))
    events = records(client.post("/api/run/stream", json={"task": "research"}))
    assert "spending limit" in events[-1]["message"]
    assert "raw provider body" not in json.dumps(events)


def test_stream_budget_exhaustion_is_incomplete(client, monkeypatch):
    backend = Mock(chat=Mock(return_value='Thought: calculate\nAction: calculator\nAction Input: {"expression":"1+1"}'))
    monkeypatch.setattr(server, "_build_backend", lambda config: backend)
    events = records(client.post("/api/run/stream", json={"task": "loop", "tools": ["calculator"], "max_iterations": 1}))
    assert events[-1]["status"] == "incomplete"
    assert events[-1]["result"] == "2"
    assert any(event["type"] == "warning" for event in events)


@pytest.mark.asyncio
async def test_progress_arrives_while_backend_is_still_blocked(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "ROOT", tmp_path)
    release = threading.Event()
    entered = threading.Event()
    backend = Mock()

    def chat(messages):
        entered.set()
        assert release.wait(5)
        return 'Thought: done\nAction: FINISH\nAction Input: complete'

    backend.chat.side_effect = chat
    monkeypatch.setattr(server, "_build_backend", lambda config: backend)
    iterator = server.run_agent_stream(server.AgentConfig(task="task", tools=[])).body_iterator
    try:
        first = json.loads(await asyncio.wait_for(anext(iterator), 2))
        assert first["type"] == "session"
        while True:
            event = json.loads(await asyncio.wait_for(anext(iterator), 2))
            if event["type"] == "model_request":
                break
        assert not release.is_set()
        assert entered.wait(1)
        release.set()
        while json.loads(await asyncio.wait_for(anext(iterator), 2))["type"] != "complete":
            pass
    finally:
        release.set()
        await iterator.aclose()


def test_cancel_does_not_schedule_another_model_call(monkeypatch, tmp_path):
    from core.agent import Agent
    from core.exceptions import AgentCancelledError
    from debugging.tracer import Tracer
    from memory.memory_manager import MemoryManager
    from tools.tool_registry import ToolRegistry
    stopped = threading.Event()
    backend = Mock()

    def chat(messages):
        stopped.set()
        return 'Thought: done\nAction: FINISH\nAction Input: answer'

    backend.chat.side_effect = chat
    agent = Agent(backend, ReActPlanner(backend), ToolRegistry(), MemoryManager(), Tracer(str(tmp_path)), cancel_event=stopped)
    with pytest.raises(AgentCancelledError):
        agent.run("task")
    assert backend.chat.call_count == 1


@pytest.mark.parametrize("raw_input", ['```json\n{"query":"paper"}\n```', '[{"query":"paper"}]', 'null'])
def test_model_action_shapes_are_recoverable(raw_input):
    thought = ReActPlanner(Mock()).parse_thought('Thought: search\nAction: web_search\nAction Input: ' + raw_input)
    assert isinstance(thought.tool_args, dict)
    if raw_input.startswith('```'):
        assert thought.tool_args == {"query": "paper"}


@pytest.mark.parametrize("provider,items", [
    ("google", {"items": [{"title": "Paper", "snippet": "Abstract", "link": "https://example.invalid/paper"}]}),
    ("tavily", {"results": [{"title": "Paper", "content": "Abstract", "url": "https://example.invalid/paper"}]}),
    ("serpapi", {"organic_results": [{"title": "Paper", "snippet": "Abstract", "link": "https://example.invalid/paper"}]}),
])
def test_search_results_include_fetchable_source_urls(monkeypatch, provider, items):
    import requests
    response = Mock()
    response.json.return_value = items
    monkeypatch.setattr(requests, "get", Mock(return_value=response))
    monkeypatch.setattr(requests, "post", Mock(return_value=response))
    result = WebSearchTool(provider=provider, api_key="synthetic-search-key", cse_id="synthetic-cse").run(query="paper")
    assert "https://example.invalid/paper" in result


def test_stream_rejects_invalid_requests_before_starting(client):
    assert client.post("/api/run/stream", json={"task": ""}).status_code == 400


def test_stream_requires_session_token():
    client = TestClient(server.app, base_url="http://127.0.0.1")
    assert client.post("/api/run/stream", json={"task": "test"}).status_code == 403


def test_empty_model_output_reports_limit_and_keeps_usage(client, monkeypatch):
    backend = Mock(chat=Mock(return_value=None))
    backend.last_response_stats = {"finish_reason": "length", "output_tokens": 2048, "reasoning_tokens": 2048}
    monkeypatch.setattr(server, "_build_backend", lambda config: backend)
    events = records(client.post("/api/run/stream", json={"task": "research", "tools": []}))
    assert events[-1]["status"] == "error"
    assert "output-token limit" in events[-1]["message"]
    metadata = next(event for event in events if event["type"] == "model_response")
    assert "reasoning_tokens=2048" in metadata["content"]
    assert Path(events[-1]["trace_path"]).is_file()


def test_openrouter_retains_safe_response_metadata(monkeypatch):
    from types import SimpleNamespace
    from backends.openrouter import OpenRouterBackend
    client = Mock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(finish_reason="length", message=SimpleNamespace(content=None))],
        usage=SimpleNamespace(completion_tokens=2048, completion_tokens_details=SimpleNamespace(reasoning_tokens=2048)),
    )
    monkeypatch.setattr("backends.openrouter.openai.OpenAI", Mock(return_value=client))
    backend = OpenRouterBackend(api_key="synthetic-test-key")
    assert backend.chat([]) is None
    assert backend.last_response_stats == {"finish_reason": "length", "output_tokens": 2048, "reasoning_tokens": 2048}


@pytest.mark.asyncio
async def test_disconnected_stream_signals_worker_to_stop(monkeypatch):
    from starlette.requests import ClientDisconnect
    received_stop = threading.Event()

    def fake_execute(config, on_event, cancel_event):
        on_event({"type": "status", "content": "working"})
        if cancel_event.wait(4):
            received_stop.set()
        return {"status": "cancelled"}

    monkeypatch.setattr(server, "_execute_run", fake_execute)
    response = server.run_agent_stream(server.AgentConfig(task="task"))

    async def send(message):
        if message["type"] == "http.response.body":
            raise OSError("connection gone")

    async def receive():
        return {"type": "http.disconnect"}

    with pytest.raises(ClientDisconnect):
        await asyncio.wait_for(response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send), 3)
    assert received_stop.wait(1)
    await response.body_iterator.aclose()
