# csv_tool.py
import csv
from tools.base_tool import BaseTool


class CsvTool(BaseTool):
    """Read, write, and filter CSV data."""

    name = "csv_tool"
    description = "Read a CSV file, write rows to a CSV file, or filter rows."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "write", "filter"],
                "description": "Operation to perform",
            },
            "path": {"type": "string", "description": "CSV file path"},
            "rows": {
                "type": "array",
                "description": "Rows to write (list of dicts)",
            },
            "filter_col": {"type": "string", "description": "Column name to filter on"},
            "filter_val": {"type": "string", "description": "Value to match"},
        },
        "required": ["action", "path"],
    }

    def run(self, **kwargs) -> str:
        action = kwargs["action"]
        path = kwargs["path"]
        rows = kwargs.get("rows")
        filter_col = kwargs.get("filter_col")
        filter_val = kwargs.get("filter_val")
        if action == "read":
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                data = list(reader)
            return f"Read {len(data)} rows.\n" + str(data[:5])

        elif action == "write":
            if not rows:
                return "No rows provided for write."
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            return f"Wrote {len(rows)} rows to {path}"

        elif action == "filter":
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                filtered = [r for r in reader if r.get(filter_col) == filter_val]
            return f"Found {len(filtered)} rows where {filter_col}={filter_val}\n{filtered[:5]}"

        return f"Unknown action: {action}"
    