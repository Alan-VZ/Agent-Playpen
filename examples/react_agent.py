# react_agent.py (~80 lines)
# Demonstrates: the ReAct planner, WebSearchTool, FetchTool, ToolRegistry, and the full agent setup wired together.
#
# Run:
#
# python examples/react_agent.py --task "What is the current population of Iceland?"
"""
react_agent.py — ReAct agent with web search, answering a research question.
~80 lines.
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backends.lm_studio import LMStudioBackend
from core.agent import Agent
from debugging.tracer import Tracer
from memory.memory_manager import MemoryManager
from planner.react_planner import ReActPlanner
from tools.tool_registry import ToolRegistry
from tools.packs.web.search_tool import WebSearchTool
from tools.packs.web.fetch_tool import FetchTool
from tools.packs.utils.calculator_tool import CalculatorTool


def build_tool_descriptions(registry: ToolRegistry) -> str:
    lines = []
    for name in registry.list_all():
        tool = registry.get(name)
        lines.append(f"  {tool.name}: {tool.description}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--task",
        default="What are the top 3 programming languages in 2026?",
        help="Research task for the agent",
    )
    args = parser.parse_args()

    # Backend
    backend = LMStudioBackend()

    # Tools
    registry = ToolRegistry()
    registry.register(WebSearchTool())
    registry.register(FetchTool())
    registry.register(CalculatorTool())

    tool_desc = build_tool_descriptions(registry)

    # Planner
    planner = ReActPlanner(backend=backend, tool_descriptions=tool_desc)

    # Observability
    tracer = Tracer(session_id="react_example")
    memory = MemoryManager()

    # Agent
    agent = Agent(
        backend=backend,
        planner=planner,
        tool_registry=registry,
        memory_manager=memory,
        tracer=tracer,
        max_iterations=8,
    )

    print(f"\n[ReAct Agent] Task: {args.task}\n")
    result = agent.run(args.task)
    print(f"\n[Final Answer]\n{result}\n")

    trace_path = tracer.save()
    print(f"[Trace saved to: {trace_path}]")


if __name__ == "__main__":
    main()
    