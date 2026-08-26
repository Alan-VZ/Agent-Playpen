import os
import openai
from backends.base_backend import BaseBackend


class GroqBackend(BaseBackend):
    """
    Groq fast inference backend.
    Uses Groq's OpenAI-compatible endpoint.
    Typically 10x faster token generation than hosted GPT-4.
    """

    GROQ_BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(
        self,
        api_key: str = None,
        model: str = "llama-3.1-70b-versatile",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        self.client = openai.OpenAI(
            base_url=self.GROQ_BASE_URL,
            api_key=api_key or os.environ["GROQ_API_KEY"],
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
                