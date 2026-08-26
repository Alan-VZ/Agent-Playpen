import os
import openai
from backends.base_backend import BaseBackend


class AzureOpenAIBackend(BaseBackend):
    """
    Azure-hosted OpenAI backend.
    Uses a deployment name instead of a model name.
    """

    def __init__(
        self,
        azure_endpoint: str = None,
        api_version: str = "2024-05-01-preview",
        deployment_name: str = None,
        api_key: str = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        self.client = openai.AzureOpenAI(
            azure_endpoint=azure_endpoint or os.environ["AZURE_OPENAI_ENDPOINT"],
            api_version=api_version or os.environ["AZURE_OPENAI_API_VERSION"],
            api_key=api_key or os.environ["AZURE_OPENAI_KEY"],
        )
        self.deployment_name = (
            deployment_name or os.environ["AZURE_OPENAI_DEPLOYMENT"]
        )
        self.max_tokens = max_tokens
        self.temperature = temperature

    def chat(self, messages: list[dict]) -> str:
        response = self.client.chat.completions.create(
            model=self.deployment_name,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return response.choices[0].message.content

    def stream(self, messages: list[dict]):
        stream = self.client.chat.completions.create(
            model=self.deployment_name,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
                