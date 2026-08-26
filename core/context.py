from dataclasses import dataclass, field
from typing import Any
import datetime


@dataclass
class AgentContext:
    """Shared mutable state passed through the entire agent loop."""

    # Unique identifier for this agent session
    session_id: str

    # The original task string given to the agent
    task: str

    # Number of completed Think-Act-Observe iterations
    iteration: int = 0

    # Chronological list of Thought objects produced by _think()
    thought_history: list = field(default_factory=list)

    # Chronological list of raw tool results from _act()
    action_history: list = field(default_factory=list)

    # Chronological list of observation strings from _observe()
    observation_history: list = field(default_factory=list)

    # Memory items retrieved at session start
    memory_snapshots: list = field(default_factory=list)

    # Arbitrary key-value metadata for extensions and plugins
    metadata: dict = field(default_factory=dict)

    # ISO-8601 UTC timestamp of session creation
    created_at: str = field(
        default_factory=lambda: datetime.datetime.utcnow().isoformat()
    )
    