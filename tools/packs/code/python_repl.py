# python_repl.py
import subprocess
import sys
from tools.base_tool import BaseTool

FORBIDDEN_IMPORTS = [
    "os.system", "subprocess", "__import__", "eval(", "exec(",
    "open(", "importlib", "ctypes", "socket",
]


class PythonReplTool(BaseTool):
    """
    Execute Python code in an isolated subprocess.
    Blocks a configurable list of dangerous imports.
    """

    name = "python_repl"
    description = "Execute Python code and return stdout and stderr."
    parameters = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python code to execute"},
            "timeout": {
                "type": "integer",
                "default": 15,
                "description": "Execution timeout in seconds",
            },
        },
        "required": ["code"],
    }

    def run(self, **kwargs) -> str:
        code = kwargs["code"]
        timeout = kwargs.get("timeout", 15)
        # Safety check: scan for forbidden patterns before executing
        for pattern in FORBIDDEN_IMPORTS:
            if pattern in code:
                return f"[BLOCKED] Code contains forbidden pattern: '{pattern}'"

        try:
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = result.stdout or ""
            errors = result.stderr or ""
            if errors:
                return f"stdout:\n{output}\nstderr:\n{errors}"
            return output if output else "(no output)"
        except subprocess.TimeoutExpired:
            return f"[TIMEOUT] Code execution exceeded {timeout} seconds."
        except Exception as e:
            return f"[ERROR] {e}"
        