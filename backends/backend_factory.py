from backends.lm_studio import LMStudioBackend
from backends.ollama import OllamaBackend
from backends.openai_backend import OpenAIBackend

try:
    from backends.anthropic_backend import AnthropicBackend
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    AnthropicBackend = None

try:
    from backends.azure_openai import AzureOpenAIBackend
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    AzureOpenAIBackend = None

try:
    from backends.groq_backend import GroqBackend
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    GroqBackend = None

try:
    from backends.together_backend import TogetherBackend
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    TogetherBackend = None


class BackendFactory:
    """
    Factory for creating backend instances by name.
    Register new backends by adding to REGISTRY.
    """

    REGISTRY = {
        "lm_studio": LMStudioBackend,
        "ollama": OllamaBackend,
        "openai": OpenAIBackend,
    }

    if AnthropicBackend is not None:
        REGISTRY["anthropic"] = AnthropicBackend
    if AzureOpenAIBackend is not None:
        REGISTRY["azure_openai"] = AzureOpenAIBackend
    if GroqBackend is not None:
        REGISTRY["groq"] = GroqBackend
    if TogetherBackend is not None:
        REGISTRY["together"] = TogetherBackend

    @classmethod
    def create(cls, name: str, **kwargs):
        """
        Instantiate a backend by its registered name.

        Args:
            name: key in REGISTRY (e.g. "lm_studio", "openai")
            **kwargs: forwarded to the backend __init__

        Returns:
            An instance of the requested BaseBackend subclass.

        Raises:
            ValueError: if name is not in REGISTRY
        """
        if name not in cls.REGISTRY:
            available = ", ".join(cls.REGISTRY.keys())
            raise ValueError(
                f"Unknown backend '{name}'. Available: {available}"
            )
        backend_cls = cls.REGISTRY[name]
        return backend_cls(**kwargs)

    @classmethod
    def register(cls, name: str, backend_cls):
        """Register a new backend class under a given name."""
        cls.REGISTRY[name] = backend_cls

    @classmethod
    def list_backends(cls) -> list[str]:
        """Return list of all registered backend names."""
        return list(cls.REGISTRY.keys())
    