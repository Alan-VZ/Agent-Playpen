# Evaluator (evaluator.py)
import json
from dataclasses import dataclass


@dataclass
class EvalResult:
    """Structured output from the LLM-as-judge evaluator."""
    scores: dict      # e.g. {"relevance": 8, "accuracy": 7, ...}
    reasoning: str    # LLM's explanation of its scores
    overall: float    # Average of all scores


EVAL_PROMPT = """You are a rigorous AI output evaluator.
Rate the following agent response on four dimensions, each from 0 to 10:
  - relevance  : Does the response directly address the task?
  - accuracy   : Are the facts and reasoning correct?
  - completeness: Does it cover all aspects of the task?
  - format     : Is the response well-structured and readable?

Task: {task}
Response: {response}

Respond with ONLY a JSON object:
{{
  "relevance": ,
  "accuracy": ,
  "completeness": ,
  "format": ,
  "reasoning": ""
}}"""


class Evaluator:
    """LLM-as-judge evaluator for agent outputs."""

    def __init__(self, backend):
        self.backend = backend

    def evaluate(self, task: str, response: str) -> EvalResult:
        prompt = EVAL_PROMPT.format(task=task, response=response)
        messages = [{"role": "user", "content": prompt}]
        raw = self.backend.chat(messages)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return EvalResult(
                scores={"relevance": 5, "accuracy": 5, "completeness": 5, "format": 5},
                reasoning="Could not parse evaluator response.",
                overall=5.0,
            )
        dimension_keys = ["relevance", "accuracy", "completeness", "format"]
        scores = {k: int(data.get(k, 5)) for k in dimension_keys}
        overall = sum(scores.values()) / len(scores)
        return EvalResult(
            scores=scores,
            reasoning=data.get("reasoning", ""),
            overall=round(overall, 2),
        )
        