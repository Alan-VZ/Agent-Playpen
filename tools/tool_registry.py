import yaml
from tools.base_tool import BaseTool


class ToolRegistry:
    """Central registry for all active tools."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance under its name."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        """Retrieve a tool by name, raising KeyError if not found."""
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered.")
        return self._tools[name]

    def list_all(self) -> list[str]:
        """Return names of all registered tools."""
        return list(self._tools.keys())

    def to_openai_schemas(self) -> list[dict]:
        """Return OpenAI function schemas for all registered tools."""
        from tools.gateway import tool_spec

        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.input_schema,
                },
            }
            for spec in (tool_spec(tool) for tool in self._tools.values())
        ]

    @classmethod
    def from_yaml_config(cls, path: str) -> "ToolRegistry":
        """
        Build a registry from a tools.yaml configuration file.
        Only tools with enabled: true are registered.
        """
        from tools.packs.web.search_tool import WebSearchTool
        from tools.packs.web.fetch_tool import FetchTool
        from tools.packs.web.nimble_extract import NimbleExtractTool
        from tools.packs.filesystem.read_file import ReadFileTool
        from tools.packs.filesystem.write_file import WriteFileTool
        from tools.packs.code.python_repl import PythonReplTool

        from tools.packs.utils.scientific_calculator_tool import (
            ScientificCalculatorTool,
        )
        from tools.packs.utils.calculator_tool import CalculatorTool
        from tools.packs.utils.datetime_tool import DatetimeTool

        TOOL_CLASSES = {
            "scientific_calculator": ScientificCalculatorTool,
            "calculator": CalculatorTool,
            "datetime": DatetimeTool,
            "web_search": WebSearchTool,
            "fetch": FetchTool,
            "nimble_extract": NimbleExtractTool,
            "read_file": ReadFileTool,
            "write_file": WriteFileTool,
            "python_repl": PythonReplTool,
        }

        registry = cls()
        with open(path, "r") as f:
            config = yaml.safe_load(f)

        for tool_name, settings in config.get("tools", {}).items():
            if settings.get("enabled", False):
                if tool_name in TOOL_CLASSES:
                    registry.register(TOOL_CLASSES[tool_name]())

        return registry
