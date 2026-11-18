import pytest
from backends.tool_protocol import normalize_json_call
from core.exceptions import AgentResponseFormatError
from planner.react_planner import ReActPlanner

SCHEMAS = [{"function": {"name": "calculator"}}]


def test_explicit_advertised_json_call_and_fenced_form():
    for raw in [
        '{"name":"calculator","arguments":{"expression":"7 * 9"}}',
        '```json\n{"name":"calculator","arguments":{"expression":"7 * 9"}}\n```',
    ]:
        normalized = normalize_json_call(raw, SCHEMAS)
        thought = ReActPlanner(None).parse_thought(normalized)
        assert not thought.is_terminal and thought.tool_args == {"expression": "7 * 9"}


@pytest.mark.parametrize(
    "raw",
    [
        '{"result":63}',
        '{"name":"unknown","arguments":{}}',
        '[{"name":"calculator","arguments":{}}]',
        '{"name":"calculator","arguments":{},"Observation":"invented"}',
        'please run {"name":"calculator","arguments":{}}',
        '{"name":"calculator","arguments":{}} {"name":"calculator","arguments":{}}',
    ],
)
def test_never_extracts_guesses_or_multiple_calls(raw):
    assert normalize_json_call(raw, SCHEMAS) is None


def test_scalar_arguments_are_rejected_without_execution():
    with pytest.raises(AgentResponseFormatError):
        normalize_json_call('{"name":"calculator","arguments":"7*9"}', SCHEMAS)


def test_recorded_response_replay_respects_auto_vs_native():
    from benchmarks.evidence import replay_response

    body = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": '{"name":"calculator","arguments":{"expression":"7 * 9"}}'
                },
            }
        ]
    }
    automatic = replay_response(body, ["calculator"], "auto")
    assert automatic["route"] == "json_call_v1" and not automatic["terminal"]
    native = replay_response(body, ["calculator"], "native")
    assert native["terminal"]


def test_live_adapter_path_normalizes_explicit_json_call_without_network():
    import json
    import httpx
    import openai
    from backends.lm_studio import LMStudioBackend

    seen = []

    def respond(request):
        seen.append(json.loads(request.content))
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
                        "message": {
                            "role": "assistant",
                            "content": '{"name":"calculator","arguments":{"expression":"7 * 9"}}',
                        },
                    }
                ],
            },
        )

    backend = object.__new__(LMStudioBackend)
    backend.client = openai.OpenAI(
        api_key="synthetic",
        base_url="http://127.0.0.1:9/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    backend.model = "fixture"
    backend.temperature = 0
    backend.max_tokens = 2048
    backend.tool_calling_mode = "auto"
    try:
        raw = backend.chat_with_tools(
            [{"role": "user", "content": "multiply"}],
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
        assert ReActPlanner(None).parse_thought(raw).tool_args == {
            "expression": "7 * 9"
        }
        backend.accept_tool_result("63")
        assert backend._native_history[-1]["content"].endswith("63")
        assert backend.last_response_stats["adapter_route"] == "json_call_v1"
        assert len(seen) == 1
    finally:
        backend.client.close()
