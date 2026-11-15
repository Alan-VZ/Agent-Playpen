from abc import ABC, abstractmethod


class BaseBackend(ABC):
    """Abstract interface implemented by all model backends."""

    def record_usage(self, response):
        """Keep only numeric provider usage; missing data is explicitly unknown."""
        usage = getattr(response, "usage", None)
        def number(name):
            value = getattr(usage, name, None)
            return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
        inputs = number("prompt_tokens")
        if inputs is None:
            inputs = number("input_tokens")
        outputs = number("completion_tokens")
        if outputs is None:
            outputs = number("output_tokens")
        total = number("total_tokens")
        self.last_usage = {"input_tokens": inputs, "output_tokens": outputs,
                           "total_tokens": total if total is not None else inputs + outputs if inputs is not None and outputs is not None else None}

    @abstractmethod
    def chat(self, messages: list[dict]) -> str:
        """Return a single assistant response for the given message list."""
        raise NotImplementedError

    @abstractmethod
    def stream(self, messages: list[dict]):
        """Yield response chunks for the given message list."""
        raise NotImplementedError
