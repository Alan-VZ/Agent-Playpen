"""Explicit connections to MCP servers declared in trusted local configuration."""

import atexit
import json
import os
from pathlib import Path
import re
import threading

from config.credentials import get_credential
from tools.base_tool import BaseTool
from universal_agent_control_plane.tool_client import MCPConnection

CONFIG = Path(__file__).resolve().parents[1] / "config/mcp_servers.json"
_connections = {}
_tools = {}
_lock = threading.RLock()


class RemoteTool(BaseTool):
    def __init__(self, server_name, connection, catalog):
        self.name = server_name + "__" + catalog["name"]
        self.remote_name = catalog["name"]
        self.description = catalog.get("description", self.remote_name)
        self.parameters = catalog["inputSchema"]
        self.connection = connection

    def run(self, **kwargs):
        result = self.connection.call(self.remote_name, kwargs)
        if result.is_error:
            return json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "remote_tool_error",
                        "message": " ".join(
                            getattr(item, "text", "") for item in result.content
                        )[:2000],
                    },
                }
            )
        if (
            result.structured_content is not None
            or "structured_content" in result.model_fields_set
        ):
            return result.structured_content
        return "\n".join(getattr(item, "text", "") for item in result.content)


def connected_tools():
    with _lock:
        return dict(_tools)


def connect_configured():
    if not CONFIG.exists():
        return {
            "connected": [],
            "errors": {},
            "message": "Copy config/mcp_servers.example.json to config/mcp_servers.json and configure trusted servers first.",
        }
    values = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
    servers = values.get("servers", {})
    if not isinstance(servers, dict) or len(servers) > 10:
        raise ValueError("Configure at most ten named MCP servers")
    errors = {}
    with _lock:
        for name, settings in servers.items():
            if name in _connections:
                continue
            connection = None
            try:
                if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,15}", name):
                    raise ValueError("Use a short simple server name")
                if not isinstance(settings, dict) or set(settings) - {
                    "command",
                    "args",
                    "cwd",
                    "url",
                    "secret_env",
                    "allowed_tools",
                }:
                    raise ValueError("Unsupported MCP configuration fields")
                allowed = settings.get("allowed_tools")
                if (
                    not isinstance(allowed, list)
                    or not allowed
                    or not all(isinstance(item, str) for item in allowed)
                ):
                    raise ValueError("Declare an explicit nonempty allowed_tools list")
                env = {
                    key: value
                    for key, value in os.environ.items()
                    if key.upper()
                    in {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}
                }
                for key in settings.get("secret_env", []):
                    value = get_credential(key)
                    if not value:
                        raise ValueError(
                            "A configured credential is missing; use API inventory"
                        )
                    env[key] = value
                connection = MCPConnection(
                    command=settings.get("command"),
                    args=settings.get("args"),
                    cwd=settings.get("cwd"),
                    url=settings.get("url"),
                    env=env,
                )
                found = {}
                for entry in connection.discover():
                    if entry["name"] in allowed:
                        tool = RemoteTool(name, connection, entry)
                        from tools.gateway import tool_spec

                        tool_spec(
                            tool
                        )  # Validate its contract before admitting a remote tool.
                        if len(tool.name) > 64:
                            raise ValueError(
                                "Namespaced MCP tool name exceeds 64 characters"
                            )
                        found[tool.name] = tool
                if {tool.remote_name for tool in found.values()} != set(allowed):
                    raise ValueError(
                        "Some allow-listed tools were not advertised by the server"
                    )
                _connections[name] = connection
                _tools.update(found)
            except Exception:
                if connection:
                    connection.close()
                errors[name] = (
                    "Connection failed. Check the command/URL, credentials and allowed_tools in local configuration."
                )
    return {"connected": list(_connections), "tools": list(_tools), "errors": errors}


@atexit.register
def close_connections():
    for connection in list(_connections.values()):
        connection.close()
