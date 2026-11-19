"""Offline MTT persistence, campaign and recommendation checks."""

import time

from fastapi.testclient import TestClient

from model_testing.store import MttStore
from model_testing.campaign import MttCampaignManager


def test_mtt_store_catalog_campaign_and_qualification(tmp_path):
    store = MttStore(tmp_path / "mtt.sqlite3")
    source = store.create_source(
        provider="lm_studio",
        name="Local",
        endpoint="http://localhost:1234/v1",
    )
    catalog = store.save_catalog(
        source["id"],
        [
            {"model_id": "model-a", "access_state": "account_or_local_ready"},
            {"model_id": "model-b", "access_state": "account_or_local_ready"},
        ],
    )
    assert catalog["snapshot"]["model_count"] == 2
    assert len(catalog["entries"]) == 2

    updated = store.save_catalog(
        source["id"],
        [{"model_id": "model-a", "access_state": "account_or_local_ready"}],
    )
    removed = [entry for entry in updated["entries"] if entry["model_id"] == "model-b"]
    assert removed and removed[0]["listed"] == 0

    campaign = store.create_campaign(
        source["id"],
        "diagnostics-v1",
        ["model-a"],
        {"max_attempts": 6, "max_model_requests": 12},
    )
    assert campaign["status"] == "queued"
    assert len(campaign["items"]) == 1

    store.save_qualification(
        source["id"],
        "model-a",
        "fingerprint-a",
        "diagnostics-v1",
        "qualified",
        100.0,
        1.0,
        None,
        ["evidence-a"],
        {"pass_count": 6, "max_elapsed_seconds": 1},
    )
    recommendation = store.recommend(
        "diagnostics-v1",
        {"free_only": True, "deadline_seconds": 400},
    )
    assert recommendation["selection"]["model_id"] == "model-a"
    assert recommendation["reason"] == "qualified candidate found"


def test_mtt_campaign_runner_persists_partial_and_complete(monkeypatch, tmp_path):
    store = MttStore(tmp_path / "mtt.sqlite3")
    source = store.create_source(
        provider="lm_studio",
        name="Local",
        endpoint="http://localhost:1234/v1",
    )
    campaign = store.create_campaign(
        source["id"],
        "diagnostics-v1",
        ["model-a"],
        {
            "case_timeout_seconds": 400,
            "max_attempts": 24,
            "max_model_requests": 80,
            "max_wall_seconds": 2400,
            "max_tokens": 300000,
        },
    )

    def isolated_attempt(config, task, seed, stopped=None, on_event=None):
        return {
            "id": f"attempt-{task}",
            "task": task,
            "status": "completed",
            "elapsed_seconds": 1,
            "evaluation": {"passed": True, "score": 100, "checks": {"valid_json": True}},
            "outcome_category": "passed",
            "usage": {
                "model_calls": [
                    {
                        "reserved_input": 100,
                        "reserved_output": 512,
                    }
                ],
                "tool_requests": 1,
                "reserved_tokens": 612,
                "actual_tokens": None,
                "estimated_reserved_usd": None,
            },
        }

    import model_testing.campaign as campaign_module

    monkeypatch.setattr(campaign_module, "isolated_attempt", isolated_attempt)
    manager = MttCampaignManager(store, tmp_path / "evidence")
    manager.start(campaign["id"])
    saved = store.get_campaign(campaign["id"])
    deadline = time.monotonic() + 5
    while saved["status"] not in {"completed", "cancelled", "failed"}:
        if time.monotonic() >= deadline:
            break
        time.sleep(0.02)
        saved = store.get_campaign(campaign["id"])

    assert saved["status"] == "completed"
    assert saved["items"][0]["status"] == "completed"
    assert saved["items"][0]["result"]["pass_count"] == 6
    qualifications = store.list_qualifications("diagnostics-v1")
    assert len(qualifications) == 1
    assert qualifications[0]["eligibility"] == "provisional"


def test_mtt_source_removal_preserves_history(tmp_path):
    store = MttStore(tmp_path / "mtt.sqlite3")
    source = store.create_source(
        provider="lm_studio",
        name="Local",
        endpoint="http://localhost:1234/v1",
    )
    store.save_catalog(
        source["id"],
        [{"model_id": "model-a", "access_state": "account_or_local_ready"}],
    )
    store.save_qualification(
        source["id"],
        "model-a",
        "fingerprint-a",
        "diagnostics-v1",
        "qualified",
        100.0,
        1.0,
        None,
        ["evidence-a"],
        {"pass_count": 6},
    )
    assert store.delete_source(source["id"])
    removed = store.get_source(source["id"])
    assert removed["status"] == "removed"
    assert store.list_catalog(source["id"], include_unlisted=True)["entries"][0]["listed"] == 0
    assert len(store.list_qualifications("diagnostics-v1")) == 1


def test_mtt_standing_policy_and_cancel(tmp_path):
    store = MttStore(tmp_path / "mtt.sqlite3")
    source = store.create_source(
        provider="lm_studio",
        name="Local",
        endpoint="http://localhost:1234/v1",
        standing_policy={
            "enabled": True,
            "profile_id": "diagnostics-v1",
            "campaign_on_discovery": True,
            "free_only": True,
        },
    )
    assert store.get_source(source["id"])["standing_policy"]["enabled"]
    campaign = store.create_campaign(
        source["id"],
        "diagnostics-v1",
        ["model-a"],
        {"case_timeout_seconds": 400},
    )
    store.update_campaign(campaign["id"], "running")
    store.update_item(campaign["items"][0]["id"], "running")
    saved = store.get_campaign(campaign["id"])
    assert saved["status"] == "running"
    store.update_campaign(campaign["id"], "cancelled", completed=True)
    store.update_item(campaign["items"][0]["id"], "cancelled", {"cancelled": True})
    saved = store.get_campaign(campaign["id"])
    assert saved["status"] == "cancelled"
    assert saved["items"][0]["status"] == "cancelled"


def test_mtt_page_and_database_first_api(monkeypatch, tmp_path):
    from debugging.dashboard import server

    monkeypatch.setenv("AGENT_PLAYPEN_MTT_DB", str(tmp_path / "mtt.sqlite3"))
    test_store = MttStore(tmp_path / "mtt.sqlite3")
    source = test_store.create_source(
        provider="lm_studio",
        name="Offline",
        endpoint="http://localhost:1234/v1",
    )
    test_store.save_catalog(
        source["id"],
        [{"model_id": "offline-model", "access_state": "account_or_local_ready"}],
    )

    client = TestClient(
        server.app,
        base_url="http://127.0.0.1",
        headers={"X-Playpen-Token": server.API_TOKEN},
    )
    assert client.get("/mtt").status_code == 200
    sources = client.get("/api/mtt/sources")
    assert sources.status_code == 200
    assert "sources" in sources.json()
    setup = client.get("/setup")
    assert setup.status_code == 200
    assert 'id="pp-menu-toggle"' in setup.text
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    assert "/api/mtt/sources" in openapi.json()["paths"]


def test_mtt_openapi_and_source_persistence_contract(tmp_path):
    store = MttStore(tmp_path / "mtt.sqlite3")
    source = store.create_source(
        provider="lm_studio",
        name="Persisted",
        endpoint="http://localhost:1234/v1",
    )
    store.save_catalog(
        source["id"],
        [
            {"model_id": "model-a"},
            {"model_id": "model-b"},
        ],
    )
    persisted = MttStore(tmp_path / "mtt.sqlite3")
    catalog = persisted.list_catalog(source["id"])
    assert catalog["source"]["name"] == "Persisted"
    assert len(catalog["entries"]) == 2


def test_failed_catalog_refresh_preserves_last_successful_models(tmp_path):
    store = MttStore(tmp_path / "mtt.sqlite3")
    source = store.create_source(
        provider="lm_studio",
        name="Local",
        endpoint="http://localhost:1234/v1",
    )
    store.save_catalog(
        source["id"],
        [{"model_id": "model-a", "access_state": "account_or_local_ready"}],
    )
    failed = store.save_catalog(
        source["id"],
        [],
        status="failed",
        error="connection refused",
    )
    entries = failed["entries"]
    assert len(entries) == 1
    assert entries[0]["model_id"] == "model-a"
    assert entries[0]["listed"] == 1
    assert failed["source"]["status"] == "failed"


def test_recommendation_blocks_expired_removed_and_deadline_mismatch(tmp_path):
    store = MttStore(tmp_path / "mtt.sqlite3")
    expired_source = store.create_source(
        provider="lm_studio",
        name="Expired",
        endpoint="http://localhost:1234/v1",
    )
    store.save_catalog(
        expired_source["id"],
        [{"model_id": "expired-model"}],
    )
    store.save_qualification(
        expired_source["id"],
        "expired-model",
        "expired-fingerprint",
        "diagnostics-v1",
        "qualified",
        100.0,
        1.0,
        None,
        ["expired-evidence"],
        {"pass_count": 6, "max_elapsed_seconds": 500},
        valid_until="2000-01-01T00:00:00+00:00",
    )

    removed_source = store.create_source(
        provider="lm_studio",
        name="Removed",
        endpoint="http://localhost:1234/v1",
    )
    store.save_catalog(
        removed_source["id"],
        [{"model_id": "removed-model"}],
    )
    store.save_qualification(
        removed_source["id"],
        "removed-model",
        "removed-fingerprint",
        "diagnostics-v1",
        "qualified",
        100.0,
        1.0,
        None,
        ["removed-evidence"],
        {"pass_count": 6, "max_elapsed_seconds": 1},
    )
    assert store.delete_source(removed_source["id"])

    recommendation = store.recommend(
        "diagnostics-v1",
        {"free_only": True, "deadline_seconds": 400},
    )
    assert recommendation["selection"] is None
    blocked_reasons = {
        reason
        for item in recommendation["blocked"]
        for reason in item.get("blocked_reasons", [])
    }
    assert "evidence_expired" in blocked_reasons
    assert "source_unavailable" in blocked_reasons

    deadline_source = store.create_source(
        provider="lm_studio",
        name="Deadline",
        endpoint="http://localhost:1234/v1",
    )
    store.save_catalog(
        deadline_source["id"],
        [{"model_id": "slow-model"}],
    )
    store.save_qualification(
        deadline_source["id"],
        "slow-model",
        "slow-fingerprint",
        "diagnostics-v1",
        "qualified",
        100.0,
        1.0,
        None,
        ["slow-evidence"],
        {"pass_count": 6, "max_elapsed_seconds": 500},
    )
    deadline = store.recommend(
        "diagnostics-v1",
        {"free_only": True, "deadline_seconds": 1},
    )
    assert deadline["selection"] is None
    assert "deadline_exceeded" in {
        reason
        for item in deadline["blocked"]
        for reason in item.get("blocked_reasons", [])
    }


def test_mtt_campaign_attempt_limit_and_partial_coverage(monkeypatch, tmp_path):
    store = MttStore(tmp_path / "mtt.sqlite3")
    source = store.create_source(
        provider="lm_studio",
        name="Local",
        endpoint="http://localhost:1234/v1",
    )
    campaign = store.create_campaign(
        source["id"],
        "diagnostics-v1",
        ["model-a"],
        {"max_attempts": 1, "max_model_requests": 80, "max_tokens": 300000},
    )
    calls = []

    def isolated_attempt(config, task, seed, stopped=None, on_event=None):
        calls.append(task)
        return {
            "id": f"attempt-{task}",
            "task": task,
            "status": "completed",
            "elapsed_seconds": 1,
            "evaluation": {"passed": True, "score": 100, "checks": {}},
            "outcome_category": "passed",
            "usage": {
                "model_calls": [{"reserved_input": 100, "reserved_output": 512}],
                "reserved_tokens": 612,
                "tool_requests": 0,
            },
        }

    import model_testing.campaign as campaign_module

    monkeypatch.setattr(campaign_module, "isolated_attempt", isolated_attempt)
    manager = MttCampaignManager(store, tmp_path / "evidence")
    manager.start(campaign["id"])
    saved = store.get_campaign(campaign["id"])
    deadline = time.monotonic() + 5
    while saved["status"] not in {"completed", "cancelled", "failed"}:
        if time.monotonic() >= deadline:
            break
        time.sleep(0.02)
        saved = store.get_campaign(campaign["id"])

    assert calls == ["D01"]
    assert saved["progress"]["ledger"]["used_attempts"] == 1
    item_result = saved["items"][0]["result"]
    assert item_result["attempt_count"] == 1
    assert item_result["coverage"] == 1 / 6
    qualifications = store.list_qualifications("diagnostics-v1")
    assert qualifications[0]["eligibility"] == "incomplete"

def test_latest_result_supersedes_old_qualification(tmp_path):
    store = MttStore(tmp_path / "mtt.sqlite3")
    source = store.create_source(
        provider="lm_studio",
        name="Local",
        endpoint="http://localhost:1234/v1",
    )
    store.save_catalog(
        source["id"],
        [{"model_id": "model-a"}],
    )
    store.save_qualification(
        source["id"],
        "model-a",
        "old-qualified-fingerprint",
        "diagnostics-v1",
        "qualified",
        100.0,
        1.0,
        None,
        ["old-evidence"],
        {"pass_count": 6, "max_elapsed_seconds": 1},
    )
    store.save_qualification(
        source["id"],
        "model-a",
        "new-failing-fingerprint",
        "diagnostics-v1",
        "not_usable_for_profile",
        17.0,
        1.0,
        None,
        ["new-evidence"],
        {"pass_count": 1, "max_elapsed_seconds": 400},
    )
    recommendation = store.recommend(
        "diagnostics-v1",
        {"free_only": True, "deadline_seconds": 400},
    )
    assert recommendation["selection"] is None


def test_unknown_profile_is_rejected(tmp_path):
    store = MttStore(tmp_path / "mtt.sqlite3")
    source = store.create_source(
        provider="lm_studio",
        name="Local",
        endpoint="http://localhost:1234/v1",
    )
    try:
        store.create_campaign(
            source["id"],
            "qualification-anything",
            ["model-a"],
            {},
        )
    except ValueError as exc:
        assert "Unknown MTT profile" in str(exc)
    else:
        raise AssertionError("Unknown profile must be rejected")


def test_campaign_request_wall_time_and_token_limits(monkeypatch, tmp_path):
    store = MttStore(tmp_path / "mtt.sqlite3")
    source = store.create_source(
        provider="lm_studio",
        name="Local",
        endpoint="http://localhost:1234/v1",
    )
    campaign = store.create_campaign(
        source["id"],
        "diagnostics-v1",
        ["model-a"],
        {
            "max_attempts": 6,
            "max_model_requests": 1,
            "max_wall_seconds": 60,
            "max_tokens": 1500,
            "case_timeout_seconds": 400,
        },
    )
    observed = {}

    def isolated_attempt(config, task, seed, stopped=None, on_event=None):
        observed["task"] = task
        observed["timeout"] = config.timeout_seconds
        observed["tokens"] = config.token_reservation_limit
        observed["model_requests"] = config.model_request_limit
        return {
            "id": "attempt-three-calls",
            "task": task,
            "status": "completed",
            "elapsed_seconds": 120,
            "evaluation": {"passed": True, "score": 100, "checks": {}},
            "outcome_category": "passed",
            "usage": {
                "model_calls": [
                    {"reserved_input": 100, "reserved_output": 512},
                    {"reserved_input": 100, "reserved_output": 512},
                    {"reserved_input": 100, "reserved_output": 512},
                ],
                "reserved_tokens": 1836,
                "tool_requests": 0,
            },
        }

    import model_testing.campaign as campaign_module

    monkeypatch.setattr(campaign_module, "isolated_attempt", isolated_attempt)
    manager = MttCampaignManager(store, tmp_path / "evidence")
    manager.start(campaign["id"])
    saved = store.get_campaign(campaign["id"])
    deadline = time.monotonic() + 5
    while saved["status"] not in {"completed", "cancelled", "failed"}:
        if time.monotonic() >= deadline:
            break
        time.sleep(0.02)
        saved = store.get_campaign(campaign["id"])

    assert observed["task"] == "D01"
    assert observed["timeout"] == 60
    assert observed["tokens"] == 1500
    assert observed["model_requests"] == 1
    assert saved["progress"]["ledger"]["used_attempts"] == 1
    assert saved["progress"]["ledger"]["used_model_requests"] == 3
    assert saved["progress"]["ledger"]["used_reserved_tokens"] == 1836
    assert saved["progress"]["ledger"]["used_wall_seconds"] == 120


def test_recovery_does_not_repeat_reserved_attempt(tmp_path):
    store = MttStore(tmp_path / "mtt.sqlite3")
    source = store.create_source(
        provider="lm_studio",
        name="Local",
        endpoint="http://localhost:1234/v1",
    )
    campaign = store.create_campaign(
        source["id"],
        "diagnostics-v1",
        ["model-a"],
        {
            "max_attempts": 1,
            "max_model_requests": 80,
            "max_tokens": 300000,
            "max_wall_seconds": 1200,
        },
    )
    item = campaign["items"][0]
    store.reserve_campaign_attempt(
        campaign["id"],
        item["id"],
        "D01",
        reserved_model_requests=1,
        reserved_tokens=612,
        reserved_wall_seconds=400,
    )
    campaign = store.get_campaign(campaign["id"])
    manager = MttCampaignManager(store, tmp_path / "evidence")
    ledger = manager._reconcile_attempt_ledger(
        campaign["id"],
        dict(campaign["progress"]["ledger"]),
    )
    assert ledger["used_attempts"] == 1
    assert ledger["used_reserved_tokens"] == 612
    assert manager._over_budget(campaign["budget"], ledger) == "attempt_limit"


def test_budget_blocks_model_calls_over_request_limit():
    from benchmarks.runner import Budget, ExperimentConfig

    budget = Budget(ExperimentConfig(model_request_limit=1))
    budget.reserve_model([{"role": "user", "content": "one"}], "agent-1")
    try:
        budget.reserve_model([{"role": "user", "content": "two"}], "agent-1")
    except RuntimeError as exc:
        assert "model request limit" in str(exc)
    else:
        raise AssertionError("Second model call must be blocked")


def test_campaign_completion_settles_model_token_and_wall_usage(tmp_path):
    store = MttStore(tmp_path / "mtt.sqlite3")
    source = store.create_source(
        provider="lm_studio",
        name="Local",
        endpoint="http://localhost:1234/v1",
    )
    campaign = store.create_campaign(
        source["id"],
        "diagnostics-v1",
        ["model-a"],
        {
            "max_attempts": 6,
            "max_model_requests": 4,
            "max_tokens": 20000,
            "max_wall_seconds": 1000,
        },
    )
    item = campaign["items"][0]
    attempts = [
        ("D01", 3, 9318, 10),
        ("D02", 3, 9318, 10),
        ("D03", 2, 6212, 10),
        ("D04", 1, 3106, 10),
    ]
    remaining_requests = 4
    remaining_tokens = 20000
    remaining_wall = 1000
    for task, model_requests, reserved_tokens, elapsed in attempts:
        store.reserve_campaign_attempt(
            campaign["id"],
            item["id"],
            task,
            reserved_model_requests=remaining_requests,
            reserved_tokens=remaining_tokens,
            reserved_wall_seconds=remaining_wall,
        )
        store.complete_campaign_attempt(
            campaign["id"],
            item["id"],
            task,
            {
                "task": task,
                "status": "completed",
                "elapsed_seconds": elapsed,
                "model_requests": model_requests,
                "reserved_tokens": reserved_tokens,
                "tool_requests": 0,
            },
        )
        remaining_requests -= model_requests
        remaining_tokens -= reserved_tokens
        remaining_wall -= elapsed

    manager = MttCampaignManager(store, tmp_path / "evidence")
    ledger = manager._reconcile_attempt_ledger(
        campaign["id"],
        dict(campaign["progress"]["ledger"]),
    )
    assert ledger["used_model_requests"] == 9
    assert ledger["used_reserved_tokens"] == 27954
    assert ledger["used_wall_seconds"] == 40
    assert manager._over_budget(campaign["budget"], ledger) == "model_request_limit"


def test_unresolved_recovery_is_not_reexecuted(monkeypatch, tmp_path):
    store = MttStore(tmp_path / "mtt.sqlite3")
    source = store.create_source(
        provider="lm_studio",
        name="Local",
        endpoint="http://localhost:1234/v1",
    )
    campaign = store.create_campaign(
        source["id"],
        "diagnostics-v1",
        ["model-a"],
        {
            "max_attempts": 6,
            "max_model_requests": 80,
            "max_tokens": 300000,
            "max_wall_seconds": 1200,
            "case_timeout_seconds": 400,
        },
    )
    item = campaign["items"][0]
    store.reserve_campaign_attempt(
        campaign["id"],
        item["id"],
        "D01",
        reserved_model_requests=1,
        reserved_tokens=612,
        reserved_wall_seconds=400,
    )

    dispatched = []

    def isolated_attempt(config, task, seed, stopped=None, on_event=None):
        dispatched.append(task)
        return {
            "id": f"attempt-{task}",
            "task": task,
            "status": "completed",
            "elapsed_seconds": 1,
            "evaluation": {"passed": True, "score": 100, "checks": {}},
            "outcome_category": "passed",
            "usage": {
                "model_calls": [{"reserved_input": 100, "reserved_output": 512}],
                "reserved_tokens": 612,
                "tool_requests": 0,
            },
        }

    import model_testing.campaign as campaign_module

    monkeypatch.setattr(campaign_module, "isolated_attempt", isolated_attempt)
    manager = MttCampaignManager(store, tmp_path / "evidence")
    manager.start(campaign["id"])
    saved = store.get_campaign(campaign["id"])
    deadline = time.monotonic() + 5
    while saved["status"] not in {"completed", "cancelled", "failed"}:
        if time.monotonic() >= deadline:
            break
        time.sleep(0.02)
        saved = store.get_campaign(campaign["id"])

    assert "D01" not in dispatched
    assert dispatched == ["D02", "D03", "D04", "D05", "D06"]
    reservations = {
        row["task_id"]: row
        for row in store.list_campaign_attempts(campaign["id"])
    }
    assert reservations["D01"]["status"] == "uncertain"


def test_fast_six_case_screen_reconciles_elapsed_time(monkeypatch, tmp_path):
    store = MttStore(tmp_path / "mtt.sqlite3")
    source = store.create_source(
        provider="lm_studio",
        name="Local",
        endpoint="http://localhost:1234/v1",
    )
    campaign = store.create_campaign(
        source["id"],
        "diagnostics-v1",
        ["model-a"],
        {
            "max_attempts": 6,
            "max_model_requests": 80,
            "max_tokens": 300000,
            "max_wall_seconds": 1200,
            "case_timeout_seconds": 400,
        },
    )

    def isolated_attempt(config, task, seed, stopped=None, on_event=None):
        return {
            "id": f"attempt-{task}",
            "task": task,
            "status": "completed",
            "elapsed_seconds": 1,
            "evaluation": {"passed": True, "score": 100, "checks": {}},
            "outcome_category": "passed",
            "usage": {
                "model_calls": [{"reserved_input": 100, "reserved_output": 512}],
                "reserved_tokens": 612,
                "tool_requests": 0,
            },
        }

    import model_testing.campaign as campaign_module

    monkeypatch.setattr(campaign_module, "isolated_attempt", isolated_attempt)
    manager = MttCampaignManager(store, tmp_path / "evidence")
    manager.start(campaign["id"])
    saved = store.get_campaign(campaign["id"])
    deadline = time.monotonic() + 5
    while saved["status"] not in {"completed", "cancelled", "failed"}:
        if time.monotonic() >= deadline:
            break
        time.sleep(0.02)
        saved = store.get_campaign(campaign["id"])

    assert saved["items"][0]["status"] == "completed"
    assert saved["items"][0]["result"]["attempt_count"] == 6
    assert saved["progress"]["ledger"]["used_wall_seconds"] == 6
