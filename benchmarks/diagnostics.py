"""Separate capability diagnostics; never substitutes for B01–B05 qualification."""

import argparse
import csv
import html
import json
from pathlib import Path
import threading
import time
import hashlib
import uuid
from datetime import datetime, timezone

TASKS = ("D01", "D02", "D03", "D04", "D05", "D06")
TITLES = {
    "D01": "Instruction and JSON",
    "D02": "One fixture read",
    "D03": "One calculator call",
    "D04": "Formulate arithmetic",
    "D05": "Conflicting source evidence",
    "D06": "Controlled error recovery",
}


def fixture(task, seed):
    specs = {
        "D01": (
            {},
            'Return only JSON {"status":"ready","count":3}. No tools are needed.',
        ),
        "D02": (
            {"record": "The verification code is amber-47."},
            'Read record with read_fixture. Return JSON {"code":"observed code"}.',
        ),
        "D03": (
            {},
            'Call calculator once for 7 * 9, then return JSON {"result":number} using its observed result.',
        ),
        "D04": (
            {
                "invoice": "Three items cost 14 credits each. Subtract a single 5-credit discount from the whole purchase."
            },
            'Read invoice. Extract the numbers and call calculator with a numeric expression for the total. Return JSON {"total":number}.',
        ),
        "D05": (
            {
                "archive": "Old notice: opening is 09:00.",
                "notice": "Current notice supersedes archive. Opening is 11:00.",
            },
            'Read archive and notice. Resolve the conflict using the current notice. Return JSON {"opens":"HH:MM","source":"document name","quote":"exact supporting text"}. Cite text actually read.',
        ),
        "D06": (
            {
                "primary": "Primary is intentionally unavailable on its first read.",
                "backup": "Verified release is 3.2.",
            },
            'Read primary. If it fails, read backup instead; do not repeatedly retry primary. Return JSON {"release":"version","source":"document name","recovered":true} based on the observed source.',
        ),
    }
    documents, prompt = specs[task]
    return {
        "task": task,
        "seed": seed,
        "documents": documents,
        "prompt": prompt
        + "\nReturn the requested JSON as your final answer. Use only the supplied local tools.",
    }


def expected(task, seed):
    return {
        "D01": {"status": "ready", "count": 3},
        "D02": {"code": "amber-47"},
        "D03": {"result": 63},
        "D04": {"total": 37},
        "D05": {"opens": "11:00", "source": "notice"},
        "D06": {"release": "3.2", "source": "backup", "recovered": True},
    }[task]


def tools_for(task):
    return {
        "D01": [],
        "D02": ["read_fixture"],
        "D03": ["calculator"],
        "D04": ["read_fixture", "calculator"],
        "D05": ["read_fixture"],
        "D06": ["read_fixture"],
    }[task]


def validate_report(task, report, documents, reads):
    required = set(expected(task, 1))
    if task == "D05":
        required.add("quote")
    if not required.issubset(report):
        return "Missing required report fields: " + ", ".join(
            sorted(required - set(report))
        )
    if task in {"D03", "D04"} and "__calculator__" not in reads:
        return "Call the calculator with the required numeric expression and use its observed result before finishing."
    if task == "D06" and "backup" not in reads:
        return "Read the backup source after the controlled error before finishing."
    if task in {"D02", "D04", "D05"} and set(documents) - reads:
        return "Read required documents: " + ", ".join(sorted(set(documents) - reads))
    if task == "D05" and (
        report.get("source") not in reads
        or not isinstance(report.get("quote"), str)
        or not report["quote"].strip()
        or report["quote"] not in documents.get(report.get("source"), "")
    ):
        return "Use an exact quotation from an observed source."
    return None


def score(data, answer, events):
    from benchmarks.tasks import parse_answer

    try:
        report = parse_answer(answer)
    except (ValueError, TypeError, AttributeError):
        return {"score": 0, "passed": False, "checks": {"valid_json": False}}
    task = data["task"]
    reads = {
        e["name"]
        for e in events
        if e.get("operation") == "read" and e.get("status") == "ok"
    }
    if any(
        e.get("operation") == "calculate" and e.get("status") == "ok" for e in events
    ):
        reads.add("__calculator__")
    checks = {
        "valid_json": True,
        "report_contract": validate_report(task, report, data["documents"], reads)
        is None,
    }
    checks.update(
        {k: report.get(k) == v for k, v in expected(task, data["seed"]).items()}
    )
    if task in {"D03", "D04"}:
        checks["calculator_executed"] = any(
            e.get("operation") == "calculate" and e.get("status") == "ok"
            for e in events
        )
    if task == "D06":
        checks["observed_failure"] = any(
            e.get("status") == "injected_failure" for e in events
        )
        checks["read_backup"] = "backup" in reads
        checks["bounded_primary_retries"] = (
            sum(e.get("name") == "primary" for e in events) <= 1
        )
    return {
        "score": round(100 * sum(checks.values()) / len(checks), 2),
        "passed": all(checks.values()),
        "checks": checks,
    }


def write_reports(record, output):
    from benchmarks.runner import atomic_json

    rows = []
    for a in record["attempts"]:
        rows.append(
            {
                "model": record["configs"][a["config_index"]]["agents"][0]["model"],
                "backend": record["configs"][a["config_index"]]["agents"][0]["backend"],
                "task": a["task"],
                "passed": a["evaluation"]["passed"],
                "status": a["status"],
                "category": a.get("outcome_category", a["status"]),
                "seconds": a["elapsed_seconds"],
                "score": a["evaluation"]["score"],
            }
        )
    atomic_json(output / "summary.json", rows)
    with (output / "comparison.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=list(rows[0]) if rows else ["model", "task"]
        )
        writer.writeheader()
        writer.writerows(rows)
    markup = (
        "<html><meta charset='utf-8'><title>Capability diagnostics</title><h1>Capability diagnostics</h1><p>Separate from baseline qualification. Every attempt has saved transport and tool evidence.</p><table border='1'><tr>"
        + "".join("<th>" + html.escape(k) + "</th>" for k in (rows[0] if rows else {}))
        + "</tr>"
    )
    for row in rows:
        markup += (
            "<tr>"
            + "".join("<td>" + html.escape(str(v)) + "</td>" for v in row.values())
            + "</tr>"
        )
    (output / "report.html").write_text(markup + "</table></html>", encoding="utf-8")


def run(configs, output, stopped=None, resume=False):
    from benchmarks.runner import isolated_attempt, atomic_json, provenance, digest

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "experiment.json"
    settings = [c.model_dump() for c in configs]
    source_root = Path(__file__).resolve().parents[1]
    fingerprints = {
        name: hashlib.sha256((source_root / name).read_bytes()).hexdigest()
        for name in (
            "benchmarks/diagnostics.py",
            "benchmarks/runner.py",
            "core/agent.py",
            "backends/base_backend.py",
            "backends/tool_protocol.py",
            "planner/react_planner.py",
        )
    }
    fixture_hashes = {task: digest(fixture(task, 1)) for task in TASKS}
    identity = digest(
        {
            "configs": settings,
            "tasks": TASKS,
            "contract": "diagnostic-v3-json-call",
            "source_hashes": fingerprints,
            "fixture_hashes": fixture_hashes,
        }
    )
    if resume:
        record = json.loads(path.read_text(encoding="utf-8"))
        if record["identity"] != identity:
            raise ValueError("Diagnostic resume settings differ")
    else:
        if path.exists():
            raise ValueError("Use a new output directory or resume")
        record = {
            "id": output.name,
            "suite": "capability-diagnostics-v1",
            "identity": identity,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "provenance": provenance(),
            "configs": settings,
            "scheduled": len(configs) * len(TASKS),
            "attempts": [],
            "status": "running",
            "scheduling": "configuration_first",
            "source_hashes": fingerprints,
            "fixture_hashes": fixture_hashes,
        }
    stop = stopped or threading.Event()
    done = {(a["config_index"], a["task"]) for a in record["attempts"]}
    atomic_json(path, record)
    last_case_finished = None
    try:
        for index, original in enumerate(configs):
            if len(original.agents) != 1:
                raise ValueError(
                    "Diagnostics require independent single-agent configurations"
                )
            for task in TASKS:
                if (index, task) in done:
                    continue
                if stop.is_set():
                    record["status"] = "cancelled"
                    return record
                config = original.model_copy(deep=True)
                config.auto_baseline_setup = False
                config.capture_diagnostics = True
                config.agents[0].tools = tools_for(task)
                progress = {
                    "config_index": index,
                    "task": task,
                    "model": config.agents[0].model,
                }
                delay = (
                    max(
                        0,
                        config.model_min_interval_seconds
                        - (time.monotonic() - last_case_finished),
                    )
                    if last_case_finished is not None
                    else 0
                )
                if delay:
                    atomic_json(
                        output / "progress.json",
                        {
                            **progress,
                            "phase": "provider pacing",
                            "wait_seconds": round(delay, 1),
                        },
                    )
                    if stop.wait(delay):
                        record["status"] = "cancelled"
                        return record
                atomic_json(output / "progress.json", {**progress, "phase": "running"})

                def event(value):
                    if value.get("type") in {
                        "transport_request",
                        "transport_response",
                        "error_diagnostic",
                        "action_response_rejected",
                    }:
                        with (output / "activity.jsonl").open(
                            "a", encoding="utf-8"
                        ) as stream:
                            stream.write(json.dumps(value, ensure_ascii=False) + "\n")

                result = isolated_attempt(config, task, 1, stopped=stop, on_event=event)
                last_case_finished = time.monotonic()
                result.update(config_index=index, repetition=0)
                record["attempts"].append(result)
                atomic_json(output / (result["id"] + ".json"), result)
                atomic_json(path, record)
                write_reports(record, output)
                print(
                    json.dumps(
                        {
                            **progress,
                            "completed": len(record["attempts"]),
                            "scheduled": record["scheduled"],
                            "status": result["status"],
                            "passed": result["evaluation"]["passed"],
                        }
                    ),
                    flush=True,
                )
        record["status"] = "cancelled" if stop.is_set() else "completed"
        return record
    finally:
        atomic_json(path, record)
        write_reports(record, output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config")
    parser.add_argument("--output")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--replay")
    args = parser.parse_args()
    if args.replay:
        from benchmarks.evidence import replay_attempt

        data = json.loads(Path(args.replay).read_text(encoding="utf-8"))
        print(json.dumps(replay_attempt(data), indent=2))
        return
    from benchmarks.runner import ExperimentConfig

    configs = [
        ExperimentConfig.model_validate(c)
        for c in json.loads(Path(args.config).read_text(encoding="utf-8"))
    ]
    run(
        configs,
        args.output or str(Path("diagnostic-results") / uuid.uuid4().hex),
        resume=args.resume,
    )


if __name__ == "__main__":
    main()
