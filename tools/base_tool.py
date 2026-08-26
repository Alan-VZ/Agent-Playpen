from abc import ABC, abstractmethod


class BaseTool(ABC):
    """Abstract base class for all Agent Playpen tools."""

    name: str = ""           # Unique machine-readable identifier
    description: str = ""   # Human-readable description for the LLM
    parameters: dict = {}    # JSON Schema describing input arguments

    @abstractmethod
    def run(self, **kwargs) -> str:
        """Execute the tool and return a string result."""
        ...

    def to_openai_schema(self) -> dict:
        """Convert tool definition to OpenAI function-calling schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
        