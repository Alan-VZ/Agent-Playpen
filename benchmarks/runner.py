"""Bounded experiments using the production Agent loop and objective scorers."""
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
import multiprocessing
import queue
from pathlib import Path
import platform
import os
import subprocess
import threading
import time
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backends.backend_factory import BackendFactory
from config.credentials import redact
from core.agent import Agent
from debugging.tracer import Tracer
from memory.memory_manager import MemoryManager
from planner.react_planner import ReActPlanner
from planner.cot_planner import CoTPlanner
from planner.tree_planner import TreePlanner
from tools.base_tool import BaseTool
from tools.packs.utils.calculator_tool import CalculatorTool
from tools.tool_registry import ToolRegistry
from benchmarks.tasks import SUITE, TASKS, fixture, score, expected, selected_tasks, baseline_setup


class Member(BaseModel):
    model_config = ConfigDict(extra="forbid")
    backend: str = "lm_studio"
    model: str = "local-model"
    role: str = Field(default="Independent researcher", max_length=2000)
    planner: str = "react"
    temperature: float = Field(default=0, ge=0, le=2)
    base_url: str | None = Field(default=None, max_length=500)
    tools: list[Literal["read_fixture", "write_artifact", "calculator"]] = Field(default_factory=lambda: ["read_fixture", "write_artifact", "calculator"])


class ExperimentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(default="single-local", min_length=1, max_length=100)
    agents: list[Member] = Field(default_factory=lambda: [Member()], min_length=1, max_length=10)
    max_concurrency: int = Field(default=2, ge=1, le=10)
    max_iterations: int = Field(default=15, ge=1, le=100)
    max_output_tokens: int = Field(default=2048, ge=64, le=16384)
    token_reservation_limit: int = Field(default=300000, ge=1000, le=10000000)
    tool_request_limit: int = Field(default=120, ge=1, le=1000)
    timeout_seconds: float = Field(default=180, ge=1, le=1800)
    # Optional declared conservative aggregate rates, not provider invoices.
    usd_per_million_input: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    usd_per_million_output: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    rate_source: str | None = Field(default=None, max_length=500)
    dollar_limit: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    auto_baseline_setup: bool = True


def prepare_baseline_configs(configs, tasks):
    setup = baseline_setup(tasks)
    result = []
    for original in configs:
        config = original.model_copy(deep=True)
        if config.auto_baseline_setup:
            for member in config.agents:
                member.planner = setup["planner"]
                member.tools = list(setup["tools"])
        result.append(config)
    return result


class Budget:
    def __init__(self, config, stopped=None, on_event=None):
        self.config = config
        self.stopped = threading.Event()
        self.external_stop = stopped or threading.Event()
        self.deadline = time.monotonic() + config.timeout_seconds
        self.lock = threading.RLock()
        self.reserved_tokens = 0
        self.tool_requests = 0
        self.reserved_cost = 0.0
        self.model_calls = []
        self.tool_events = []
        self.artifacts = {}
        self.reservations_closed = False
        self.on_event = on_event

    def active(self):
        if self.external_stop.is_set():
            self.stopped.set()
        if self.stopped.is_set() or self.reservations_closed:
            raise RuntimeError("Run cancelled; further calls and artifacts are blocked")
        if time.monotonic() >= self.deadline:
            self.stopped.set()
            raise TimeoutError("Attempt deadline exceeded")

    def reserve_model(self, messages, agent_id):
        # UTF-8 bytes plus conservative message framing allowance; not actual usage.
        inputs = len(json.dumps(messages, ensure_ascii=False).encode("utf-8")) + 1024
        outputs = self.config.max_output_tokens
        with self.lock:
            self.active()
            if self.reserved_tokens + inputs + outputs > self.config.token_reservation_limit:
                raise RuntimeError("Aggregate token reservation limit reached")
            cost = None
            if self.config.usd_per_million_input is not None and self.config.usd_per_million_output is not None:
                cost = (inputs * self.config.usd_per_million_input + outputs * self.config.usd_per_million_output) / 1e6
            if self.config.dollar_limit is not None and (cost is None or self.reserved_cost + cost > self.config.dollar_limit):
                raise RuntimeError("Estimated dollar reservation limit reached or rates unavailable")
            self.reserved_tokens += inputs + outputs
            self.reserved_cost += cost or 0
            call = {"agent_id": agent_id, "reserved_input": inputs, "reserved_output": outputs,
                    "estimated_reserved_usd": cost, "actual_tokens": None, "status": "started"}
            self.model_calls.append(call)
            return call

    def tool(self, operation, name, agent_id):
        self.active()
        if self.tool_requests >= self.config.tool_request_limit:
            raise RuntimeError("Aggregate tool request limit reached")
        self.tool_requests += 1
        event = {"agent_id": agent_id, "operation": operation, "name": name, "status": "ok"}
        self.tool_events.append(event)
        return event

    def publish(self, event):
        with self.lock:
            if not self.reservations_closed and not self.stopped.is_set() and self.on_event:
                self.on_event(redact(event))


class ReadFixture(BaseTool):
    name = "read_fixture"
    description = "Read a named frozen input document. Unknown names are denied."
    parameters = {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}

    def __init__(self, data, budget, agent_id):
        self.data, self.budget, self.agent_id = data, budget, agent_id
        self.counts = {}

    def run(self, **kwargs):
        name = kwargs.get("name", "")
        with self.budget.lock:
            event = self.budget.tool("read", name, self.agent_id)
            if name not in self.data["documents"]:
                event["status"] = "denied"
                return "[ERROR] Unknown fixture; arbitrary filesystem access is unavailable."
            self.counts[name] = self.counts.get(name, 0) + 1
            if self.data["task"] == "B04" and name == "primary" and self.counts[name] == 1:
                event["status"] = "injected_failure"
                return "[ERROR] Temporary source failure. Alternative source: backup. No automatic retry."
            return self.data["documents"][name]


class WriteArtifact(BaseTool):
    name = "write_artifact"
    description = "Write report.json to this agent's isolated artifact collection."
    parameters = {"type": "object", "properties": {"name": {"type": "string"}, "content": {"type": "string"}}, "required": ["name", "content"]}

    def __init__(self, budget, agent_id):
        self.budget, self.agent_id = budget, agent_id

    def run(self, **kwargs):
        with self.budget.lock:
            event = self.budget.tool("write", kwargs.get("name", ""), self.agent_id)
            content = kwargs.get("content", "")
            if kwargs.get("name") != "report.json" or not isinstance(content, str) or len(content) > 20000:
                event["status"] = "denied"
                return "[ERROR] Only bounded report.json artifacts are allowed."
            self.budget.artifacts.setdefault(self.agent_id, {})["report.json"] = redact(content)
            return "Saved report.json"


class BoundedCalculator(CalculatorTool):
    description = "Evaluate ONE numeric arithmetic expression of at most 200 characters using + - * / % and parentheses. No JSON, variables, scripts, or exponentiation. Return the final report through FINISH, not this calculator."
    parameters = {"type":"object", "properties":{"expression":{"type":"string", "maxLength":200,
                  "description":"Numeric arithmetic only, for example '(3 + 4) - 2'. Not a JSON object or program."}}, "required":["expression"]}

    def __init__(self, budget, agent_id):
        self.budget, self.agent_id = budget, agent_id

    def run(self, **kwargs):
        with self.budget.lock:
            event = self.budget.tool("calculate", "calculator", self.agent_id)
            expression = kwargs.get("expression", "")
            if not isinstance(expression, str) or not expression.strip():
                event["status"] = "invalid_arguments"
                raise ValueError("Calculator requires a nonempty 'expression' string containing numeric arithmetic.")
            if len(expression) > 200:
                event["status"] = "invalid_arguments"
                raise ValueError("Arithmetic expression exceeds 200 characters. Break it into smaller calculations.")
            if "**" in expression or any(c not in "0123456789.+-*/%() \t" for c in expression):
                event["status"] = "invalid_arguments"
                raise ValueError("Calculator accepts numeric arithmetic only, not JSON, variables or code. Example: '(3 + 4) - 2'. Return final JSON through FINISH.")
            return super().run(**kwargs)


class MeteredBackend:
    def __init__(self, backend, budget, agent_id):
        self.backend, self.budget, self.agent_id = backend, budget, agent_id

    def chat(self, messages):
        call = self.budget.reserve_model(messages, self.agent_id)
        try:
            with self.budget.lock:
                self.budget.active()
                remaining = max(.001, self.budget.deadline - time.monotonic())
                client = getattr(self.backend, "client", None)
                if client is not None and hasattr(client, "timeout"):
                    client.timeout = remaining
                call["request_timeout_seconds"] = round(remaining, 3)
            value = self.backend.chat(messages)
            with self.budget.lock:
                self.budget.active()
                stats = getattr(self.backend, "last_usage", None) or getattr(self.backend, "last_response_stats", {}) or {}
                total = stats.get("total_tokens")
                call["actual_tokens"] = total if isinstance(total, int) and total >= 0 else None
                identity = getattr(self.backend, "last_model_identity", None)
                call["reported_model"] = identity if isinstance(identity, str) and len(identity) <= 500 else None
                call["status"] = "completed"
            return value
        except Exception:
            with self.budget.lock:
                call["status"] = "failed"
            raise


def make_backend(member, config):
    kwargs = {"model": member.model, "temperature": member.temperature, "max_tokens": config.max_output_tokens}
    if member.backend == "anthropic":
        kwargs.pop("temperature")
    if member.backend in {"lm_studio", "ollama"} and member.base_url:
        from urllib.parse import urlsplit
        parsed = urlsplit(member.base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Benchmark local model URLs must use HTTP loopback without credentials")
        kwargs["base_url"] = member.base_url
    elif member.backend == "azure_openai":
        from config.security import azure_endpoint
        kwargs.pop("model")
        kwargs["deployment_name"] = member.model
        kwargs["azure_endpoint"] = azure_endpoint(member.base_url or os.getenv("AZURE_OPENAI_ENDPOINT", ""))
    backend = BackendFactory.create(member.backend, **kwargs)
    client = getattr(backend, "client", None)
    if client is not None:
        if hasattr(client, "timeout"):
            client.timeout = config.timeout_seconds
        if hasattr(client, "max_retries"):
            client.max_retries = 0
    return backend


def run_member(member, config, data, budget, agent_id, peers=None, backend_factory=make_backend):
    backend = None
    lease = None
    tracer = Tracer.__new__(Tracer)
    tracer.events, tracer._iteration, tracer.on_event, tracer._rich = [], 0, lambda event: budget.publish({"agent_id": agent_id, **event}), False
    tracer._print = lambda event: None
    try:
        if backend_factory is make_backend and member.backend in {"lm_studio","ollama"}:
            from debugging.dashboard.model_sources import model_lease
            context = model_lease(member.backend,member.model,member.base_url,deadline=budget.deadline,
                                  stopped=budget.external_stop,on_status=tracer.on_status)
            actual = context.__enter__()
            lease = context
            member = member.model_copy(update={"model":actual})
        backend = backend_factory(member, config)
        metered = MeteredBackend(backend, budget, agent_id)
        registry = ToolRegistry()
        for tool in (ReadFixture(data, budget, agent_id), WriteArtifact(budget, agent_id), BoundedCalculator(budget, agent_id)):
            if tool.name in member.tools:
                registry.register(tool)
        planners = {"react": ReActPlanner, "cot": CoTPlanner, "tree": TreePlanner}
        if member.planner not in planners:
            raise ValueError("Unsupported planner")
        agent = Agent(metered, planners[member.planner](metered), registry,
                      MemoryManager({"enabled_stores": ["working", "conversation"]}), tracer,
                      config.max_iterations, cancel_event=budget.stopped)
        task = data["prompt"] + "\nYour role: " + member.role
        if peers is not None:
            task += "\nCritique these independent reports; verify against inputs, preserve decisive dissent, then produce the required final JSON:\n" + json.dumps(peers)[:24000]
        answer = agent.run(task)
        return {"agent_id": agent_id, "status": agent.completion_status, "answer": answer,
                "message": agent.stop_reason if agent.completion_status != "success" else "",
                "trace": [asdict(e) for e in tracer.events]}
    except Exception as exc:
        code = getattr(exc, "status_code", None)
        return {"agent_id": agent_id, "status": "error", "answer": "", "error_type": type(exc).__name__,
                "http_status": code, "message": "Model or execution failed; inspect credential readiness and configured limits.",
                "trace": [asdict(e) for e in tracer.events]}
    finally:
        client = getattr(backend, "client", None)
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        if lease is not None:
            lease.__exit__(None,None,None)


def attempt(config, task, seed=1, stopped=None, backend_factory=make_backend, on_event=None):
    data = fixture(task, seed)
    started = time.monotonic()
    budget = Budget(config, stopped, on_event)
    results = []
    futures = []
    pool = ThreadPoolExecutor(max_workers=config.max_concurrency)
    timed_out = False
    try:
        # Last member synthesizes after independent reports; one-agent runs have no synthesis overhead.
        researchers = config.agents if len(config.agents) == 1 else config.agents[:-1]
        futures = [pool.submit(run_member, member, config, data, budget, f"agent-{i + 1}", None, backend_factory)
                   for i, member in enumerate(researchers)]
        while any(not f.done() for f in futures):
            budget.active()
            wait(futures, timeout=min(.1, max(.01, budget.deadline - time.monotonic())))
        results = [f.result() for f in futures]
        if len(config.agents) > 1:
            final = pool.submit(run_member, config.agents[-1], config, data, budget,
                                f"agent-{len(config.agents)}", [{"agent_id": r["agent_id"], "status": r["status"], "answer": r["answer"]} for r in results], backend_factory)
            while not final.done():
                budget.active()
                wait([final], timeout=.1)
            results.append(final.result())
    except TimeoutError:
        timed_out = True
        budget.stopped.set()
    except RuntimeError:
        budget.stopped.set()
    finally:
        seen = {r["agent_id"] for r in results}
        for future in futures:
            if future.done() and not future.cancelled():
                result = future.result()
                if result["agent_id"] not in seen:
                    results.append(result)
        with budget.lock:
            budget.reservations_closed = True
        pool.shutdown(wait=False, cancel_futures=True)
    final = results[-1] if results else {"answer": "", "agent_id": "none", "status": "incomplete"}
    with budget.lock:
        # Snapshot under lock; late model responses cannot change published records or create artifacts.
        events = json.loads(json.dumps(budget.tool_events))
        artifacts = json.loads(json.dumps(budget.artifacts))
        calls = json.loads(json.dumps(budget.model_calls))
    evaluation = score(data, final["answer"], events, artifacts.get(final["agent_id"], {}))
    evaluation["expected"] = expected(task, seed)
    status = "timeout" if timed_out else "cancelled" if budget.stopped.is_set() else "completed" if final["status"] == "success" else "execution_failed"
    evaluation["passed"] = evaluation["passed"] and status == "completed"
    actuals = [c["actual_tokens"] for c in calls]
    return redact({"id": uuid.uuid4().hex, "task": task, "seed": seed, "status": status,
                   "elapsed_seconds": round(time.monotonic() - started, 3), "evaluation": evaluation,
                   "agents": results, "tool_events": events, "artifacts": artifacts,
                   "fixture_hash": digest(data), "artifact_hashes": {a: {n: digest(v) for n, v in files.items()} for a, files in artifacts.items()},
                   "usage": {"model_calls": calls, "tool_requests": len(events), "reserved_tokens": budget.reserved_tokens,
                             "actual_tokens": sum(actuals) if actuals and all(v is not None for v in actuals) else None,
                             "estimated_reserved_usd": budget.reserved_cost if config.usd_per_million_input is not None and config.usd_per_million_output is not None else None,
                             "rate_source": config.rate_source, "actual_cost": None}})


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _process_attempt(config, task, seed, stop, output, events):
    """Spawn entry point: only trusted fixture tools are registered in this process."""
    def publish(event):
        try:
            events.put_nowait(event)
        except queue.Full:
            pass
    result = attempt(ExperimentConfig.model_validate(config), task, seed, stopped=stop, on_event=publish)
    output.put(result)


def isolated_attempt(config, task, seed, stopped=None, on_event=None):
    """Terminate local worker processes after a deadline; remote billing may continue."""
    context = multiprocessing.get_context("spawn")
    output, events, stop = context.Queue(1), context.Queue(256), context.Event()
    process = context.Process(target=_process_attempt, args=(config.model_dump(), task, seed, stop, output, events), daemon=True)
    started = time.monotonic()
    process.start()
    result = None
    cancel_deadline = None
    try:
        while time.monotonic() - started < config.timeout_seconds + 10:
            if stopped and stopped.is_set():
                stop.set()
                if cancel_deadline is None:
                    cancel_deadline = time.monotonic() + 2
                if time.monotonic() >= cancel_deadline:
                    break
            try:
                result = output.get(timeout=.1)
            except queue.Empty:
                pass
            while True:
                try:
                    event = events.get_nowait()
                    if on_event:
                        on_event(event)
                except queue.Empty:
                    break
            if result is not None:
                return result
            if not process.is_alive():
                break
        # Keep a structured failure even for worker crashes or blocked constructors.
        data = fixture(task, seed)
        status = "cancelled" if stopped and stopped.is_set() else "timeout" if process.is_alive() else "execution_failed"
        return {"id": uuid.uuid4().hex, "task": task, "seed": seed, "status": status,
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "evaluation": {"score": 0, "passed": False, "checks": {"worker_completed": False}},
                "agents": [], "tool_events": [], "artifacts": {}, "fixture_hash": digest(data), "artifact_hashes": {},
                "usage": {"model_calls": [], "tool_requests": 0, "reserved_tokens": 0, "actual_tokens": None,
                          "estimated_reserved_usd": None, "actual_cost": None, "usage_incomplete": True}}
    finally:
        stop.set()
        process.join(timeout=.5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)
        if process.is_alive():
            process.kill()
            process.join(timeout=2)
        output.close()
        events.close()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(redact(value), indent=2), encoding="utf-8")
    # Windows may briefly deny replacement while a dashboard poll reads the
    # previous snapshot. Keep the old complete file and retry the atomic swap.
    for retry in range(10):
        try:
            temporary.replace(path)
            break
        except PermissionError:
            if retry == 9:
                raise
            time.sleep(.02 * (retry + 1))


def provenance():
    root = Path(__file__).resolve().parents[1]
    def git(*args):
        try:
            return subprocess.check_output(["git", "-c", f"safe.directory={root.as_posix()}", *args], cwd=root, timeout=5, stderr=subprocess.DEVNULL, text=True).strip()
        except (OSError, subprocess.SubprocessError):
            return "unknown"
    from importlib.metadata import version, PackageNotFoundError
    dependencies = {}
    for name in ("openai", "anthropic", "httpx", "pydantic", "pytest"):
        try:
            dependencies[name] = version(name)
        except PackageNotFoundError:
            dependencies[name] = "not installed"
    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain")),
            "python": platform.python_version(), "dependencies": dependencies, "cache": "cold", "memory": "fresh"}


def run_experiment(configs, output, repeats=5, stopped=None, on_progress=None, backend_factory=make_backend, resume=False, tasks=None):
    task_ids = selected_tasks(tasks)
    configs = prepare_baseline_configs(configs, task_ids)
    if repeats not in {1, 5, 20}:
        raise ValueError("Repeats must be 1 (smoke), 5 (baseline), or 20 (extended)")
    if not configs:
        raise ValueError("At least one configuration is required")
    for config in configs:
        if backend_factory is make_backend and any(member.model.strip() in {"", "local-model"} for member in config.agents):
            raise ValueError("Choose an explicit model ID from Refresh model list before running benchmarks; local-model is a placeholder.")
        if config.dollar_limit is not None and (config.usd_per_million_input is None or config.usd_per_million_output is None or not config.rate_source):
            raise ValueError("Dollar reservations require declared rates and their source")
        if any(member.backend not in BackendFactory.REGISTRY or member.planner not in {"react", "cot", "tree"} for member in config.agents):
            raise ValueError("Unsupported backend or planner")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "experiment.json"
    serialized = [c.model_dump() for c in configs]
    fixture_hashes = {f"{task}:{seed}": digest(fixture(task, seed)) for task in task_ids for seed in range(1, repeats + 1)}
    contract_hash = hashlib.sha256((Path(__file__).parent / "tasks.py").read_bytes()).hexdigest()
    identity = digest({"configs": serialized, "suite": SUITE, "repeats": repeats, "fixtures": fixture_hashes, "contract": contract_hash})
    if resume:
        record = json.loads(path.read_text(encoding="utf-8"))
        if record["identity"] != identity:
            raise ValueError("Resume configuration does not match original experiment")
    else:
        if path.exists():
            raise ValueError("Experiment already exists; use resume or a new output directory")
        record = {"id": uuid.uuid4().hex, "suite": SUITE, "rubric": "1.0", "identity": identity,
                  "created_at": datetime.now(timezone.utc).isoformat(), "configs": serialized,
                  "config_hashes": [digest(c) for c in serialized], "repeats": repeats,
                  "selected_tasks": list(task_ids),
                  "fixture_hashes": fixture_hashes,
                  "contract_hash": contract_hash, "evidence_type": "model experiment" if backend_factory is make_backend else "scripted harness check; not model performance",
                  "scheduled": len(configs) * repeats * len(task_ids), "provenance": provenance(), "attempts": [], "status": "running"}
    stop = stopped or threading.Event()
    completed = {(r["config_index"], r["task"], r["repetition"]) for r in record["attempts"]}
    atomic_json(path, record)
    try:
        for repetition in range(repeats):
            for task in task_ids:
                # Rotate configuration order so persistent providers are not always first/last.
                for offset in range(len(configs)):
                    index = (offset + repetition) % len(configs)
                    if (index, task, repetition) in completed:
                        continue
                    if stop.is_set():
                        record["status"] = "cancelled"
                        return record
                    callback = (lambda event: on_progress({"type": "activity", "task": task, "config_index": index, "repetition": repetition, **event})) if on_progress else None
                    if backend_factory is make_backend:
                        result = isolated_attempt(configs[index], task, seed=repetition + 1, stopped=stop, on_event=callback)
                    else:
                        # Injection is restricted to Python callers for offline regression testing.
                        result = attempt(configs[index], task, seed=repetition + 1, stopped=stop, backend_factory=backend_factory, on_event=callback)
                    result.update(config_index=index, repetition=repetition)
                    record["attempts"].append(result)
                    atomic_json(output / (result["id"] + ".json"), result)
                    atomic_json(path, record)
                    if on_progress:
                        on_progress({"completed": len(record["attempts"]), "scheduled": record["scheduled"], "task": task, "status": result["status"]})
                    if backend_factory is make_backend:
                        from debugging.dashboard.readiness import Inventory, classify
                        rejected = False
                        for report in result["agents"]:
                            code = report.get("http_status")
                            if code in {401, 402, 403, 429}:
                                member_index = int(report["agent_id"].split("-")[-1]) - 1
                                provider = configs[index].agents[member_index].backend
                                try:
                                    Inventory(Path(__file__).resolve().parents[1]).update(provider, status=classify(code), checked_at=datetime.now(timezone.utc).isoformat(), scope="operation test")
                                except (ValueError, OSError):
                                    pass
                                rejected = rejected or code == 401
                        if rejected:
                            record["status"] = "needs_setup"
                            return record
        record["status"] = "cancelled" if stop.is_set() else "completed"
        return record
    finally:
        atomic_json(path, record)


def wilson(passes, n):
    if not n:
        return [0, 1]
    z = 1.96
    p = passes / n
    center = (p + z*z/(2*n)) / (1 + z*z/n)
    margin = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / (1 + z*z/n)
    return [round(center-margin, 4), round(center+margin, 4)]


def summaries(record):
    rows = []
    task_ids = selected_tasks(record.get("selected_tasks"))
    for index, config in enumerate(record["configs"]):
        attempts = [r for r in record["attempts"] if r["config_index"] == index]
        times = sorted(r["elapsed_seconds"] for r in attempts)
        n = len(times)
        tasks = {}
        for task in TASKS:
            group = [r for r in attempts if r["task"] == task]
            passed = sum(r["evaluation"]["passed"] for r in group)
            tasks[task] = {"passed": passed, "attempted": len(group), "selected": task in task_ids, "scheduled": record["repeats"] if task in task_ids else 0, "wilson95": wilson(passed, len(group))}
        costs = [r["usage"]["estimated_reserved_usd"] for r in attempts]
        actuals = [r["usage"]["actual_tokens"] for r in attempts]
        rows.append({"name": config["name"], "agents": len(config["agents"]), "tasks": tasks,
                     "passed": sum(r["evaluation"]["passed"] for r in attempts), "attempted": n,
                     "scheduled": record["repeats"] * len(task_ids),
                     "selected_tasks": list(task_ids),
                     "minimum_quality": min((r["evaluation"]["score"] for r in attempts), default=None),
                     "mean_quality": round(sum(r["evaluation"]["score"] for r in attempts)/n, 2) if n else None,
                     "median_seconds": ((times[(n-1)//2] + times[n//2])/2) if n else None,
                     "p95_seconds": times[math.ceil(.95*n)-1] if n else None,
                     "actual_tokens": sum(actuals) if actuals and all(v is not None for v in actuals) else None,
                     "reserved_tokens": sum(r["usage"]["reserved_tokens"] for r in attempts),
                     "tool_requests": sum(r["usage"]["tool_requests"] for r in attempts),
                     "estimated_reserved_usd": sum(costs) if costs and all(v is not None for v in costs) else None,
                     "violations": sum(e.get("status") == "denied" for r in attempts for e in r["tool_events"]),
                     "qualified": len(task_ids) == len(TASKS) and record["repeats"] >= 5 and all(t["passed"] == record["repeats"] for t in tasks.values()),
                     "selection_passed": record["repeats"] >= 5 and all(tasks[t]["passed"] == record["repeats"] for t in task_ids)})
    return rows
