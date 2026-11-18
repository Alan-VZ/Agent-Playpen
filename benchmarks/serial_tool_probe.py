"""Single request-level probe: no tool dispatch, no baseline score."""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from backends.groq_backend import GroqBackend
from benchmarks.evidence import install_transport_capture
from benchmarks.runner import atomic_json, digest, provenance
from config.credentials import redact


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--cooldown", type=float, default=60)
    args = parser.parse_args()
    reference = json.loads(Path(args.reference).read_text(encoding="utf-8"))
    case = next(a for a in reference["attempts"] if a["task"] == "D05")
    original = next(
        e["payload"] for e in case["interactions"] if e["kind"] == "transport_request"
    )
    first_response = next(
        e["payload"]
        for e in case["interactions"]
        if e["kind"] == "transport_response" and e.get("status_code") == 200
    )
    body = {**original, "parallel_tool_calls": False}
    events = []
    backend = GroqBackend(
        model=body["model"],
        temperature=body["temperature"],
        max_tokens=body["max_tokens"],
    )
    backend.client.timeout = 400
    backend.client.max_retries = 0
    install_transport_capture(
        backend, lambda kind, data: events.append({"kind": kind, **data})
    )
    # An explicit cooldown keeps this probe outside the previous case's minute.
    time.sleep(max(0, min(args.cooldown, 60)))
    result = {
        "scope": "single request serialization probe; no tools executed, not a complete D05 run",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "provenance": provenance(),
        "reference_attempt": case["id"],
        "reference_request_sha256": digest(original),
        "requested_change": {"parallel_tool_calls": False},
        "original_tool_call_count": len(
            first_response["choices"][0]["message"].get("tool_calls") or []
        ),
    }
    try:
        response = backend.client.chat.completions.create(**body)
        backend.record_usage(response)
        calls = response.choices[0].message.tool_calls or []
        result.update(
            status="completed",
            tool_call_count=len(calls),
            constraint_satisfied=len(calls) == 1,
            response=response.model_dump(),
            usage=backend.last_usage,
        )
    except Exception as exc:
        result.update(
            status="error",
            error_type=type(exc).__name__,
            message=redact(str(exc))[:800],
        )
    finally:
        result["interactions"] = events
        atomic_json(Path(args.output) / "probe.json", result)
        backend.client.close()
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"interactions", "response", "message"}
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
