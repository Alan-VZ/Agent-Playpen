# shell_exec.py
import subprocess
from tools.base_tool import BaseTool

# Only commands on this allowlist may be executed
COMMAND_ALLOWLIST = ["ls", "pwd", "cat", "echo", "head", "tail", "wc", "grep", "date"]


class ShellExecTool(BaseTool):
    """Run shell commands from a configurable allowlist."""

    name = "shell_exec"
    description = "Run an allowed shell command and return its output."
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to run"},
        },
        "required": ["command"],
    }

    def __init__(self, allowlist: list[str] | None = None):
        self.allowlist = allowlist or COMMAND_ALLOWLIST

    def run(self, **kwargs) -> str:
        command = kwargs["command"]
        cmd_name = command.strip().split()[0]
        if cmd_name not in self.allowlist:
            return f"[BLOCKED] Command '{cmd_name}' is not in the allowlist."
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=15
            )
            return result.stdout or result.stderr or "(no output)"
        except subprocess.TimeoutExpired:
            return "[TIMEOUT] Command exceeded 15 seconds."
        except Exception as e:
            return f"[ERROR] {e}"
        