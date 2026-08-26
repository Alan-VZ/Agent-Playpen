# list_dir.py
from pathlib import Path
from tools.base_tool import BaseTool


class ListDirTool(BaseTool):
    """List files and directories within an allowed path."""

    name = "list_dir"
    description = "List files and subdirectories at the given path."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "default": ".",
                "description": "Directory path to list",
            }
        },
        "required": [],
    }

    def __init__(self, allowed_dirs: list[str] | None = None):
        self.allowed_dirs = [
            Path(d).resolve() for d in (allowed_dirs or ["."])
        ]

    def _check_allowed(self, path: Path):
        resolved = path.resolve()
        for allowed in self.allowed_dirs:
            try:
                resolved.relative_to(allowed)
                return
            except ValueError:
                continue
        raise PermissionError(f"Access denied: '{path}' is outside allowed directories.")

    def run(self, **kwargs) -> str:
        path = kwargs.get("path", ".")
        p = Path(path)
        self._check_allowed(p)
        if not p.is_dir():
            return f"'{path}' is not a directory."
        entries = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name))
        lines = [
            f"{'[DIR] ' if e.is_dir() else '[FILE]'} {e.name}"
            for e in entries
        ]
        return "\n".join(lines) if lines else "(empty directory)"
    