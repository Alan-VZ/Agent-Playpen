from abc import ABC, abstractmethod


class BaseBackend(ABC):
    """Abstract interface implemented by all model backends."""

    @property
    def uses_native_tools(self):
        import openai
        return getattr(self, "tool_calling_mode", "prompt") != "prompt" and isinstance(getattr(self, "client", None), (openai.OpenAI, openai.AzureOpenAI))

    @property
    def native_tool_capability(self):
        return getattr(self, "_native_tool_capability", "untested")

    def record_usage(self, response):
        """Keep only numeric provider usage; missing data is explicitly unknown."""
        identity = getattr(response, "model", None)
        self.last_model_identity = (
            identity if isinstance(identity, str) and len(identity) <= 500 else None
        )
        usage = getattr(response, "usage", None)

        def number(name):
            value = getattr(usage, name, None)
            return (
                value
                if isinstance(value, int) and not isinstance(value, bool) and value >= 0
                else None
            )

        inputs = number("prompt_tokens")
        if inputs is None:
            inputs = number("input_tokens")
        outputs = number("completion_tokens")
        if outputs is None:
            outputs = number("output_tokens")
        total = number("total_tokens")
        self.last_usage = {
            "input_tokens": inputs,
            "output_tokens": outputs,
            "total_tokens": total
            if total is not None
            else inputs + outputs
            if inputs is not None and outputs is not None
            else None,
        }
        choices = getattr(response, "choices", None)
        choice = choices[0] if isinstance(choices, list) and choices else None
        details = getattr(usage, "completion_tokens_details", None)
        reasoning = getattr(details, "reasoning_tokens", None)
        self.last_response_stats = {
            "finish_reason": getattr(choice, "finish_reason", None),
            "output_tokens": outputs,
            "reasoning_tokens": reasoning
            if isinstance(reasoning, int) and not isinstance(reasoning, bool)
            else None,
        }

    def reset_tool_session(self):
        self._native_history = []
        self._pending_native_call = None

    def accept_tool_result(self, text):
        """Pair a native call with its actual observation, never model prose."""
        from config.credentials import redact

        pending = getattr(self, "_pending_native_call", None)
        if pending:
            self._native_tool_capability = "observed working"
            self._native_history.append(
                {
                    "role": "tool",
                    "tool_call_id": pending,
                    "content": redact(str(text))[:2000],
                }
            )
            self._pending_native_call = None
        elif self.uses_native_tools:
            if not hasattr(self, "_native_history"):
                self.reset_tool_session()
            self._native_history.append({"role": "user", "content": "Runtime observation/feedback: " + redact(str(text))[:4000]})

    def chat_with_tools(self, messages, schemas):
        """Normalize native OpenAI-compatible calls into the shared action contract.

        Other providers retain the existing prompt adapter. There is no silent
        retry/fallback after a provider rejection, which could duplicate cost.
        """
        import json
        import os
        import openai
        from core.exceptions import AgentResponseFormatError

        mode = getattr(
            self, "tool_calling_mode", os.getenv("TOOL_CALLING_MODE", "auto")
        )
        client = getattr(self, "client", None)
        if mode == "prompt" or not schemas:
            return self.chat(messages)
        if not isinstance(client, (openai.OpenAI, openai.AzureOpenAI)):
            if mode == "native":
                raise AgentResponseFormatError(
                    "This backend has no native tool adapter; select prompt mode."
                )
            return self.chat(messages)
        response = client.with_options(max_retries=0).chat.completions.create(
            model=getattr(self, "model", None)
            or getattr(self, "deployment_name", None),
            messages=[*messages, *getattr(self, "_native_history", [])],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            tools=schemas,
            tool_choice="auto",
            **getattr(self, "native_request_options", {}),
        )
        self.record_usage(response)
        message = response.choices[0].message
        calls = message.tool_calls or []
        if calls:
            self._native_tool_capability = "advertised by provider"
            if len(calls) != 1:
                self._native_tool_capability = "observed failing"
                raise AgentResponseFormatError(
                    "Return exactly one tool call at a time; none of these calls was executed."
                )
            call = calls[0].function
            try:
                arguments = json.loads(call.arguments)
            except (TypeError, ValueError):
                self._native_tool_capability = "observed failing"
                raise AgentResponseFormatError(
                    "Tool arguments must be a valid JSON object; no tool was executed."
                ) from None
            if not isinstance(arguments, dict):
                self._native_tool_capability = "observed failing"
                raise AgentResponseFormatError(
                    "Tool arguments must be an object; no tool was executed."
                )
            if call.name not in {schema["function"]["name"] for schema in schemas}:
                self._native_tool_capability = "observed failing"
                raise AgentResponseFormatError(
                    "Select an advertised tool; no tool was executed."
                )
            if not hasattr(self, "_native_history"):
                self.reset_tool_session()
            self._pending_native_call = calls[0].id
            self._native_history.append(
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": calls[0].id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": call.arguments,
                            },
                        }
                    ],
                }
            )
            return (
                "Thought: Native tool request\nAction: "
                + call.name
                + "\nAction Input: "
                + json.dumps(arguments)
            )
        content = message.content
        if isinstance(content, str) and content.strip():
            if not hasattr(self, "_native_history"):
                self.reset_tool_session()
            self._native_history.append({"role": "assistant", "content": content})
        if not isinstance(content, str) or not content.strip():
            raise AgentResponseFormatError(
                "The provider returned neither a tool call nor an answer."
            )
        if mode == "auto":
            from backends.tool_protocol import normalize_json_call
            normalized = normalize_json_call(content, schemas)
            if normalized is not None:
                self.last_response_stats["adapter_route"] = "json_call_v1"
                return normalized
        if "Action:" in content:
            return content
        return "Thought: Final answer\nAction: FINISH\nAction Input: " + json.dumps(
            content
        )

    @abstractmethod
    def chat(self, messages: list[dict]) -> str:
        """Return a single assistant response for the given message list."""
        raise NotImplementedError

    @abstractmethod
    def stream(self, messages: list[dict]):
        """Yield response chunks for the given message list."""
        raise NotImplementedError
