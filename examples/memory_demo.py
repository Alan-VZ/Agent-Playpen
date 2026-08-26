# memory_demo.py (~60 lines)
# Demonstrates: all memory types — semantic memory, vector store, episodic memory, and conversation buffer — in a single runnable script.

# Run:

# python examples/memory_demo.py

"""
memory_demo.py — Demonstrates all Agent Playpen memory types.
~60 lines.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.in_memory import InMemoryStore
from memory.conversation_buffer import ConversationBuffer
from memory.episodic_memory import EpisodicMemory
from memory.semantic_memory import SemanticMemory


def demo_in_memory():
    print("--- InMemoryStore ---")
    store = InMemoryStore()
    store.set("user_name", "Alan")
    store.set("last_topic", "quantum computing")
    print(f"  user_name   : {store.get('user_name')}")
    print(f"  last_topic  : {store.get('last_topic')}")
    store.delete("last_topic")
    print(f"  after delete: {store.keys()}")


def demo_conversation_buffer():
    print("\n--- ConversationBuffer ---")
    buf = ConversationBuffer(max_tokens=200)
    buf.add_message("user", "What is LM Studio?")
    buf.add_message("assistant", "LM Studio is a local LLM runtime.")
    buf.add_message("user", "Which models does it support?")
    msgs = buf.get_messages()
    for m in msgs:
        print(f"  [{m['role']}] {m['content']}")


def demo_episodic_memory():
    print("\n--- EpisodicMemory ---")
    mem = EpisodicMemory()
    mem.save_episode("User asked about quantum computing", tags=["science", "tech"])
    mem.save_episode("User requested a Python tutorial", tags=["code", "tutorial"])
    mem.save_episode("User discussed travel plans", tags=["personal"])
    recent = mem.retrieve_recent(n=2)
    print(f"  Recent episodes: {[ep.summary for ep in recent]}")
    similar = mem.retrieve_similar("Python coding help")
    print(f"  Similar to 'Python': {[ep.summary for ep in similar]}")


def demo_semantic_memory():
    print("\n--- SemanticMemory ---")
    mem = SemanticMemory()
    mem.remember("Python is a high-level programming language", source="wikipedia")
    mem.remember("LM Studio runs models locally on your computer", source="docs")
    mem.remember("Groq uses LPU hardware for fast inference", source="groq.com")
    recalled = mem.recall("local LLM model", top_k=2)
    print(f"  Recalled for 'local LLM model': {recalled}")
    print(f"  All facts: {mem.list_all()}")


if __name__ == "__main__":
    demo_in_memory()
    demo_conversation_buffer()
    demo_episodic_memory()
    demo_semantic_memory()
    print("\n[memory_demo.py complete]")
    