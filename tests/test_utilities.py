import json
from unittest.mock import Mock

import pytest
import requests

from advanced.guardrails import Guardrails
from advanced.prompt_optimizer import PromptOptimizer
from advanced.rate_limiter import RateLimitedBackend, TokenBucketRateLimiter
from core.context import AgentContext
from debugging.cost_tracker import CostTracker
from debugging.inspector import Inspector
from debugging.replay import load_trace, replay
from tools.packs.api.graphql_tool import GraphQLTool
from tools.packs.api.http_tool import HttpTool
from tools.packs.web.fetch_tool import FetchTool


@pytest.mark.parametrize("text,accepted", [
    ("Solve this equation", True), ("ignore previous instructions", False),
    ("Contact user@example.org", False), ("123-45-6789", False),
])
def test_input_guardrails(text, accepted):
    assert Guardrails().check_input(text).passed is accepted


def test_output_truncation():
    assert Guardrails().check_output("abcdef", max_chars=3).modified_text == "abc"


def test_cost_accounting():
    tracker = CostTracker()
    tracker.record("gpt-4o", 1000, 1000)
    tracker.record("local-model", 500, 500)
    assert tracker.session_total_usd == pytest.approx(0.0125)
    assert len(tracker.per_step_breakdown) == 2


def test_prompt_optimizer_selects_measured_best():
    backend = Mock(chat=Mock(return_value="answer"))
    evaluator = Mock()
    evaluator.evaluate.side_effect = [Mock(overall=3), Mock(overall=8)]
    optimizer = PromptOptimizer(backend, evaluator)
    optimizer.add_variant("a", "Answer {task}")
    optimizer.add_variant("b", "Check {task}")
    optimizer.run_trial("a", "question")
    optimizer.run_trial("b", "question")
    assert optimizer.select_best().id == "b"


def test_rate_limit_retries_only_transient_errors(monkeypatch):
    monkeypatch.setattr("advanced.rate_limiter.time.sleep", lambda delay: None)
    backend = Mock()
    backend.chat.side_effect = [RuntimeError("429"), "success"]
    wrapper = RateLimitedBackend(backend, Mock())
    assert wrapper.chat([]) == "success"
    backend.chat.side_effect = ValueError("invalid request")
    with pytest.raises(ValueError):
        wrapper.chat([])


def test_token_bucket_refills(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr("advanced.rate_limiter.time.monotonic", lambda: clock[0])
    limiter = TokenBucketRateLimiter(2, 1)
    limiter.acquire(2)
    clock[0] = 1.0
    limiter.acquire(1)
    assert limiter._tokens == 0


def test_inspector_and_replay(tmp_path, capsys):
    ctx = AgentContext("session", "task")
    inspector = Inspector()
    callback = Mock()
    inspector.register_step_hook(0, callback)
    inspector.check_hooks(ctx)
    callback.assert_called_once_with(ctx)
    assert json.loads(inspector.inspect(ctx))["task"] == "task"
    path = tmp_path / "trace.json"
    path.write_text(json.dumps([{"type": "observe", "content": "42"}]))
    replay(load_trace(str(path)), delay=0)
    assert "42" in capsys.readouterr().out


@pytest.mark.parametrize("failure", [False, True])
def test_fetch_conversion_and_network_error(monkeypatch, failure):
    response = Mock(text="<h1>Title</h1><p>Body</p>")
    request = Mock(return_value=response)
    if failure:
        request.side_effect = requests.RequestException("offline")
    monkeypatch.setattr(requests, "get", request)
    output = FetchTool().run(url="https://example.invalid")
    assert ("Fetch error" if failure else "# Title") in output


@pytest.mark.parametrize("tool,method,kwargs", [
    (HttpTool, "request", {"method": "GET", "url": "https://example.invalid"}),
    (GraphQLTool, "post", {"endpoint": "https://example.invalid", "query": "{version}"}),
])
def test_api_tools_mock_transport(monkeypatch, tool, method, kwargs):
    monkeypatch.setattr(requests, method, Mock(return_value=Mock(status_code=200, text="result")))
    assert "result" in tool().run(**kwargs)


@pytest.mark.parametrize("tool,method,kwargs", [
    (HttpTool, "request", {"method": "GET", "url": "https://example.invalid"}),
    (GraphQLTool, "post", {"endpoint": "https://example.invalid", "query": "{version}"}),
])
def test_api_tools_report_network_failure(monkeypatch, tool, method, kwargs):
    monkeypatch.setattr(requests, method, Mock(side_effect=requests.RequestException("offline")))
    assert "[ERROR]" in tool().run(**kwargs)
