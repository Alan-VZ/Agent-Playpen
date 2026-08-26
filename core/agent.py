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

    # Truncate observations to prevent context window blowout.
    MAX_OBSERVATION_LENGTH = 2000

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

        # Plan initial steps
        plan = self.planner.plan(task, ctx)

        # Main reasoning loop: re-plan dynamically based on observations
        while ctx.iteration < self.max_iterations:
            # Get the next step from the planner.
            # For ReAct, this calls the planner to decide the next action
            # based on accumulated observations.
            step = self.planner.next_step(ctx)
            if step is None:
                break

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

            # Store observation in memory for future retrieval
            try:
                self.memory.store(observation, memory_type="conversation")
            except KeyError:
                # Memory store not enabled, skip
                pass

            ctx.iteration += 1

        # Fallback: return last observation if no terminal thought was reached
        if ctx.observation_history:
            # Strip the "Observation: " prefix before returning
            last = ctx.observation_history[-1]
            if last.startswith("Observation: "):
                return last[len("Observation: ") :]
            return last
        return ""

    def _think(self, step, ctx):
        """Call the backend to produce a Thought."""
        prompt = self.planner.format_thought_prompt(step, ctx)
        raw = self.backend.chat(prompt)
        return self.planner.parse_thought(raw)

    def _act(self, thought, ctx):
        """Execute the tool named in the thought.
        
        Errors are caught and returned as observations, allowing the agent
        to retry if the model made a typo in tool arguments.
        """
        try:
            return self.executor.run(thought.tool_name, thought.tool_args)
        except Exception as exc:
            self.tracer.on_error(exc)
            # Return error as a recoverable observation, not a crash
            return f"Error: {thought.tool_name} failed: {exc}"

    def _observe(self, action_result, ctx):
        """Format the action result as an observation string, with length cap."""
        obs = f"Observation: {action_result}"
        if len(obs) > self.MAX_OBSERVATION_LENGTH:
            obs = obs[: self.MAX_OBSERVATION_LENGTH] + "... (truncated)"
        return obs