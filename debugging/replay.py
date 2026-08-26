#  Session Replay (replay.py)
import json
import time
from pathlib import Path


def load_trace(path: str) -> list[dict]:
    """Load a saved trace JSON file and return the event list."""
    data = Path(path).read_text(encoding="utf-8")
    return json.loads(data)


def replay(trace: list[dict], interactive: bool = False, delay: float = 0.5) -> None:
    """
    Replay a saved trace, printing each event with a delay.

    Args:
        trace: list of event dicts loaded by load_trace()
        interactive: if True, wait for Enter keypress between steps
        delay: seconds to pause between events in non-interactive mode
    """
    COLOURS = {
        "think": "\033[96m",    # Cyan
        "act":   "\033[93m",    # Yellow
        "observe": "\033[92m",  # Green
        "error": "\033[91m",    # Red
        "reset": "\033[0m",
    }

    print("=== TRACE REPLAY START ===\n")
    for i, event in enumerate(trace):
        etype = event.get("type", "unknown")
        colour = COLOURS.get(etype, "")
        reset = COLOURS["reset"]

        print(
            f"{colour}[{i+1}/{len(trace)}] "
            f"iter={event.get('iteration', '?')} "
            f"type={etype.upper()}{reset}"
        )
        print(f"  timestamp : {event.get('timestamp', '')}")
        if event.get("tool_name"):
            print(f"  tool      : {event['tool_name']}")
        print(f"  content   : {event.get('content', '')[:200]}")
        print()

        if interactive:
            input("  [Press Enter for next event...]")
        else:
            time.sleep(delay)

    print("=== TRACE REPLAY END ===")
    