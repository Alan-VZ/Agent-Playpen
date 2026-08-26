import re
from planner.base_planner import BasePlanner, Plan, Step, Thought

COT_SYSTEM_PROMPT = """You are an expert problem solver.
Given a task, first write out your complete chain of thought —
explain every reasoning step clearly. Then list the concrete
actions to take as a numbered plan.

Format your response as:

## Reasoning
<your full chain of thought>

## Plan
1. <first action>
2. <second action>
...

Use FINISH as the last step when the task is complete.
"""


class CoTPlanner(BasePlanner):
    """
    Chain-of-Thought planner: generates the full reasoning chain
    upfront, extracts a step list, then executes steps sequentially.
    """

    def __init__(self, backend):
        self.backend = backend

    def plan(self, task: str, ctx) -> Plan:
        """Call the backend once to get full reasoning and a step list."""
        messages = [
            {"role": "system", "content": COT_SYSTEM_PROMPT},
            {"role": "user", "content": f"Task: {task}"},
        ]
        raw = self.backend.chat(messages)

        # Extract the Plan section
        plan_match = re.search(r"## Plan\n(.+?)$", raw, re.DOTALL)
        plan_text = plan_match.group(1).strip() if plan_match else raw

        # Extract rationale
        reason_match = re.search(r"## Reasoning\n(.+?)(?=## Plan)", raw, re.DOTALL)
        rationale = reason_match.group(1).strip() if reason_match else ""

        # Parse numbered steps
        step_lines = re.findall(r"^\d+\.\s+(.+)$", plan_text, re.MULTILINE)
        steps = [
            Step(index=i, description=line.strip())
            for i, line in enumerate(step_lines)
        ]

        if not steps:
            steps = [Step(index=0, description=task)]

        return Plan(task=task, steps=steps, rationale=rationale)

    def next_step(self, ctx) -> Step:
        return Step(index=ctx.iteration, description=ctx.task)

    def format_thought_prompt(self, step: Step, ctx) -> list[dict]:
        """For CoT, each step gets its own focused prompt."""
        return [
            {"role": "system", "content": COT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Task: {ctx.task}\n"
                    f"Current step {step.index}: {step.description}\n"
                    "State the tool to use and its arguments, "
                    "or write FINISH and the final answer."
                ),
            },
        ]

    def parse_thought(self, raw: str) -> Thought:
        """Simple terminal/action split for CoT step execution."""
        import json
        if "FINISH" in raw.upper():
            answer = re.sub(r"FINISH", "", raw, flags=re.IGNORECASE).strip()
            return Thought(reasoning=raw, is_terminal=True, answer=answer)
        # Expect: Action: tool_name\nArgs: {...}
        action_match = re.search(r"Action:\s*(\w+)", raw)
        args_match = re.search(r"Args:\s*(\{.+\})", raw, re.DOTALL)
        tool_name = action_match.group(1) if action_match else "calculator"
        try:
            tool_args = json.loads(args_match.group(1)) if args_match else {}
        except json.JSONDecodeError:
            tool_args = {}
        return Thought(reasoning=raw, tool_name=tool_name, tool_args=tool_args)
    