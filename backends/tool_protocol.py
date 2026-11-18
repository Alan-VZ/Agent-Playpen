"""Explicit JSON-call dialect for Auto mode, without prose extraction or guesses."""

import json
import re
from core.exceptions import AgentResponseFormatError

VERSION = "json-call-v1"


def normalize_json_call(content, schemas):
    if not isinstance(content, str):
        return None
    text = content.strip()
    if text.startswith("```"):
        match = re.fullmatch(r"```(?:json)?\s*\n?([\s\S]*?)\s*```", text, re.IGNORECASE)
        if not match:
            return None
        text = match.group(1)
    try:
        value = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(value, dict) or set(value) != {"name", "arguments"}:
        return None
    allowed = {schema["function"]["name"] for schema in schemas}
    if not isinstance(value["name"], str) or value["name"] not in allowed:
        return None
    if not isinstance(value["arguments"], dict):
        raise AgentResponseFormatError(
            "JSON-call arguments must be one object. No tool was executed."
        )
    return (
        "Thought: Explicit JSON tool request\nAction: "
        + value["name"]
        + "\nAction Input: "
        + json.dumps(value["arguments"])
    )
