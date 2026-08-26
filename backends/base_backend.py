from abc import ABC, abstractmethod


class BaseBackend(ABC):
    """Abstract interface implemented by all model backends."""

    @abstractmethod
    def chat(self, messages: list[dict]) -> str:
        """Return a single assistant response for the given message list."""
        raise NotImplementedError

    @abstractmethod
    def stream(self, messages: list[dict]):
        """Yield response chunks for the given message list."""
        raise NotImplementedError
