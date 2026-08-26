# State Inspector (inspector.py)
import json
from dataclasses import asdict
from core.context import AgentContext


class Inspector:
    """Inspect and dump AgentContext state at any point in execution."""

    def __init__(self):
        self._hooks: dict[int, list] = {}

    def inspect(self, ctx: AgentContext) -> str:
        """Dump the full context as indented JSON."""
        try:
            data = asdict(ctx)
        except TypeError:
            data = ctx.__dict__
        return json.dumps(data, indent=2, default=str)

    def register_step_hook(self, iteration: int, callback) -> None:
        """
        Register a callback to fire when ctx.iteration == iteration.
        callback receives (ctx) as its only argument.
        """
        self._hooks.setdefault(iteration, []).append(callback)

    def check_hooks(self, ctx: AgentContext) -> None:
        """Call registered hooks if the current iteration matches."""
        hooks = self._hooks.get(ctx.iteration, [])
        for hook in hooks:
            hook(ctx)

    def inspect_at_step(self, ctx: AgentContext, n: int) -> None:
        """Print context dump when iteration equals n."""
        def _hook(c):
            print(f"\n--- Inspector: Step {n} ---\n{self.inspect(c)}\n")
        self.register_step_hook(n, _hook)
        self.check_hooks(ctx)
        