import os
import openai
from backends.base_backend import BaseBackend


class OpenAIBackend(BaseBackend):
    """
    OpenAI cloud API backend.
    Supports GPT-4o, GPT-4o-mini, and o3.
    """

    def __init__(
        self,
        api_key: str = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        org_id: str = None,
    ):
        self.client = openai.OpenAI(
            api_key=api_key or os.environ["OPENAI_API_KEY"],
            organization=org_id or os.getenv("OPENAI_ORG_ID"),
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
                