"""Bounded, credential-redacted transport evidence and offline parser replay."""

import json
import hashlib
from config.credentials import redact
from planner.react_planner import ReActPlanner

LIMIT = 256_000


def bounded(value):
    safe = redact(value)
    text = json.dumps(safe, ensure_ascii=False, default=str)
    if len(text.encode("utf-8")) <= LIMIT:
        return {"payload": safe, "truncated": False}
    return {
        "payload_text": text.encode("utf-8")[:LIMIT].decode("utf-8", errors="ignore"),
        "truncated": True,
        "redacted_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def install_transport_capture(backend, emit):
    """Capture JSON bodies only, never authentication headers; no provider calls."""
    client = getattr(getattr(backend, "client", None), "_client", None)
    hooks = getattr(client, "event_hooks", None)
    if not isinstance(hooks, dict):
        return False

    def request(req):
        try:
            body = json.loads(req.content)
        except (ValueError, UnicodeError):
            body = {"unavailable": "non-JSON request body"}
        emit(
            "transport_request",
            {"method": req.method, "endpoint": req.url.path, **bounded(body)},
        )

    def response(res):
        if "text/event-stream" in res.headers.get("content-type", ""):
            emit(
                "transport_response",
                {
                    "status_code": res.status_code,
                    "unavailable": "streaming body not captured",
                },
            )
            return
        try:
            body = json.loads(res.read())
        except (ValueError, UnicodeError):
            body = {"unavailable": "non-JSON response body"}
        emit("transport_response", {"status_code": res.status_code, **bounded(body)})

    hooks.setdefault("request", []).append(request)
    hooks.setdefault("response", []).append(response)
    return True


def replay_text(raw, tool_names=()):
    """Replay text normalization/parsing only. No model call or tool execution."""
    planner = ReActPlanner(None)
    planner.available_tool_names = set(tool_names)
    try:
        thought = planner.parse_thought(raw)
        return {
            "accepted": True,
            "terminal": thought.is_terminal,
            "tool": thought.tool_name,
            "arguments": thought.tool_args,
            "answer": thought.answer,
        }
    except Exception as exc:
        return {
            "accepted": False,
            "error_type": type(exc).__name__,
            "message": str(exc),
        }


def replay_response(payload, tool_names=(), mode="auto"):
    """Replay current normalization plus parsing; never dispatch calls."""
    try:
        choice = payload["choices"][0]
        if choice.get("finish_reason") == "length":
            return {"accepted": False, "category": "output_limit"}
        message = choice["message"]
        calls = message.get("tool_calls") or []
        if calls:
            if len(calls) != 1:
                return {"accepted": False, "category": "multiple_native_calls"}
            call = calls[0]["function"]
            arguments = json.loads(call["arguments"])
            return {
                "accepted": call["name"] in tool_names and isinstance(arguments, dict),
                "terminal": False,
                "tool": call["name"],
                "arguments": arguments,
                "route": "native",
            }
        raw = message.get("content") or ""
        if tool_names and mode == "auto":
            from backends.tool_protocol import normalize_json_call

            normalized = normalize_json_call(
                raw, [{"function": {"name": name}} for name in tool_names]
            )
            if normalized:
                return {**replay_text(normalized, tool_names), "route": "json_call_v1"}
        if tool_names and mode != "prompt" and "Action:" not in raw:
            raw = "Thought: Final answer\nAction: FINISH\nAction Input: " + json.dumps(
                raw
            )
        return {**replay_text(raw, tool_names), "route": "text"}
    except Exception as exc:
        return {
            "accepted": False,
            "category": "malformed_response",
            "message": str(exc),
        }


def replay_attempt(data):
    requests = {
        e.get("call_index"): e.get("payload", {})
        for e in data.get("interactions", [])
        if e.get("kind") == "transport_request"
    }
    modes = {
        e.get("call_index"): e.get("reservation", {}).get("tool_calling_mode", "auto")
        for e in data.get("interactions", [])
        if e.get("kind") == "request_diagnostic"
    }
    results = []
    for event in data.get("interactions", []):
        if event.get("kind") != "transport_response":
            continue
        item = {"call_index": event.get("call_index"), "replay_version": "json-call-v1"}
        if event.get("truncated") or "payload" not in event:
            results.append(
                {
                    **item,
                    "replay_available": False,
                    "reason": "bounded or unavailable body",
                }
            )
            continue
        if event.get("status_code", 200) >= 400:
            results.append(
                {
                    **item,
                    "replay_available": True,
                    "accepted": False,
                    "category": "provider_rate_limit"
                    if event["status_code"] == 429
                    else "provider_rejection",
                    "http_status": event["status_code"],
                }
            )
            continue
        tools = [
            s["function"]["name"]
            for s in requests.get(event.get("call_index"), {}).get("tools", [])
        ]
        results.append(
            {
                **item,
                "replay_available": True,
                **replay_response(
                    event["payload"], tools, modes.get(event.get("call_index"), "auto")
                ),
            }
        )
    return results
