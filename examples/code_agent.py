# code_agent.py (~70 lines)
# Demonstrates: code generation, PythonReplTool execution, error reading, and iterative self-correction until the code runs successfully.

# 
# Run:
# python examples/code_agent.py --task "Write a Python function that computes the nth Fibonacci number"
"""
code_agent.py — Generate Python code, run it, fix errors, iterate.
~70 lines. Demonstrates PythonReplTool and iterative correction.
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
from tools.packs.code.python_repl import PythonReplTool
from tools.packs.code.linter_tool import LinterTool
from tools.packs.filesystem.write_file import WriteFileTool


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--task",
        default="Write a Python function that sorts a list of dicts by a given key.",
        help="Coding task for the agent",
    )
    args = parser.parse_args()

    backend = LMStudioBackend()

    registry = ToolRegistry()
    registry.register(PythonReplTool())
    registry.register(LinterTool())
    registry.register(WriteFileTool(allowed_dirs=[".", "output"]))

    tool_desc = (
        "python_repl: Execute Python code and return stdout/stderr.\n"
        "linter: Check Python code for syntax and style errors with ruff.\n"
        "write_file: Save code to a file."
    )

    planner = ReActPlanner(backend=backend, tool_descriptions=tool_desc)
    tracer = Tracer(session_id="code_example")
    memory = MemoryManager()

    agent = Agent(
        backend=backend,
        planner=planner,
        tool_registry=registry,
        memory_manager=memory,
        tracer=tracer,
        max_iterations=10,
    )

    full_task = (
        f"{args.task}\n"
        "Write the code, lint it, run it with a test case, "
        "fix any errors, and save the final version to output/solution.py."
    )

    print(f"\n[Code Agent] Task: {full_task}\n")
    result = agent.run(full_task)
    print(f"\n[Result]\n{result}")
    tracer.save()


if __name__ == "__main__":
    main()
    