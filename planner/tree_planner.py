import json
from planner.base_planner import BasePlanner, Plan, Step, Thought

BRANCH_PROMPT = """Given the task and current context, generate {n} distinct
approaches (branches) for the next step. Number them 1 to {n}.
Each branch should be a single concrete action.

Task: {task}
Context: {context}

Respond with a JSON array:
[
  {{"branch": 1, "description": "..."}},
  {{"branch": 2, "description": "..."}},
  ...
]"""

SCORE_PROMPT = """Rate the following candidate step on a scale of 0-10
for how likely it is to make progress toward the goal.
Respond with ONLY a JSON object: {{"score": , "reason": ""}}

Task: {task}
Candidate step: {candidate}
"""


class TreePlanner(BasePlanner):
    """
    Tree-of-Thought planner.
    Generates N branches per step, scores each, selects best,
    and supports backtracking on dead ends.
    """

    def __init__(self, backend, n_branches: int = 3):
        self.backend = backend
        self.n_branches = n_branches
        self.branch_history = []   # Stack of (step, score) for backtracking

    def _generate_branches(self, task: str, context: str) -> list[dict]:
        """Ask the LLM to generate N alternative approaches."""
        prompt = BRANCH_PROMPT.format(
            n=self.n_branches, task=task, context=context
        )
        messages = [{"role": "user", "content": prompt}]
        raw = self.backend.chat(messages)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return [{"branch": 1, "description": task}]

    def _score_branch(self, task: str, candidate: str) -> int:
        """Ask the LLM to score a single branch candidate."""
        prompt = SCORE_PROMPT.format(task=task, candidate=candidate)
        messages = [{"role": "user", "content": prompt}]
        raw = self.backend.chat(messages)
        try:
            data = json.loads(raw)
            return int(data.get("score", 5))
        except (json.JSONDecodeError, ValueError):
            return 5   # Default to neutral score on parse failure

    def plan(self, task: str, ctx) -> Plan:
        """Generate and score branches, return the best as a single-step plan."""
        branches = self._generate_branches(task, "")
        scored = [
            (b, self._score_branch(task, b["description"]))
            for b in branches
        ]
        # Select the highest-scoring branch
        best = max(scored, key=lambda x: x[1])
        self.branch_history.append(best)
        return Plan(
            task=task,
            steps=[Step(index=0, description=best[0]["description"])],
            rationale=f"Best branch scored {best[1]}/10 out of {self.n_branches} candidates.",
        )

    def next_step(self, ctx) -> Step:
        return Step(index=ctx.iteration, description=ctx.task)

    def format_thought_prompt(self, step: Step, ctx) -> list[dict]:
        return [
            {
                "role": "user",
                "content": (
                    f"Task: {ctx.task}\n"
                    f"Selected branch: {step.description}\n"
                    "What tool should be called? Respond with:\n"
                    "Action: \nArgs: "
                ),
            }
        ]

    def parse_thought(self, raw: str) -> Thought:
        import re
        if "FINISH" in raw.upper():
            return Thought(reasoning=raw, is_terminal=True, answer=raw)
        action_match = re.search(r"Action:\s*(\w+)", raw)
        args_match = re.search(r"Args:\s*(\{.+\})", raw, re.DOTALL)
        tool_name = action_match.group(1) if action_match else "calculator"
        try:
            tool_args = json.loads(args_match.group(1)) if args_match else {}
        except json.JSONDecodeError:
            tool_args = {}
        return Thought(reasoning=raw, tool_name=tool_name, tool_args=tool_args)

    def backtrack(self):
        """Remove the last selected branch and try the next-best candidate."""
        if self.branch_history:
            self.branch_history.pop()
            