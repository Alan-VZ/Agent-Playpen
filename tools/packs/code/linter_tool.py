# linter_tool.py
import subprocess
import tempfile
import os
from tools.base_tool import BaseTool


class LinterTool(BaseTool):
    """Run ruff on a code string and return lint results."""

    name = "linter"
    description = "Lint Python code with ruff and return any warnings or errors."
    parameters = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python source code to lint"},
        },
        "required": ["code"],
    }

    def run(self, **kwargs) -> str:
        code = kwargs["code"]
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp_path = f.name

        try:
            result = subprocess.run(
                ["ruff", "check", tmp_path],
                capture_output=True,
                text=True,
                timeout=15,
            )
            output = result.stdout or result.stderr or "(no lint issues found)"
            return output.replace(tmp_path, "")
        except FileNotFoundError:
            return "[ERROR] ruff is not installed. Run: pip install ruff"
        finally:
            os.unlink(tmp_path)
