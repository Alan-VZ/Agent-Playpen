import openai
from backends.base_backend import BaseBackend


class OllamaBackend(BaseBackend):
    """
    Connects to a locally running Ollama server.
    Ollama exposes an OpenAI-compatible API at http://localhost:11434/v1
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        model: str = "mistral",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ):
        self.client = openai.OpenAI(
            base_url=base_url,
            api_key="ollama",   # placeholder — Ollama does not require a key
        )
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def chat(self, messages: list[dict]) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return response.choices[0].message.content

    def stream(self, messages: list[dict]):
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
                