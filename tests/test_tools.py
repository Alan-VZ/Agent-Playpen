import pytest

from tools.packs.filesystem.read_file import ReadFileTool
from tools.packs.filesystem.write_file import WriteFileTool
from tools.packs.utils.calculator_tool import CalculatorTool
from tools.packs.web.search_tool import WebSearchTool
from tools.tool_registry import ToolRegistry


@pytest.mark.parametrize("expression,expected", [
    ("6*7", "42"), ("-(3+2)", "-5"), ("2**3", "8"), ("7%3", "1"),
    ("4/2", "2.0"), ("3-1", "2"),
])
def test_calculator(expression, expected):
    assert CalculatorTool().run(expression=expression) == expected


@pytest.mark.parametrize("expression", ["__import__('os')", "1/0", "x", "[1,2]"])
def test_calculator_rejects_invalid_input(expression):
    assert CalculatorTool().run(expression=expression).startswith("[ERROR]")


def test_filesystem_roundtrip_and_append(tmp_path):
    writer = WriteFileTool([str(tmp_path)])
    path = tmp_path / "nested" / "sample.txt"
    writer.run(path=str(path), content="hello")
    writer.run(path=str(path), content=" world", mode="a")
    assert ReadFileTool([str(tmp_path)]).run(path=str(path)) == "hello world"


@pytest.mark.parametrize("tool", [ReadFileTool, WriteFileTool])
def test_filesystem_rejects_sibling_paths(tmp_path, tool):
    with pytest.raises(PermissionError):
        tool([str(tmp_path / "allowed")]).run(path=str(tmp_path / "outside"), content="x")


def test_write_invalid_mode_does_not_change_file(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text("original")
    with pytest.raises(ValueError):
        WriteFileTool([str(tmp_path)]).run(path=str(path), content="bad", mode="invalid")
    assert path.read_text() == "original"


def test_registry_schemas_and_missing_tool():
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    assert registry.to_openai_schemas()[0]["function"]["name"] == "calculator"
    with pytest.raises(KeyError):
        registry.get("unknown")


def test_search_falls_back_after_provider_error(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake")
    monkeypatch.setenv("GOOGLE_CSE_ID", "fake")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    tool = WebSearchTool("auto")
    def fail(*args):
        raise RuntimeError("offline")
    monkeypatch.setattr(tool, "_google", fail)
    monkeypatch.setattr(tool, "_ddgs", lambda *args: "- Result: example")
    assert tool.run(query="test") == "- Result: example"
