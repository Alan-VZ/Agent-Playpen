from config.security import openrouter_endpoint
from config.credentials import require_credential

import openai

from backends.base_backend import BaseBackend


class OpenRouterBackend(BaseBackend):
    """OpenRouter cloud backend using the OpenAI-compatible API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "openai/gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        base_url: str = "https://openrouter.ai/api/v1",
    ):
        self.client = openai.OpenAI(
            http_client=openai.DefaultHttpxClient(follow_redirects=False),
            api_key=require_credential("OPENROUTER_API_KEY", api_key or ""),
            base_url=openrouter_endpoint(base_url),
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
