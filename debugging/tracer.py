# Execution Tracer (tracer.py)
import json
from config.credentials import redact
import datetime
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class TraceEvent:
    """A single recorded event in an agent execution trace."""
    type: str          # think | act | observe | error
    content: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    iteration: int = 0
    tool_name: str = ""


class Tracer:
    """
    Records all agent events and saves them to a JSON trace file.
    Pretty-prints to console using rich if available.
    """

    def __init__(self, trace_dir: str = "./traces", session_id: str = "default", on_event=None):
        self.trace_dir = Path(trace_dir)
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id
        self.events: list[TraceEvent] = []
        self._iteration = 0
        self.on_event = on_event

        # Use rich for coloured output if available
        try:
            from rich.console import Console
            self._console = Console()
            self._rich = True
        except ImportError:
            self._rich = False

    def _record(self, event: TraceEvent) -> None:
        event.content = redact(event.content)
        event.tool_name = redact(event.tool_name)
        self.events.append(event)
        if self.on_event is not None:
            self.on_event(redact(asdict(event)))
        self._print(event)

    def _print(self, event: TraceEvent) -> None:
        msg = f"[{event.type.upper()}] iter={event.iteration} {event.content[:120]}"
        if self._rich:
            colours = {"think": "cyan", "act": "yellow", "observe": "green", "error": "red"}
            colour = colours.get(event.type, "white")
            self._console.print(f"[{colour}]{msg}[/{colour}]")
        else:
            print(msg)

    def on_think(self, thought) -> None:
        self._record(TraceEvent(
            type="think",
            content="Final response ready." if thought.is_terminal else f"Selected action: {thought.tool_name}",
            iteration=self._iteration,
        ))

    def on_action(self, tool_name: str, tool_args: dict) -> None:
        self._record(TraceEvent(
            type="act",
            content=f"{tool_name}({tool_args})",
            iteration=self._iteration,
            tool_name=tool_name,
        ))

    def on_observe(self, observation: str) -> None:
        self._record(TraceEvent(
            type="observe",
            content=redact(observation)[:2000],
            iteration=self._iteration,
        ))
        self._iteration += 1

    def on_error(self, exc: Exception) -> None:
        self._record(TraceEvent(
            type="error",
            content=redact(str(exc))[:1000],
            iteration=self._iteration,
        ))

    def on_status(self, message: str, event_type: str = "status") -> None:
        self._record(TraceEvent(type=event_type, content=message, iteration=self._iteration))

    def on_response(self, answer: str) -> None:
        self.on_status(redact(answer), event_type="response")

    def save(self) -> str:
        """Persist the full trace to disk and return the file path."""
        path = self.trace_dir / f"{self.session_id}.json"
        data = [asdict(e) for e in self.events]
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return str(path)

