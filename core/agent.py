from core.context import AgentContext
from core.exceptions import AgentMaxIterationsError, AgentToolError
from backends.base_backend import BaseBackend
from planner.base_planner import BasePlanner
from tools.tool_executor import ToolExecutor
from tools.tool_registry import ToolRegistry
from memory.memory_manager import MemoryManager
from debugging.tracer import Tracer
import uuid


class Agent:
    """Orchestrates the Think -> Act -> Observe reasoning loop."""

    def __init__(
        self,
        backend: BaseBackend,
        planner: BasePlanner,
        tool_registry: ToolRegistry,
        memory_manager: MemoryManager,
        tracer: Tracer,
        max_iterations: int = 10,
    ):
        self.backend = backend
        self.planner = planner
        self.executor = ToolExecutor(tool_registry)
        self.memory = memory_manager
        self.tracer = tracer
        self.max_iterations = max_iterations

    def run(self, task: str) -> str:
        """Execute a task end-to-end and return the final answer."""
        ctx = AgentContext(
            session_id=str(uuid.uuid4()),
            task=task,
        )
        # Seed context with relevant memories from previous sessions
        ctx.memory_snapshots = self.memory.retrieve(task, top_k=5)

        # Ask the planner to decompose the task into steps
        plan = self.planner.plan(task, ctx)

        for step in plan.steps:
            if ctx.iteration >= self.max_iterations:
                raise AgentMaxIterationsError(ctx.iteration)

            # THINK: call backend to produce a structured Thought
            thought = self._think(step, ctx)
            self.tracer.on_think(thought)
            ctx.thought_history.append(thought)

            # If the planner considers this terminal, return the answer
            if thought.is_terminal:
                return thought.answer

            # ACT: execute the tool named in the Thought
            action_result = self._act(thought, ctx)
            self.tracer.on_action(thought.tool_name, thought.tool_args)
            ctx.action_history.append(action_result)

            # OBSERVE: format the result as a natural-language observation
            observation = self._observe(action_result, ctx)
            self.tracer.on_observe(observation)
            ctx.observation_history.append(observation)

            ctx.iteration += 1

        # Fallback: return last observation if no terminal thought was reached
        return ctx.observation_history[-1] if ctx.observation_history else ""

    def _think(self, step, ctx):
        """Call the backend to produce a Thought."""
        prompt = self.planner.format_thought_prompt(step, ctx)
        raw = self.backend.chat(prompt)
        return self.planner.parse_thought(raw)

    def _act(self, thought, ctx):
        """Execute the tool named in the thought."""
        try:
            return self.executor.run(thought.tool_name, thought.tool_args)
        except Exception as exc:
            self.tracer.on_error(exc)
            raise AgentToolError(thought.tool_name, exc) from exc

    def _observe(self, action_result, ctx):
        """Format the action result as an observation string."""
        return f"Observation: {action_result}"