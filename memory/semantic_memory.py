# Semantic Memory (semantic_memory.py)
import uuid
from dataclasses import dataclass, field
from memory.base_memory import BaseMemory


@dataclass
class Fact:
    """A discrete remembered fact."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    source: str = ""


class SemanticMemory(BaseMemory):
    """
    Long-term fact store with keyword-based retrieval.
    For production, swap _retrieve_by_keyword for vector search.
    """

    def __init__(self):
        self._facts: dict[str, Fact] = {}

    def remember(self, fact: str, source: str = "") -> str:
        """Store a fact and return its ID."""
        f = Fact(text=fact, source=source)
        self._facts[f.id] = f
        return f.id

    def recall(self, query: str, top_k: int = 5) -> list[str]:
        """Retrieve facts relevant to the query using keyword overlap."""
        query_words = set(query.lower().split())
        scored = []
        for f in self._facts.values():
            fact_words = set(f.text.lower().split())
            overlap = len(query_words & fact_words)
            if overlap > 0:
                scored.append((f.text, overlap))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [text for text, _ in scored[:top_k]]

    def forget(self, fact_id: str) -> None:
        """Remove a fact by its ID."""
        self._facts.pop(fact_id, None)

    def list_all(self) -> list[str]:
        return [f.text for f in self._facts.values()]

    def store(self, key: str, value: str) -> None:
        self.remember(value, source=key)

    def retrieve(self, query: str, top_k: int = 5) -> list:
        return self.recall(query, top_k)
    