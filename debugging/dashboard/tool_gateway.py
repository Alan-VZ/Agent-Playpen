"""Uniform tool catalog and execution console; authenticated by the dashboard."""

import json
import os
from pathlib import Path
import threading

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from tools.gateway import build_gateway, default_registry
from tools.external_mcp import connect_configured, connected_tools

_gateway = None
_lock = threading.RLock()


class Call(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    tool: str = Field(min_length=1, max_length=64)
    arguments: dict


def get_gateway(root):
    global _gateway
    with _lock:
        if _gateway is None:
            registry = default_registry(allowed_dirs=[root], include_writes=True)
            path = Path(
                os.environ.get(
                    "PLAYPEN_TOOL_DATA_DIR", str(root / "traces/tool-gateway")
                )
            )
            _gateway = build_gateway(registry, database=path / "tools.sqlite3")
        from tools.gateway import tool_spec

        for name, tool in connected_tools().items():
            if name not in _gateway.tools:
                _gateway.register(tool_spec(tool))
        return _gateway


def install(server):
    @server.app.get("/tools")
    def page(request: Request):
        return server.templates.TemplateResponse(
            request=request,
            name="tools.html",
            context={"session_token": server.API_TOKEN},
        )

    @server.app.get("/api/tool-gateway")
    def catalog():
        gateway = get_gateway(server.ROOT)
        return {
            "gateway_version": gateway.version,
            "tools": [
                {**spec, "readiness": gateway.readiness(spec["name"])}
                for spec in gateway.catalog()
            ],
            "history": gateway.history()[-30:],
        }

    @server.app.post("/api/tool-gateway/call")
    def call(payload: Call):
        return get_gateway(server.ROOT).execute(payload.tool, payload.arguments)

    @server.app.get("/api/tool-gateway/executions/{execution_id}")
    def record(execution_id: str):
        try:
            return get_gateway(server.ROOT).get(execution_id)
        except KeyError:
            raise HTTPException(404, "Unknown execution") from None

    @server.app.post("/api/tool-gateway/replay/{execution_id}")
    def replay(execution_id: str):
        try:
            return get_gateway(server.ROOT).replay(execution_id)
        except (KeyError, ValueError) as exc:
            raise HTTPException(400, str(exc)) from None

    @server.app.post("/api/tool-gateway/mcp/connect")
    def connect():
        try:
            result = connect_configured()
            get_gateway(server.ROOT)
            return result
        except (ValueError, OSError, json.JSONDecodeError):
            raise HTTPException(
                400,
                "Check config/mcp_servers.json; no commands are accepted through this API.",
            ) from None
