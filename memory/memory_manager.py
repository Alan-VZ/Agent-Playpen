# Memory Manager (memory_manager.py)
import os
from memory.in_memory import InMemoryStore
from memory.conversation_buffer import ConversationBuffer
from memory.vector_store import VectorStoreMemory
from memory.episodic_memory import EpisodicMemory
from memory.semantic_memory import SemanticMemory
from memory.working_memory import WorkingMemory


class MemoryManager:
    """
    Unified router across all memory stores.
    Selectively enables stores based on config.
    """

    STORE_TYPES = ["working", "conversation", "vector", "episodic", "semantic"]

    def __init__(self, config: dict = None):
        cfg = config or {}
        enabled = cfg.get(
            "enabled_stores",
            os.getenv("MEMORY_ENABLED_STORES", "working,conversation").split(","),
        )

        self.stores = {}
        if "working" in enabled:
            self.stores["working"] = WorkingMemory()
        if "conversation" in enabled:
            self.stores["conversation"] = ConversationBuffer(
                max_tokens=int(os.getenv("MAX_CONVERSATION_TOKENS", "4000"))
            )
        if "vector" in enabled:
            self.stores["vector"] = VectorStoreMemory(
                provider=os.getenv("MEMORY_VECTOR_PROVIDER", "chroma"),
                embed_model=os.getenv("MEMORY_EMBED_MODEL", "all-MiniLM-L6-v2"),
            )
        if "episodic" in enabled:
            self.stores["episodic"] = EpisodicMemory()
        if "semantic" in enabled:
            self.stores["semantic"] = SemanticMemory()

    def store(self, text: str, memory_type: str = "working") -> None:
        """Store text in the named memory store."""
        if memory_type not in self.stores:
            raise KeyError(f"Memory store '{memory_type}' is not enabled.")
        self.stores[memory_type].store(key="auto", value=text)

    def retrieve(self, query: str, memory_type: str = None, top_k: int = 5) -> list:
        """
        Retrieve from a specific store, or aggregate across all enabled stores.
        """
        if memory_type:
            if memory_type not in self.stores:
                return []
            return self.stores[memory_type].retrieve(query, top_k)

        # Aggregate from all stores
        results = []
        for store in self.stores.values():
            results.extend(store.retrieve(query, top_k))
        return results[:top_k]
    