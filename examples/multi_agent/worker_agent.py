# Demonstrates: an orchestrator that spawns a ResearchWorker and a WriterWorker, routes the search task to the first, passes results to the second, and collects the final document.

# Run:

# python examples/multi_agent/orchestrator.py --topic "future of autonomous vehicles"

# worker_agent.py — WorkerAgent base class with specialise() method
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))

from core.agent import Agent
from backends.lm_studio import LMStudioBackend
from debugging.tracer import Tracer
from memory.memory_manager import MemoryManager
from planner.react_planner import ReActPlanner
from tools.tool_registry import ToolRegistry
from tools.packs.web.search_tool import WebSearchTool
from tools.packs.web.fetch_tool import FetchTool
from tools.packs.utils.summarize_tool import SummarizeTool
from tools.packs.filesystem.write_file import WriteFileTool
from typing import Optional

ROLE_TOOLS = {
    "researcher": ["web_search", "fetch", "summarize"],
    "writer":     ["write_file", "summarize"],
}


class WorkerAgent:
    """A specialised agent worker with a role-specific tool set."""

    def __init__(self, role: str, worker_id: Optional[str] = None):
        self.role = role
        self.worker_id = worker_id or role

        backend = LMStudioBackend()
        registry = ToolRegistry()

        tool_objects = {
            "web_search": WebSearchTool(),
            "fetch":      FetchTool(),
            "summarize":  SummarizeTool(backend=backend),
            "write_file": WriteFileTool(allowed_dirs=[".", "output"]),
        }

        for tool_name in ROLE_TOOLS.get(role, []):
            if tool_name in tool_objects:
                registry.register(tool_objects[tool_name])

        planner = ReActPlanner(backend=backend)
        tracer = Tracer(session_id=f"worker_{self.worker_id}")
        memory = MemoryManager()

        self.agent = Agent(
            backend=backend,
            planner=planner,
            tool_registry=registry,
            memory_manager=memory,
            tracer=tracer,
            max_iterations=8,
        )

    def run(self, task: str) -> str:
        return self.agent.run(task)

    def specialise(self, role: str) -> "WorkerAgent":
        return WorkerAgent(role=role, worker_id=self.worker_id)
    