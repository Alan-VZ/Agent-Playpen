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


def replay_response(payload, tool_names=()):
    """Validate recorded native shapes or replay text; never dispatch calls."""
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
        return {
            **replay_text(message.get("content") or "", tool_names),
            "route": "text",
        }
    except (KeyError, IndexError, TypeError, ValueError) as exc:
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
    results = []
    for event in data.get("interactions", []):
        if event.get("kind") != "transport_response":
            continue
        if event.get("truncated") or "payload" not in event:
            results.append(
                {
                    "call_index": event.get("call_index"),
                    "replay_available": False,
                    "reason": "bounded or unavailable body",
                }
            )
            continue
        tools = [
            s["function"]["name"]
            for s in requests.get(event.get("call_index"), {}).get("tools", [])
        ]
        results.append(
            {
                "call_index": event.get("call_index"),
                "replay_available": True,
                **replay_response(event["payload"], tools),
            }
        )
    return results
