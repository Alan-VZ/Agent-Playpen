# file_agent.py (~60 lines)
#Demonstrates: ReadFileTool, WriteFileTool, and the filesystem tool pack for CSV-to-markdown summarisation.

# Run:

# python examples/file_agent.py --input data/sample.csv --output output/summary.md
"""
file_agent.py — Read a CSV, process it, write a summary markdown file.
~60 lines. Demonstrates the filesystem tool pack.
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
from tools.packs.filesystem.read_file import ReadFileTool
from tools.packs.filesystem.write_file import WriteFileTool
from tools.packs.data.csv_tool import CsvTool


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",  default="data/sample.csv", help="Input CSV path")
    parser.add_argument("--output", default="output/summary.md", help="Output markdown path")
    args = parser.parse_args()

    backend = LMStudioBackend()

    registry = ToolRegistry()
    registry.register(ReadFileTool(allowed_dirs=[".", "data"]))
    registry.register(WriteFileTool(allowed_dirs=[".", "output"]))
    registry.register(CsvTool())

    planner = CoTPlanner(backend=backend)
    tracer = Tracer(session_id="file_example")
    memory = MemoryManager()

    agent = Agent(
        backend=backend,
        planner=planner,
        tool_registry=registry,
        memory_manager=memory,
        tracer=tracer,
        max_iterations=6,
    )

    task = (
        f"Read the CSV file at '{args.input}', "
        f"summarise its contents as a markdown report, "
        f"and write the report to '{args.output}'."
    )

    print(f"\n[File Agent] Task: {task}\n")
    result = agent.run(task)
    print(f"\n[Done] {result}")
    tracer.save()


if __name__ == "__main__":
    main()
    