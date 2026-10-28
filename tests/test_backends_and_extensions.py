import importlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from advanced.evaluator import Evaluator
from advanced.self_critique import SelfCritiqueLoop
from backends.backend_factory import BackendFactory
from debugging.dashboard import server
from tools.packs.code.python_repl import PythonReplTool
from tools.packs.data.json_tool import JsonTool
from tools.packs.utils.datetime_tool import DatetimeTool


@pytest.mark.parametrize("module_name,class_name,kwargs,client_name", [
    ("lm_studio", "LMStudioBackend", {}, "OpenAI"),
    ("ollama", "OllamaBackend", {}, "OpenAI"),
    ("openai_backend", "OpenAIBackend", {"api_key": "fake"}, "OpenAI"),
    ("openrouter", "OpenRouterBackend", {"api_key": "fake"}, "OpenAI"),
    ("azure_openai", "AzureOpenAIBackend", {"api_key": "fake", "azure_endpoint": "https://example.invalid", "deployment_name": "test"}, "AzureOpenAI"),
])
def test_openai_compatible_backend_chat_and_stream(monkeypatch, module_name, class_name, kwargs, client_name):
    module = importlib.import_module(f"backends.{module_name}")
    client = Mock()
    monkeypatch.setattr(module.openai, client_name, Mock(return_value=client))
    backend = getattr(module, class_name)(**kwargs)
    messages = [{"role": "user", "content": "hello"}]
    client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="reply"))])
    assert backend.chat(messages) == "reply"
    client.chat.completions.create.return_value = [SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="part"))])]
    assert list(backend.stream(messages)) == ["part"]


def test_anthropic_backend_dashboard_constructor(monkeypatch):
    module = importlib.import_module("backends.anthropic_backend")
    client = Mock()
    monkeypatch.setattr(module.anthropic, "Anthropic", Mock(return_value=client))
    backend = server._build_backend(server.AgentConfig(backend="anthropic", api_key="fake"))
    client.messages.create.return_value = SimpleNamespace(content=[SimpleNamespace(text="reply")])
    assert backend.chat([{"role": "system", "content": "rules"}, {"role": "user", "content": "hello"}]) == "reply"
    assert client.messages.create.call_args.kwargs["system"] == "rules"


def test_azure_dashboard_constructor(monkeypatch):
    module = importlib.import_module("backends.azure_openai")
    monkeypatch.setattr(module.openai, "AzureOpenAI", Mock())
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.invalid")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "test")
    backend = server._build_backend(server.AgentConfig(backend="azure_openai", api_key="fake"))
    assert backend.deployment_name == "test"


def test_factory_unknown_backend():
    with pytest.raises(ValueError, match="Unknown backend"):
        BackendFactory.create("missing")


@pytest.mark.parametrize("raw", ["not json", "[]", "null", '{"accuracy":"bad"}'])
def test_evaluator_invalid_response_does_not_crash(raw):
    result = Evaluator(Mock(chat=Mock(return_value=raw))).evaluate("task", "answer")
    assert result.reasoning


def test_evaluator_valid_scores():
    raw = json.dumps({"relevance": 8, "accuracy": 9, "completeness": 7, "format": 8, "reasoning": "checked"})
    assert Evaluator(Mock(chat=Mock(return_value=raw))).evaluate("task", "answer").overall == 8


def test_self_critique_refines_and_stops():
    backend = Mock()
    backend.chat.side_effect = ["Fix arithmetic", "42", "NO_IMPROVEMENTS_NEEDED"]
    assert SelfCritiqueLoop(backend).run("task", "41") == "42"
    assert backend.chat.call_count == 3


def test_json_tool_roundtrip(tmp_path):
    path = str(tmp_path / "data.json")
    tool = JsonTool()
    tool.run(action="write", path=path, data={"user": {"name": "Ada"}})
    assert tool.run(action="get", path=path, json_path="user.name") == "Ada"
    assert json.loads(tool.run(action="read", path=path))["user"]["name"] == "Ada"


def test_datetime_difference():
    assert DatetimeTool().run(action="diff", date_str="2026-01-01", date_str_2="2026-01-03") == "2 days, 0 hours"


def test_python_tool_executes_in_subprocess():
    assert PythonReplTool().run(code="print(6 * 7)").strip() == "42"


def test_python_tool_reports_errors():
    assert "ZeroDivisionError" in PythonReplTool().run(code="print(1 / 0)")
