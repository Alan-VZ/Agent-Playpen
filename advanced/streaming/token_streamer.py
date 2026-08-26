# token_streamer.py — Async token streamer with UI helpers
import asyncio
import sys


class TokenStreamer:
    """
    Async generator wrapper around a synchronous stream.
    Supports console and file output helpers.
    """

    def __init__(self, backend, messages: list[dict]):
        self.backend = backend
        self.messages = messages
        self._tokens = []

    async def tokens(self):
        """Yield tokens asynchronously from the backend stream."""
        loop = asyncio.get_event_loop()
        sync_stream = await loop.run_in_executor(
            None, lambda: list(self.backend.stream(self.messages))
        )
        for token in sync_stream:
            self._tokens.append(token)
            yield token

    async def write_to_console(self) -> str:
        """Stream tokens to stdout in real time and return full text."""
        full = []
        async for token in self.tokens():
            sys.stdout.write(token)
            sys.stdout.flush()
            full.append(token)
        print()   # Newline after stream ends
        return "".join(full)

    async def write_to_file(self, path: str) -> str:
        """Stream tokens and write them to a file simultaneously."""
        full = []
        with open(path, "w", encoding="utf-8") as f:
            async for token in self.tokens():
                f.write(token)
                f.flush()
                full.append(token)
        return "".join(full)
    