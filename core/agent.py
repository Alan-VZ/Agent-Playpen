from core.context import AgentContext
from core.exceptions import AgentCancelledError
from config.credentials import redact
from backends.base_backend import BaseBackend
from planner.base_planner import BasePlanner
from tools.tool_executor import ToolExecutor
from tools.tool_registry import ToolRegistry
from memory.memory_manager import MemoryManager
from debugging.tracer import Tracer
import uuid
import json


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
        cancel_event=None,
    ):
        if max_iterations < 1:
            raise ValueError("max_iterations must be at least 1")
        self.backend = backend
        self.planner = planner
        self.executor = ToolExecutor(tool_registry)
        self.memory = memory_manager
        self.tracer = tracer
        self.max_iterations = max_iterations
        self.cancel_event = cancel_event
        self.completion_status = "running"
        self.stop_reason = ""

    def _check_cancelled(self):
        if self.cancel_event is not None and self.cancel_event.is_set():
            self.completion_status = "cancelled"
            raise AgentCancelledError("Run stopped; no further operations were scheduled.")

    def run(self, task: str) -> str:
        """Execute a task end-to-end and return the final answer."""
        self.completion_status = "running"
        self.stop_reason = "The iteration budget or planned steps ended."
        cached_reads = {}
        read_attempts = {}
        ctx = AgentContext(
            session_id=str(uuid.uuid4()),
            task=task,
        )
        self._check_cancelled()
        # Seed context with relevant memories from previous sessions
        ctx.memory_snapshots = self.memory.retrieve(task, top_k=5)

        # Expose registered tool contracts for every entry point, including CLI.
        self.planner.tool_descriptions = "\n".join(
            str(schema["function"]) for schema in self.executor.registry.to_openai_schemas()
        ) or "No tools available."

        self.tracer.on_status("Preparing the task and planning the next action.")
        self.planner.plan(task, ctx)

        # Main reasoning loop: re-plan dynamically based on observations
        while ctx.iteration < self.max_iterations:
            self._check_cancelled()
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
                self.completion_status = "success"
                self.tracer.on_response(thought.answer or "")
                return redact(thought.answer)

            # ACT: execute the tool named in the Thought
            self._check_cancelled()
            read_key = None
            if thought.tool_name in {"web_search", "fetch"}:
                args = dict(thought.tool_args)
                if thought.tool_name == "web_search" and isinstance(args.get("query"), str):
                    args["query"] = " ".join(args["query"].casefold().split())
                read_key = (thought.tool_name, json.dumps(args, sort_keys=True, ensure_ascii=False))
                read_attempts[read_key] = read_attempts.get(read_key, 0) + 1
                if read_attempts[read_key] >= 3:
                    self.stop_reason = f"The same {thought.tool_name} request was attempted three times. Change the query/provider or supply a known source URL."
                    break
            if read_key is not None and read_key in cached_reads:
                self.tracer.on_status("Repeated identical read request: reusing the cached result without another network call. Change the request or finish with the limitation.", "warning")
                action_result = "Cached result (no new network call): " + str(cached_reads[read_key])
            else:
                self.tracer.on_action(thought.tool_name, thought.tool_args)
                action_result = self._act(thought, ctx)
                if read_key is not None:
                    cached_reads[read_key] = action_result
            self._check_cancelled()
            if isinstance(action_result, str) and action_result.lower().startswith(("no results", "fetch error", "error:", "[error]")):
                self.tracer.on_status("The tool returned no usable result or an error. Try another query/source; this is not evidence that the requested document does not exist.", "warning")
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

        self.completion_status = "incomplete"
        self.tracer.on_status("Stopped before a final answer: " + self.stop_reason, "warning")
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
        self.tracer.on_status(f"Step {ctx.iteration + 1}: waiting for the model response.", "model_request")
        raw = self.backend.chat(prompt)
        self._check_cancelled()
        stats = getattr(self.backend, "last_response_stats", None)
        summary = f"Step {ctx.iteration + 1}: model response received ({len(raw) if isinstance(raw, str) else 0} text characters)."
        if isinstance(stats, dict):
            summary += " " + "; ".join(f"{key}={value}" for key, value in stats.items() if value is not None)
        self.tracer.on_status(summary, "model_response")
        if not isinstance(raw, str) or not raw.strip():
            if isinstance(stats, dict) and stats.get("finish_reason") == "length":
                raise ValueError("The model hit the output-token limit before producing an answer. Increase Max tokens or choose a model that fits the current budget; reasoning tokens may consume the output allowance.")
            raise ValueError("The model returned an empty text response. Try another model or increase the output token limit.")
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
            return redact(f"Error: {thought.tool_name} failed: {exc}")

    def _observe(self, action_result, ctx):
        """Format the action result as an observation string, with length cap."""
        obs = redact(f"Observation: {action_result}")
        if len(obs) > self.MAX_OBSERVATION_LENGTH:
            obs = obs[: self.MAX_OBSERVATION_LENGTH] + "... (truncated)"
        return obs
