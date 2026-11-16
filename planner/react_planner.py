import re
import json
from core.exceptions import AgentResponseFormatError
from planner.base_planner import BasePlanner, Plan, Step, Thought

REACT_SYSTEM_PROMPT = """You are an AI agent that solves tasks step by step.
At each step you must respond in EXACTLY this format:

Thought: <brief action summary, without private internal reasoning>
Action: <the name of the tool to call, or FINISH if done>
Action Input: <JSON object of arguments for the tool, or the final answer>

Available tools:
{tool_descriptions}

Rules:
- Never skip the Thought / Action / Action Input structure.
- Use FINISH as the Action when you have the final answer.
- Action Input must be valid JSON.
- Return exactly ONE action per response, then wait for its real observation.
- Never invent an Observation or continue with additional actions in that response.
- Include every required tool argument. An arithmetic calculator accepts an
  arithmetic expression, not a script or program.
- Do not repeat identical unsuccessful searches or fetches. Change the query,
  use a known source URL, or finish with the limitation clearly stated.
- Search snippets can be irrelevant. Check title, URL, and source content.
- A failed search does not prove that a document does not exist.
"""

REACT_USER_TEMPLATE = """Task: {task}

{history}

Step {step_index}: {step_description}
"""


class ReActPlanner(BasePlanner):
    """
    Implements the ReAct (Reason + Act) planning strategy.
    The LLM produces interleaved reasoning and tool-call instructions,
    one iteration at a time.
    """

    def __init__(self, backend, tool_descriptions: str = ""):
        self.backend = backend
        self.tool_descriptions = tool_descriptions
        self.available_tool_names = set()

    def plan(self, task: str, ctx) -> Plan:
        """
        ReAct does not pre-plan all steps.
        Returns a single placeholder Step; the loop drives iteration.
        """
        return Plan(
            task=task,
            steps=[Step(index=0, description=task)],
            rationale="ReAct plans one step at a time during execution.",
        )

    def next_step(self, ctx) -> Step:
        """Always return a continuation step unless terminated."""
        return Step(index=ctx.iteration, description=ctx.task)

    def format_thought_prompt(self, step: Step, ctx) -> list[dict]:
        """Build the messages array for the Think phase."""
        history = "\n".join(
            [f"Thought: {t.reasoning}\nAction: {t.tool_name}\nAction Input: {json.dumps(t.tool_args)}\n{o}"
             if t.tool_name else f"Format correction (no tool executed): {o}"
             for t, o in zip(ctx.thought_history, ctx.observation_history)]
        )
        user_content = REACT_USER_TEMPLATE.format(
            task=ctx.task,
            history=history,
            step_index=step.index,
            step_description=step.description,
        )
        return [
            {
                "role": "system",
                "content": REACT_SYSTEM_PROMPT.format(
                    tool_descriptions=self.tool_descriptions
                ),
            },
            {"role": "user", "content": user_content},
        ]

    def parse_thought(self, raw: str) -> Thought:
        """
        Extract Thought / Action / Action Input from LLM output.
        Falls back to marking terminal if Action is FINISH.
        """

        def final_answer(text):
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
            try:
                decoded = json.loads(cleaned)
                if isinstance(decoded, str):
                    return decoded
                if isinstance(decoded, dict) and set(decoded) == {"answer"} and isinstance(decoded["answer"], str):
                    return decoded["answer"]
            except json.JSONDecodeError:
                pass
            return text.strip()


        if not re.search(r"^\s*Action:\s*", raw, re.MULTILINE):
            # Detect unsupported calls; never translate model-specific syntax or
            # execute text that merely describes a tool operation.
            call_text = re.search(r"<\s*(?:tool_call|function\b)", raw, re.IGNORECASE)
            named_call = any(re.search(r"\b" + re.escape(name) + r"\s*\(", raw) for name in self.available_tool_names)
            try:
                candidate = json.loads(raw.strip())
            except (ValueError, TypeError):
                candidate = None
            shaped_call = isinstance(candidate, dict) and isinstance(candidate.get("name"), str) and candidate["name"] in self.available_tool_names and "arguments" in candidate
            if call_text or named_call or shaped_call:
                raise AgentResponseFormatError("Unrecognized tool-call text is not a final answer. Return one Action: tool_name and Action Input: JSON arguments. No tool was executed.")
            if re.search(r"^\s*(Thought|Action Input|Observation):", raw, re.MULTILINE):
                raise AgentResponseFormatError("Missing Action. Return one Action and its Action Input, or Action: FINISH with the final answer.")
            return Thought(reasoning=raw, is_terminal=True, answer=final_answer(raw))

        if len(re.findall(r"^[ \t]*Action:", raw, re.MULTILINE)) != 1 or re.search(r"^[ \t]*Observation:", raw, re.MULTILINE):
            raise AgentResponseFormatError("Return exactly one action and wait. Do not invent observations or include additional actions. No tool was executed.")

        thought_match = re.search(r"Thought:\s*(.+?)(?=Action:|$)", raw, re.DOTALL)
        action_match = re.search(r"^[ \t]*Action:[ \t]*([^\r\n]+)", raw, re.MULTILINE)
        if not action_match:
            raise AgentResponseFormatError("Action must name a tool or FINISH on the same line.")
        input_match = re.search(r"^[ \t]*Action Input:[ \t]*(.*)$", raw[action_match.end():], re.DOTALL | re.MULTILINE)

        reasoning = thought_match.group(1).strip() if thought_match else raw
        action = action_match.group(1).strip() if action_match else "FINISH"
        if not input_match or not input_match.group(1).strip():
            raise AgentResponseFormatError("Missing Action Input. Supply one JSON object containing the tool's required arguments, or the final answer for FINISH. No tool was executed.")
        raw_input = input_match.group(1).strip()

        if action.upper() == "FINISH":
            return Thought(
                reasoning=reasoning,
                is_terminal=True,
                answer=final_answer(raw_input),
            )

        try:
            cleaned_input = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_input, flags=re.IGNORECASE)
            tool_args = json.loads(cleaned_input)
            if not isinstance(tool_args, dict):
                raise AgentResponseFormatError("Tool Action Input must be a JSON object with named arguments. No tool was executed.")
        except json.JSONDecodeError:
            raise AgentResponseFormatError("Invalid Action Input JSON. Return one JSON object, without additional actions or observations. No tool was executed.") from None

        return Thought(
            reasoning=reasoning,
            tool_name=action,
            tool_args=tool_args,
            is_terminal=False,
        )
