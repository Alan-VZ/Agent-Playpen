# message_bus.py — Asyncio pub/sub message bus
import asyncio
from collections import defaultdict


class MessageBus:
    """
    Asyncio Queue-based publish/subscribe message bus.
    Supports multiple subscribers per topic.
    """

    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

    def publish(self, topic: str, message: dict) -> None:
        """Publish a message to all subscribers of a topic."""
        for queue in self._subscribers.get(topic, []):
            queue.put_nowait(message)

    async def subscribe(self, topic: str):
        """
        Subscribe to a topic and yield messages as an async generator.
        Unsubscribes automatically when the generator is closed.
        """
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[topic].append(queue)
        try:
            while True:
                message = await queue.get()
                yield message
        finally:
            self._subscribers[topic].remove(queue)

    def unsubscribe(self, topic: str, queue: asyncio.Queue) -> None:
        """Remove a specific queue subscription from a topic."""
        if queue in self._subscribers.get(topic, []):
            self._subscribers[topic].remove(queue)

    def topics(self) -> list[str]:
        return list(self._subscribers.keys())
    