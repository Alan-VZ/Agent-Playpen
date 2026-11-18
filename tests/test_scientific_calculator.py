import csv
import io
import json
import os
from pathlib import Path
import subprocess
import time
from xml.etree import ElementTree

import pytest
from fastapi.testclient import TestClient

from playpen_qalculate import CalculationError, QalculateEngine
from playpen_qalculate.engine import checked_bindings, checked_expression
from playpen_qalculate.plotting import vector_values
from tools.packs.utils import scientific_calculator_tool as adapter


@pytest.mark.parametrize(
    "expression",
    [
        "load(1)",
        "EXPORT(1)",
        "ｌｏａｄ(1)",
        "save 1",
        "plot(x)",
        "system(1)",
        "unknown(2)",
        "1\nquit",
        "1;quit",
        "ans+1",
        "rand()",
        '"file"',
        "../file",
        "x:=2",
        "sqrt(2",
        "x(x+1)",
    ],
)
def test_blocks_commands_and_ambiguous_calls(expression):
    with pytest.raises(CalculationError):
        checked_expression(expression)


def test_exact_inputs_and_validation():
    assert checked_expression("50 ohm*2 A to V") == "50 ohm*2 A to V"
    assert checked_bindings({"distance": "120 km", "duration": 2}) == {
        "distance": "120 km",
        "duration": "2",
    }
    for values in [{"x": 0.1}, {"x": True}, {"load": "1"}, {"x": "export(1)"}]:
        with pytest.raises(CalculationError):
            checked_bindings(values)
    with pytest.raises(CalculationError, match="Precision"):
        QalculateEngine().evaluate("2", precision=True)


def test_diagnostic_pass_prevents_false_success(monkeypatch, tmp_path):
    engine = QalculateEngine(work_dir=tmp_path)
    calls = []

    def process(*args):
        calls.append(args)
        return "warning: Division by zero.\n1 / 0 = 1 / 0", ""

    monkeypatch.setattr(engine, "_process", process)
    with pytest.raises(CalculationError, match="Division by zero"):
        engine.evaluate("1/0")
    assert len(calls) == 1


def test_precision_strings_and_shared_deadline(monkeypatch, tmp_path):
    engine = QalculateEngine(work_dir=tmp_path)
    calls = []

    def process(argv, directory, deadline):
        calls.append((argv, deadline))
        return ("qalc 1.0" if argv == ["--version"] else "0.3000000000000000000001"), ""

    monkeypatch.setattr(engine, "_process", process)
    deadline = time.monotonic() + 2
    result = engine.evaluate("0.1+0.2", precision=80, _deadline=deadline)
    assert result["result"] == "0.3000000000000000000001"
    assert all(c[1] == deadline for c in calls)
    assert "--terse" not in calls[0][0] and "--terse" in calls[1][0]


def test_subprocess_uses_isolated_environment_and_no_shell(monkeypatch, tmp_path):
    captured = {}

    class Process:
        stdout = io.BytesIO(b"3")
        stderr = io.BytesIO()
        returncode = 0

        def wait(self, timeout=None):
            pass

    def popen(argv, **kwargs):
        captured.update(kwargs)
        return Process()

    engine = QalculateEngine(__file__)
    monkeypatch.setenv("OPENROUTER_API_KEY", "must-not-reach-child")
    monkeypatch.setattr(subprocess, "Popen", popen)
    assert engine._process(["--version"], tmp_path, time.monotonic() + 1)[0] == "3"
    assert captured["shell"] is False
    assert "OPENROUTER_API_KEY" not in captured["env"]
    assert captured["env"]["QALCULATE_USER_DIR"] == str(tmp_path)


def test_subprocess_timeout_kills_child(monkeypatch, tmp_path):
    class Process:
        stdout = io.BytesIO()
        stderr = io.BytesIO()
        killed = False

        def wait(self, timeout=None):
            if timeout is not None:
                raise subprocess.TimeoutExpired("qalc", timeout)

        def kill(self):
            self.killed = True

    process = Process()
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: process)
    with pytest.raises(CalculationError, match="terminated"):
        QalculateEngine(__file__)._process([], tmp_path, time.monotonic() + 1)
    assert process.killed


def test_subprocess_output_limit(monkeypatch, tmp_path):
    class Process:
        stdout = io.BytesIO(b"x" * 9000)
        stderr = io.BytesIO()
        returncode = 0

        def wait(self, timeout=None):
            pass

        def kill(self):
            pass

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: Process())
    with pytest.raises(CalculationError, match="output exceeded"):
        QalculateEngine(__file__, max_output=4096)._process(
            [], tmp_path, time.monotonic() + 1
        )


def test_vector_gaps_preserve_precision():
    assert vector_values("[0.1234567890123456789  (1 / 0)  i]", 3) == [
        "0.1234567890123456789",
        None,
        None,
    ]
    with pytest.raises(CalculationError):
        vector_values("[1  2]", 3)


def test_adapter_missing_dependency_and_unknown_fields(monkeypatch, tmp_path):
    monkeypatch.setattr(
        adapter,
        "configured_engine",
        lambda: (QalculateEngine("missing-qalc"), tmp_path),
    )
    result = json.loads(adapter.ScientificCalculatorTool().run(expression="1+2"))
    assert not result["ok"] and result["error"]["code"] == "dependency_missing"
    for kwargs in [
        {"executable": "elsewhere"},
        {"output_dir": "elsewhere"},
        {"operation": "plot", "mode": "exact"},
    ]:
        assert not json.loads(
            adapter.ScientificCalculatorTool().run(expression="1", **kwargs)
        )["ok"]


def test_registration_and_api_boundaries(monkeypatch, tmp_path):
    from core.runner import TOOL_MAP
    from debugging.dashboard import server, scientific
    from tools.tool_registry import ToolRegistry

    assert TOOL_MAP["scientific_calculator"] is adapter.ScientificCalculatorTool
    assert "scientific_calculator" in server.TOOL_CHOICES
    config = tmp_path / "tools.yaml"
    config.write_text("tools:\n  scientific_calculator:\n    enabled: true\n")
    assert ToolRegistry.from_yaml_config(str(config)).list_all() == [
        "scientific_calculator"
    ]
    monkeypatch.setattr(
        scientific, "configured_engine", lambda: (QalculateEngine("missing"), tmp_path)
    )
    monkeypatch.setattr(
        scientific, "calculate_request", lambda **kw: {"ok": True, "result": "0.3"}
    )
    client = TestClient(server.app, base_url="http://127.0.0.1")
    headers = {"X-Playpen-Token": server.API_TOKEN}
    assert (
        client.post("/api/scientific-calculator", json={"expression": "1"}).status_code
        == 403
    )
    assert (
        client.post(
            "/api/scientific-calculator",
            headers=headers,
            json={"expression": "1", "executable": "bad"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/scientific-calculator",
            headers=headers,
            json={"expression": "1", "precision": True},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/scientific-calculator",
            headers=headers,
            json={"expression": "0.1+0.2"},
        ).json()["result"]
        == "0.3"
    )
    assert not client.get("/api/scientific-calculator/status", headers=headers).json()[
        "available"
    ]
    assert client.get("/scientific-calculator").status_code == 200
    plot_id = "a" * 32
    folder = tmp_path / plot_id
    folder.mkdir()
    (folder / "plot.svg").write_text("<svg/>")
    assert (
        client.get(
            f"/api/scientific-calculator/artifacts/{plot_id}/plot.svg", headers=headers
        ).text
        == "<svg/>"
    )
    assert (
        client.get(
            f"/api/scientific-calculator/artifacts/{plot_id}/secret.txt",
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.get(
            "/api/scientific-calculator/artifacts/not-an-id/plot.svg", headers=headers
        ).status_code
        == 404
    )


@pytest.fixture
def real_engine(tmp_path):
    binary = os.environ.get("QALCULATE_TEST_BINARY")
    if not binary:
        pytest.skip("Set QALCULATE_TEST_BINARY to opt into real local Qalculate checks")
    return QalculateEngine(binary, work_dir=tmp_path / "work")


@pytest.mark.parametrize(
    ("expression", "variables", "mode", "expected"),
    [
        ("0.1+0.2", None, "approximate", "0.3"),
        (
            "distance/duration",
            {"distance": "120 km", "duration": "2 h"},
            "approximate",
            "60 km/h",
        ),
        ("50 ohm*2 A to V", None, "approximate", "100 V"),
        ("integrate(x^2,0,1)", None, "exact", "1/3"),
        ("sqrt(-1)", None, "exact", "i"),
        ("det([1,2;3,4])", None, "exact", "-2"),
    ],
)
def test_real_scientific_operations(real_engine, expression, variables, mode, expected):
    assert (
        real_engine.evaluate(expression, variables=variables, mode=mode)["result"]
        == expected
    )


def test_real_high_precision_errors_and_algebra(real_engine):
    result = real_engine.evaluate("sqrt(2)", precision=80)["result"]
    assert result.startswith(
        "1.414213562373095048801688724209698078569671875376948073176679737990732478462107"
    )
    assert "2" in real_engine.evaluate("solve(x^2=4,x)", mode="exact")["result"]
    assert real_engine.evaluate("diff(x^3,x)", mode="exact")["result"] == "3x^2"
    with pytest.raises(CalculationError, match="zero"):
        real_engine.evaluate("1/0")


def test_real_graph_files_gaps_and_precision(real_engine, tmp_path):
    result = real_engine.plot(
        "sin(x)",
        output_dir=tmp_path / "plots",
        x_min="-2",
        x_max="2",
        points=51,
        precision=80,
    )
    paths = result["artifacts"]
    assert result["finite_samples"] == 51
    svg = Path(paths["svg"]).read_text(encoding="utf-8")
    ElementTree.fromstring(svg)
    assert "<script" not in svg and "<polyline" in svg
    data = json.loads(Path(paths["json"]).read_text())
    rows = list(csv.reader(Path(paths["csv"]).open(newline="")))
    assert len(rows) == 52
    assert len(data["samples"][0]["y"]) > 70
    assert rows[1][1] == data["samples"][0]["y"]
    gap = real_engine.plot(
        "1/x", output_dir=tmp_path / "plots", x_min="-2", x_max="2", points=5
    )
    assert gap["finite_samples"] == 4 and gap["warnings"]
    assert (
        Path(gap["artifacts"]["svg"]).read_text(encoding="utf-8").count("<polyline")
        == 2
    )


def test_real_tool_roundtrip_through_agent(real_engine, monkeypatch, tmp_path):
    from core.agent import Agent
    from debugging.tracer import Tracer
    from memory.memory_manager import MemoryManager
    from planner.react_planner import ReActPlanner
    from tools.tool_registry import ToolRegistry

    class ScriptedBackend:
        calls = 0

        def chat(self, messages):
            self.calls += 1
            if self.calls == 1:
                assert "scientific_calculator" in messages[0]["content"]
                return 'Thought: Compute speed with units\nAction: scientific_calculator\nAction Input: {"expression":"distance/duration","variables":{"distance":"120 km","duration":"2 h"},"precision":80}'
            assert '"result": "60 km/h"' in messages[-1]["content"]
            return 'Thought: Report observed result\nAction: FINISH\nAction Input: "60 km/h"'

    monkeypatch.setattr(adapter, "configured_engine", lambda: (real_engine, tmp_path))
    registry = ToolRegistry()
    registry.register(adapter.ScientificCalculatorTool())
    backend = ScriptedBackend()
    agent = Agent(
        backend,
        ReActPlanner(backend),
        registry,
        MemoryManager({"enabled_stores": []}),
        Tracer(str(tmp_path / "traces")),
        max_iterations=3,
    )
    assert agent.run("What is the speed for 120 km travelled in 2 h?") == "60 km/h"
    assert agent.completion_status == "success" and backend.calls == 2
