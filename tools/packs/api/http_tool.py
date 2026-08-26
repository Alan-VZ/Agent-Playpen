# http_tool.py
import requests
from tools.base_tool import BaseTool


class HttpTool(BaseTool):
    """Make generic HTTP requests (GET, POST, PUT, DELETE)."""

    name = "http"
    description = "Make an HTTP request and return the response body."
    parameters = {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
            },
            "url": {"type": "string", "description": "Target URL"},
            "headers": {"type": "object", "description": "Request headers dict"},
            "body": {"type": "object", "description": "JSON request body"},
            "auth_token": {
                "type": "string",
                "description": "Authorization token for header",
            },
        },
        "required": ["method", "url"],
    }

    def run(self, **kwargs) -> str:
        method = kwargs["method"]
        url = kwargs["url"]
        hdrs = kwargs.get("headers") or {}
        body = kwargs.get("body")
        auth_token = kwargs.get("auth_token")
        if auth_token:
            hdrs["Authorization"] = f"Bearer {auth_token}"
        try:
            resp = requests.request(
                method, url, headers=hdrs, json=body, timeout=20
            )
            return f"Status: {resp.status_code}\n{resp.text[:3000]}"
        except requests.RequestException as e:
            return f"[ERROR] {e}"
