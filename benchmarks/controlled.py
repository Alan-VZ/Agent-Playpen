"""Checkpointed matched-task study. Arm A is diagnostic, never a baseline pass."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import csv
import html
import hashlib
import json
import multiprocessing
from pathlib import Path
import queue
import time
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from benchmarks.runner import (
    ExperimentConfig,
    Member,
    Budget,
    MeteredBackend,
    attempt,
    make_backend,
    atomic_json,
    digest,
    provenance,
)
from benchmarks.tasks import fixture, score, selected_tasks, baseline_setup
from benchmarks.outcomes import category, safe_error
from config.credentials import redact
from debugging.dashboard.model_sources import model_lease, local_state, select_model


class StudyModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["lm_studio", "openrouter", "groq"]
    model: str = Field(min_length=1, max_length=500)
    base_url: str | None = None


class StudyPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    models: list[StudyModel] = Field(min_length=1, max_length=12)
    seeds: list[int] = Field(
        default_factory=lambda: list(range(1, 6)), min_length=1, max_length=20
    )
    rounds: int = Field(default=2, ge=1, le=5)
    timeout_seconds: float = Field(default=180, ge=1, le=1800)
    max_output_tokens: int = Field(default=2048, ge=64, le=16384)
    max_iterations: int = Field(default=10, ge=1, le=100)
    temperature: float = Field(default=0, ge=0, le=2)
    cloud_interval_seconds: float = Field(default=4, ge=0, le=60)
    tasks: list[str] = Field(default_factory=lambda: ["B01"])

    @model_validator(mode="after")
    def validate_identity(self):
        selected_tasks(self.tasks)
        if len(set(self.seeds)) != len(self.seeds) or any(s < 1 for s in self.seeds):
            raise ValueError("Seeds must be distinct positive integers.")
        if len({(m.provider, m.model) for m in self.models}) != len(self.models):
            raise ValueError("Duplicate model IDs in study plan.")
        if any(
            m.provider == "openrouter" and not m.model.endswith(":free")
            for m in self.models
        ):
            raise ValueError("This study permits only free OpenRouter model IDs.")
        return self


def source_fingerprint():
    root = Path(__file__).resolve().parents[1]
    files = []
    for folder in [
        "benchmarks",
        "core",
        "planner",
        "backends",
        "tools",
        "config",
        "debugging",
        "memory",
    ]:
        for path in sorted((root / folder).rglob("*.py")):
            files.append(
                (
                    str(path.relative_to(root)),
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
            )
    return digest(files)


def cases(plan):
    """Keep model identities/order fixed; counterbalance arm order on repeats."""
    rows = []
    groups = {}
    for index, model in enumerate(plan.models):
        groups.setdefault(model.provider, []).append(index)
    for round_index in range(plan.rounds):
        for provider, indices in groups.items():
            if provider == "lm_studio":
                order = [
                    (i, seed, task)
                    for i in indices
                    for seed in plan.seeds
                    for task in plan.tasks
                ]
            else:
                # Spread scarce cloud quota across models and task types. Keep
                # local models grouped to avoid loading a model for every case.
                order = [
                    (i, seed, plan.tasks[(offset + j) % len(plan.tasks)])
                    for seed in plan.seeds
                    for offset in range(len(plan.tasks))
                    for j, i in enumerate(indices)
                ]
            for model_index, seed, task in order:
                model = plan.models[model_index]
                arms = (
                    ["A", "B"]
                    if (round_index + plan.seeds.index(seed)) % 2 == 0
                    else ["B", "A"]
                )
                for arm in arms:
                    rows.append(
                        {
                            "case_id": f"r{round_index + 1}-m{model_index + 1}-s{seed}-{arm}"
                            + (f"-{task}" if plan.tasks != ["B01"] else ""),
                            "round": round_index + 1,
                            "model_index": model_index,
                            "seed": seed,
                            "arm": arm,
                            "task": task,
                            "provider": model.provider,
                            "model": model.model,
                        }
                    )
    return rows


def direct_messages(data):
    # Keep the task contract, remove only the tool-transport instruction.
    contract = data["prompt"].split("\nUse read_fixture(name)", 1)[0]
    if data["task"] == "B03":
        contract = contract.replace(
            "Write the same JSON to report.json using write_artifact. ", ""
        )
    if data["task"] == "B04":
        contract = contract.replace(
            "Retrieve primary, empty and backup; recover from primary error without looping.",
            "Use the supplied source snapshots to describe the correct recovery result; no retrieval is performed in this diagnostic.",
        )
    inputs = "\n\n".join(
        "[" + name + "]\n" + body for name, body in data["documents"].items()
    )
    return [
        {
            "role": "system",
            "content": "Solve the task using the supplied input documents. No tools are available. Return only the requested final JSON.",
        },
        {
            "role": "user",
            "content": contract
            + "\nFixture seed: "
            + str(data["seed"])
            + "\n\nInput documents:\n"
            + inputs,
        },
    ]


def direct_attempt(
    config, seed, stopped, publish, backend_factory=make_backend, task="B01"
):
    data = fixture(task, seed)
    budget = Budget(config, stopped, publish)
    backend = None
    started = time.monotonic()
    result = {
        "id": uuid.uuid4().hex,
        "task": task,
        "seed": seed,
        "status": "execution_failed",
        "baseline_eligible": False,
        "diagnostic_correct": False,
        "agents": [],
        "tool_events": [],
        "artifacts": {},
        "fixture_hash": digest(data),
    }
    try:
        member = config.agents[0]
        with model_lease(
            member.backend,
            member.model,
            member.base_url,
            deadline=budget.deadline,
            stopped=stopped,
            on_status=lambda text: publish({"type": "status", "content": text}),
        ) as actual:
            member = member.model_copy(update={"model": actual})
            backend = backend_factory(member, config)
            answer = MeteredBackend(backend, budget, "agent-1").chat(
                direct_messages(data)
            )
            evaluation = score(data, answer, [], {})
            answer_checks = {
                k: v
                for k, v in evaluation["checks"].items()
                if k
                not in {
                    "read_inputs",
                    "no_violations",
                    "artifact",
                    "observed_failure",
                    "bounded_reads",
                    "checked_empty",
                }
            }
            result.update(
                status="completed",
                answer=redact(answer),
                evaluation=evaluation,
                answer_checks=answer_checks,
                diagnostic_correct=bool(answer_checks) and all(answer_checks.values()),
                agents=[
                    {
                        "agent_id": "agent-1",
                        "status": "success",
                        "answer": redact(answer),
                    }
                ],
            )
    except Exception as exc:
        result["agents"] = [
            {"agent_id": "agent-1", "status": "error", "answer": "", **safe_error(exc)}
        ]
        result["evaluation"] = {
            "passed": False,
            "score": 0,
            "checks": {"completed_response": False},
        }
    finally:
        if backend is not None:
            client = getattr(backend, "client", None)
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
    # A must never appear as a strict baseline pass, even with perfect arithmetic.
    result["evaluation"]["passed"] = False
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    result["usage"] = {
        "model_calls": budget.model_calls,
        "reserved_tokens": budget.reserved_tokens,
        "tool_requests": 0,
    }
    result["outcome_category"] = category(result)
    return redact(result)


def _worker(case, raw_config, stop, output, events):
    def publish(event):
        try:
            events.put_nowait(redact(event))
        except queue.Full:
            pass

    config = ExperimentConfig.model_validate(raw_config)
    try:
        result = (
            direct_attempt(
                config, case["seed"], stop, publish, task=case.get("task", "B01")
            )
            if case["arm"] == "A"
            else attempt(
                config,
                case.get("task", "B01"),
                case["seed"],
                stopped=stop,
                on_event=publish,
            )
        )
        result["baseline_eligible"] = case["arm"] == "B"
        result["outcome_category"] = category(result)
        output.put(result)
    except Exception as exc:
        output.put(
            {
                "status": "execution_failed",
                "agents": [{"status": "error", **safe_error(exc)}],
                "evaluation": {
                    "passed": False,
                    "checks": {"worker_completed": False},
                    "score": 0,
                },
                "outcome_category": "execution_error",
            }
        )


def isolated_case(case, config, diagnostic_path, on_event=None, stop_file=None):
    context = multiprocessing.get_context("spawn")
    output = context.Queue(1)
    events = context.Queue(256)
    stop = context.Event()
    process = context.Process(
        target=_worker,
        args=(case, config.model_dump(), stop, output, events),
        daemon=True,
    )
    started = time.monotonic()
    captured = []
    result = None
    cancel_at = None

    def drain():
        while True:
            try:
                event = events.get_nowait()
            except (queue.Empty, EOFError, OSError):
                return
            captured.append(event)
            with diagnostic_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(redact(event), ensure_ascii=True) + "\n")
            if on_event:
                on_event(event)

    try:
        process.start()
        while time.monotonic() - started < config.timeout_seconds + 10:
            if stop_file is not None and stop_file.exists():
                stop.set()
                cancel_at = cancel_at or time.monotonic()
                if time.monotonic() - cancel_at >= 2:
                    break
            try:
                result = output.get(timeout=0.1)
            except queue.Empty:
                pass
            drain()
            if result is not None:
                break
            if not process.is_alive():
                try:
                    result = output.get(timeout=0.5)
                except queue.Empty:
                    pass
                break
        if result is None:
            result = {
                "status": "cancelled"
                if cancel_at is not None
                else "timeout"
                if process.is_alive()
                else "execution_failed",
                "agents": [],
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "evaluation": {
                    "passed": False,
                    "score": 0,
                    "checks": {"worker_completed": False},
                },
                "baseline_eligible": case["arm"] == "B",
                "diagnostic_correct": False,
                "usage_incomplete": True,
            }
        result["outcome_category"] = category(result)
        result["diagnostic_events"] = len(captured)
        result["partial_trace"] = [
            e
            for e in captured
            if e.get("type") not in {"request_diagnostic", "response_diagnostic"}
        ][-40:]
        return redact(result)
    finally:
        stop.set()
        process.join(timeout=0.5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)
        if process.is_alive():
            process.kill()
            process.join(timeout=2)
        drain()
        output.close()
        events.close()


def summarize(record):
    return [
        row
        for task in record["plan"].get("tasks", ["B01"])
        for row in _summarize_task(record, task)
    ]


def _summarize_task(record, task):
    rows = []
    for round_index in range(1, record["plan"]["rounds"] + 1):
        for model_index, model in enumerate(record["plan"]["models"]):
            results = [
                r
                for r in record["results"]
                if r["round"] == round_index
                and r["model_index"] == model_index
                and r.get("task", "B01") == task
            ]
            row = {
                "round": round_index,
                "provider": model["provider"],
                "model": model["model"],
                "task": task,
                "planned_per_arm": len(record["plan"]["seeds"]),
            }
            for arm in ["A", "B"]:
                items = [r for r in results if r["arm"] == arm]
                row[arm + "_completed"] = len(items)
                row[arm + "_attempted"] = sum(r.get("attempted", True) for r in items)
                row[arm + "_unavailable"] = sum(
                    r.get("attempted") is False for r in items
                )
                row[arm + "_correct"] = sum(
                    bool(r.get("diagnostic_correct"))
                    if arm == "A"
                    else bool(r.get("evaluation", {}).get("passed"))
                    for r in items
                )
                row[arm + "_categories"] = dict(
                    Counter(r.get("outcome_category", "unknown") for r in items)
                )
            rows.append(row)
    return rows


def render(record, target):
    rows = summarize(record)
    with (target / "comparison.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as stream:
        fields = [
            "round",
            "task",
            "provider",
            "model",
            "planned_per_arm",
            "A_completed",
            "A_attempted",
            "A_unavailable",
            "A_correct",
            "A_categories",
            "B_completed",
            "B_attempted",
            "B_unavailable",
            "B_correct",
            "B_categories",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {k: json.dumps(v) if isinstance(v, dict) else v for k, v in row.items()}
            )
    headings = [
        "Round",
        "Task",
        "Provider",
        "Model",
        "A correct / processed",
        "B strict passes / processed",
        "A outcomes",
        "B outcomes",
    ]
    body = ""
    for row in rows:
        values = [
            row["round"],
            row["task"],
            row["provider"],
            row["model"],
            str(row["A_correct"]) + "/" + str(row["A_completed"]),
            str(row["B_correct"]) + "/" + str(row["B_completed"]),
            json.dumps(row["A_categories"]),
            json.dumps(row["B_categories"]),
        ]
        body += (
            "<tr>"
            + "".join("<td>" + html.escape(str(v)) + "</td>" for v in values)
            + "</tr>"
        )
    page = (
        '<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="30"><title>Controlled A/B study</title><style>body{font:15px/1.5 system-ui;margin:30px}table{border-collapse:collapse}td,th{border:1px solid #aaa;padding:8px;text-align:left}</style><h1>Controlled baseline A/B study</h1><p>'
        + html.escape(record["status"])
        + " · "
        + str(len(record["results"]))
        + "/"
        + str(record["scheduled"])
        + " attempts</p><p>Arm A is a direct-answer diagnostic, never a baseline pass. Arm B uses the unchanged scorer and real fixture tool. The same models and seeds repeat in both rounds. Provider/timeout/protocol/answer failures remain distinct.</p><table><tr>"
        + "".join("<th>" + h + "</th>" for h in headings)
        + "</tr>"
        + body
        + "</table>"
    )
    (target / "comparison.html").write_text(page, encoding="utf-8")


def run(plan, target, resume=False):
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    (target / "diagnostics").mkdir(exist_ok=True)
    identity = digest(plan.model_dump())
    path = target / "study.json"
    schedule = cases(plan)
    if path.exists():
        if not resume:
            raise ValueError("Study exists; use --resume.")
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("source_fingerprint") != source_fingerprint():
            raise ValueError("Source files changed; create a new controlled study.")
        if record["identity"] != identity:
            raise ValueError("Resume plan changed.")
        if record["provenance"]["commit"] != provenance()["commit"]:
            raise ValueError("Source commit changed; create a new controlled study.")
        (target / "STOP").unlink(missing_ok=True)
    else:
        record = {
            "id": target.name,
            "status": "running",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "plan": plan.model_dump(),
            "identity": identity,
            "provenance": provenance(),
            "source_fingerprint": source_fingerprint(),
            "task_contract_hash": digest(
                {task: fixture(task, 1) for task in plan.tasks}
            ),
            "scheduled": len(schedule),
            "results": [],
            "current": None,
            "quota_policy": "Finish batch; mark quota-blocked cases unavailable. No paid fallback.",
            "tool_policy": "Only free local read_fixture, calculator and isolated write_artifact. No live search or paid tool APIs.",
            "diagnostic_policy": "Arm A scores answer fields only; it excludes actual reads, writes and recovery execution. B02/B03/B05 repeat the same frozen source contents across seeds.",
        }
        record["provenance"]["cache"] = (
            "Provider cache uncontrolled; fresh process and conversation per case."
        )
    done = {r["case_id"] for r in record["results"]}
    last_request = {}
    try:
        for case in schedule:
            if source_fingerprint() != record["source_fingerprint"]:
                record["status"] = "source_changed"
                break
            if case["case_id"] in done:
                continue
            if (target / "STOP").exists():
                record["status"] = "stopped"
                break
            if case["provider"] in record.get("quota_blocked_providers", {}):
                record["results"].append(
                    {
                        **case,
                        "status": "unavailable",
                        "outcome_category": "provider_quota_unavailable",
                        "attempted": False,
                        "evaluation": {"passed": False},
                        "message": record["quota_blocked_providers"][case["provider"]],
                    }
                )
                done.add(case["case_id"])
                atomic_json(path, record)
                render(record, target)
                continue
            model = plan.models[case["model_index"]]
            interval = (
                plan.cloud_interval_seconds if model.provider != "lm_studio" else 0
            )
            wait = max(
                0, last_request.get(model.provider, 0) + interval - time.monotonic()
            )
            if wait:
                time.sleep(wait)
            config = ExperimentConfig(
                name=case["case_id"],
                agents=[
                    Member(
                        backend=model.provider,
                        model=model.model,
                        base_url=model.base_url,
                        temperature=plan.temperature,
                        tools=baseline_setup([case["task"]])["tools"],
                    )
                ],
                max_concurrency=1,
                max_iterations=plan.max_iterations,
                max_output_tokens=plan.max_output_tokens,
                timeout_seconds=plan.timeout_seconds,
                capture_diagnostics=True,
                model_min_interval_seconds=interval,
            )
            record["current"] = {
                **case,
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
            record["status"] = "running"
            atomic_json(path, record)
            render(record, target)
            print("START " + json.dumps(case), flush=True)

            def progress(event):
                if event.get("type") == "request_diagnostic":
                    last_request[model.provider] = time.monotonic()
                record["current"]["latest_event"] = {
                    "type": event.get("type"),
                    "content": str(event.get("content", ""))[:500],
                }
                if event.get("type") in {
                    "model_request",
                    "model_response",
                    "error",
                    "warning",
                    "request_diagnostic",
                }:
                    atomic_json(path, record)

            diagnostic = target / "diagnostics" / (case["case_id"] + ".jsonl")
            # Each case is checkpointed; previous evidence is never overwritten.
            if diagnostic.exists():
                diagnostic.rename(
                    diagnostic.with_name(
                        diagnostic.stem
                        + "-interrupted-"
                        + uuid.uuid4().hex[:8]
                        + ".jsonl"
                    )
                )
            result = isolated_case(case, config, diagnostic, progress, target / "STOP")
            result.update(case)
            result["attempted"] = True
            messages = " ".join(
                str(a.get("message", "")) for a in result.get("agents", [])
            ).lower()
            if (
                case["provider"] == "openrouter"
                and result.get("outcome_category") == "provider_rate_limit"
                and any(
                    term in messages
                    for term in [
                        "free-models-per-day",
                        "free models per day",
                        "daily",
                        "per day",
                        "per-day",
                    ]
                )
            ):
                record.setdefault("quota_blocked_providers", {})["openrouter"] = (
                    "OpenRouter daily free-request quota exhausted; skipped without making a request."
                )
            result["diagnostic_file"] = str(diagnostic.relative_to(target))
            record["results"].append(result)
            done.add(case["case_id"])
            record["current"] = None
            atomic_json(path, record)
            render(record, target)
            print(
                "RESULT "
                + json.dumps(
                    {
                        **case,
                        "category": result["outcome_category"],
                        "direct_correct": result.get("diagnostic_correct"),
                        "baseline_pass": result.get("evaluation", {}).get("passed"),
                        "seconds": result.get("elapsed_seconds"),
                    }
                ),
                flush=True,
            )
        else:
            record["status"] = "completed"
    except BaseException:
        record["status"] = "interrupted"
        raise
    finally:
        atomic_json(path, record)
        render(record, target)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    plan = StudyPlan.model_validate(
        json.loads(Path(args.plan).read_text(encoding="utf-8"))
    )
    if len({(m.provider, m.model) for m in plan.models}) != len(plan.models):
        raise ValueError("Duplicate model IDs in study plan.")
    target = Path(args.output)
    target.mkdir(parents=True, exist_ok=True)
    snapshot_path = target / "original-local-model.json"
    if (
        any(m.provider == "lm_studio" for m in plan.models)
        and not snapshot_path.exists()
    ):
        state = local_state("lm_studio", "http://localhost:1234/v1")
        atomic_json(snapshot_path, state)
    try:
        run(plan, target, args.resume)
    finally:
        if snapshot_path.exists():
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            loaded = [m["id"] for m in snapshot.get("models", []) if m.get("loaded")]
            if loaded:
                try:
                    restored = select_model(
                        "lm_studio", loaded[0], "http://localhost:1234/v1"
                    )
                    atomic_json(
                        target / "restoration.json",
                        {"status": "restored", "result": restored},
                    )
                except Exception as exc:
                    atomic_json(
                        target / "restoration.json",
                        {"status": "needs_verification", **safe_error(exc)},
                    )


if __name__ == "__main__":
    main()
