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

    state = BaselineSettlementState("B01", {"orders.csv"})
    state.observed.add("fixture_read")
    state.distinct_calculations.update({"37+12-5", "37-5", "37+5"})
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
