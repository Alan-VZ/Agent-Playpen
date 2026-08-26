import re
from planner.base_planner import BasePlanner, Plan, Step, Thought

REACT_SYSTEM_PROMPT = """You are an AI agent that solves tasks step by step.
At each step you must respond in EXACTLY this format:

Thought: <your reasoning about what to do next>
Action: <the name of the tool to call, or FINISH if done>
Action Input: <JSON object of arguments for the tool, or the final answer>

Available tools:
{tool_descriptions}

Rules:
- Never skip the Thought / Action / Action Input structure.
- Use FINISH as the Action when you have the final answer.
- Action Input must be valid JSON.
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
            [f"Thought: {t.reasoning}\nAction: {t.tool_name}\nObservation: {o}"
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
        import json

        thought_match = re.search(r"Thought:\s*(.+?)(?=Action:|$)", raw, re.DOTALL)
        action_match = re.search(r"Action:\s*(.+?)(?=Action Input:|$)", raw, re.DOTALL)
        input_match = re.search(r"Action Input:\s*(.+?)$", raw, re.DOTALL)

        reasoning = thought_match.group(1).strip() if thought_match else raw
        action = action_match.group(1).strip() if action_match else "FINISH"
        raw_input = input_match.group(1).strip() if input_match else "{}"

        if action.upper() == "FINISH":
            return Thought(
                reasoning=reasoning,
                is_terminal=True,
                answer=raw_input,
            )

        try:
            tool_args = json.loads(raw_input)
        except json.JSONDecodeError:
            tool_args = {"input": raw_input}

        return Thought(
            reasoning=reasoning,
            tool_name=action,
            tool_args=tool_args,
            is_terminal=False,
        )