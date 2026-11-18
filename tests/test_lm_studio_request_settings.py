"""Client settings must be explicit on every LM Studio request path."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import openai
import pytest

from backends.lm_studio import LMStudioBackend


@pytest.mark.parametrize("route", ["chat", "stream", "native"])
def test_explicit_lm_studio_inference_settings(route):
    backend = object.__new__(LMStudioBackend)
    backend.client = MagicMock(spec=openai.OpenAI)
    backend.client.chat = MagicMock()
    backend.client.with_options.return_value = backend.client
    backend.model = "test-model"
    backend.temperature = 0
    backend.max_tokens = 4096
    backend.tool_calling_mode = "native"
    backend.record_usage = MagicMock()
    create = backend.client.chat.completions.create
    messages = [{"role": "user", "content": "hello"}]
    if route == "stream":
        create.return_value = [SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="hello"))])]
        assert list(backend.stream(messages)) == ["hello"]
    else:
        create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="hello", tool_calls=[]))])
        if route == "native":
            backend.chat_with_tools(messages, [{"type": "function", "function": {"name": "calculator", "parameters": {"type": "object"}}}])
        else:
            assert backend.chat(messages) == "hello"
    payload = create.call_args.kwargs
    assert payload["model"] == "test-model"
    assert payload["temperature"] == 0
    assert payload["max_tokens"] == 4096
