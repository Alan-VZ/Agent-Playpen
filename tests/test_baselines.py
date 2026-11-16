import json
import re
import threading
import time
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from benchmarks.tasks import TASKS, expected, fixture, score, selected_tasks, task_catalog
from benchmarks.runner import (ExperimentConfig, Member, Budget, ReadFixture, WriteArtifact,
                               attempt, run_experiment, summaries, wilson, BoundedCalculator, isolated_attempt)
from benchmarks.report import render_report
from debugging.dashboard import server, maintenance
from debugging.dashboard.readiness import Inventory, preflight, requirements, classify
from config import credentials


class ScriptedBackend:
    """Knows the answer only in tests. This is a runner check, not a model result."""
    def __init__(self):
        self.step = 0

    def chat(self, messages):
        prompt = messages[-1]["content"]
        # The task contract is embedded by the real planner.
        task = next(t for t, phrase in [("B01", "Deduplicate"), ("B02", "Prefer current notice"), ("B03", "Inspect all files"), ("B04", "Retrieve primary"), ("B05", "Choose a pump")] if phrase in prompt)
        seed = int(re.search(r"Fixture seed: (\d+)", prompt).group(1))
        data = fixture(task, seed)
        answer = expected(task, seed)
        names = list(data["documents"])
        if self.step < len(names):
            action, args = "read_fixture", {"name": names[self.step]}
        elif task == "B03" and self.step == len(names):
            action, args = "write_artifact", {"name": "report.json", "content": json.dumps(answer)}
        else:
            self.step += 1
            return 'Thought: Complete\nAction: FINISH\nAction Input: ' + json.dumps(answer)
        self.step += 1
        return 'Thought: Inspect input\nAction: ' + action + '\nAction Input: ' + json.dumps(args)


def scripted(member, config):
    return ScriptedBackend()


@pytest.mark.parametrize("task", TASKS)
def test_scripted_end_to_end_through_production_agent(task):
    result = attempt(ExperimentConfig(), task, backend_factory=scripted)
    assert result["status"] == "completed"
    assert result["evaluation"]["passed"], result
    assert result["usage"]["actual_tokens"] is None
    assert result["usage"]["estimated_reserved_usd"] is None


@pytest.mark.parametrize("task", TASKS)
def test_score_rejects_answer_without_tool_evidence(task):
    data = fixture(task)
    assert not score(data, expected(task, 1), [], {})["passed"]


@pytest.mark.parametrize("value", ['null', '[]', '{', '"plain text"'])
def test_invalid_output_is_not_a_neutral_score(value):
    result = score(fixture("B01"), value, [], {})
    assert result["score"] == 0
    assert not result["passed"]


def test_wrong_citation_and_arithmetic_fail():
    data = fixture("B02")
    answer = expected("B02", 1)
    answer["citations"]["opens"]["quote"] = "Unrelated but plausible"
    events = [{"operation": "read", "name": n, "status": "ok"} for n in data["documents"]]
    assert not score(data, answer, events, {})["checks"]["citation_opens"]
    data = fixture("B01")
    answer = expected("B01", 1)
    answer["net_total"] += 1
    assert not score(data, answer, [{"operation": "read", "name": "orders.csv", "status": "ok"}], {})["passed"]


@pytest.mark.parametrize("count", [1, 2, 4, 10])
def test_team_sizes_have_stable_attribution_and_aggregate_limits(count):
    config = ExperimentConfig(agents=[Member() for _ in range(count)], max_concurrency=2)
    result = attempt(config, "B05", backend_factory=scripted)
    assert result["evaluation"]["passed"]
    assert [r["agent_id"] for r in result["agents"]] == [f"agent-{n+1}" for n in range(count)]
    assert result["usage"]["tool_requests"] == count * 3
    assert len(result["usage"]["model_calls"]) == count * 4


@pytest.mark.parametrize("task", TASKS)
def test_team_can_satisfy_same_task_contract_without_single_agent_read_penalty(task):
    config = ExperimentConfig(agents=[Member(), Member(), Member(role="Critic")])
    result = attempt(config, task, backend_factory=scripted)
    assert result["evaluation"]["passed"], result


def test_budget_is_atomic_and_write_cannot_escape_or_arrive_late():
    budget = Budget(ExperimentConfig(tool_request_limit=1))
    writer = WriteArtifact(budget, "agent-1")
    assert writer.run(name="../secret", content="bad").startswith("[ERROR]")
    assert budget.tool_events[0]["status"] == "denied"
    with pytest.raises(RuntimeError):
        writer.run(name="report.json", content="late")
    budget.stopped.set()
    with pytest.raises(RuntimeError):
        writer.run(name="report.json", content="late")
    assert not budget.artifacts


def test_fixture_fault_resets_and_unknown_paths_are_denied():
    for _ in range(2):
        budget = Budget(ExperimentConfig())
        reader = ReadFixture(fixture("B04"), budget, "agent-1")
        assert reader.run(name="primary").startswith("[ERROR]")
        assert reader.run(name="empty") == ""
        assert reader.run(name="../../answers").startswith("[ERROR]")


def test_calculator_rejects_unbounded_exponentiation():
    calculator = BoundedCalculator(Budget(ExperimentConfig()), "agent-1")
    with pytest.raises(ValueError):
        calculator.run(expression="9**999999999")
    assert calculator.run(expression="3*4-2") == "10"


def test_token_budget_blocks_call_before_execution():
    factory = Mock(return_value=ScriptedBackend())
    result = attempt(ExperimentConfig(token_reservation_limit=1000), "B01", backend_factory=factory)
    assert result["status"] == "execution_failed"
    assert not result["evaluation"]["passed"]
    assert result["usage"]["model_calls"] == []


def test_cancel_prevents_future_artifacts_and_deadline_returns():
    release = threading.Event()
    class Slow:
        def chat(self, messages):
            release.wait(3)
            return 'Thought: write\nAction: write_artifact\nAction Input: {"name":"report.json","content":"late"}'
    started = time.monotonic()
    try:
        result = attempt(ExperimentConfig(timeout_seconds=1), "B03", backend_factory=lambda m, c: Slow())
        assert time.monotonic() - started < 2
        assert result["status"] == "timeout"
        assert result["artifacts"] == {}
    finally:
        release.set()


def test_resume_preserves_failed_attempts_and_exports_escape(tmp_path):
    config = ExperimentConfig(name="<script>alert(1)</script>")
    record = run_experiment([config], tmp_path / "results", repeats=1, backend_factory=scripted)
    assert len(record["attempts"]) == 5
    assert summaries(record)[0]["passed"] == 5
    original_ids = [r["id"] for r in record["attempts"]]
    resumed = run_experiment([config], tmp_path / "results", repeats=1, backend_factory=lambda m,c: pytest.fail("must not rerun"), resume=True)
    assert [r["id"] for r in resumed["attempts"]] == original_ids
    render_report(record, tmp_path / "results")
    report = (tmp_path / "results" / "comparison.html").read_text(encoding="utf-8")
    assert "<script>alert" not in report
    assert "&lt;script&gt;" in report
    with pytest.raises(ValueError):
        run_experiment([ExperimentConfig()], tmp_path / "results", repeats=1, resume=True)
    assert wilson(5, 5)[0] < .6


def test_readiness_tracks_teams_tools_and_fallbacks(tmp_path):
    config = {"agents": [{"backend": "openrouter", "tools": ["web_search"], "search_provider": "tavily"},
                         {"backend": "openrouter", "tools": ["nimble_extract"], "fallback_providers": ["brave"]}]}
    assert set(requirements(config)) == {"openrouter", "tavily", "nimble", "brave"}
    result = preflight(tmp_path, config)
    assert not result["ready"]
    assert set(result["blocking"]) == set(requirements(config))
    assert preflight(tmp_path, {"backend": "lm_studio"})["ready"]


def test_inventory_missing_saved_stale_and_invalidation(tmp_path, monkeypatch):
    inventory = Inventory(tmp_path)
    assert next(r for r in inventory.rows() if r["provider"] == "openrouter")["status"] == "missing"
    credentials.store.set("OPENROUTER_API_KEY", "fake-openrouter-value")
    monkeypatch.setattr(maintenance, "verify_access", lambda p, b: {"status": "verified", "message": "Accepted"})
    assert inventory.check("openrouter")["status"] == "verified"
    row = next(r for r in inventory.rows() if r["provider"] == "openrouter")
    assert not row["stale"]
    inventory.invalidate("openrouter")
    assert next(r for r in inventory.rows() if r["provider"] == "openrouter")["status"] == "unchecked"
    assert "fake-openrouter-value" not in inventory.path.read_text(encoding="utf-8")


@pytest.mark.parametrize("code,status", [(401,"authentication_rejected"),(402,"quota"),(403,"permission_denied"),(429,"rate_limited"),(500,"connection_failed")])
def test_readiness_errors_do_not_all_mean_bad_key(tmp_path, monkeypatch, code, status):
    def fail(*args):
        raise maintenance.MaintenanceError(f"Provider returned HTTP {code}.")
    monkeypatch.setattr(maintenance, "verify_access", fail)
    assert Inventory(tmp_path).check("openrouter")["status"] == status
    assert classify(code) == status


def test_inventory_vault_failure_does_not_prevent_repair_page(tmp_path, monkeypatch):
    def fail(name):
        raise credentials.CredentialError("Unavailable")
    monkeypatch.setattr(credentials.store, "get", fail)
    monkeypatch.setattr(server, "ROOT", tmp_path)
    client = TestClient(server.app, base_url="http://127.0.0.1", headers={"X-Playpen-Token": server.API_TOKEN})
    result = client.post("/api/readiness", json={"config": {"backend": "openrouter"}})
    assert result.status_code == 200
    assert not result.json()["ready"]
    assert all(r["status"] == "storage_unavailable" for r in result.json()["providers"])


def test_new_routes_are_session_protected_and_pages_render(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "ROOT", tmp_path)
    client = TestClient(server.app, base_url="http://127.0.0.1")
    assert client.post("/api/readiness", json={}).status_code == 403
    assert client.post("/api/benchmarks", json={}).status_code == 403
    for page in ["/", "/api-inventory", "/baselines"]:
        response = client.get(page)
        assert response.status_code == 200
        assert 'pp-secrets' in response.text
        assert 'aria-expanded="false"' in response.text
    client.headers["X-Playpen-Token"] = server.API_TOKEN
    assert client.post("/api/benchmarks", json={"configs":[{"agents":[{"backend":"openrouter"}]}],"repeats":1}).status_code == 409
    assert client.get("/api/benchmarks/not-an-id").status_code == 404
    assert client.post("/api/readiness/check", json={"provider":"unknown"}).status_code == 400


def test_save_invalidates_and_does_not_automatically_check(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "ENV_PATH", tmp_path / ".env")
    verify = Mock(side_effect=AssertionError("No automatic provider checks"))
    monkeypatch.setattr(maintenance, "verify_access", verify)
    client = TestClient(server.app, base_url="http://127.0.0.1", headers={"X-Playpen-Token": server.API_TOKEN})
    response = client.post("/api/save-key", json={"name":"OPENROUTER_API_KEY", "value":"inventoried-test-secret"})
    assert response.status_code == 200
    assert "inventoried-test-secret" not in response.text
    assert not verify.called
    result = client.post("/api/readiness", json={"config":{"backend":"openrouter"}}).json()
    assert result["ready"]
    assert "inventoried-test-secret" not in json.dumps(result)
    assert client.post("/api/readiness/review", json={"provider":"openrouter","next_review":"2026-12-15"}).status_code == 200
    row = next(r for r in Inventory(tmp_path).rows() if r["provider"] == "openrouter")
    assert row["next_review"] == "2026-12-15"


def test_concurrency_is_bounded_and_a_failed_researcher_is_isolated():
    state = {"active": 0, "peak": 0}
    lock = threading.Lock()
    class Counting(ScriptedBackend):
        def chat(self, messages):
            with lock:
                state["active"] += 1
                state["peak"] = max(state["peak"], state["active"])
            try:
                time.sleep(.01)
                return super().chat(messages)
            finally:
                with lock:
                    state["active"] -= 1
    def factory(member, config):
        if member.role == "Fail":
            raise RuntimeError("Injected worker failure")
        return Counting()
    config = ExperimentConfig(agents=[Member(role="Fail"), *[Member() for _ in range(9)]], max_concurrency=2)
    result = attempt(config, "B05", backend_factory=factory)
    assert result["evaluation"]["passed"]
    assert result["agents"][0]["status"] == "error"
    assert 1 <= state["peak"] <= 2


def test_money_reservations_require_known_rates_and_are_atomic():
    config = ExperimentConfig(dollar_limit=.01)
    budget = Budget(config)
    with pytest.raises(RuntimeError):
        budget.reserve_model([], "agent-1")
    budget = Budget(ExperimentConfig(dollar_limit=.01, usd_per_million_input=1, usd_per_million_output=1, rate_source="Test rate"))
    outcomes = []
    def reserve():
        try:
            budget.reserve_model([], "agent")
            outcomes.append(True)
        except RuntimeError:
            outcomes.append(False)
    threads = [threading.Thread(target=reserve) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert 0 < sum(outcomes) < 10
    assert budget.reserved_cost <= .01


def test_timeout_does_not_cancel_the_whole_experiment():
    global_stop = threading.Event()
    release = threading.Event()
    class Slow:
        def chat(self, messages):
            release.wait(3)
            return '{}'
    try:
        result = attempt(ExperimentConfig(timeout_seconds=1), "B01", stopped=global_stop, backend_factory=lambda m,c:Slow())
        assert result["status"] == "timeout"
        assert not global_stop.is_set()
    finally:
        release.set()


def test_paid_verification_requires_opt_in_and_has_separate_ledger(tmp_path, monkeypatch):
    credentials.store.set("EXA_API_KEY", "fake-exa-key")
    tool = Mock()
    monkeypatch.setattr(maintenance, "WebSearchTool", Mock(return_value=tool))
    inventory = Inventory(tmp_path)
    assert inventory.check("exa")["status"] == "unsupported"
    assert not tool.run.called
    assert inventory.check("exa", True)["status"] == "verified"
    assert tool.run.call_count == 1
    ledger = inventory.read()["exa"]["verification_usage"]
    assert ledger[0]["attempts"] == 1 and ledger[0]["actual_cost"] is None
    tool.run.side_effect = RuntimeError("exa HTTP 401")
    assert inventory.check("exa", True)["status"] == "authentication_rejected"


@pytest.mark.parametrize("provider", ["openai", "anthropic", "groq"])
def test_authenticated_model_checks_have_fixed_destinations_and_no_secret_output(tmp_path, monkeypatch, provider):
    from debugging.dashboard import readiness
    name = credentials.BACKEND_KEYS[provider]
    credentials.store.set(name, "fake-model-check-secret")
    response = Mock(status_code=200)
    response.iter_content.return_value = [b'{"data":[]}']
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    session = Mock()
    session.get.return_value = response
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(readiness.requests, "Session", Mock(return_value=session))
    result = Inventory(tmp_path).check(provider)
    assert result["status"] == "verified"
    assert result["scope"] == "authenticated model listing"
    assert "fake-model-check-secret" not in json.dumps(result)
    assert session.trust_env is False
    assert session.get.call_args.kwargs["allow_redirects"] is False
    assert session.get.call_args.args[0] == readiness.MODEL_CHECKS[provider]


def test_real_process_adapter_against_loopback_fake_model():
    """Exercise Windows spawn, actual SDK transport, usage, and worker teardown for free."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            data=json.dumps({"models":[{"key":"fixture-model","type":"llm","loaded_instances":[{"id":"fixture-model"}]}]}).encode()
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            backend = ScriptedBackend()
            backend.step = int(re.search(r"\nStep (\d+):", payload["messages"][-1]["content"]).group(1))
            content = backend.chat(payload["messages"])
            response = {"id":"test-completion","object":"chat.completion","created":1,"model":"fixture-model",
                        "choices":[{"index":0,"message":{"role":"assistant","content":content},"finish_reason":"stop"}],
                        "usage":{"prompt_tokens":100,"completion_tokens":50,"total_tokens":150}}
            data = json.dumps(response).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        config = ExperimentConfig(agents=[Member(base_url=f"http://127.0.0.1:{http.server_port}/v1", model="fixture-model")], timeout_seconds=30)
        result = isolated_attempt(config, "B01", 1)
        assert result["evaluation"]["passed"], result
        assert result["usage"]["actual_tokens"] == 300
    finally:
        http.shutdown()
        http.server_close()


def test_five_repeats_use_distinct_seeded_inputs_and_qualify(tmp_path):
    record = run_experiment([ExperimentConfig()], tmp_path / "five", repeats=5, backend_factory=scripted)
    assert len(record["attempts"]) == 25
    assert summaries(record)[0]["qualified"]
    assert len({r["fixture_hash"] for r in record["attempts"] if r["task"] == "B01"}) == 5


@pytest.mark.parametrize("values", [[], ["B06"], ["B01", "B01"], [None], "B01"])
def test_invalid_task_selections_are_rejected(values):
    with pytest.raises(ValueError):
        selected_tasks(values)


def test_task_subset_is_shared_recorded_and_reports_unselected_tasks(tmp_path):
    configs = [ExperimentConfig(name="single"), ExperimentConfig(name="team", agents=[Member(), Member(), Member()])]
    record = run_experiment(configs, tmp_path / "subset", repeats=1, tasks=["B04", "B01"], backend_factory=scripted)
    assert record["selected_tasks"] == ["B01", "B04"]
    assert record["scheduled"] == 4
    assert len(record["attempts"]) == 4
    assert {r["task"] for r in record["attempts"]} == {"B01", "B04"}
    for task in ["B01", "B04"]:
        assert len({r["fixture_hash"] for r in record["attempts"] if r["task"] == task}) == 1
    rows = render_report(record, tmp_path / "subset")
    assert all(row["scheduled"] == 2 for row in rows)
    assert all(row["tasks"]["B02"]["scheduled"] == 0 for row in rows)
    assert "Not selected" in (tmp_path / "subset" / "comparison.csv").read_text()
    resumed = run_experiment(configs, tmp_path / "subset", repeats=1, tasks=["B01", "B04"], backend_factory=scripted, resume=True)
    assert len(resumed["attempts"]) == 4
    with pytest.raises(ValueError, match="Resume configuration"):
        run_experiment(configs, tmp_path / "subset", repeats=1, tasks=["B01"], backend_factory=scripted, resume=True)


def test_subset_pass_does_not_claim_full_suite_qualification(tmp_path):
    record = run_experiment([ExperimentConfig()], tmp_path / "subset-five", repeats=5, tasks=["B01"], backend_factory=scripted)
    row = summaries(record)[0]
    assert row["selection_passed"]
    assert not row["qualified"]
    assert row["passed"] == row["scheduled"] == 5


def test_task_catalog_and_checkbox_pages_are_available_without_answer_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "ROOT", tmp_path)
    client = TestClient(server.app, base_url="http://127.0.0.1")
    assert client.get("/api/benchmark-tasks").status_code == 403
    client.headers["X-Playpen-Token"] = server.API_TOKEN
    catalog = client.get("/api/benchmark-tasks").json()["tasks"]
    assert [t["id"] for t in catalog] == list(TASKS)
    assert catalog == task_catalog()
    assert all("expected" not in task for task in catalog)
    for page in ["/", "/baselines"]:
        html = client.get(page).text
        assert html.count('name="baseline_tasks"') == 5
        assert "Load selected tasks" in html if page == "/" else "Select all" in html
    invalid = {"configs":[{}],"tasks":["B99"],"repeats":1}
    assert client.post("/api/benchmarks", json=invalid).status_code == 400
    invalid["tasks"] = []
    assert client.post("/api/benchmarks", json=invalid).status_code == 422


def test_dashboard_launch_runs_only_checked_tasks(tmp_path, monkeypatch):
    from debugging.dashboard import experiments
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(experiments, "JOBS", {})
    errors = []
    def offline(configs, output, repeats, **kwargs):
        try:
            return run_experiment(configs, output, repeats, backend_factory=scripted, **kwargs)
        except Exception as exc:
            errors.append(repr(exc))
            raise
    monkeypatch.setattr(experiments, "run_experiment", offline)
    client = TestClient(server.app, base_url="http://127.0.0.1", headers={"X-Playpen-Token": server.API_TOKEN})
    response = client.post("/api/benchmarks", json={"configs":[{"agents":[{"model":"fixture-model"}]}],"tasks":["B01","B05"],"repeats":1})
    assert response.status_code == 200
    job = response.json()["id"]
    result = None
    for _ in range(100):
        result = client.get("/api/benchmarks/" + job).json()
        if result["status"] != "running":
            break
        time.sleep(.02)
    assert not errors, errors
    assert result["status"] == "completed", result
    assert result["selected_tasks"] == ["B01", "B05"]
    assert result["progress"]["scheduled"] == 2
    assert [r["task"] for r in result["attempts"]] == ["B01", "B05"]


def test_search_check_returns_bounded_redacted_preview_without_saving_response(tmp_path, monkeypatch):
    credentials.store.set("NIMBLE_API_KEY", "private-test-key-never-display")
    tool = Mock()
    tool.run.return_value = "Result private-test-key-never-display " + "x" * 4000
    monkeypatch.setattr(maintenance, "WebSearchTool", Mock(return_value=tool))
    inventory = Inventory(tmp_path)
    result = inventory.check("nimble", True)
    assert result["status"] == "verified"
    assert len(result["test_result"]) <= 2500
    assert "private-test-key-never-display" not in result["test_result"]
    assert "test_result" not in inventory.read()["nimble"]
    assert "Result" not in json.dumps(inventory.read())
    tool.run.return_value = "[ERROR] provider operation failed"
    result = inventory.check("nimble", True)
    assert result["status"] != "verified" and result["test_result"] is None


def test_history_distinguishes_finished_attempts_from_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "ROOT", tmp_path)
    root = tmp_path / "benchmark-results"
    for name, passed in [("a" * 32, False), ("b" * 32, True)]:
        path = root / name
        path.mkdir(parents=True)
        record = {"created_at":"2026-11-16T12:00:00+00:00", "status":"completed", "scheduled":1,
                  "attempts":[{"status":"completed", "evaluation":{"passed":passed}}]}
        (path / "experiment.json").write_text(json.dumps(record), encoding="utf-8")
    client = TestClient(server.app, base_url="http://127.0.0.1", headers={"X-Playpen-Token":server.API_TOKEN})
    rows = {row["id"]:row for row in client.get("/api/benchmarks").json()}
    assert rows["a" * 32]["status"] == rows["b" * 32]["status"] == "completed"
    assert rows["a" * 32]["completed"] == rows["b" * 32]["completed"] == 1
    assert rows["a" * 32]["passed"] == 0 and rows["b" * 32]["passed"] == 1


def test_baseline_format_correction_does_not_execute_empty_fixture_call():
    backend = Mock()
    backend.chat.side_effect = [
        'Thought: read\nAction: read_fixture',
        'Thought: read\nAction: read_fixture\nAction Input: {"name":"orders.csv"}',
        'Thought: finish\nAction: FINISH\nAction Input: ' + json.dumps(expected('B01', 1)),
    ]
    result = attempt(ExperimentConfig(max_iterations=4), 'B01', seed=1, backend_factory=lambda m,c:backend)
    assert result['status'] == 'completed' and result['evaluation']['passed']
    assert len(result['tool_events']) == 1
    assert result['tool_events'][0]['name'] == 'orders.csv'
    assert result['tool_events'][0]['status'] == 'ok'
    assert 'no tool was executed' in backend.chat.call_args_list[1].args[0][-1]['content']
