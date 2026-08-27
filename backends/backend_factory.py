from backends.base_backend import BaseBackend
from backends.lm_studio import LMStudioBackend
from backends.ollama import OllamaBackend
from backends.openai_backend import OpenAIBackend
from backends.openrouter import OpenRouterBackend

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
    """Factory for creating backend instances by name."""

    REGISTRY: dict[str, type[BaseBackend]] = {
        "lm_studio": LMStudioBackend,
        "ollama": OllamaBackend,
        "openai": OpenAIBackend,
        "openrouter": OpenRouterBackend,
    }

    _OPTIONAL_BACKENDS: dict[str, type[BaseBackend] | None] = {
        "anthropic": AnthropicBackend,
        "azure_openai": AzureOpenAIBackend,
        "groq": GroqBackend,
        "together": TogetherBackend,
    }

    for _name, _backend_cls in _OPTIONAL_BACKENDS.items():
        if _backend_cls is not None:
            REGISTRY[_name] = _backend_cls

    @classmethod
    def create(cls, name: str, **kwargs) -> BaseBackend:
        """Instantiate a backend by its registered name."""
        if name not in cls.REGISTRY:
            available = ", ".join(sorted(cls.REGISTRY.keys()))
            raise ValueError(f"Unknown backend '{name}'. Available: {available}")
        backend_cls = cls.REGISTRY[name]
        return backend_cls(**kwargs)

    @classmethod
    def register(cls, name: str, backend_cls: type[BaseBackend]) -> None:
        """Register a new backend class under a given name."""
        cls.REGISTRY[name] = backend_cls

    @classmethod
    def list_backends(cls) -> list[str]:
        """Return a stable list of all registered backend names."""
        return sorted(cls.REGISTRY.keys())
    