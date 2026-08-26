# graphql_tool.py
import requests
from tools.base_tool import BaseTool


class GraphQLTool(BaseTool):
    """Execute a GraphQL query against an endpoint."""

    name = "graphql"
    description = "Run a GraphQL query and return the response data."
    parameters = {
        "type": "object",
        "properties": {
            "endpoint": {"type": "string", "description": "GraphQL endpoint URL"},
            "query": {"type": "string", "description": "GraphQL query string"},
            "variables": {"type": "object", "description": "Query variables dict"},
            "auth_token": {"type": "string", "description": "Authorization token"},
        },
        "required": ["endpoint", "query"],
    }

    def run(self, **kwargs) -> str:
        endpoint = kwargs["endpoint"]
        query = kwargs["query"]
        variables = kwargs.get("variables") or {}
        auth_token = kwargs.get("auth_token")
        headers = {"Content-Type": "application/json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        payload = {"query": query, "variables": variables}
        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=20)
            return resp.text[:3000]
        except requests.RequestException as e:
            return f"[ERROR] {e}"
