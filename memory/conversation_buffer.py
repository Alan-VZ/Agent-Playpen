from collections import deque
from memory.base_memory import BaseMemory


class ConversationBuffer(BaseMemory):
    """
    Rolling conversation window with token-aware trimming.
    Requires: pip install tiktoken
    """

    def __init__(self, max_tokens: int = 4000, model: str = "gpt-4o"):
        self.max_tokens = max_tokens
        self.model = model
        self._messages: deque = deque()
        self._enc = None

    def _get_encoder(self):
        if self._enc is None:
            try:
                import tiktoken
                self._enc = tiktoken.encoding_for_model(self.model)
            except Exception:
                self._enc = None
        return self._enc

    def _count_tokens(self, text: str) -> int:
        enc = self._get_encoder()
        if enc:
            return len(enc.encode(text))
        return len(text) // 4   # Rough fallback: 4 chars per token

    def add_message(self, role: str, content: str) -> None:
        self._messages.append({"role": role, "content": content})
        self.trim_to_token_limit()

    def trim_to_token_limit(self) -> None:
        """Remove oldest messages until under the token limit."""
        while self._messages:
            total = sum(
                self._count_tokens(m["content"]) for m in self._messages
            )
            if total <= self.max_tokens:
                break
            self._messages.popleft()

    def get_messages(self) -> list[dict]:
        return list(self._messages)

    def store(self, key: str, value: str) -> None:
        self.add_message(role=key, content=value)

    def retrieve(self, query: str, top_k: int = 5) -> list:
        msgs = list(self._messages)
        return msgs[-top_k:]

    def clear(self) -> None:
        self._messages.clear()
