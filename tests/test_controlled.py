import json
import threading
from collections import Counter
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from benchmarks import controlled
from benchmarks.outcomes import category, safe_error
from benchmarks.runner import ExperimentConfig, Member
from benchmarks.tasks import expected, fixture
from planner.react_planner import ReActPlanner, AgentResponseFormatError


def plan():
    return controlled.StudyPlan(
        models=[
            {
                "provider": provider,
                "model": f"model-{i}" + (":free" if provider == "openrouter" else ""),
            }
            for provider in ["groq", "openrouter", "lm_studio"]
            for i in range(4)
        ]
    )


def test_full_matched_schedule():
    rows = controlled.cases(plan())
    assert len(rows) == 240
    assert len({r["case_id"] for r in rows}) == 240
    assert set(
        Counter((r["provider"], r["model"], r["seed"], r["arm"]) for r in rows).values()
    ) == {2}
    assert rows[0]["arm"] != rows[120]["arm"]


@pytest.mark.parametrize(
    "changes",
    [
        {"seeds": [1, 1]},
        {"seeds": [0]},
        {"models": [{"provider": "other", "model": "x"}]},
        {"models": [{"provider": "openrouter", "model": "paid"}]},
    ],
)
def test_invalid_manifest(changes):
    with pytest.raises(ValidationError):
        controlled.StudyPlan.model_validate({**plan().model_dump(), **changes})


@pytest.mark.parametrize(
    "text",
    [
        '<tool_call>{"name":"read_fixture"}</tool_call>',
        '```python\nread_fixture("orders.csv")\n```',
        '{"name":"read_fixture","arguments":{"name":"orders.csv"}}',
    ],
)
def test_tool_descriptions_are_not_final_answers(text):
    planner = ReActPlanner(Mock())
    planner.available_tool_names = {"read_fixture"}
    with pytest.raises(AgentResponseFormatError):
        planner.parse_thought(text)
    assert planner.parse_thought('{"net_total":44}').is_terminal
    assert planner.parse_thought("42").is_terminal


def test_direct_perfect_answer_is_only_diagnostic():
    backend = Mock()
    backend.chat.return_value = json.dumps(expected("B01", 1))
    backend.last_usage = {}
    backend.last_response_stats = {}
    result = controlled.direct_attempt(
        ExperimentConfig(agents=[Member(backend="groq", model="test")]),
        1,
        threading.Event(),
        lambda e: None,
        lambda m, c: backend,
    )
    assert result["diagnostic_correct"]
    assert result["evaluation"]["passed"] is False
    assert result["baseline_eligible"] is False
    assert not result["tool_events"]
    prompt = controlled.direct_messages(fixture("B01", 1))[1]["content"]
    assert "orders.csv" in prompt
    assert "Action:" not in prompt


@pytest.mark.parametrize(
    "code, expected_category",
    [
        (429, "provider_rate_limit"),
        (401, "provider_rejection"),
        (400, "provider_error"),
    ],
)
def test_provider_failures_are_distinct(code, expected_category):
    error = RuntimeError("hidden")
    error.status_code = code
    error.body = {
        "error": {
            "message": "Tool choice is none, but model called a tool",
            "code": "tool_use_failed",
            "failed_generation": "never save this",
        }
    }
    safe = safe_error(error)
    assert "failed_generation" not in json.dumps(safe)
    assert safe["provider_code"] == "tool_use_failed"
    assert category({"agents": [safe]}) == expected_category


def test_checkpoint_resume_and_quota_skip(tmp_path, monkeypatch):
    p = controlled.StudyPlan(
        models=[{"provider": "openrouter", "model": "test:free"}],
        seeds=[1, 2],
        rounds=1,
        cloud_interval_seconds=0,
    )
    calls = []

    def fake(case, *args):
        calls.append(case["case_id"])
        return {
            "status": "execution_failed",
            "outcome_category": "provider_rate_limit",
            "agents": [{"message": "Daily free-models-per-day exhausted"}],
            "evaluation": {"passed": False},
        }

    monkeypatch.setattr(controlled, "isolated_case", fake)
    first = controlled.run(p, tmp_path)
    assert len(calls) == 1
    assert len(first["results"]) == 4
    assert sum(r.get("attempted", False) for r in first["results"]) == 1
    assert first["results"][1]["outcome_category"] == "provider_quota_unavailable"
    (tmp_path / "STOP").touch()
    second = controlled.run(p, tmp_path, resume=True)
    assert len(second["results"]) == 4
    assert len(calls) == 1
    assert not (tmp_path / "STOP").exists()
    with pytest.raises(ValueError, match="plan changed"):
        controlled.run(p.model_copy(update={"seeds": [3]}), tmp_path, resume=True)


def test_live_status_stop_export_and_model_guard(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from debugging.dashboard import server
    monkeypatch.setattr(server, "ROOT", tmp_path)
    sid = "a" * 32
    target = tmp_path / "controlled-results" / sid
    p = controlled.StudyPlan(models=[{"provider": "groq", "model": "test"}], seeds=[1], rounds=1)
    (target).mkdir(parents=True)
    record = {"id": sid, "plan": p.model_dump(), "scheduled": 2, "status": "running", "results": [], "current": {"model": "test"}}
    (target / "study.json").write_text(json.dumps(record), encoding="utf-8")
    controlled.render(record, target)
    client = TestClient(server.app, base_url="http://127.0.0.1")
    assert client.get(f"/api/controlled-tests/{sid}").status_code == 403
    client.headers["X-Playpen-Token"] = server.API_TOKEN
    data = client.get(f"/api/controlled-tests/{sid}").json()
    assert data["completed"] == 0 and data["scheduled"] == 2
    page = client.get(f"/controlled-tests/{sid}")
    assert page.status_code == 200 and "Arm A" in page.text
    assert client.get(f"/api/controlled-tests/{sid}/export/csv").status_code == 200
    assert client.get(f"/api/controlled-tests/{sid}/export/invalid").status_code == 404
    assert client.post("/api/local-models/load", json={"model": "test"}).status_code == 409
    assert client.post(f"/api/controlled-tests/{sid}/stop", json={}).status_code == 200
    assert (target / "STOP").exists()
