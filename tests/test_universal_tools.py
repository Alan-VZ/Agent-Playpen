import asyncio
import json
from pathlib import Path
import sys
from unittest.mock import Mock

import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from backends.base_backend import BaseBackend
from core.exceptions import AgentResponseFormatError
from tools.gateway import build_gateway, default_registry
from tools.tool_executor import ToolExecutor
from tools.tool_registry import ToolRegistry

ROOT = Path(__file__).resolve().parents[1]


def test_all_local_contracts_and_file_operations(tmp_path):
    registry = default_registry(allowed_dirs=[tmp_path], include_writes=True)
    gateway = build_gateway(registry)
    assert set(registry.list_all()) == {
        "calculator",
        "scientific_calculator",
        "datetime",
        "web_search",
        "fetch",
        "nimble_extract",
        "read_file",
        "write_file",
    }
    for spec in gateway.catalog():
        assert spec["inputSchema"]["additionalProperties"] is False
    path = str(tmp_path / "example.txt")
    assert gateway.execute("write_file", {"path": path, "content": "fixture text"})[
        "ok"
    ]
    read = gateway.execute("read_file", {"path": path})
    assert read["result"] == "fixture text"
    assert (
        gateway.execute("read_file", {"path": str(tmp_path.parent / "outside.txt")})[
            "error"
        ]["code"]
        == "execution_error"
    )
    assert (
        gateway.execute("calculator", {"expression": 42})["error"]["code"]
        == "invalid_arguments"
    )
    assert (
        gateway.execute("nimble_extract", {"url": "https://example.org"})["error"][
            "code"
        ]
        == "not_ready"
    )
    assert (
        gateway.execute("calculator", {"expression": "9**9999999"})["error"]["code"]
        == "tool_error"
    )
    result = gateway.execute("calculator", {"expression": "6*7"})
    assert gateway.replay(result["execution_id"])["result"] == "42"
    with pytest.raises(ValueError):
        gateway.replay(read["execution_id"])


def test_frozen_search_and_fetch_share_executor():
    registry = default_registry()
    registry.get("web_search").run = Mock(return_value="Frozen search: source A")
    registry.get("fetch").run = Mock(return_value="Frozen document A")
    executor = ToolExecutor(registry)
    assert executor.run("web_search", {"query": "fixture"}) == "Frozen search: source A"
    assert executor.last_result["status"] == "succeeded"
    assert (
        executor.run("fetch", {"url": "https://example.org/fixture"})
        == "Frozen document A"
    )
    assert executor.last_result["tool"] == "fetch"
    assert "Error:" in executor.run("fetch", {"url": 23})
    registry.get("fetch").run.assert_called_once()


def test_console_api_and_complete_record(monkeypatch, tmp_path):
    from debugging.dashboard import server, tool_gateway

    monkeypatch.setattr(
        tool_gateway,
        "_gateway",
        build_gateway(
            default_registry(allowed_dirs=[tmp_path]), database=tmp_path / "tools.db"
        ),
    )
    client = TestClient(server.app, base_url="http://127.0.0.1")
    headers = {"X-Playpen-Token": server.API_TOKEN}
    assert client.get("/tools").status_code == 200
    assert client.get("/api/tool-gateway").status_code == 403
    catalog = client.get("/api/tool-gateway", headers=headers).json()
    assert len(catalog["tools"]) == 7
    assert (
        client.post(
            "/api/tool-gateway/call",
            headers=headers,
            json={
                "tool": "calculator",
                "arguments": {"expression": "6*7"},
                "command": "bad",
            },
        ).status_code
        == 422
    )
    record = client.post(
        "/api/tool-gateway/call",
        headers=headers,
        json={"tool": "calculator", "arguments": {"expression": "6*7"}},
    ).json()
    assert record["ok"] and record["result"] == "42"
    assert (
        client.get(
            "/api/tool-gateway/executions/" + record["execution_id"], headers=headers
        ).json()
        == record
    )
    replay = client.post(
        "/api/tool-gateway/replay/" + record["execution_id"], headers=headers
    ).json()
    assert replay["result_sha256"] == record["result_sha256"]


@pytest.mark.parametrize("mode", ["auto", "native"])
@pytest.mark.parametrize("backend_name", ["lm_studio", "groq", "openrouter", "openai"])
def test_provider_native_calls_normalize_without_network(backend_name, mode):
    from backends.backend_factory import BackendFactory

    backend = object.__new__(BackendFactory.REGISTRY[backend_name])
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
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call1",
                                    "type": "function",
                                    "function": {
                                        "name": "calculator",
                                        "arguments": '{"expression":"6*7"}',
                                    },
                                }
                            ],
                        },
                    }
                ],
            },
        )

    backend.client = openai.OpenAI(
        api_key="synthetic-test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        base_url="http://127.0.0.1:9/v1",
        max_retries=0,
    )
    backend.model = "fixture"
    backend.temperature = 0
    backend.max_tokens = 128
    backend.tool_calling_mode = mode
    try:
        schemas = default_registry().to_openai_schemas()
        raw = backend.chat_with_tools([{"role": "user", "content": "6*7"}], schemas)
        assert "Action: calculator" in raw and "6*7" in raw
        assert requests[0]["tools"] == schemas and requests[0]["tool_choice"] == "auto"
    finally:
        backend.client.close()


def test_native_adapter_rejects_invented_parallel_calls():
    class Backend(BaseBackend):
        def chat(self, messages):
            return "prompt"

        def stream(self, messages):
            yield ""

    backend = Backend()
    backend.client = None
    backend.tool_calling_mode = "native"
    with pytest.raises(AgentResponseFormatError, match="no native tool adapter"):
        backend.chat_with_tools([], default_registry().to_openai_schemas())
    backend.tool_calling_mode = "prompt"
    assert (
        backend.chat_with_tools([], default_registry().to_openai_schemas()) == "prompt"
    )


def test_real_mcp_stdio_and_persistent_connection(tmp_path):
    from universal_agent_control_plane.tool_client import MCPConnection
    from tools.external_mcp import RemoteTool

    connection = MCPConnection(
        command=sys.executable,
        args=["-m", "tools.mcp_server", "--data-dir", str(tmp_path / "mcp-data")],
        cwd=str(ROOT),
        timeout=15,
    )
    try:
        catalog = connection.discover()
        calculator = next(t for t in catalog if t["name"] == "calculator")
        assert "expression" in calculator["inputSchema"]["properties"]
        registry = ToolRegistry()
        registry.register(RemoteTool("local", connection, calculator))
        gateway = build_gateway(registry)
        for expression, answer in [("6*7", "42"), ("12+3", "15")]:
            record = gateway.execute("local__calculator", {"expression": expression})
            assert record["ok"] and record["result"]["result"] == answer
        assert connection.thread.is_alive()
        invalid = connection.call("calculator", {"expression": 42})
        assert invalid.is_error
    finally:
        connection.close()
        connection.thread.join(timeout=5)
    assert not connection.thread.is_alive()


def test_in_memory_mcp_exposes_same_tool_contracts():
    from tools.mcp_server import create_server
    from mcp.client import Client

    async def run():
        server = create_server()
        async with Client(server) as client:
            tools = await client.list_tools()
            assert "write_file" not in [tool.name for tool in tools.tools]
            result = await client.call_tool("calculator", {"expression": "6*7"})
            assert result.structured_content["result"] == "42" and not result.is_error

    asyncio.run(run())


def test_trusted_tool_configuration_is_not_agent_writable(tmp_path):
    gateway = build_gateway(
        default_registry(allowed_dirs=[tmp_path], include_writes=True)
    )
    for name in ("mcp_servers.json", "qalculate.json"):
        result = gateway.execute(
            "write_file", {"path": str(tmp_path / name), "content": "{}"}
        )
        assert not result["ok"] and not (tmp_path / name).exists()


def test_native_agent_roundtrip_uses_real_tool_role(tmp_path):
    from backends.openai_backend import OpenAIBackend
    from core.agent import Agent
    from debugging.tracer import Tracer
    from memory.memory_manager import MemoryManager
    from planner.react_planner import ReActPlanner

    backend = object.__new__(OpenAIBackend)
    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        if len(requests) == 1:
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-one",
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
                and m.get("tool_call_id") == "call-one"
                and m.get("content") == "42"
                for m in body["messages"]
            )
            message = {"role": "assistant", "content": "42"}
        return httpx.Response(
            200,
            json={
                "id": "test",
                "object": "chat.completion",
                "created": 1,
                "model": "test",
                "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
            },
        )

    backend.client = openai.OpenAI(
        api_key="synthetic",
        base_url="http://127.0.0.1:9/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    backend.model = "test"
    backend.temperature = 0
    backend.max_tokens = 128
    registry = ToolRegistry()
    registry.register(default_registry().get("calculator"))
    tracer = Tracer(str(tmp_path / "traces"))
    try:
        agent = Agent(
            backend,
            ReActPlanner(backend),
            registry,
            MemoryManager({"enabled_stores": []}),
            tracer,
            max_iterations=3,
        )
        assert agent.run("Calculate 6*7") == "42"
        records = [
            json.loads(e.content) for e in tracer.events if e.type == "tool_result"
        ]
        assert len(records) == 1 and records[0]["result"] == "42" and records[0]["ok"]
    finally:
        backend.client.close()


@pytest.mark.parametrize("value", [None, True, [1, 2], {"value": "42"}])
def test_external_structured_results_preserve_json_types(value):
    from types import SimpleNamespace
    from tools.external_mcp import RemoteTool

    response = SimpleNamespace(
        is_error=False,
        structured_content=value,
        model_fields_set={"structured_content"},
        content=[],
    )
    tool = RemoteTool(
        "remote",
        SimpleNamespace(call=lambda *args: response),
        {"name": "value", "inputSchema": {"type": "object"}},
    )
    registry = ToolRegistry()
    registry.register(tool)
    record = build_gateway(registry).execute("remote__value", {})
    assert (
        record["ok"]
        and record["result"] == value
        and type(record["result"]) is type(value)
    )
