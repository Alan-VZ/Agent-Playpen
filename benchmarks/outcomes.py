"""Stable operational categories, separate from objective answer checks."""

from config.credentials import redact


def safe_error(exc):
    body = getattr(exc, "body", None)
    body = body.get("error", body) if isinstance(body, dict) else {}
    body = body if isinstance(body, dict) else {}
    code = getattr(exc, "status_code", None)
    message = body.get("message")
    if not isinstance(message, str):
        message = str(exc) if code is None else "Provider rejected the request."
    return redact(
        {
            "error_type": type(exc).__name__,
            "http_status": code,
            "provider_code": str(body.get("code", ""))[:100],
            "message": message[:800],
        }
    )


def category(result):
    if result.get("diagnostic_correct") is True:
        return "diagnostic_correct"
    if (
        result.get("evaluation", {}).get("passed")
        and result.get("status") == "completed"
    ):
        return "passed"
    if result.get("status") in {"timeout", "cancelled", "interrupted"}:
        return result["status"]
    calls = result.get("usage", {}).get("model_calls", [])
    if calls:
        last = calls[-1]
        if last.get("response_stats", {}).get("finish_reason") == "error":
            return "provider_error"
        if (
            last.get("response_stats", {}).get("finish_reason") == "length"
            and last.get("text_characters") == 0
        ):
            return "output_limit"
    messages = " ".join(a.get("message", "") for a in result.get("agents", [])).lower()
    if "truncated" in messages or "output-token limit" in messages:
        return "output_limit"
    if "repeated" in messages:
        return "repeated_action"
    if "validation failed" in messages:
        return "final_report_validation"
    if "iteration budget" in messages:
        return "iteration_limit"
    for agent in result.get("agents", []):
        if "returned no completion choices" in agent.get("message", "").lower():
            return "provider_error"
        code = agent.get("http_status")
        if code == 429:
            return "provider_rate_limit"
        if code in {401, 402, 403, 404}:
            return "provider_rejection"
        if code:
            return "provider_error"
        if agent.get("error_type") in {"APITimeoutError", "TimeoutError"}:
            return "timeout"
        if agent.get("error_type") in {"APIConnectionError", "ConnectionError"}:
            return "provider_connection"
        if agent.get("error_type") == "ModelManagementError":
            return "model_setup"
        if (
            "format" in agent.get("message", "").lower()
            or "invalid model response" in agent.get("message", "").lower()
        ):
            return "response_format"
    checks = result.get("evaluation", {}).get("checks", {})
    if checks.get("valid_json") and (
        checks.get("read_inputs") is False
        or any(k.startswith("citation_") and v is False for k, v in checks.items())
    ):
        return "missing_or_unsupported_evidence"
    if any(a.get("status") == "incomplete" for a in result.get("agents", [])):
        return "incomplete_execution"
    if result.get("status") == "execution_failed":
        return "execution_error"
    if result.get("evaluation", {}).get("checks", {}).get("valid_json") is False:
        return "response_format"
    return "incorrect_answer"


def categories(result):
    """Contributing observed symptoms in addition to the primary category."""
    found = {category(result)}
    events = result.get("partial_events", []) + [
        event for agent in result.get("agents", []) for event in agent.get("trace", [])
    ]
    text = " ".join(
        str(e.get("content", ""))
        for e in events
        if e.get("type") in {"warning", "error"}
    ).lower()
    if "format" in text or "model response rejected" in text:
        found.add("response_format")
    if "repeated" in text or "already been read" in text or "exact calculation" in text:
        found.add("repeated_action")
    if "final answer rejected" in text:
        found.add("final_report_validation")
    if "truncated" in text:
        found.add("output_limit")
    if any(
        e.get("type") == "tool_result" and '"ok": false' in e.get("content", "")
        for e in events
    ):
        found.add("tool_execution_error")
    return sorted(found)
