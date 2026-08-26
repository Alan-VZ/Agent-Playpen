from memory.base_memory import BaseMemory


class WorkingMemory(BaseMemory):
    """In-memory working store for transient state."""

    def __init__(self):
        self._items: dict[str, str] = {}

    def store(self, key: str, value: str) -> None:
        self._items[key] = value

    def retrieve(self, query: str, top_k: int = 5) -> list:
        matches = [
            value for key, value in self._items.items()
            if query.lower() in key.lower() or query.lower() in str(value).lower()
        ]
        return matches[:top_k]

    def clear(self) -> None:
        self._items.clear()
