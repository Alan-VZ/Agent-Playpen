"""SQLite storage for MTT sources, catalog entries, campaigns and qualifications."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Iterable


def default_mtt_database_path() -> Path:
    override = os.getenv("AGENT_PLAYPEN_MTT_DB")
    if override:
        return Path(override)
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "AgentPlaypen" / "mtt" / "mtt.sqlite3"
    return Path.home() / ".agent-playpen" / "mtt" / "mtt.sqlite3"


def now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()

MTT_DIAGNOSTIC_PROFILES = frozenset({
    "diagnostics-v1",
    "diagnostics-screen-v1",
})


class MttStore:
    def __init__(self, database_path: str | Path | None = None):
        self.path = Path(database_path) if database_path else default_mtt_database_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self):
        connection = sqlite3.connect(str(self.path), timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize(self):
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    name TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    account_alias TEXT NOT NULL DEFAULT '',
                    credential_ref TEXT NOT NULL DEFAULT '',
                    standing_policy TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'created',
                    last_error TEXT NOT NULL DEFAULT '',
                    last_refresh_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS catalog_snapshots (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error TEXT NOT NULL DEFAULT '',
                    snapshot_hash TEXT NOT NULL DEFAULT '',
                    model_count INTEGER NOT NULL DEFAULT 0,
                    fetched_at TEXT NOT NULL,
                    FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS catalog_entries (
                    source_id TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    display_name TEXT NOT NULL DEFAULT '',
                    model_type TEXT NOT NULL DEFAULT 'unknown',
                    revision TEXT NOT NULL DEFAULT '',
                    listed INTEGER NOT NULL DEFAULT 1,
                    access_state TEXT NOT NULL DEFAULT 'unknown',
                    installed INTEGER NOT NULL DEFAULT 0,
                    loaded INTEGER NOT NULL DEFAULT 0,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY(source_id, model_id),
                    FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS screening_campaigns (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    profile_id TEXT NOT NULL,
                    standing_policy_id TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    budget TEXT NOT NULL DEFAULT '{}',
                    progress TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS screening_items (
                    id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    configuration_fingerprint TEXT NOT NULL DEFAULT '',
                    profile_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    result TEXT NOT NULL DEFAULT '{}',
                    evidence_path TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    FOREIGN KEY(campaign_id) REFERENCES screening_campaigns(id) ON DELETE CASCADE,
                    FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS qualification_decisions (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    configuration_fingerprint TEXT NOT NULL,
                    profile_id TEXT NOT NULL,
                    eligibility TEXT NOT NULL,
                    q_score REAL,
                    coverage REAL,
                    confidence REAL,
                    evidence_refs TEXT NOT NULL DEFAULT '[]',
                    result TEXT NOT NULL DEFAULT '{}',
                    valid_until TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS task_requirements (
                    id TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL,
                    requirements TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS campaign_attempt_reservations (
                    id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reserved_model_requests INTEGER NOT NULL DEFAULT 0,
                    reserved_tokens INTEGER NOT NULL DEFAULT 0,
                    reserved_wall_seconds REAL NOT NULL DEFAULT 0,
                    result TEXT NOT NULL DEFAULT '{}',
                    evidence_path TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    UNIQUE(campaign_id, item_id, task_id),
                    FOREIGN KEY(campaign_id) REFERENCES screening_campaigns(id) ON DELETE CASCADE,
                    FOREIGN KEY(item_id) REFERENCES screening_items(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_catalog_entries_source
                    ON catalog_entries(source_id, listed);
                CREATE INDEX IF NOT EXISTS idx_campaign_items_campaign
                    ON screening_items(campaign_id, status);
                CREATE INDEX IF NOT EXISTS idx_qualifications_lookup
                    ON qualification_decisions(source_id, model_id, profile_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_campaign_attempt_reservations
                    ON campaign_attempt_reservations(campaign_id, status);
                """
            )

    def create_source(
        self,
        provider: str,
        name: str,
        endpoint: str,
        account_alias: str = "",
        credential_ref: str = "",
        standing_policy: dict | None = None,
    ) -> dict:
        source_id = uuid.uuid4().hex
        timestamp = now_iso()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO sources (
                    id, provider, name, endpoint, account_alias, credential_ref,
                    standing_policy, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'created', ?, ?)
                """,
                (
                    source_id,
                    provider,
                    name,
                    endpoint,
                    account_alias,
                    credential_ref,
                    json.dumps(standing_policy or {}, sort_keys=True),
                    timestamp,
                    timestamp,
                ),
            )
        return self.get_source(source_id)

    def get_source(self, source_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM sources WHERE id = ?", (source_id,)
            ).fetchone()
        return self._source_dict(row) if row else None

    def list_sources(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM sources ORDER BY created_at DESC"
            ).fetchall()
        return [self._source_dict(row) for row in rows]

    def update_source_status(
        self,
        source_id: str,
        status: str,
        last_error: str = "",
        standing_policy: dict | None = None,
    ):
        timestamp = now_iso()
        with self.connect() as connection:
            if standing_policy is None:
                connection.execute(
                    """
                    UPDATE sources
                    SET status = ?, last_error = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (status, last_error[:2000], timestamp, source_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE sources
                    SET status = ?, last_error = ?, standing_policy = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        status,
                        last_error[:2000],
                        json.dumps(standing_policy, sort_keys=True),
                        timestamp,
                        source_id,
                    ),
                )

    def save_catalog(
        self,
        source_id: str,
        entries: Iterable[dict],
        status: str = "completed",
        error: str = "",
    ) -> dict:
        timestamp = now_iso()
        snapshot_id = uuid.uuid4().hex
        entries = list(entries)
        serialized = json.dumps(entries, sort_keys=True)
        import hashlib

        snapshot_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO catalog_snapshots (
                    id, source_id, status, error, snapshot_hash,
                    model_count, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    source_id,
                    status,
                    error[:4000],
                    snapshot_hash,
                    len(entries),
                    timestamp,
                ),
            )
            ids = set()
            # A failed or unconfigured refresh is not evidence of model removal.
            # Preserve the last successful catalog until a completed snapshot.
            if status == "completed":
                for entry in entries:
                    model_id = str(entry.get("model_id") or entry.get("id") or "").strip()
                    if not model_id:
                        continue
                    ids.add(model_id)
                    connection.execute(
                        """
                        INSERT INTO catalog_entries (
                            source_id, model_id, display_name, model_type, revision,
                            listed, access_state, installed, loaded,
                            first_seen_at, last_seen_at, metadata
                        ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(source_id, model_id) DO UPDATE SET
                            display_name = excluded.display_name,
                            model_type = excluded.model_type,
                            revision = excluded.revision,
                            listed = 1,
                            access_state = excluded.access_state,
                            installed = excluded.installed,
                            loaded = excluded.loaded,
                            last_seen_at = excluded.last_seen_at,
                            metadata = excluded.metadata
                        """,
                        (
                            source_id,
                            model_id,
                            str(entry.get("display_name") or model_id),
                            str(entry.get("model_type") or "llm"),
                            str(entry.get("revision") or ""),
                            str(entry.get("access_state") or "unknown"),
                            1 if entry.get("installed") else 0,
                            1 if entry.get("loaded") else 0,
                            timestamp,
                            timestamp,
                            json.dumps(entry, sort_keys=True),
                        ),
                    )
                if ids:
                    placeholders = ",".join("?" for _ in ids)
                    connection.execute(
                        f"""
                        UPDATE catalog_entries
                        SET listed = 0
                        WHERE source_id = ? AND model_id NOT IN ({placeholders})
                        """,
                        (source_id, *sorted(ids)),
                    )
                else:
                    connection.execute(
                        "UPDATE catalog_entries SET listed = 0 WHERE source_id = ?",
                        (source_id,),
                    )
            connection.execute(
                """
                UPDATE sources
                SET status = ?, last_error = ?, last_refresh_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, error[:2000], timestamp, timestamp, source_id),
            )
        return self.list_catalog(source_id)

    def list_catalog(self, source_id: str, include_unlisted: bool = True) -> dict:
        with self.connect() as connection:
            if include_unlisted:
                rows = connection.execute(
                    """
                    SELECT * FROM catalog_entries
                    WHERE source_id = ?
                    ORDER BY listed DESC, model_id ASC
                    """,
                    (source_id,),
                ).fetchall()
                snapshot = connection.execute(
                    """
                    SELECT * FROM catalog_snapshots
                    WHERE source_id = ?
                    ORDER BY fetched_at DESC LIMIT 1
                    """,
                    (source_id,),
                ).fetchone()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM catalog_entries
                    WHERE source_id = ? AND listed = 1
                    ORDER BY model_id ASC
                    """,
                    (source_id,),
                ).fetchall()
                snapshot = connection.execute(
                    """
                    SELECT * FROM catalog_snapshots
                    WHERE source_id = ? AND status = 'completed'
                    ORDER BY fetched_at DESC LIMIT 1
                    """,
                    (source_id,),
                ).fetchone()
        return {
            "source": self.get_source(source_id),
            "snapshot": dict(snapshot) if snapshot else None,
            "entries": [self._catalog_dict(row) for row in rows],
        }

    def create_campaign(
        self,
        source_id: str,
        profile_id: str,
        model_ids: list[str],
        budget: dict | None = None,
        standing_policy_id: str = "",
    ) -> dict:
        campaign_id = uuid.uuid4().hex
        timestamp = now_iso()
        if not model_ids:
            raise ValueError("Select at least one model.")
        if profile_id not in MTT_DIAGNOSTIC_PROFILES:
            raise ValueError("Unknown MTT profile.")
        budget = budget or {
            "max_attempts": 24,
            "max_model_requests": 80,
            "max_wall_seconds": 1200,
            "max_tokens": 300000,
            "cost_limit": None,
        }
        initial_progress = {
            "queued": len(dict.fromkeys(model_ids)),
            "running": 0,
            "completed": 0,
            "passed": 0,
            "blocked": 0,
            "failed": 0,
            "ledger": {
                "used_attempts": 0,
                "used_model_requests": 0,
                "used_tokens": 0,
                "used_reserved_tokens": 0,
                "used_wall_seconds": 0,
                "used_tool_requests": 0,
                "estimated_cost": None,
            },
        }
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO screening_campaigns (
                    id, source_id, profile_id, standing_policy_id,
                    status, budget, progress, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'queued', ?, ?, ?, ?)
                """,
                (
                    campaign_id,
                    source_id,
                    profile_id,
                    standing_policy_id,
                    json.dumps(budget, sort_keys=True),
                    json.dumps(initial_progress, sort_keys=True),
                    timestamp,
                    timestamp,
                ),
            )
            for model_id in dict.fromkeys(model_ids):
                item_id = uuid.uuid4().hex
                connection.execute(
                    """
                    INSERT INTO screening_items (
                        id, campaign_id, source_id, model_id,
                        profile_id, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'queued', ?, ?)
                    """,
                    (
                        item_id,
                        campaign_id,
                        source_id,
                        model_id,
                        profile_id,
                        timestamp,
                        timestamp,
                    ),
                )
        return self.get_campaign(campaign_id)

    def get_campaign(self, campaign_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM screening_campaigns WHERE id = ?",
                (campaign_id,),
            ).fetchone()
            if not row:
                return None
            items = connection.execute(
                """
                SELECT * FROM screening_items
                WHERE campaign_id = ?
                ORDER BY created_at ASC
                """,
                (campaign_id,),
            ).fetchall()
        result = dict(row)
        result["budget"] = json.loads(row["budget"])
        result["progress"] = json.loads(row["progress"])
        result["items"] = [self._item_dict(item) for item in items]
        return result

    def list_campaigns(self, limit: int = 100) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM screening_campaigns
                ORDER BY created_at DESC LIMIT ?
                """,
                (max(1, min(limit, 500)),),
            ).fetchall()
        result = []
        for row in rows:
            campaign = dict(row)
            campaign["budget"] = json.loads(row["budget"])
            campaign["progress"] = json.loads(row["progress"])
            result.append(campaign)
        return result

    def update_campaign(self, campaign_id: str, status: str, progress: dict | None = None, completed: bool = False):
        timestamp = now_iso()
        with self.connect() as connection:
            if progress is None:
                connection.execute(
                    """
                    UPDATE screening_campaigns
                    SET status = ?, updated_at = ?, completed_at = ?
                    WHERE id = ?
                    """,
                    (status, timestamp, timestamp if completed else None, campaign_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE screening_campaigns
                    SET status = ?, progress = ?, updated_at = ?, completed_at = ?
                    WHERE id = ?
                    """,
                    (
                        status,
                        json.dumps(progress, sort_keys=True),
                        timestamp,
                        timestamp if completed else None,
                        campaign_id,
                    ),
                )

    def update_item(
        self,
        item_id: str,
        status: str,
        result: dict | None = None,
        evidence_path: str = "",
        configuration_fingerprint: str = "",
    ):
        timestamp = now_iso()
        completed = status in {"completed", "cancelled", "failed", "blocked"}
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE screening_items
                SET status = ?, configuration_fingerprint = ?, result = ?,
                    evidence_path = ?, updated_at = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    configuration_fingerprint,
                    json.dumps(result or {}, sort_keys=True),
                    evidence_path,
                    timestamp,
                    timestamp if completed else None,
                    item_id,
                ),
            )

    def reserve_campaign_attempt(
        self,
        campaign_id: str,
        item_id: str,
        task_id: str,
        reserved_model_requests: int,
        reserved_tokens: int,
        reserved_wall_seconds: float,
    ) -> dict:
        timestamp = now_iso()
        import hashlib

        attempt_id = hashlib.sha256(
            f"{campaign_id}|{item_id}|{task_id}".encode("utf-8")
        ).hexdigest()
        with self.connect() as connection:
            existing = connection.execute(
                """
                SELECT * FROM campaign_attempt_reservations
                WHERE campaign_id = ? AND item_id = ? AND task_id = ?
                """,
                (campaign_id, item_id, task_id),
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO campaign_attempt_reservations (
                        id, campaign_id, item_id, task_id, status,
                        reserved_model_requests, reserved_tokens,
                        reserved_wall_seconds, result, evidence_path,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 'reserved', ?, ?, ?, '{}', '', ?, ?)
                    """,
                    (
                        attempt_id,
                        campaign_id,
                        item_id,
                        task_id,
                        max(0, int(reserved_model_requests)),
                        max(0, int(reserved_tokens)),
                        max(0.0, float(reserved_wall_seconds)),
                        timestamp,
                        timestamp,
                    ),
                )
            row = connection.execute(
                """
                SELECT * FROM campaign_attempt_reservations
                WHERE campaign_id = ? AND item_id = ? AND task_id = ?
                """,
                (campaign_id, item_id, task_id),
            ).fetchone()
        result = self._campaign_attempt_dict(row)
        result["_is_existing"] = existing is not None
        return result

    def complete_campaign_attempt(
        self,
        campaign_id: str,
        item_id: str,
        task_id: str,
        result: dict,
        evidence_path: str = "",
    ) -> dict:
        timestamp = now_iso()
        unresolved_statuses = {"timeout", "cancelled", "execution_failed"}
        unresolved = (
            bool(result.get("usage_incomplete"))
            or result.get("status") in unresolved_statuses
        )
        status = "uncertain" if unresolved else "completed"
        with self.connect() as connection:
            row_before = connection.execute(
                """
                SELECT reserved_model_requests, reserved_tokens,
                       reserved_wall_seconds
                FROM campaign_attempt_reservations
                WHERE campaign_id = ? AND item_id = ? AND task_id = ?
                """,
                (campaign_id, item_id, task_id),
            ).fetchone()
            model_requests = int(row_before["reserved_model_requests"]) if row_before else 0
            reserved_tokens = int(row_before["reserved_tokens"]) if row_before else 0
            reserved_wall = float(row_before["reserved_wall_seconds"]) if row_before else 0.0
            if not unresolved:
                observed_requests = result.get("model_requests")
                if observed_requests is not None:
                    model_requests = max(1, int(observed_requests))
                observed_tokens = result.get("reserved_tokens")
                if observed_tokens is not None:
                    reserved_tokens = max(0, int(observed_tokens))
                elapsed = result.get("elapsed_seconds")
                if elapsed is not None:
                    reserved_wall = max(0.0, float(elapsed))
            connection.execute(
                """
                UPDATE campaign_attempt_reservations
                SET status = ?,
                    reserved_model_requests = ?,
                    reserved_tokens = ?,
                    reserved_wall_seconds = ?,
                    result = ?,
                    evidence_path = ?,
                    updated_at = ?,
                    completed_at = ?
                WHERE campaign_id = ? AND item_id = ? AND task_id = ?
                """,
                (
                    status,
                    model_requests,
                    reserved_tokens,
                    reserved_wall,
                    json.dumps(result, sort_keys=True),
                    evidence_path,
                    timestamp,
                    timestamp,
                    campaign_id,
                    item_id,
                    task_id,
                ),
            )
            row = connection.execute(
                """
                SELECT * FROM campaign_attempt_reservations
                WHERE campaign_id = ? AND item_id = ? AND task_id = ?
                """,
                (campaign_id, item_id, task_id),
            ).fetchone()
        return self._campaign_attempt_dict(row)

    def mark_campaign_attempt_uncertain(
        self,
        campaign_id: str,
        item_id: str,
        task_id: str,
        evidence_path: str = "",
        reason: str = "process_recovery_uncertain",
    ) -> dict:
        timestamp = now_iso()
        result = {
            "status": "uncertain",
            "usage_incomplete": True,
            "message": (
                "The process stopped after reserving this attempt. "
                "It was not retried because provider execution is uncertain."
            ),
            "reason": reason,
        }
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE campaign_attempt_reservations
                SET status = 'uncertain',
                    result = ?,
                    evidence_path = ?,
                    updated_at = ?,
                    completed_at = ?
                WHERE campaign_id = ? AND item_id = ? AND task_id = ?
                """,
                (
                    json.dumps(result, sort_keys=True),
                    evidence_path,
                    timestamp,
                    timestamp,
                    campaign_id,
                    item_id,
                    task_id,
                ),
            )
            row = connection.execute(
                """
                SELECT * FROM campaign_attempt_reservations
                WHERE campaign_id = ? AND item_id = ? AND task_id = ?
                """,
                (campaign_id, item_id, task_id),
            ).fetchone()
        return self._campaign_attempt_dict(row)

    def list_campaign_attempts(self, campaign_id: str) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM campaign_attempt_reservations
                WHERE campaign_id = ?
                ORDER BY created_at ASC
                """,
                (campaign_id,),
            ).fetchall()
        return [self._campaign_attempt_dict(row) for row in rows]

    def save_qualification(
        self,
        source_id: str,
        model_id: str,
        configuration_fingerprint: str,
        profile_id: str,
        eligibility: str,
        q_score: float | None,
        coverage: float | None,
        confidence: float | None,
        evidence_refs: list[str],
        result: dict,
        valid_until: str | None = None,
    ) -> dict:
        record_id = uuid.uuid4().hex
        if valid_until is None:
            from datetime import datetime, timedelta, timezone

            expiry_days = {
                "qualified": 90,
                "provisional": 30,
                "not_usable_for_profile": 90,
                "quarantined": 7,
                "incomplete": 1,
                "blocked": 1,
                "insufficient_evidence": 1,
                "inconclusive": 1,
            }.get(eligibility, 1)
            valid_until = (
                datetime.now(timezone.utc) + timedelta(days=expiry_days)
            ).isoformat()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO qualification_decisions (
                    id, source_id, model_id, configuration_fingerprint,
                    profile_id, eligibility, q_score, coverage, confidence,
                    evidence_refs, result, valid_until, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    source_id,
                    model_id,
                    configuration_fingerprint,
                    profile_id,
                    eligibility,
                    q_score,
                    coverage,
                    confidence,
                    json.dumps(evidence_refs, sort_keys=True),
                    json.dumps(result, sort_keys=True),
                    valid_until,
                    now_iso(),
                ),
            )
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM qualification_decisions WHERE id = ?",
                (record_id,),
            ).fetchone()
        return self._qualification_dict(row)

    def list_qualifications(self, profile_id: str | None = None) -> list[dict]:
        with self.connect() as connection:
            if profile_id:
                rows = connection.execute(
                    """
                    SELECT * FROM qualification_decisions
                    WHERE profile_id = ?
                    ORDER BY created_at DESC
                    """,
                    (profile_id,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM qualification_decisions
                    ORDER BY created_at DESC
                    """,
                ).fetchall()
        return [self._qualification_dict(row) for row in rows]

    def latest_qualification(
        self,
        profile_id: str,
        source_id: str | None = None,
        model_id: str | None = None,
    ) -> dict | None:
        clauses = ["profile_id = ?"]
        parameters: list[str] = [profile_id]
        if source_id:
            clauses.append("source_id = ?")
            parameters.append(source_id)
        if model_id:
            clauses.append("model_id = ?")
            parameters.append(model_id)
        with self.connect() as connection:
            row = connection.execute(
                f"""
                SELECT * FROM qualification_decisions
                WHERE {' AND '.join(clauses)}
                ORDER BY created_at DESC LIMIT 1
                """,
                tuple(parameters),
            ).fetchone()
        return self._qualification_dict(row) if row else None

    def recommend(
        self,
        profile_id: str,
        application_requirements: dict | None = None,
    ) -> dict:
        application_requirements = application_requirements or {}
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT q.*, s.provider, s.endpoint, s.name AS source_name,
                       s.status AS source_status,
                       c.listed AS catalog_listed
                FROM qualification_decisions q
                JOIN sources s ON s.id = q.source_id
                LEFT JOIN catalog_entries c
                  ON c.source_id = q.source_id
                 AND c.model_id = q.model_id
                WHERE q.profile_id = ?
                ORDER BY q.created_at DESC
                """,
                (profile_id,),
            ).fetchall()

        latest: dict[tuple[str, str], sqlite3.Row] = {}
        for row in rows:
            key = (row["source_id"], row["model_id"])
            if key not in latest:
                latest[key] = row

        qualified = []
        provisional = []
        blocked = []
        untested = []
        free_only = bool(application_requirements.get("free_only"))
        deadline = application_requirements.get("deadline_seconds")
        provider_filter = application_requirements.get("provider")
        for row in latest.values():
            if provider_filter and row["provider"] != provider_filter:
                continue
            item = dict(row)
            item["q_score"] = row["q_score"]
            item["coverage"] = row["coverage"]
            item["confidence"] = row["confidence"]
            item["evidence_refs"] = json.loads(row["evidence_refs"])
            item["result"] = json.loads(row["result"])
            eligibility = row["eligibility"]
            item["model_id"] = row["model_id"]
            item["source_status"] = row["source_status"]
            item["catalog_listed"] = row["catalog_listed"]

            reasons = []
            if row["source_status"] in {"removed", "failed", "configuration_required"}:
                reasons.append("source_unavailable")
            if not row["catalog_listed"]:
                reasons.append("model_removed_or_not_listed")
            if row["valid_until"]:
                from datetime import datetime, timezone

                try:
                    expires = datetime.fromisoformat(row["valid_until"])
                    if expires.tzinfo is None:
                        expires = expires.replace(tzinfo=timezone.utc)
                    if expires <= datetime.now(timezone.utc):
                        reasons.append("evidence_expired")
                except (TypeError, ValueError):
                    reasons.append("invalid_evidence_expiry")
            if not row["valid_until"]:
                reasons.append("evidence_expiry_missing")
            if free_only and row["provider"] not in {"lm_studio", "ollama"}:
                reasons.append("not_free_local")
            if provider_filter and row["provider"] != provider_filter:
                reasons.append("provider_mismatch")
            if deadline is not None:
                observed = item["result"].get("max_elapsed_seconds")
                if observed is None:
                    reasons.append("deadline_evidence_missing")
                elif float(observed) > float(deadline):
                    reasons.append("deadline_exceeded")
            if reasons:
                blocked.append({**item, "eligibility": "blocked", "blocked_reasons": reasons})
            elif free_only and row["provider"] not in {"lm_studio", "ollama"}:
                blocked.append({**item, "eligibility": "blocked_cost"})
            elif eligibility == "qualified":
                qualified.append(item)
            elif eligibility == "provisional":
                provisional.append(item)
            else:
                blocked.append(item)
        qualified.sort(key=lambda item: (-(item["q_score"] or 0), item["model_id"]))
        provisional.sort(key=lambda item: (-(item["q_score"] or 0), item["model_id"]))
        return {
            "profile_id": profile_id,
            "requirements": application_requirements,
            "deadline_seconds": deadline,
            "qualified": qualified,
            "provisional": provisional,
            "blocked": blocked,
            "untested": untested,
            "selection": qualified[0] if qualified else None,
            "reason": "qualified candidate found" if qualified else "no qualified candidate",
        }

    def delete_source(self, source_id: str) -> bool:
        with self.connect() as connection:
            timestamp = now_iso()
            cursor = connection.execute(
                """
                UPDATE sources
                SET status = 'removed',
                    standing_policy = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    json.dumps({"enabled": False}, sort_keys=True),
                    timestamp,
                    source_id,
                ),
            )
            connection.execute(
                "UPDATE catalog_entries SET listed = 0 WHERE source_id = ?",
                (source_id,),
            )
        return cursor.rowcount > 0

    def _source_dict(self, row: sqlite3.Row) -> dict:
        item = dict(row)
        item["standing_policy"] = json.loads(row["standing_policy"])
        return item

    def _catalog_dict(self, row: sqlite3.Row) -> dict:
        item = dict(row)
        item["metadata"] = json.loads(row["metadata"])
        return item

    def _item_dict(self, row: sqlite3.Row) -> dict:
        item = dict(row)
        item["result"] = json.loads(row["result"])
        return item

    def _qualification_dict(self, row: sqlite3.Row) -> dict:
        item = dict(row)
        item["evidence_refs"] = json.loads(row["evidence_refs"])
        item["result"] = json.loads(row["result"])
        return item

    def _campaign_attempt_dict(self, row: sqlite3.Row | None) -> dict:
        if row is None:
            return {}
        item = dict(row)
        item["result"] = json.loads(row["result"])
        return item
