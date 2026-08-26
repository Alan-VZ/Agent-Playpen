import os
import openai
from backends.base_backend import BaseBackend


class TogetherBackend(BaseBackend):
    """
    Together AI backend.
    Popular models: meta-llama/Llama-3-70b-chat-hf,
                    mistralai/Mixtral-8x7B-Instruct-v0.1
    """

    TOGETHER_BASE_URL = "https://api.together.xyz/v1"

    def __init__(
        self,
        api_key: str = None,
        model: str = "meta-llama/Llama-3-70b-chat-hf",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        self.client = openai.OpenAI(
            base_url=self.TOGETHER_BASE_URL,
            api_key=api_key or os.environ["TOGETHER_API_KEY"],
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
                