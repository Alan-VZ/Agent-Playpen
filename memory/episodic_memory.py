# Episodic Memory (episodic_memory.py)
import uuid
import datetime
from dataclasses import dataclass, field
from memory.base_memory import BaseMemory


@dataclass
class Episode:
    """A recorded agent session with summary, tags, and timestamp."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    summary: str = ""
    tags: list = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.utcnow().isoformat()
    )
    embedding: list = field(default_factory=list)


class EpisodicMemory(BaseMemory):
    """Store and retrieve discrete agent episodes (past sessions)."""

    def __init__(self):
        self._episodes: list[Episode] = []

    def save_episode(self, summary: str, tags: list = None) -> Episode:
        ep = Episode(summary=summary, tags=tags or [])
        self._episodes.append(ep)
        return ep

    def retrieve_recent(self, n: int = 5) -> list[Episode]:
        """Return the N most recently stored episodes."""
        return self._episodes[-n:]

    def retrieve_similar(self, query: str, top_k: int = 5) -> list[Episode]:
        """Simple keyword match — replace with embeddings for production."""
        query_lower = query.lower()
        scored = [
            (ep, sum(1 for w in query_lower.split() if w in ep.summary.lower()))
            for ep in self._episodes
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [ep for ep, score in scored[:top_k] if score > 0]

    def store(self, key: str, value: str) -> None:
        self.save_episode(summary=value, tags=[key])

    def retrieve(self, query: str, top_k: int = 5) -> list:
        return [ep.summary for ep in self.retrieve_similar(query, top_k)]
    