from abc import ABC, abstractmethod


class BaseMemory(ABC):
    """Abstract interface for all memory stores."""

    @abstractmethod
    def store(self, key: str, value: str) -> None:
        """Persist a value under the given key."""

    @abstractmethod
    def retrieve(self, query: str, top_k: int = 5) -> list:
        """Return candidate items related to the query."""

    def clear(self) -> None:
        """Remove all stored data."""
        raise NotImplementedError
