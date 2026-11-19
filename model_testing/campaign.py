"""Bounded MTT campaign execution built on Playpen's existing diagnostics."""

from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path

from benchmarks.runner import ExperimentConfig, Member, isolated_attempt, atomic_json
from benchmarks.diagnostics import TASKS
from model_testing.store import MttStore, MTT_DIAGNOSTIC_PROFILES


class MttCampaignManager:
    def __init__(self, store: MttStore, evidence_root: str | Path | None = None):
        self.store = store
        self.evidence_root = (
            Path(evidence_root) if evidence_root
            else store.path.parent / "evidence"
        )
        self.evidence_root.mkdir(parents=True, exist_ok=True)
        self.threads: dict[str, threading.Thread] = {}
        self.stop_events: dict[str, threading.Event] = {}
        self.lock = threading.RLock()

    def start(self, campaign_id: str) -> dict:
        campaign = self.store.get_campaign(campaign_id)
        if not campaign:
            raise ValueError("Unknown screening campaign.")
        with self.lock:
            existing = self.threads.get(campaign_id)
        if existing and existing.is_alive():
            return campaign
        if campaign["status"] in {"completed", "cancelled", "failed"}:
            return campaign
        stop = threading.Event()
        try:
            from debugging.dashboard.experiments import JOBS, LOCK

            with LOCK:
                active = [
                    job
                    for job_id, job in JOBS.items()
                    if job_id != f"mtt-{campaign_id}"
                    and job.get("status") == "running"
                ]
                if active:
                    raise RuntimeError(
                        "Stop or finish the active model experiment before starting MTT."
                    )
                JOBS[f"mtt-{campaign_id}"] = {
                    "status": "running",
                    "stop": stop,
                    "events": [],
                    "progress": {"completed": 0, "scheduled": 0},
                }
        except ImportError:
            pass
        with self.lock:
            self.stop_events[campaign_id] = stop
        thread = threading.Thread(
            target=self._run_campaign,
            args=(campaign_id, stop),
            name=f"mtt-campaign-{campaign_id[:8]}",
            daemon=True,
        )
        with self.lock:
            self.threads[campaign_id] = thread
        thread.start()
        return self.store.get_campaign(campaign_id)

    def cancel(self, campaign_id: str) -> dict:
        with self.lock:
            stop = self.stop_events.get(campaign_id)
            if stop:
                stop.set()
        self.store.update_campaign(campaign_id, "cancelled", completed=True)
        campaign = self.store.get_campaign(campaign_id)
        for item in campaign["items"]:
            if item["status"] in {"queued", "running"}:
                self.store.update_item(item["id"], "cancelled", {"cancelled": True})
        try:
            from debugging.dashboard.experiments import JOBS, LOCK

            with LOCK:
                job = JOBS.get(f"mtt-{campaign_id}")
                if job:
                    job["stop"].set()
        except ImportError:
            pass
        return self.store.get_campaign(campaign_id)

    def status(self, campaign_id: str) -> dict:
        return self.store.get_campaign(campaign_id)

    def reconcile(self) -> list[dict]:
        recovered = []
        for campaign in self.store.list_campaigns(limit=500):
            if campaign["status"] not in {"queued", "running"}:
                continue
            try:
                recovered.append(self.start(campaign["id"]))
            except RuntimeError as exc:
                self.store.update_campaign(
                    campaign["id"],
                    "queued",
                    {
                        "message": str(exc),
                        "error_type": "shared_job_admission",
                        "deferred": True,
                    },
                )
        return recovered

    def _update_job(self, campaign_id: str, status: str, progress: dict):
        try:
            from debugging.dashboard.experiments import JOBS, LOCK

            with LOCK:
                job = JOBS.get(f"mtt-{campaign_id}")
                if job:
                    job["status"] = status
                    job["progress"] = progress
        except ImportError:
            pass

    def _ledger(self, campaign):
        budget = dict(campaign.get("budget") or {})
        progress = dict(campaign.get("progress") or {})
        ledger = dict(progress.get("ledger") or {})
        ledger.setdefault("used_attempts", 0)
        ledger.setdefault("used_model_requests", 0)
        ledger.setdefault("used_tokens", 0)
        ledger.setdefault("used_reserved_tokens", 0)
        ledger.setdefault("used_wall_seconds", 0)
        ledger.setdefault("used_tool_requests", 0)
        ledger.setdefault("estimated_cost", None)
        return budget, ledger

    def _reconcile_attempt_ledger(self, campaign_id: str, ledger: dict) -> dict:
        rows = self.store.list_campaign_attempts(campaign_id)
        ledger["used_attempts"] = len(rows)
        ledger["used_model_requests"] = sum(
            int(row["reserved_model_requests"]) for row in rows
        )
        ledger["used_reserved_tokens"] = sum(
            int(row["reserved_tokens"]) for row in rows
        )
        ledger["used_wall_seconds"] = sum(
            float(row["reserved_wall_seconds"]) for row in rows
        )
        ledger["used_tool_requests"] = sum(
            int((row["result"] or {}).get("tool_requests") or 0)
            for row in rows
        )
        costs = [
            float((row["result"] or {}).get("estimated_reserved_usd") or 0)
            for row in rows
            if (row["result"] or {}).get("estimated_reserved_usd") is not None
        ]
        ledger["estimated_cost"] = sum(costs) if costs else None
        return ledger

    def _over_budget(self, budget, ledger):
        if ledger["used_attempts"] >= int(budget.get("max_attempts", 24)):
            return "attempt_limit"
        if ledger["used_model_requests"] >= int(budget.get("max_model_requests", 80)):
            return "model_request_limit"
        if ledger["used_wall_seconds"] >= float(budget.get("max_wall_seconds", 1200)):
            return "wall_time_limit"
        if ledger["used_reserved_tokens"] >= int(budget.get("max_tokens", 300000)):
            return "token_limit"
        cost_limit = budget.get("cost_limit")
        if cost_limit is not None:
            estimated = ledger.get("estimated_cost")
            if estimated is not None and float(estimated) > float(cost_limit):
                return "cost_limit"
        return None

    def _diagnostic_qualification(self, record, profile_id="diagnostics-v1"):
        attempts = record.get("attempts") or []
        attempt_count = len(attempts)
        scheduled_count = int(record.get("scheduled") or attempt_count)
        complete_count = sum(
            attempt.get("status") == "completed"
            for attempt in attempts
        )
        pass_count = sum(
            bool(attempt.get("evaluation", {}).get("passed"))
            for attempt in attempts
        )
        blocked_count = sum(
            attempt.get("outcome_category") in {
                "provider_rejection",
                "provider_rate_limit",
                "provider_error",
                "quota",
                "provider_connection",
                "timeout",
                "execution_failed",
            }
            or attempt.get("status") in {"timeout", "execution_failed", "cancelled"}
            for attempt in attempts
        )
        coverage = (
            complete_count / scheduled_count
            if scheduled_count
            else 0
        )
        if attempt_count == 0 or scheduled_count == 0 or complete_count == 0:
            return "incomplete", pass_count, coverage, blocked_count
        if blocked_count == attempt_count:
            return "blocked", pass_count, coverage, blocked_count
        if complete_count < scheduled_count or attempt_count < scheduled_count:
            return "incomplete", pass_count, coverage, blocked_count
        if pass_count == scheduled_count and complete_count == scheduled_count:
            if profile_id not in MTT_DIAGNOSTIC_PROFILES:
                return "incomplete", pass_count, coverage, blocked_count
            return "provisional", pass_count, coverage, blocked_count
        return "not_usable_for_profile", pass_count, coverage, blocked_count

    def _run_campaign(self, campaign_id: str, stop: threading.Event):
        campaign = self.store.get_campaign(campaign_id)
        source = self.store.get_source(campaign["source_id"])
        if not source:
            self.store.update_campaign(
                campaign_id,
                "failed",
                {"message": "Source no longer exists."},
                completed=True,
            )
            self._update_job(campaign_id, "failed", {"completed": 0, "scheduled": 0})
            return
        if source["status"] in {"removed", "failed", "configuration_required"}:
            self.store.update_campaign(
                campaign_id,
                "failed",
                {
                    "message": "Source is unavailable.",
                    "source_status": source["status"],
                },
                completed=True,
            )
            for item in campaign["items"]:
                self.store.update_item(
                    item["id"],
                    "blocked",
                    {
                        "profile_id": item["profile_id"],
                        "error_type": "source_unavailable",
                        "source_status": source["status"],
                    },
                )
            self._update_job(campaign_id, "failed", {"completed": len(campaign["items"]), "scheduled": len(campaign["items"]) * 6})
            return
        campaign_dir = self.evidence_root / campaign_id
        campaign_dir.mkdir(parents=True, exist_ok=True)
        budget = dict(campaign["budget"])
        _, ledger = self._ledger(campaign)
        ledger = self._reconcile_attempt_ledger(campaign_id, ledger)
        progress = {
            "queued": len(campaign["items"]),
            "running": 0,
            "completed": 0,
            "passed": 0,
            "blocked": 0,
            "failed": 0,
            "ledger": ledger,
        }
        self.store.update_campaign(campaign_id, "running", progress)
        completed = 0
        passed = 0
        blocked = 0
        failed = 0
        for item in campaign["items"]:
            if stop.is_set():
                break
            if item["status"] in {"completed", "cancelled", "blocked"}:
                completed += 1
                continue
            self.store.update_item(item["id"], "running")
            max_output = 512 if source["provider"] == "groq" else 2048
            remaining_wall = max(
                0.0,
                float(budget.get("max_wall_seconds", 1200))
                - float(ledger["used_wall_seconds"]),
            )
            remaining_requests = max(
                0,
                int(budget.get("max_model_requests", 80))
                - int(ledger["used_model_requests"]),
            )
            remaining_tokens = max(
                0,
                int(budget.get("max_tokens", 300000))
                - int(ledger["used_reserved_tokens"]),
            )
            remaining_attempts = max(
                0,
                int(budget.get("max_attempts", 24))
                - int(ledger["used_attempts"]),
            )
            remaining_tool_requests = max(
                0,
                120 - int(ledger["used_tool_requests"]),
            )
            budget_stop = self._over_budget(budget, ledger)
            if budget_stop:
                blocked += 1
                completed += 1
                self.store.update_item(
                    item["id"],
                    "blocked",
                    {
                        "profile_id": item["profile_id"],
                        "error_type": "campaign_budget_reached",
                        "message": f"Campaign stopped at {budget_stop}.",
                        "attempt_count": 0,
                        "pass_count": 0,
                        "coverage": 0,
                    },
                    str(campaign_dir),
                )
                continue
            if (
                remaining_attempts <= 0
                or remaining_requests <= 0
                or remaining_tokens < 1000
                or remaining_wall <= 1
                or remaining_tool_requests <= 0
            ):
                blocked += 1
                completed += 1
                reason = (
                    "model_request_limit"
                    if remaining_requests <= 0
                    else "attempt_limit"
                    if remaining_attempts <= 0
                    else "wall_time_limit"
                    if remaining_wall <= 1
                    else "token_limit"
                    if remaining_tokens < 1000
                    else "tool_request_limit"
                )
                self.store.update_item(
                    item["id"],
                    "blocked",
                    {
                        "profile_id": item["profile_id"],
                        "error_type": reason,
                        "attempt_count": 0,
                        "pass_count": 0,
                        "coverage": 0,
                    },
                    str(campaign_dir),
                )
                continue
            timeout_seconds = min(
                float(budget.get("case_timeout_seconds", 400)),
                1800,
                remaining_wall,
            )
            cost_limit = budget.get("cost_limit")
            if cost_limit is not None and source["provider"] not in {"lm_studio", "ollama"}:
                reason = "Cost limits cannot be enforced for this source without declared provider rates."
                blocked += 1
                completed += 1
                self.store.update_item(
                    item["id"],
                    "blocked",
                    {
                        "profile_id": item["profile_id"],
                        "error_type": "cost_policy_not_resolvable",
                        "message": reason,
                        "attempt_count": 0,
                        "pass_count": 0,
                        "coverage": 0,
                    },
                    str(campaign_dir),
                )
                progress = {
                    "queued": max(0, len(campaign["items"]) - completed),
                    "running": 0,
                    "completed": completed,
                    "passed": passed,
                    "blocked": blocked,
                    "failed": failed,
                    "ledger": ledger,
                }
                self.store.update_campaign(campaign_id, "running", progress)
                continue
            if (
                cost_limit is not None
                and source["provider"] in {"lm_studio", "ollama"}
                and float(cost_limit) > 0
            ):
                reason = "Dollar limits for local sources require declared local-energy or provider rates."
                blocked += 1
                completed += 1
                self.store.update_item(
                    item["id"],
                    "blocked",
                    {
                        "profile_id": item["profile_id"],
                        "error_type": "cost_policy_not_resolvable",
                        "message": reason,
                        "attempt_count": 0,
                        "pass_count": 0,
                        "coverage": 0,
                    },
                    str(campaign_dir),
                )
                progress = {
                    "queued": max(0, len(campaign["items"]) - completed),
                    "running": 0,
                    "completed": completed,
                    "passed": passed,
                    "blocked": blocked,
                    "failed": failed,
                    "ledger": ledger,
                }
                self.store.update_campaign(campaign_id, "running", progress)
                continue
            config = ExperimentConfig(
                name=f"mtt-{item['model_id'][:24]}",
                agents=[
                    Member(
                        backend=source["provider"],
                        model=item["model_id"],
                        base_url=source["endpoint"] or None,
                        planner="react",
                        tool_calling_mode="auto",
                        temperature=0,
                        tools=[],
                    )
                ],
                max_concurrency=1,
                max_iterations=10,
                max_output_tokens=max_output,
                token_reservation_limit=remaining_tokens,
                model_request_limit=remaining_requests,
                tool_request_limit=remaining_tool_requests,
                timeout_seconds=timeout_seconds,
                capture_diagnostics=True,
                auto_baseline_setup=False,
                model_min_interval_seconds=(
                    60 if source["provider"] == "groq" else 0
                ),
                dollar_limit=None,
            )
            model_dir = campaign_dir / f"item-{item['id'][:12]}"
            model_dir.mkdir(parents=True, exist_ok=True)
            try:
                attempts = []
                scheduled_count = len(TASKS)
                done_tasks = set()
                experiment_path = model_dir / "experiment.json"
                if experiment_path.exists():
                    try:
                        existing_record = json.loads(
                            experiment_path.read_text(encoding="utf-8")
                        )
                        attempts = list(existing_record.get("attempts") or [])
                        done_tasks = {
                            str(attempt["task"])
                            for attempt in attempts
                            if attempt.get("task")
                        }
                    except (json.JSONDecodeError, OSError, KeyError):
                        attempts = []
                        done_tasks = set()
                budget_stop = None
                for task in TASKS:
                    if task in done_tasks:
                        continue
                    budget_stop = self._over_budget(budget, ledger)
                    if budget_stop:
                        break
                    if stop.is_set():
                        break
                    remaining_wall = max(
                        0.0,
                        float(budget.get("max_wall_seconds", 1200))
                        - float(ledger["used_wall_seconds"]),
                    )
                    remaining_requests = max(
                        0,
                        int(budget.get("max_model_requests", 80))
                        - int(ledger["used_model_requests"]),
                    )
                    remaining_tokens = max(
                        0,
                        int(budget.get("max_tokens", 300000))
                        - int(ledger["used_reserved_tokens"]),
                    )
                    attempt_timeout = min(
                        float(budget.get("case_timeout_seconds", 400)),
                        1800,
                        remaining_wall,
                    )
                    if (
                        remaining_requests <= 0
                        or remaining_tokens < 1000
                        or attempt_timeout <= 1
                    ):
                        budget_stop = (
                            "model_request_limit"
                            if remaining_requests <= 0
                            else "token_limit"
                            if remaining_tokens < 1000
                            else "wall_time_limit"
                        )
                        break
                    reservation = self.store.reserve_campaign_attempt(
                        campaign_id,
                        item["id"],
                        task,
                        reserved_model_requests=remaining_requests,
                        reserved_tokens=remaining_tokens,
                        reserved_wall_seconds=attempt_timeout,
                    )
                    if reservation.get("_is_existing"):
                        if reservation.get("status") == "completed":
                            existing_attempt = reservation["result"]
                            if existing_attempt:
                                attempts.append(existing_attempt)
                                done_tasks.add(task)
                                ledger = self._reconcile_attempt_ledger(
                                    campaign_id,
                                    ledger,
                                )
                                continue
                        if reservation.get("status") in {"reserved", "uncertain"}:
                            uncertain = self.store.mark_campaign_attempt_uncertain(
                                campaign_id,
                                item["id"],
                                task,
                                str(model_dir),
                            )
                            done_tasks.add(task)
                            attempts.append(
                                uncertain["result"]
                                if uncertain.get("result")
                                else {
                                    "task": task,
                                    "status": "uncertain",
                                    "elapsed_seconds": attempt_timeout,
                                    "evaluation": {
                                        "passed": False,
                                        "score": 0,
                                        "checks": {"worker_completed": False},
                                    },
                                    "usage_incomplete": True,
                                    "usage": {
                                        "usage_incomplete": True,
                                        "model_calls": [],
                                        "tool_requests": None,
                                        "reserved_tokens": None,
                                        "actual_tokens": None,
                                    },
                                }
                            )
                            ledger = self._reconcile_attempt_ledger(
                                campaign_id,
                                ledger,
                            )
                            continue
                    if reservation.get("status") == "completed":
                        existing_attempt = reservation["result"]
                        if existing_attempt:
                            attempts.append(existing_attempt)
                            done_tasks.add(task)
                            ledger = self._reconcile_attempt_ledger(
                                campaign_id,
                                ledger,
                            )
                            continue
                    ledger = self._reconcile_attempt_ledger(
                        campaign_id,
                        ledger,
                    )
                    attempt_config = config.model_copy(deep=True)
                    attempt_config.timeout_seconds = attempt_timeout
                    attempt_config.token_reservation_limit = remaining_tokens
                    attempt_config.model_request_limit = remaining_requests
                    attempt_config.tool_request_limit = max(
                        1,
                        120 - int(ledger["used_tool_requests"]),
                    )
                    attempt = isolated_attempt(
                        attempt_config,
                        task,
                        seed=1,
                        stopped=stop,
                    )
                    attempts.append(attempt)
                    usage = attempt.get("usage") or {}
                    model_calls = usage.get("model_calls") or []
                    tool_requests = (
                        len(attempt.get("tool_events") or [])
                        if attempt.get("tool_events") is not None
                        else int(usage.get("tool_requests") or 0)
                    )
                    cost = usage.get("actual_cost")
                    if cost is None:
                        cost = usage.get("estimated_reserved_usd")
                    attempt_result = {
                        **attempt,
                        "tool_requests": tool_requests,
                        "model_requests": len(model_calls),
                        "reserved_tokens": usage.get("reserved_tokens"),
                        "actual_tokens": usage.get("actual_tokens"),
                        "estimated_reserved_usd": cost,
                    }
                    self.store.complete_campaign_attempt(
                        campaign_id,
                        item["id"],
                        task,
                        attempt_result,
                        str(model_dir),
                    )
                    ledger = self._reconcile_attempt_ledger(
                        campaign_id,
                        ledger,
                    )
                    partial_record = {
                        "id": uuid.uuid4().hex,
                        "suite": "mtt-diagnostics-screen-v1",
                        "campaign_id": campaign_id,
                        "profile_id": item["profile_id"],
                        "status": "running",
                        "scheduled": scheduled_count,
                        "attempts": attempts,
                        "source_status": source["status"],
                    }
                    atomic_json(experiment_path, partial_record)
                    partial_pass_count = sum(
                        bool(attempt.get("evaluation", {}).get("passed"))
                        for attempt in attempts
                    )
                    partial_complete_count = sum(
                        attempt.get("status") == "completed"
                        for attempt in attempts
                    )
                    self.store.update_item(
                        item["id"],
                        "running",
                        {
                            "profile_id": item["profile_id"],
                            "attempt_count": len(attempts),
                            "pass_count": partial_pass_count,
                            "coverage": partial_complete_count / scheduled_count,
                            "partial": True,
                            "evidence_path": str(model_dir),
                        },
                        str(model_dir),
                    )
                    progress = {
                        "queued": max(0, len(campaign["items"]) - completed),
                        "running": 1,
                        "completed": completed,
                        "passed": passed,
                        "blocked": blocked,
                        "failed": failed,
                        "ledger": ledger,
                    }
                    self.store.update_campaign(campaign_id, "running", progress)
                    budget_stop = self._over_budget(budget, ledger)
                    if budget_stop:
                        break

                record = {
                    "id": uuid.uuid4().hex,
                    "suite": "mtt-diagnostics-screen-v1",
                    "campaign_id": campaign_id,
                    "profile_id": item["profile_id"],
                    "status": "cancelled" if stop.is_set() else "completed",
                    "scheduled": scheduled_count,
                    "attempts": attempts,
                    "source_status": source["status"],
                }
                atomic_json(model_dir / "experiment.json", record)

                eligibility, pass_count, coverage, blocked_count = (
                    self._diagnostic_qualification(record, item["profile_id"])
                )
                attempt_count = len(attempts)
                q_score = round(100 * pass_count / attempt_count, 2) if attempt_count else None
                max_elapsed = max(
                    (
                        float(attempt.get("elapsed_seconds") or 0)
                        for attempt in attempts
                    ),
                    default=0,
                )
                result = {
                    "profile_id": item["profile_id"],
                    "attempt_count": attempt_count,
                    "pass_count": pass_count,
                    "blocked_count": blocked_count,
                    "coverage": coverage,
                    "q_score": q_score,
                    "status": record["status"],
                    "budget_stop": budget_stop,
                    "max_elapsed_seconds": max_elapsed,
                    "outcome_categories": sorted(
                        {
                            attempt.get("outcome_category", attempt.get("status"))
                            for attempt in attempts
                        }
                    ),
                    "record_id": record["id"],
                    "evidence_path": str(model_dir),
                }
                fingerprint = (
                    source["provider"]
                    + ":"
                    + item["model_id"]
                    + ":"
                    + config.model_dump_json()
                    + ":"
                    + item["profile_id"]
                )
                import hashlib

                configuration_fingerprint = hashlib.sha256(
                    fingerprint.encode("utf-8")
                ).hexdigest()
                if eligibility in {"blocked", "incomplete"} and budget_stop:
                    status = "blocked"
                elif stop.is_set():
                    status = "cancelled"
                elif eligibility == "blocked":
                    status = "blocked"
                elif eligibility == "incomplete":
                    status = "completed"
                else:
                    status = "completed"
                self.store.update_item(
                    item["id"],
                    status,
                    result,
                    str(model_dir),
                    configuration_fingerprint,
                )
                if eligibility == "blocked":
                    blocked += 1
                elif pass_count:
                    passed += 1
                else:
                    failed += 1
                self.store.save_qualification(
                    source_id=source["id"],
                    model_id=item["model_id"],
                    configuration_fingerprint=configuration_fingerprint,
                    profile_id=item["profile_id"],
                    eligibility=eligibility,
                    q_score=q_score,
                    coverage=coverage,
                    confidence=None,
                    evidence_refs=[
                        str(model_dir / "experiment.json"),
                    ],
                    result=result,
                )
            except Exception as exc:
                failed += 1
                self.store.update_item(
                    item["id"],
                    "cancelled" if stop.is_set() else "failed",
                    {
                        "profile_id": item["profile_id"],
                        "error_type": type(exc).__name__,
                        "message": str(exc)[:2000],
                    },
                    str(model_dir),
                )
            completed += 1
            self.store.update_campaign(
                campaign_id,
                "cancelled" if stop.is_set() else "running",
                {
                    "queued": max(0, len(campaign["items"]) - completed),
                    "running": 1 if not stop.is_set() else 0,
                    "completed": completed,
                    "passed": passed,
                    "blocked": blocked,
                    "failed": failed,
                    "ledger": ledger,
                },
            )
            if stop.is_set():
                break
        status = "cancelled" if stop.is_set() else "completed"
        self.store.update_campaign(
            campaign_id,
            status,
            {
                "queued": max(0, len(campaign["items"]) - completed),
                "running": 0,
                "completed": completed,
                "passed": passed,
                "blocked": blocked,
                "failed": failed,
                "ledger": ledger,
            },
            completed=True,
        )
        final_progress = {
            "completed": completed,
            "scheduled": sum(
                1
                for item in campaign["items"]
            ) * 6,
            "passed": passed,
            "blocked": blocked,
            "failed": failed,
            "ledger": ledger,
        }
        self._update_job(campaign_id, status, final_progress)
        with self.lock:
            self.threads.pop(campaign_id, None)
            self.stop_events.pop(campaign_id, None)
