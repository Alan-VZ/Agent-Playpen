# sql_tool.py
import sqlite3
import re
from tools.base_tool import BaseTool


class SqliteTool(BaseTool):
    """Execute safe, read-only parameterised SELECT queries on a SQLite database."""

    name = "sqlite_query"
    description = "Run a SELECT query on a SQLite database file."
    parameters = {
        "type": "object",
        "properties": {
            "db_path": {"type": "string", "description": "Path to the .db file"},
            "query": {"type": "string", "description": "SELECT SQL query"},
            "params": {
                "type": "array",
                "description": "Query parameters for parameterised queries",
            },
        },
        "required": ["db_path", "query"],
    }

    ALLOWED_PATTERN = re.compile(r"^\s*SELECT\b", re.IGNORECASE)

    def run(self, **kwargs) -> str:
        db_path = kwargs["db_path"]
        query = kwargs["query"]
        params = kwargs.get("params") or []
        if not self.ALLOWED_PATTERN.match(query):
            return "[BLOCKED] Only SELECT queries are permitted."
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            cols = [d[0] for d in cursor.description] if cursor.description else []
            result_lines = [" | ".join(cols)]
            for row in rows[:50]:
                result_lines.append(" | ".join(str(c) for c in row))
            return "\n".join(result_lines)
        finally:
            conn.close()
            