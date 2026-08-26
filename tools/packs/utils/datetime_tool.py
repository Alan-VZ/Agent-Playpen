# datetime_tool.py
import datetime
from tools.base_tool import BaseTool


class DatetimeTool(BaseTool):
    """Date and time utilities: now, format, parse, diff."""

    name = "datetime"
    description = "Get current datetime, format dates, parse date strings, or compute diffs."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["now", "format", "parse", "diff"],
            },
            "date_str": {"type": "string", "description": "Date string to parse or format"},
            "fmt": {"type": "string", "description": "strftime format string"},
            "date_str_2": {"type": "string", "description": "Second date for diff"},
        },
        "required": ["action"],
    }

    def run(self, **kwargs) -> str:
        action = kwargs["action"]
        date_str = kwargs.get("date_str")
        fmt = kwargs.get("fmt", "%Y-%m-%d %H:%M:%S")
        date_str_2 = kwargs.get("date_str_2")
        if action == "now":
            return datetime.datetime.now(datetime.timezone.utc).strftime(fmt) + " UTC"
        elif action == "format":
            if not date_str:
                return "[ERROR] date_str is required for format."
            dt = datetime.datetime.fromisoformat(date_str)
            return dt.strftime(fmt)
        elif action == "parse":
            if not date_str:
                return "[ERROR] date_str is required for parse."
            dt = datetime.datetime.fromisoformat(date_str)
            return str(dt)
        elif action == "diff":
            if not date_str or not date_str_2:
                return "[ERROR] date_str and date_str_2 are required for diff."
            dt1 = datetime.datetime.fromisoformat(date_str)
            dt2 = datetime.datetime.fromisoformat(date_str_2)
            delta = abs(dt2 - dt1)
            return f"{delta.days} days, {delta.seconds // 3600} hours"
        return f"Unknown action: {action}"
