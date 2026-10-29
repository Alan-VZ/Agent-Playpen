"""Search contracts, credential isolation, and recoverable provider failures."""
import json
from unittest.mock import Mock

import pytest
import requests

from config import credentials
from debugging.dashboard import server
from tools.packs.web.api_search import API_PROVIDERS
from tools.packs.web.search_tool import WebSearchTool


CASES = [
    ("serper", "POST", "https://google.serper.dev/search", "X-API-KEY", "json", "num",
     {"organic": [{"title": "Prelec paper", "link": "https://example.org/paper", "snippet": "Bayesian truth serum"}]}),
    ("brave", "GET", "https://api.search.brave.com/res/v1/web/search", "X-Subscription-Token", "params", "count",
     {"web": {"results": [{"title": "Prelec paper", "url": "https://example.org/paper", "description": "Bayesian truth serum"}]}}),
    ("exa", "POST", "https://api.exa.ai/search", "x-api-key", "json", "numResults",
     {"results": [{"title": "Prelec paper", "url": "https://example.org/paper", "highlights": ["Bayesian truth serum"]}]}),
    ("firecrawl", "POST", "https://api.firecrawl.dev/v2/search", "Authorization", "json", "limit",
     {"success": True, "data": {"web": [{"title": "Prelec paper", "url": "https://example.org/paper", "description": "Bayesian truth serum"}]}}),
    ("openwebninja", "GET", "https://api.openwebninja.com/realtime-web-search/search", "x-api-key", "params", "num",
     {"status": "OK", "data": {"organic_results": [{"title": "Prelec paper", "url": "https://example.org/paper", "snippet": "Bayesian truth serum"}]}}),
]


@pytest.mark.parametrize("provider,method,url,header,body_field,count_field,data", CASES)
def test_saved_search_key_reaches_only_its_provider(monkeypatch, provider, method, url, header, body_field, count_field, data):
    secret = "fake-search-credential-123456789"
    credentials.store.set(credentials.SEARCH_KEYS[provider], secret)
    credentials.store.set("OPENROUTER_API_KEY", "fake-model-credential-123456789")
    request = Mock(return_value=Mock(status_code=200, json=Mock(return_value=data)))
    monkeypatch.setattr(requests, "request", request)
    tool = server._tool_factory("web_search", server.AgentConfig(task="research", search_provider=provider))
    result = tool.run(query="Prelec paper", num_results=100)
    assert f"Search provider: {provider}" in result
    assert "Bayesian truth serum" in result and "https://example.org/paper" in result
    args, kwargs = request.call_args
    assert args == (method, url)
    assert kwargs["headers"][header] == (f"Bearer {secret}" if provider == "firecrawl" else secret)
    assert kwargs[body_field][count_field] == 10
    assert secret not in json.dumps(kwargs[body_field])
    assert secret not in result
    assert "fake-model-credential" not in json.dumps(kwargs)
    assert kwargs["allow_redirects"] is False and kwargs["timeout"] == 15
    if provider == "firecrawl":
        assert "scrapeOptions" not in kwargs[body_field]


@pytest.mark.parametrize("provider", API_PROVIDERS)
def test_missing_search_key_fails_before_network(monkeypatch, provider):
    request = Mock()
    monkeypatch.setattr(requests, "request", request)
    with pytest.raises(RuntimeError, match=credentials.SEARCH_KEYS[provider]):
        WebSearchTool(provider).run(query="Prelec")
    request.assert_not_called()


@pytest.mark.parametrize("status,hint", [(302, "HTTP 302"), (401, "saved API key"), (402, "credits"), (403, "permissions"), (429, "quota"), (503, "HTTP 503")])
def test_http_errors_are_actionable_without_exposing_response(monkeypatch, status, hint):
    response = Mock(status_code=status, text="sensitive provider response")
    request = Mock(return_value=response)
    monkeypatch.setattr(requests, "request", request)
    with pytest.raises(RuntimeError, match=hint) as error:
        WebSearchTool("brave", api_key="private-test-key").run(query="paper")
    assert "private-test-key" not in str(error.value)
    assert "sensitive" not in str(error.value)
    response.json.assert_not_called()
    assert request.call_count == 1
    assert request.call_args.kwargs["allow_redirects"] is False


@pytest.mark.parametrize("exception,hint", [(requests.Timeout("secret"), "timed out"), (requests.ConnectionError("secret"), "connection failed")])
def test_network_errors_do_not_echo_exception(monkeypatch, exception, hint):
    monkeypatch.setattr(requests, "request", Mock(side_effect=exception))
    with pytest.raises(RuntimeError, match=hint) as error:
        WebSearchTool("serper", api_key="private-test-key").run(query="paper")
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("provider,data", [
    ("serper", {"organic": []}), ("brave", {"web": {"results": []}}),
    ("exa", {"results": []}), ("firecrawl", {"success": True, "data": {"web": []}}),
    ("openwebninja", {"status": "OK", "data": {"organic_results": []}}),
])
def test_empty_results_are_not_reported_as_success(monkeypatch, provider, data):
    monkeypatch.setattr(requests, "request", Mock(return_value=Mock(status_code=200, json=Mock(return_value=data))))
    assert WebSearchTool(provider, api_key="fake-key").run(query="paper").startswith("No results")


@pytest.mark.parametrize("provider,data", [
    ("serper", []), ("brave", {"web": None}), ("exa", {"results": {}}),
    ("firecrawl", {"success": False, "error": "sensitive"}),
    ("openwebninja", {"status": "ERROR", "message": "sensitive"}),
])
def test_malformed_and_unsuccessful_responses_are_safe(monkeypatch, provider, data):
    monkeypatch.setattr(requests, "request", Mock(return_value=Mock(status_code=200, json=Mock(return_value=data))))
    with pytest.raises(RuntimeError) as error:
        WebSearchTool(provider, api_key="fake-key").run(query="paper")
    assert "sensitive" not in str(error.value)


def test_auto_uses_configured_api_then_falls_back_on_quota(monkeypatch):
    credentials.store.set("SERPER_API_KEY", "test-serper-key")
    credentials.store.set("BRAVE_API_KEY", "test-brave-key")
    request = Mock(side_effect=[Mock(status_code=429), Mock(status_code=200, json=Mock(return_value=CASES[1][-1]))])
    monkeypatch.setattr(requests, "request", request)
    result = WebSearchTool("auto").run(query="Prelec paper")
    assert "Search provider: brave" in result
    assert [call.args[1] for call in request.call_args_list] == [CASES[0][2], CASES[1][2]]


def test_auto_without_api_keys_does_not_call_paid_services(monkeypatch):
    request = Mock()
    monkeypatch.setattr(requests, "request", request)
    monkeypatch.setattr(WebSearchTool, "_ddgs", lambda *args: "Prelec paper")
    assert WebSearchTool("auto").run(query="Prelec paper") == "Prelec paper"
    request.assert_not_called()


def test_output_keeps_sources_and_bounds_provider_content(monkeypatch):
    data = {"results": [
        {"title": "Unsafe", "url": "javascript:alert(1)"},
        {"title": "Paper", "url": "https://example.org/paper", "highlights": ["test-key-123", "x" * 5000]},
        {"title": "Extra", "url": "https://example.org/extra"},
    ]}
    monkeypatch.setattr(requests, "request", Mock(return_value=Mock(status_code=200, json=Mock(return_value=data))))
    result = WebSearchTool("exa", api_key="test-key-123").run(query="paper", num_results=1)
    assert "test-key-123" not in result and "[REDACTED]" in result
    assert "javascript:" not in result and "Extra" not in result
    assert "https://example.org/paper" in result and len(result) < 1500
