# write_file.py
from pathlib import Path
from tools.base_tool import BaseTool


class WriteFileTool(BaseTool):
    """Write text content to a file within allowed directories."""

    name = "write_file"
    description = "Write text content to a file at the given path."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Destination file path"},
            "content": {"type": "string", "description": "Text content to write"},
            "mode": {
                "type": "string",
                "default": "w",
                "enum": ["w", "a"],
                "description": "'w' to overwrite, 'a' to append",
            },
        },
        "required": ["path", "content"],
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
        path = kwargs["path"]
        content = kwargs["content"]
        mode = kwargs.get("mode", "w")
        p = Path(path)
        self._check_allowed(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        if mode == "w":
            p.write_text(content, encoding="utf-8")
        else:
            with open(p, "a", encoding="utf-8") as f:
                f.write(content)
        return f"Written {len(content)} characters to {path}"
    