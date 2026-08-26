from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Optional


class Step(BaseModel):
    """A single step in an agent plan."""
    index: int
    description: str          # Human-readable description of this step
    tool_hint: Optional[str] = None   # Suggested tool, if any


class Plan(BaseModel):
    """An ordered sequence of Steps produced by a planner."""
    task: str
    steps: list[Step]
    rationale: Optional[str] = None   # Why this plan structure was chosen


class Thought(BaseModel):
    """Structured output of a single Think phase."""
    reasoning: str            # Internal chain-of-thought
    tool_name: Optional[str] = None   # Tool to call, or None if terminal
    tool_args: dict = {}      # Arguments for the tool
    is_terminal: bool = False # True means this is the final answer
    answer: Optional[str] = None      # Populated when is_terminal is True


class BasePlanner(ABC):
    """Abstract interface all planners must implement."""

    @abstractmethod
    def plan(self, task: str, ctx) -> Plan:
        """Decompose task into an ordered Plan of Steps."""
        ...

    @abstractmethod
    def next_step(self, ctx) -> Optional[Step]:
        """Return the next Step to execute, or None if done."""
        ...

    @abstractmethod
    def format_thought_prompt(self, step: Step, ctx) -> list[dict]:
        """Build the messages list to send to the backend for the Think phase."""
        ...

    @abstractmethod
    def parse_thought(self, raw: str) -> Thought:
        """Parse raw LLM output into a structured Thought."""
        ...