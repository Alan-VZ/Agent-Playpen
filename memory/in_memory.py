from memory.base_memory import BaseMemory


class InMemoryStore(BaseMemory):
    """
    Simple dict-based in-process memory store.
    No persistence — data is lost when the process ends.
    """

    def __init__(self):
        self._store: dict = {}

    def store(self, key: str, value: str) -> None:
        self._store[key] = value

    def retrieve(self, key: str, top_k: int = 5) -> list:
        val = self._store.get(key)
        return [val] if val else []

    def get(self, key: str) -> str:
        return self._store.get(key, "")

    def set(self, key: str, value: str) -> None:
        self._store[key] = value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def keys(self) -> list:
        return list(self._store.keys())
    