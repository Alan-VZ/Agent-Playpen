# Prompt Optimizer (prompt_optimizer.py)
import random
from dataclasses import dataclass, field
from advanced.evaluator import Evaluator


@dataclass
class PromptVariant:
    id: str
    template: str
    scores: list = field(default_factory=list)

    @property
    def average_score(self) -> float:
        return sum(self.scores) / len(self.scores) if self.scores else 0.0


IMPROVE_PROMPT = """Given these prompt variants and their performance scores,
suggest a new, improved variant that might score higher.

Variants:
{variants}

Respond with ONLY the text of the new prompt variant. No commentary."""


class PromptOptimizer:
    """
    A/B test prompt variants and select the highest scorer.
    Uses Evaluator for scoring and LLM for variant generation.
    """

    def __init__(self, backend, evaluator: Evaluator = None):
        self.backend = backend
        self.evaluator = evaluator or Evaluator(backend)
        self.variants: dict[str, PromptVariant] = {}

    def add_variant(self, variant_id: str, template: str) -> None:
        self.variants[variant_id] = PromptVariant(id=variant_id, template=template)

    def run_trial(self, variant_id: str, task: str, expected: str = "") -> float:
        """Run a trial for the given variant, score, and record the result."""
        variant = self.variants[variant_id]
        prompt = variant.template.format(task=task)
        response = self.backend.chat([{"role": "user", "content": prompt}])
        result = self.evaluator.evaluate(task=task, response=response)
        variant.scores.append(result.overall)
        return result.overall

    def select_best(self) -> PromptVariant:
        """Return the variant with the highest average score."""
        return max(self.variants.values(), key=lambda v: v.average_score)

    def suggest_improvement(self) -> str:
        """Ask the LLM to propose a new variant based on current scores."""
        summary = "\n".join(
            f"  id={v.id} avg_score={v.average_score:.1f} template={v.template[:80]}"
            for v in self.variants.values()
        )
        prompt = IMPROVE_PROMPT.format(variants=summary)
        return self.backend.chat([{"role": "user", "content": prompt}])
    