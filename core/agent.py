from core.context import AgentContext
from core.exceptions import AgentCancelledError, AgentResponseFormatError
from config.credentials import redact
from backends.base_backend import BaseBackend
from planner.base_planner import BasePlanner, Thought
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
        final_answer_validator=None,
    ):
        if max_iterations < 1:
            raise ValueError("max_iterations must be at least 1")
        self.backend = backend
        self.planner = planner
        self.executor = ToolExecutor(tool_registry)
        self.memory = memory_manager
        self.tracer = tracer
        self.executor.on_event = lambda event: self.tracer.on_status(f"Tool {event['tool']}: {event['status']} · execution {event['execution_id']}", "tool_" + event["status"])
        self.max_iterations = max_iterations
        self.cancel_event = cancel_event
        self.final_answer_validator = final_answer_validator
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
        if getattr(type(self.backend), "reset_tool_session", None):
            self.backend.reset_tool_session()
        cached_reads = {}
        read_attempts = {}
        format_errors = 0
        final_errors = 0
        ctx = AgentContext(
            session_id=str(uuid.uuid4()),
            task=task,
        )
        self._check_cancelled()
        # Seed context with relevant memories from previous sessions
        ctx.memory_snapshots = self.memory.retrieve(task, top_k=5)

        # Expose registered tool contracts for every entry point, including CLI.
        self.planner.tool_descriptions = "\n".join(
            json.dumps(schema["function"]) for schema in self.executor.registry.to_openai_schemas()
        ) or "No tools available."
        self.planner.available_tool_names = set(self.executor.registry.list_all())

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
            try:
                thought = self._think(step, ctx)
            except AgentResponseFormatError as exc:
                format_errors += 1
                feedback = redact(str(exc))
                if getattr(type(self.backend), "accept_tool_result", None):
                    self.backend.accept_tool_result("Error: " + feedback)
                self.tracer.on_status("Model response rejected: " + feedback, "warning")
                if format_errors >= 3:
                    self.completion_status = "incomplete"
                    self.stop_reason = "Three consecutive invalid model responses. " + feedback
                    self.tracer.on_status("Stopped before a final answer: " + self.stop_reason, "warning")
                    return ""
                observation = "Observation: Response format error; no tool was executed. " + feedback
                ctx.thought_history.append(Thought(reasoning="Response format correction"))
                ctx.observation_history.append(observation)
                self.tracer.on_observe(observation)
                ctx.iteration += 1
                continue
            format_errors = 0
            self.tracer.on_think(thought)
            ctx.thought_history.append(thought)

            # If the planner considers this terminal, return the answer
            if thought.is_terminal:
                problem = self.final_answer_validator(thought.answer or "") if self.final_answer_validator else None
                if problem:
                    final_errors += 1
                    self.tracer.on_status("Final answer rejected: " + problem, "warning")
                    self.tracer.on_status("Rejected final report: " + redact(thought.answer or "")[:4000], "final_report_rejected")
                    if final_errors >= 2:
                        self.completion_status = "incomplete"
                        self.stop_reason = "Final report validation failed twice: " + problem
                        return ""
                    observation = "Observation: Final report validation failed. " + problem + " Return a corrected final report; do not repeat unchanged reads."
                    ctx.observation_history.append(observation)
                    self.tracer.on_observe(observation)
                    ctx.iteration += 1
                    continue
                self.completion_status = "success"
                self.tracer.on_response(thought.answer or "")
                return redact(thought.answer)

            # ACT: execute the tool named in the Thought
            self._check_cancelled()
            read_key = None
            if thought.tool_name in {"web_search", "fetch", "read_fixture"}:
                args = dict(thought.tool_args)
                if thought.tool_name == "web_search" and isinstance(args.get("query"), str):
                    args["query"] = " ".join(args["query"].casefold().split())
                read_key = (thought.tool_name, json.dumps(args, sort_keys=True, ensure_ascii=False))
                read_attempts[read_key] = read_attempts.get(read_key, 0) + 1
                if thought.tool_name == "read_fixture" and read_attempts[read_key] >= 3:
                    feedback = "This fixture has already been read. Use the existing observation to calculate and return the final report; no read was executed."
                    if read_attempts[read_key] >= 4:
                        self.stop_reason = "Repeated unchanged fixture reads after recovery feedback."
                        break
                    if getattr(type(self.backend), "accept_tool_result", None):
                        self.backend.accept_tool_result(feedback)
                    ctx.observation_history.append("Observation: " + feedback)
                    self.tracer.on_status(feedback, "warning")
                    self.tracer.on_observe(feedback)
                    ctx.iteration += 1
                    continue
                if thought.tool_name != "read_fixture" and read_attempts[read_key] >= 3:
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
            if getattr(type(self.backend), "accept_tool_result", None):
                self.backend.accept_tool_result(action_result)
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
        native = getattr(type(self.backend), "chat_with_tools", None)
        raw = self.backend.chat_with_tools(prompt, self.executor.registry.to_openai_schemas()) if native else self.backend.chat(prompt)
        self._check_cancelled()
        stats = getattr(self.backend, "last_response_stats", None)
        summary = f"Step {ctx.iteration + 1}: model response received ({len(raw) if isinstance(raw, str) else 0} text characters)."
        if isinstance(stats, dict):
            summary += " " + "; ".join(f"{key}={value}" for key, value in stats.items() if value is not None)
        self.tracer.on_status(summary, "model_response")
        if isinstance(stats, dict) and stats.get("finish_reason") == "length":
            raise AgentResponseFormatError("Output was truncated at the output-token limit. No action was executed and this is not a final answer. Reply concisely within the existing token budget; do not repeat the analysis. If reasoning consumes the allowance, increase Max tokens or use a supported lower reasoning budget.")
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("The model returned an empty text response. Try another model or increase the output token limit.")
        thought = self.planner.parse_thought(raw)
        if not thought.is_terminal and thought.tool_name in self.executor.registry.list_all():
            tool = self.executor.registry.get(thought.tool_name)
            parameters = tool.to_openai_schema()["function"].get("parameters", {})
            missing = [name for name in parameters.get("required", []) if name not in thought.tool_args]
            if missing:
                raise AgentResponseFormatError("Tool " + thought.tool_name + " is missing required arguments: " + ", ".join(missing) + ". Supply them in Action Input. No tool was executed.")
        return thought

    def _act(self, thought, ctx):
        """Execute the tool named in the thought.

        Errors are caught and returned as observations, allowing the agent
        to retry if the model made a typo in tool arguments.
        """
        try:
            value = self.executor.run(thought.tool_name, thought.tool_args)
            if isinstance(self.executor.last_result, dict):
                self.tracer.on_tool_result(self.executor.last_result)
            return value
        except Exception as exc:
            if isinstance(self.executor.last_result, dict):
                self.tracer.on_tool_result(self.executor.last_result)
            self.tracer.on_error(exc)
            # Return error as a recoverable observation, not a crash
            return redact(f"Error: {thought.tool_name} failed: {exc}")

    def _observe(self, action_result, ctx):
        """Format the action result as an observation string, with length cap."""
        obs = redact(f"Observation: {action_result}")
        if len(obs) > self.MAX_OBSERVATION_LENGTH:
            obs = obs[: self.MAX_OBSERVATION_LENGTH] + "... (truncated)"
        return obs
