import asyncio
import json
import threading
from unittest.mock import Mock

import pytest

from advanced.multi_agent.manager import AgentManager
from advanced.multi_agent.message_bus import MessageBus
from core.agent import Agent
from core.context import AgentContext
from debugging.tracer import Tracer
from memory.memory_manager import MemoryManager
from planner.cot_planner import CoTPlanner
from planner.react_planner import ReActPlanner
from planner.tree_planner import TreePlanner
from tools.packs.utils.calculator_tool import CalculatorTool
from tools.tool_executor import ToolExecutor
from tools.tool_registry import ToolRegistry


def make_agent(tmp_path, replies, planner_cls=ReActPlanner, max_iterations=5):
    backend = Mock()
    backend.chat.side_effect = replies
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    agent = Agent(backend, planner_cls(backend), registry, MemoryManager(),
                  Tracer(str(tmp_path / "traces")), max_iterations)
    return agent, backend


def test_react_observation_feedback_and_memory(tmp_path):
    agent, backend = make_agent(tmp_path, [
        'Thought: calculate\nAction: calculator\nAction Input: {"expression":"6*7"}',
        'Thought: done\nAction: FINISH\nAction Input: 42',
    ])
    assert agent.run("multiply") == "42"
    assert "42" in backend.chat.call_args_list[1].args[0][-1]["content"]
    assert agent.memory.retrieve("42")


def test_tool_error_is_recoverable(tmp_path):
    agent, backend = make_agent(tmp_path, [
        'Thought: try\nAction: missing\nAction Input: {}',
        'Thought: recover\nAction: FINISH\nAction Input: recovered',
    ])
    assert agent.run("task") == "recovered"
    assert "not registered" in backend.chat.call_args.args[0][-1]["content"]


def test_iteration_budget(tmp_path):
    agent, backend = make_agent(tmp_path, [
        'Thought: loop\nAction: calculator\nAction Input: {"expression":"1+1"}',
    ], max_iterations=1)
    assert agent.run("task") == "2"
    assert backend.chat.call_count == 1


@pytest.mark.parametrize("limit", [0, -1])
def test_invalid_iteration_budget(tmp_path, limit):
    with pytest.raises(ValueError):
        make_agent(tmp_path, [], max_iterations=limit)


def test_plain_text_answer_is_preserved():
    assert ReActPlanner(Mock()).parse_thought("The answer is 42.").answer == "The answer is 42."


def test_cot_executes_planned_steps_with_feedback(tmp_path):
    agent, backend = make_agent(tmp_path, [
        '## Reasoning\nUse arithmetic.\n## Plan\n1. Multiply six by seven\n2. FINISH',
        'Action: calculator\nArgs: {"expression":"6*7"}',
        'FINISH 42',
    ], planner_cls=CoTPlanner)
    assert agent.run("task") == "42"
    assert "Multiply six by seven" in backend.chat.call_args_list[1].args[0][-1]["content"]
    assert "42" in backend.chat.call_args_list[2].args[0][-1]["content"]


def test_tree_uses_selected_branch(tmp_path):
    agent, backend = make_agent(tmp_path, [
        '[{"branch":1,"description":"Compute six times seven"}]',
        '{"score":9}', 'FINISH 42',
    ], planner_cls=TreePlanner)
    assert "42" in agent.run("task")
    assert "Compute six times seven" in backend.chat.call_args.args[0][-1]["content"]


@pytest.mark.parametrize("raw", ['[]', '{}', 'null', '[{}]', 'not json'])
def test_tree_invalid_branches_fall_back(raw):
    backend = Mock()
    backend.chat.side_effect = [raw, '{"score":5}']
    plan = TreePlanner(backend).plan("task", AgentContext("id", "task"))
    assert plan.steps[0].description == "task"


def test_memory_manager_keeps_multiple_working_items():
    memory = MemoryManager({"enabled_stores": ["working"]})
    memory.store("apple one")
    memory.store("apple two")
    assert len(memory.retrieve("apple")) == 2


@pytest.mark.parametrize("store", ["working", "conversation", "episodic", "semantic"])
def test_memory_store_retrieve(store):
    memory = MemoryManager({"enabled_stores": [store]})
    memory.store("apple fact", store)
    assert memory.retrieve("apple", store)


def test_ten_agent_routing():
    manager = AgentManager()
    for i in range(10):
        manager.spawn(str(i), Mock(run=Mock(return_value=str(i))))
    assert len(manager.broadcast("task")) == 10
    assert manager.route("task", "9") == "9"
    with pytest.raises(ValueError):
        manager.spawn("9", Mock())
    manager.kill("9")
    with pytest.raises(KeyError):
        manager.route("task", "9")


@pytest.mark.asyncio
async def test_message_bus_fanout_and_cleanup():
    bus = MessageBus()
    streams = [bus.subscribe("topic"), bus.subscribe("topic")]
    tasks = [asyncio.create_task(anext(stream)) for stream in streams]
    await asyncio.sleep(0)
    bus.publish("topic", {"value": 42})
    assert await asyncio.wait_for(asyncio.gather(*tasks), 1) == [{"value": 42}] * 2
    for stream in streams:
        await stream.aclose()
    assert not bus._subscribers["topic"]


def test_executor_timeout_returns_without_waiting():
    release = threading.Event()
    registry = ToolRegistry()
    registry.register(Mock(name="unused", **{}))
    tool = Mock()
    tool.name = "slow"
    tool.run.side_effect = lambda **kwargs: release.wait(2)
    registry.register(tool)
    try:
        with pytest.raises(TimeoutError):
            ToolExecutor(registry).run("slow", {}, timeout=0.01)
    finally:
        release.set()


def test_trace_persistence(tmp_path):
    tracer = Tracer(str(tmp_path))
    tracer.on_action("calculator", {"expression": "1+1"})
    tracer.on_observe("2")
    from pathlib import Path
    events = json.loads(Path(tracer.save()).read_text())
    assert [e["type"] for e in events] == ["act", "observe"]
