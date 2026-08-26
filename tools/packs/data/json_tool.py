# json_tool.py
import json
from pathlib import Path
from tools.base_tool import BaseTool


class JsonTool(BaseTool):
    """Read, write, and access JSON files by dot-notation path."""

    name = "json_tool"
    description = "Read or write a JSON file, or get a value by dot-path."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "write", "get"],
            },
            "path": {"type": "string", "description": "JSON file path"},
            "data": {"type": "object", "description": "Data to write"},
            "json_path": {
                "type": "string",
                "description": "Dot-notation path e.g. 'user.address.city'",
            },
        },
        "required": ["action", "path"],
    }

    def run(self, **kwargs) -> str:
        action = kwargs["action"]
        path = kwargs["path"]
        data = kwargs.get("data")
        json_path = kwargs.get("json_path")
        p = Path(path)

        if action == "read":
            content = json.loads(p.read_text(encoding="utf-8"))
            return json.dumps(content, indent=2)

        elif action == "write":
            p.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return f"Written JSON to {path}"

        elif action == "get":
            if not json_path:
                return "[ERROR] json_path is required for get."
            content = json.loads(p.read_text(encoding="utf-8"))
            keys = json_path.split(".")
            val = content
            for k in keys:
                val = val[k]
            return str(val)

        return f"Unknown action: {action}"
    