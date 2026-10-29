import json
from unittest.mock import Mock
from types import SimpleNamespace

import pytest

from core.agent import Agent
from debugging.tracer import Tracer
from memory.memory_manager import MemoryManager
from planner.react_planner import ReActPlanner
from tools.tool_registry import ToolRegistry
from tools.packs.web.search_tool import WebSearchTool
from tools.packs.web.fetch_tool import FetchTool


def test_free_engines_fall_back_after_empty_and_unrelated_results(monkeypatch):
    import ddgs
    search = Mock()
    search.__enter__ = Mock(return_value=search)
    search.__exit__ = Mock(return_value=False)
    search.text.side_effect = [
        [{"title": "Rob Haswell weather", "body": "Meteorologist", "href": "https://example.invalid/weather"}],
        [{"title": "A Bayesian Truth Serum", "body": "Drazen Prelec", "href": "https://example.invalid/paper"}],
    ]
    monkeypatch.setattr(ddgs, "DDGS", Mock(return_value=search))
    result = WebSearchTool("ddgs").run(query="Bayesian Truth Serum Drazen Prelec", num_results=1)
    assert "Search engine: yahoo" in result
    assert "Rob Haswell" not in result
    assert [call.kwargs["backend"] for call in search.text.call_args_list] == ["duckduckgo", "yahoo"]


def test_explicit_duckduckgo_does_not_silently_use_other_engines(monkeypatch):
    import ddgs
    search = Mock()
    search.__enter__ = Mock(return_value=search)
    search.__exit__ = Mock(return_value=False)
    search.text.return_value = []
    monkeypatch.setattr(ddgs, "DDGS", Mock(return_value=search))
    assert WebSearchTool("duckduckgo").run(query="paper").startswith("No results")
    assert search.text.call_count == 1
    assert search.text.call_args.kwargs["backend"] == "duckduckgo"


def test_relevance_heuristic_is_conservative_for_short_queries():
    assert WebSearchTool._matches_query("cars", "Automobile guide")
    assert not WebSearchTool._matches_query("Bayesian truth serum Prelec", "Rob Haswell weather")
    assert WebSearchTool._matches_query("Bayesian truth serum Prelec", "Drazen Prelec at MIT")


@pytest.mark.parametrize("query", ["", "   "])
def test_empty_query_is_rejected(query):
    with pytest.raises(ValueError):
        WebSearchTool().run(query=query)


def test_auto_rejects_unrelated_paid_results_before_free_fallback(monkeypatch):
    tool = WebSearchTool("auto")
    monkeypatch.setattr(tool, "_has_google_credentials", lambda: True)
    monkeypatch.setattr(tool, "_has_tavily_credentials", lambda: False)
    monkeypatch.setattr(tool, "_has_serpapi_credentials", lambda: False)
    monkeypatch.setattr(tool, "_google", lambda *args: "Rob Haswell weather report")
    monkeypatch.setattr(tool, "_ddgs", lambda *args: "Bayesian Truth Serum / Prelec")
    assert "Prelec" in tool.run(query="Bayesian Truth Serum Prelec")


def test_duplicate_search_uses_cache_and_stops_loop(tmp_path):
    backend = Mock(chat=Mock(return_value='Thought: search\nAction: web_search\nAction Input: {"query":"same query"}'))
    tool = Mock()
    tool.name = "web_search"
    tool.run.return_value = "No results found."
    tool.to_openai_schema.return_value = {"function": {"name": "web_search"}}
    registry = ToolRegistry()
    registry.register(tool)
    agent = Agent(backend, ReActPlanner(backend), registry, MemoryManager(), Tracer(str(tmp_path)), max_iterations=10)
    agent.run("research")
    assert tool.run.call_count == 1
    assert backend.chat.call_count == 3
    assert agent.completion_status == "incomplete"
    assert "three times" in agent.stop_reason


@pytest.mark.parametrize("text", [
    'Thought: done\nAction: FINISH\nAction Input: {"answer":"Readable answer"}',
    '{"answer":"Readable answer"}',
    '```json\n{"answer":"Readable answer"}\n```',
])
def test_final_answer_envelopes_are_unwrapped(text):
    assert ReActPlanner(Mock()).parse_thought(text).answer == "Readable answer"


def test_structured_answer_with_other_fields_is_preserved():
    text = json.dumps({"answer": "Answer", "sources": ["https://example.invalid"]})
    assert ReActPlanner(Mock()).parse_thought(text).answer == text


def test_pdf_fetch_extracts_text_instead_of_binary(monkeypatch):
    import requests
    import pypdf
    response = Mock(content=b"%PDF-test", text="binary garbage")
    monkeypatch.setattr(requests, "get", Mock(return_value=response))
    reader = SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: "Bayesian Truth Serum / Prelec")])
    monkeypatch.setattr(pypdf, "PdfReader", Mock(return_value=reader))
    assert FetchTool().run(url="https://example.invalid/paper.pdf") == "Bayesian Truth Serum / Prelec"


def test_pdf_with_no_text_returns_actionable_error(monkeypatch):
    import requests
    import pypdf
    monkeypatch.setattr(requests, "get", Mock(return_value=Mock(content=b"%PDF-test")))
    monkeypatch.setattr(pypdf, "PdfReader", Mock(return_value=SimpleNamespace(pages=[])))
    assert "OCR" in FetchTool().run(url="https://example.invalid/scan.pdf")


def test_paper_search_uses_crossref_after_free_engines_fail(monkeypatch):
    tool = WebSearchTool("auto")
    monkeypatch.setattr(tool, "_has_google_credentials", lambda: False)
    monkeypatch.setattr(tool, "_has_tavily_credentials", lambda: False)
    monkeypatch.setattr(tool, "_has_serpapi_credentials", lambda: False)
    monkeypatch.setattr(tool, "_ddgs", lambda *args: "No results found.")
    monkeypatch.setattr(tool, "_crossref", lambda *args: "Bayesian Truth Serum / Prelec / DOI")
    assert "Prelec" in tool.run(query="Bayesian Truth Serum Prelec paper")


def test_crossref_metadata_has_authors_and_canonical_doi(monkeypatch):
    import requests
    response = Mock()
    response.json.return_value = {"message": {"items": [{"title": ["A Bayesian Truth Serum"], "DOI": "10.1126/science.1102081", "author": [{"given": "Drazen", "family": "Prelec"}]}]}}
    monkeypatch.setattr(requests, "get", Mock(return_value=response))
    text = WebSearchTool("crossref").run(query="Prelec paper")
    assert "not full text" in text
    assert "Drazen Prelec" in text
    assert "https://doi.org/10.1126/science.1102081" in text
