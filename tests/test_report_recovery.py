"""Bounded recovery must not execute truncated calls or fabricate answers."""
import json
from unittest.mock import Mock

from core.agent import Agent
from benchmarks.runner import validate_final_report
from debugging.tracer import Tracer
from memory.memory_manager import MemoryManager
from planner.react_planner import ReActPlanner
from tools.base_tool import BaseTool
from tools.tool_registry import ToolRegistry


class FixtureTool(BaseTool):
    name = "read_fixture"
    description = "Read fixed input"
    parameters = {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}

    def __init__(self):
        self.calls = 0

    def run(self, name):
        self.calls += 1
        return "fixed input"


def agent_for(tmp_path, replies, validator=None, reasons=None):
    backend = Mock()
    prompts = []
    replies = iter(replies)
    reasons = iter(reasons or [])

    def chat(messages):
        prompts.append(messages)
        backend.last_response_stats = {"finish_reason": next(reasons, "stop")}
        return next(replies)

    backend.chat.side_effect = chat
    registry = ToolRegistry()
    tool = FixtureTool()
    registry.register(tool)
    agent = Agent(backend, ReActPlanner(backend), registry, MemoryManager({"enabled_stores": []}), Tracer(str(tmp_path)), max_iterations=8, final_answer_validator=validator)
    return agent, tool, prompts


def test_truncated_tool_call_is_not_executed(tmp_path):
    agent, tool, prompts = agent_for(tmp_path, ['Thought: read\nAction: read_fixture\nAction Input: {"name":"x"}', 'done'], reasons=['length','stop'])
    assert agent.run('task') == 'done'
    assert tool.calls == 0
    assert 'truncated' in prompts[1][-1]['content']


def test_unchanged_fixture_is_cached_and_loop_can_recover(tmp_path):
    call = 'Thought: read\nAction: read_fixture\nAction Input: {"name":"x"}'
    agent, tool, prompts = agent_for(tmp_path, [call, call, call, 'done'])
    assert agent.run('task') == 'done'
    assert tool.calls == 1
    assert 'already been read' in prompts[3][-1]['content']


def test_final_consistency_feedback_corrects_without_expected_answers(tmp_path):
    incorrect = {"net_total":44,"valid_orders":3,"duplicate_ids":["A"],"category_totals":{"parts":37,"service":12}}
    correct = {**incorrect,"category_totals":{"parts":32,"service":12}}
    agent, _, prompts = agent_for(tmp_path, [json.dumps(incorrect), json.dumps(correct)], lambda answer: validate_final_report('B01',answer))
    assert json.loads(agent.run('task')) == correct
    assert 'do not sum' in prompts[1][-1]['content']
    assert agent.completion_status == 'success'
    # Consistent but wrong answers must still be caught by the unchanged scorer.
    assert validate_final_report('B01',json.dumps({**correct,"net_total":45,"category_totals":{"parts":33,"service":12}})) is None


def test_repeated_invalid_final_report_stops_incomplete(tmp_path):
    agent, _, _ = agent_for(tmp_path, ['prose','still prose'], lambda answer: validate_final_report('B01',answer))
    assert agent.run('task') == ''
    assert agent.completion_status == 'incomplete'
    assert 'validation failed twice' in agent.stop_reason


def test_autonomous_and_guided_settlement_have_distinct_identity(tmp_path):
    backend = Mock()
    backend.chat.side_effect = ["done"]
    backend.last_response_stats = {"finish_reason": "stop"}
    registry = ToolRegistry()
    autonomous = Agent(
        backend, ReActPlanner(backend), registry,
        MemoryManager({"enabled_stores": []}), Tracer(str(tmp_path)),
        settlement_mode="autonomous",
    )
    guided = Agent(
        backend, ReActPlanner(backend), registry,
        MemoryManager({"enabled_stores": []}), Tracer(str(tmp_path)),
        settlement_mode="guided",
    )
    assert autonomous.settlement_mode == "autonomous"
    assert guided.settlement_mode == "guided"


def test_guided_settlement_rejects_extra_tool_after_defined_state(tmp_path):
    from benchmarks.settlement import BaselineSettlementState
    from decimal import Decimal

    state = BaselineSettlementState("B01", {
        "orders.csv": "id,category,status,amount\nA,parts,paid,37\nA,parts,paid,37\nB,parts,refund,5\nC,service,paid,12\nD,parts,cancelled,99\n"
    })
    state.observed.add("fixture_read")
    state.calculation_results.update({Decimal("44"), Decimal("32"), Decimal("12")})
    assert state.ready()

    backend = Mock()
    backend.chat.side_effect = [
        'Thought: read\nAction: read_fixture\nAction Input: {"name":"orders.csv"}',
        'Thought: complete\nAction: FINISH\nAction Input: ' + json.dumps({
            "net_total":44,
            "valid_orders":3,
            "duplicate_ids":["A"],
            "category_totals":{"parts":32,"service":12},
        }),
    ]
    backend.last_response_stats = {"finish_reason":"stop"}
    registry = ToolRegistry()
    tool = FixtureTool()
    registry.register(tool)
    agent = Agent(
        backend,
        ReActPlanner(backend),
        registry,
        MemoryManager({"enabled_stores": []}),
        Tracer(str(tmp_path)),
        max_iterations=4,
        settlement_mode="guided",
        settlement_state=state,
    )
    assert json.loads(agent.run("task"))["net_total"] == 44
    assert tool.calls == 0
    assert agent.completion_status == "success"


def test_failed_operations_do_not_advance_guided_state():
    from benchmarks.settlement import BaselineSettlementState

    b01 = BaselineSettlementState("B01", {
        "orders.csv": "id,category,status,amount\nA,parts,paid,37\nA,parts,paid,37\nB,parts,refund,5\nC,service,paid,12\nD,parts,cancelled,99\n"
    })
    failed_read = {"ok": True, "status": "succeeded", "result": "[ERROR] read failed"}
    b01.record("read_fixture", {"name": "orders.csv"}, "[ERROR] read failed", failed_read)
    b01.record("calculator", {"expression": "1/0"}, "Error: division failed", {"ok": False, "status": "failed"})
    assert not b01.ready()
    assert "orders.csv" in b01.remaining()

    b02 = BaselineSettlementState("B02", {"archive": "old", "notice": "new", "catalog": "21"})
    for name in ("archive", "notice", "catalog"):
        b02.record("read_fixture", {"name": name}, "[ERROR] source unavailable", {"ok": True, "status": "succeeded", "result": "[ERROR] source unavailable"})
    assert not b02.ready()


def test_verified_b01_calculation_results_are_required():
    from benchmarks.settlement import BaselineSettlementState

    state = BaselineSettlementState("B01", {
        "orders.csv": "id,category,status,amount\nA,parts,paid,37\nA,parts,paid,37\nB,parts,refund,5\nC,service,paid,12\nD,parts,cancelled,99\n"
    })
    succeeded = {"ok": True, "status": "succeeded"}
    state.record("read_fixture", {"name": "orders.csv"}, "fixture", succeeded)
    state.record("calculator", {"expression": "44"}, "44", succeeded)
    assert not state.ready()
    state.record("calculator", {"expression": "32"}, "32", succeeded)
    state.record("calculator", {"expression": "12"}, "12", succeeded)
    assert state.ready()


def test_guided_terminal_report_is_withheld_until_state_is_ready(tmp_path):
    from benchmarks.settlement import BaselineSettlementState

    state = BaselineSettlementState("B01", {"orders.csv": "fixture"})
    backend = Mock()
    backend.chat.side_effect = [
        'Thought: finish\nAction: FINISH\nAction Input: ' + json.dumps({
            "net_total":44,
            "valid_orders":3,
            "duplicate_ids":["A"],
            "category_totals":{"parts":32,"service":12},
        }),
        'Thought: finish\nAction: FINISH\nAction Input: ' + json.dumps({
            "net_total":44,
            "valid_orders":3,
            "duplicate_ids":["A"],
            "category_totals":{"parts":32,"service":12},
        }),
    ]
    backend.last_response_stats = {"finish_reason":"stop"}
    agent = Agent(
        backend,
        ReActPlanner(backend),
        ToolRegistry(),
        MemoryManager({"enabled_stores": []}),
        Tracer(str(tmp_path)),
        max_iterations=4,
        settlement_mode="guided",
        settlement_state=state,
    )
    assert agent.run("task") == ""
    assert agent.completion_status == "incomplete"
    assert "required observed state" in agent.stop_reason


def test_b02_and_b05_reports_require_observed_evidence():
    from benchmarks.settlement import BaselineSettlementState

    b02 = BaselineSettlementState("B02", {
        "archive": "Old.",
        "notice": "The library opens at 10:00. Closed on Sundays.",
        "catalog": "The library lends books for 21 days.",
    })
    for name in b02.documents:
        b02.record("read_fixture", {"name": name}, b02.documents[name], {"ok": True, "status": "succeeded"})
    b02.record_report(json.dumps({
        "opens": "10:00",
        "closed": "Sunday",
        "loan_days": 21,
        "citations": {
            "opens": {"source": "notice", "quote": "The library opens at 10:00."},
            "closed": {"source": "notice", "quote": "Closed on another day."},
            "loan_days": {"source": "catalog", "quote": "The library lends books for 21 days."},
        },
    }))
    assert not b02.ready()

    b05 = BaselineSettlementState("B05", {
        "authority": "Maximum load is 10 A. Pump A requires 12 A. Pump B requires 8 A."
    })
    b05.record("read_fixture", {"name": "authority"}, b05.documents["authority"], {"ok": True, "status": "succeeded"})
    b05.record_report(json.dumps({
        "choice": "B",
        "source": "authority",
        "quote": "Pump B requires 8 A.",
        "rejected_reason": "A exceeds the limit.",
    }))
    assert not b05.ready()

    b02_valid = BaselineSettlementState("B02", {
        "archive": "Old.",
        "notice": "The library opens at 10:00. Closed on Sundays.",
        "catalog": "The library lends books for 21 days.",
    })
    for name in b02_valid.documents:
        b02_valid.record("read_fixture", {"name": name}, b02_valid.documents[name], {"ok": True, "status": "succeeded"})
    b02_valid.record_report(json.dumps({
        "opens": "10:00",
        "closed": "Sunday",
        "loan_days": 21,
        "citations": {
            "opens": {"source": "notice", "quote": "The library opens at 10:00."},
            "closed": {"source": "notice", "quote": "Closed on Sundays."},
            "loan_days": {"source": "catalog", "quote": "The library lends books for 21 days."},
        },
    }))
    assert b02_valid.ready()

    b05_valid = BaselineSettlementState("B05", {
        "authority": "Maximum load is 10 A. Pump A requires 12 A. Pump B requires 8 A."
    })
    b05_valid.record("read_fixture", {"name": "authority"}, b05_valid.documents["authority"], {"ok": True, "status": "succeeded"})
    b05_valid.record_report(json.dumps({
        "choice": "B",
        "max_load": 10,
        "chosen_load": 8,
        "source": "authority",
        "quote": "Pump B requires 8 A.",
        "rejected_reason": "Pump A exceeds the 10 A maximum: 12 A.",
    }))
    assert b05_valid.ready()


def test_invalid_whitespace_expression_does_not_block_valid_correction(tmp_path):
    class CalculatorGuard(BaseTool):
        name = "calculator"
        description = "calculator"
        parameters = {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        }

        def __init__(self):
            self.calls = []

        def run(self, expression):
            self.calls.append(expression)
            if expression == "1 2":
                raise ValueError("Invalid arithmetic expression")
            if expression == "12":
                return "12"
            raise ValueError("Unexpected expression")

    backend = Mock()
    backend.chat.side_effect = [
        'Thought: invalid\nAction: calculator\nAction Input: {"expression":"1 2"}',
        'Thought: corrected\nAction: calculator\nAction Input: {"expression":"12"}',
        'Thought: done\nAction: FINISH\nAction Input: "12"',
    ]
    backend.last_response_stats = {"finish_reason": "stop"}
    registry = ToolRegistry()
    calculator = CalculatorGuard()
    registry.register(calculator)
    agent = Agent(
        backend,
        ReActPlanner(backend),
        registry,
        MemoryManager({"enabled_stores": []}),
        Tracer(str(tmp_path)),
        max_iterations=5,
    )
    assert agent.run("Calculate 12") == "12"
    assert calculator.calls == ["1 2", "12"]
