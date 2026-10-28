from config.credentials import require_credential
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
            http_client=openai.DefaultHttpxClient(follow_redirects=False),
            base_url=self.GROQ_BASE_URL,
            api_key=require_credential("GROQ_API_KEY", api_key or ""),
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
