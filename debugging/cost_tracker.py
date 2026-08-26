# Cost Tracker (cost_tracker.py)
from dataclasses import dataclass, field


PRICE_TABLE = {
    # model_name: (input_cost_per_1k_usd, output_cost_per_1k_usd)
    "gpt-4o":             (0.0025,  0.0100),
    "gpt-4o-mini":        (0.00015, 0.00060),
    "claude-3-5-sonnet":  (0.0030,  0.0150),
    "claude-3-opus":      (0.0150,  0.0750),
    "llama-3.1-70b-versatile": (0.00059, 0.00079),   # Groq
    "local-model":        (0.0,     0.0),             # LM Studio
}


@dataclass
class CostRecord:
    model: str
    input_tokens: int
    output_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    step: int = 0

    @property
    def total_cost_usd(self) -> float:
        return self.input_cost_usd + self.output_cost_usd


class CostTracker:
    """
    Track token usage and compute USD cost per step and per session.
    Uses PRICE_TABLE for per-model pricing.
    """

    def __init__(self):
        self._records: list[CostRecord] = []
        self._step = 0

    def record(self, model: str, input_tokens: int, output_tokens: int) -> None:
        """Record token usage for one LLM call."""
        prices = PRICE_TABLE.get(model, (0.0, 0.0))
        input_cost = (input_tokens / 1000) * prices[0]
        output_cost = (output_tokens / 1000) * prices[1]
        rec = CostRecord(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost_usd=input_cost,
            output_cost_usd=output_cost,
            step=self._step,
        )
        self._records.append(rec)
        self._step += 1

    @property
    def session_total_usd(self) -> float:
        return sum(r.total_cost_usd for r in self._records)

    @property
    def per_step_breakdown(self) -> list[dict]:
        return [
            {
                "step": r.step,
                "model": r.model,
                "in_tok": r.input_tokens,
                "out_tok": r.output_tokens,
                "cost_usd": round(r.total_cost_usd, 6),
            }
            for r in self._records
        ]

    def report(self) -> None:
        """Print a formatted cost summary table."""
        print("\n=== Cost Report ===")
        print(f"{'Step':<6} {'Model':<30} {'In Tok':>8} {'Out Tok':>8} {'USD':>10}")
        print("-" * 68)
        for r in self._records:
            print(
                f"{r.step:<6} {r.model:<30} "
                f"{r.input_tokens:>8} {r.output_tokens:>8} "
                f"${r.total_cost_usd:>9.6f}"
            )
        print("-" * 68)
        print(f"{'TOTAL':<6} {'':30} {'':8} {'':8} ${self.session_total_usd:.6f}")
        print()