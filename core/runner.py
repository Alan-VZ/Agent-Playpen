import argparse
import sys

from backends.backend_factory import BackendFactory
from core.agent import Agent
from debugging.cost_tracker import CostTracker
from debugging.tracer import Tracer
from memory.memory_manager import MemoryManager
from planner.react_planner import ReActPlanner
from planner.cot_planner import CoTPlanner
from planner.tree_planner import TreePlanner
from tools.tool_registry import ToolRegistry
from tools.packs.web.search_tool import WebSearchTool
from tools.packs.web.fetch_tool import FetchTool
from tools.packs.filesystem.read_file import ReadFileTool
from tools.packs.filesystem.write_file import WriteFileTool
from tools.packs.code.python_repl import PythonReplTool
from tools.packs.utils.calculator_tool import CalculatorTool
from tools.packs.utils.datetime_tool import DatetimeTool


PLANNERS = {
    "react": ReActPlanner,
    "cot": CoTPlanner,
    "tree": TreePlanner,
}

TOOL_MAP = {
    "web_search": WebSearchTool,
    "fetch": FetchTool,
    "read_file": ReadFileTool,
    "write_file": WriteFileTool,
    "python_repl": PythonReplTool,
    "calculator": CalculatorTool,
    "datetime": DatetimeTool,
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Agent Playpen — run an AI agent from the CLI"
    )
    parser.add_argument(
        "--task",
        required=True,
        help="The task or question for the agent to solve",
    )
    parser.add_argument(
        "--backend",
        default="lm_studio",
        choices=list(BackendFactory.REGISTRY.keys()),
        help="Which LLM backend to use (default: lm_studio)",
    )
    parser.add_argument(
        "--planner",
        default="react",
        choices=list(PLANNERS.keys()),
        help="Planning strategy (default: react)",
    )
    parser.add_argument(
        "--tools",
        nargs="+",
        default=["web_search", "fetch", "calculator"],
        help="Space-separated list of tool names to enable",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=10,
        help="Maximum Think-Act-Observe iterations (default: 10)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # --- Backend ---
    backend = BackendFactory.create(args.backend)

    # --- Planner ---
    planner_cls = PLANNERS[args.planner]
    planner = planner_cls(backend=backend)

    # --- Tools ---
    registry = ToolRegistry()
    for tool_name in args.tools:
        if tool_name not in TOOL_MAP:
            print(f"[WARN] Unknown tool: {tool_name} — skipping")
            continue
        registry.register(TOOL_MAP[tool_name]())

    # --- Memory ---
    memory = MemoryManager()

    # --- Observability ---
    tracer = Tracer()
    cost_tracker = CostTracker()

    # --- Agent ---
    agent = Agent(
        backend=backend,
        planner=planner,
        tool_registry=registry,
        memory_manager=memory,
        tracer=tracer,
        max_iterations=args.max_iter,
    )

    print(f"\n[Agent Playpen] Running task: {args.task}\n")
    result = agent.run(args.task)
    print(f"\n[Result]\n{result}\n")
    cost_tracker.report()


if __name__ == "__main__":
    main()
