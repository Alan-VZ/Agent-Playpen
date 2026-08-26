# research_agent.py (~100 lines)
# Demonstrates: a multi-step pipeline — search, fetch, summarise each result, synthesise into a final report, and write to disk.

# Run:

# python examples/research_agent.py --topic "quantum computing breakthroughs 2026"
"""
research_agent.py — Multi-step research pipeline.
~100 lines. Search -> Fetch -> Summarise -> Synthesise -> Write.
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backends.lm_studio import LMStudioBackend
from core.agent import Agent
from debugging.tracer import Tracer
from memory.memory_manager import MemoryManager
from planner.cot_planner import CoTPlanner
from tools.tool_registry import ToolRegistry
from tools.packs.web.search_tool import WebSearchTool
from tools.packs.web.fetch_tool import FetchTool
from tools.packs.utils.summarize_tool import SummarizeTool
from tools.packs.filesystem.write_file import WriteFileTool


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--topic",
        default="AI agent frameworks 2026",
        help="Research topic",
    )
    parser.add_argument(
        "--output",
        default="output/research_report.md",
        help="Output file path",
    )
    args = parser.parse_args()

    backend = LMStudioBackend()

    registry = ToolRegistry()
    registry.register(WebSearchTool(provider="duckduckgo"))
    registry.register(FetchTool(max_chars=5000))
    registry.register(SummarizeTool(backend=backend))
    registry.register(WriteFileTool(allowed_dirs=[".", "output"]))

    planner = CoTPlanner(backend=backend)
    tracer = Tracer(session_id="research_example")
    memory = MemoryManager()

    agent = Agent(
        backend=backend,
        planner=planner,
        tool_registry=registry,
        memory_manager=memory,
        tracer=tracer,
        max_iterations=15,
    )

    task = (
        f"Research the topic: '{args.topic}'.\n"
        "Step 1: Search the web for the top 3 results.\n"
        "Step 2: Fetch the full content of each result URL.\n"
        "Step 3: Summarise each page in 100 words.\n"
        "Step 4: Synthesise all summaries into a structured research report "
        "with an introduction, key findings, and conclusion.\n"
        f"Step 5: Write the complete report to '{args.output}'."
    )

    print(f"\n[Research Agent] Topic: {args.topic}\n")
    result = agent.run(task)
    print(f"\n[Done] Report written. Final output:\n{result}")
    tracer.save()


if __name__ == "__main__":
    main()
    