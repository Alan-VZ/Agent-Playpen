import os
import anthropic
from backends.base_backend import BaseBackend


class AnthropicBackend(BaseBackend):
    """
    Anthropic Claude backend.
    Supports Claude 3.5 Sonnet and Claude 3 Opus.
    Note: Anthropic requires the system prompt to be passed separately
    from the messages array — this class handles that split automatically.
    """

    def __init__(
        self,
        api_key: str = None,
        model: str = "claude-3-5-sonnet-20241022",
        max_tokens: int = 4096,
    ):
        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ["ANTHROPIC_API_KEY"]
        )
        self.model = model
        self.max_tokens = max_tokens

    def _split_messages(self, messages: list[dict]):
        """
        Separate the system message from the human/assistant turns.
        Claude's API requires system as a top-level str, not a message role.
        """
        system = ""
        turns = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                turns.append(m)
        return system, turns

    def chat(self, messages: list[dict]) -> str:
        system, turns = self._split_messages(messages)
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=turns,
        )
        return response.content[0].text

    def stream(self, messages: list[dict]):
        system, turns = self._split_messages(messages)
        with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=turns,
        ) as stream:
            for text in stream.text_stream:
                yield text
