# basic_chat.py (~40 lines)
# Demonstrates: loading the LM Studio backend, maintaining conversation history, and running an interactive REPL chat loop.
#
# Run:
#
# python examples/basic_chat.py
"""
basic_chat.py — Minimal interactive chat loop with LM Studio.
~40 lines. No planner, no tools. Just a conversation.
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backends.lm_studio import LMStudioBackend

SYSTEM_PROMPT = (
    "You are a helpful, concise assistant. "
    "Keep your replies brief unless asked to elaborate."
)


def main():
    backend = LMStudioBackend(
        base_url=os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1"),
        model=os.getenv("LM_STUDIO_MODEL", "local-model"),
    )

    if not backend.health_check():
        print("[ERROR] LM Studio is not running. Open LM Studio and start the server.")
        sys.exit(1)

    print("Agent Playpen — basic_chat.py")
    print("Type 'exit' or 'quit' to end the session.\n")

    conversation = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            break

        if user_input.lower() in ("exit", "quit", ""):
            print("Goodbye.")
            break

        conversation.append({"role": "user", "content": user_input})
        reply = backend.chat(conversation)
        conversation.append({"role": "assistant", "content": reply})
        print(f"Assistant: {reply}\n")


if __name__ == "__main__":
    main()
    