# read_file.py
from pathlib import Path
from tools.base_tool import BaseTool


class ReadFileTool(BaseTool):
    """Read a file from disk within allowed directories."""

    name = "read_file"
    description = "Read and return the contents of a file."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to read"},
            "encoding": {
                "type": "string",
                "default": "utf-8",
                "description": "File encoding",
            },
        },
        "required": ["path"],
    }

    def __init__(self, allowed_dirs: list[str] | None = None):
        # Default to current working directory if not specified
        self.allowed_dirs = [
            Path(d).resolve() for d in (allowed_dirs or ["."])
        ]

    def _check_allowed(self, path: Path):
        resolved = path.resolve()
        for allowed in self.allowed_dirs:
            try:
                resolved.relative_to(allowed)
                return   # Path is within an allowed directory
            except ValueError:
                continue
        raise PermissionError(
            f"Access denied: '{path}' is outside allowed directories."
        )

    def run(self, **kwargs) -> str:
        path = kwargs["path"]
        encoding = kwargs.get("encoding", "utf-8")
        p = Path(path)
        self._check_allowed(p)
        try:
            return p.read_text(encoding=encoding)
        except UnicodeDecodeError:
            return p.read_text(encoding="latin-1")
        