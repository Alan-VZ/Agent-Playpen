"""Compatibility surface backed by UACP's universal tool execution layer."""

import json
from tools.tool_registry import ToolRegistry


class ToolExecutor:
    def __init__(self, registry: ToolRegistry, default_timeout: int = 30):
        self.registry = registry
        self.default_timeout = default_timeout
        self.gateway = None
        self.last_result = None
        self.on_event = None

    def run(self, name: str, args: dict, timeout=None) -> str:
        from tools.gateway import build_gateway

        if self.gateway is None:
            self.gateway = build_gateway(
                self.registry,
                event=lambda event: self.on_event(event) if self.on_event else None,
            )
        result = self.gateway.execute(
            name, args, timeout=timeout if timeout is not None else self.default_timeout
        )
        self.last_result = result
        if not result["ok"]:
            message = result["error"]["message"]
            if result["status"] == "timed_out":
                raise TimeoutError(message)
            if result["error"]["code"] == "unknown_tool":
                raise KeyError(message)
            detail = result.get("result")
            return (
                "Error: "
                + message
                + (
                    " " + json.dumps(detail, ensure_ascii=False)
                    if detail is not None
                    else ""
                )
            )
        value = result["result"]
        return (
            value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        )
