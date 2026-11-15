import json
from decimal import Decimal
from unittest.mock import Mock

import pytest
import requests
from fastapi.testclient import TestClient

from config import credentials
from debugging.dashboard import model_pricing as pricing, server


@pytest.fixture(autouse=True)
def price_cache(monkeypatch):
    monkeypatch.setattr(pricing, "_cache", {})


def source(data, stale=False):
    return {"data": data, "fetched_at": "2026-10-29T10:00:00+00:00", "stale": stale}


@pytest.mark.parametrize("value,expected", [("0", 0), (0, 0), ("0.00000015", .15), (Decimal("0.0000006"), .6),
    (None, None), (True, None), ("", None), ("-1", None), ("NaN", None), (float("inf"), None), ("1e999", None), ("1e-999", None), ({}, None)])
def test_price_units_and_missing_values(value, expected):
    assert pricing.rate(value, 1_000_000) == expected


def test_openrouter_prices_are_normalized_once_and_keep_provenance():
    catalog = pricing.ModelCatalog("openrouter", [{"id": "openai/demo", "pricing": {"prompt": "0.00000015", "completion": "0.0000006", "input_cache_read": "0.000000075"}}], "review-time")
    detail = pricing.model_details("openrouter", catalog)[0]
    assert catalog == ["openai/demo"]
    assert detail["id"] == "openai/demo"
    assert detail["pricing"]["input_per_million"] == .15
    assert detail["pricing"]["output_per_million"] == .6
    assert detail["pricing"]["cache_read_per_million"] == .075
    assert detail["pricing"]["status"] == "published"
    assert detail["pricing"]["fetched_at"] == "review-time"


def test_dynamic_or_missing_openrouter_rate_is_not_free():
    rows = pricing.ModelCatalog("openrouter", [{"id": "variable", "pricing": {"prompt": "-1", "completion": "-1"}}, {"id": "free", "pricing": {"prompt": "0", "completion": "0"}}])
    details = {row["id"]: row["pricing"] for row in pricing.model_details("openrouter", rows)}
    assert details["variable"]["status"] == "unavailable"
    assert details["variable"]["input_per_million"] is None
    assert details["free"]["input_per_million"] == 0 and details["free"]["output_per_million"] == 0


def test_together_token_rates_are_already_per_million_and_media_are_not():
    text = pricing.provider_price("together", {"type": "chat", "pricing": {"input": .2, "output": .8}}, "now")
    assert text["input_per_million"] == .2 and text["output_per_million"] == .8
    image = pricing.provider_price("together", {"type": "image", "pricing": {"input": .2, "output": .8}}, "now")
    assert image["input_per_million"] is None
    hourly = pricing.provider_price("together", {"type": "chat", "pricing": {"input": 0, "output": 0, "hourly": 1}}, "now")
    assert "hourly" in " ".join(hourly["notes"])


def test_price_ranges_are_not_silently_reduced_to_the_cheapest_rate():
    assert pricing._money_cell("$1 - $5") is None
    assert pricing._money_cell("From $1") is None
    assert pricing._money_cell("$1 / MTok") == 1


def reference_data():
    return {
        "demo": {"litellm_provider": "openai", "mode": "chat", "input_cost_per_token": .000001, "output_cost_per_token": .000002},
        "groq/demo": {"litellm_provider": "groq", "mode": "chat", "input_cost_per_token": .000003, "output_cost_per_token": .000004},
        "together_ai/vendor/demo": {"litellm_provider": "together_ai", "mode": "chat", "input_cost_per_token": .000005, "output_cost_per_token": .000006},
        "together-ai-up-to-4b": {"litellm_provider": "together_ai", "mode": "chat", "input_cost_per_token": 0},
        "embedding": {"litellm_provider": "openai", "mode": "embedding", "input_cost_per_token": .000001},
        "azure/demo": {"litellm_provider": "azure", "mode": "chat", "input_cost_per_token": .000007},
        "bad-mode": {"litellm_provider": "openai", "mode": []},
        "bad-provider": {"litellm_provider": {}, "mode": "chat"},
    }


def test_reference_rates_require_exact_provider_and_model(monkeypatch):
    monkeypatch.setattr(pricing, "snapshot", lambda *args: source(reference_data()))
    assert pricing.model_details("openai", ["demo"])[0]["pricing"]["input_per_million"] == 1
    assert pricing.model_details("groq", ["demo"])[0]["pricing"]["input_per_million"] == 3
    together = pricing.model_details("together", ["vendor/demo"])[0]["pricing"]
    assert together["input_per_million"] == 5 and together["status"] == "reference"
    assert together["source_url"] == pricing.REFERENCE_PAGE
    assert pricing.model_details("openai", ["Demo"])[0]["pricing"]["input_per_million"] is None
    assert pricing.model_details("azure_openai", ["demo"])[0]["pricing"]["status"] == "account_specific"
    index = pricing.reference_index(source(reference_data()))
    assert not any(name == "embedding" or name.startswith("together-ai-") for _, name in index)


def test_long_context_tiers_are_retained():
    data = reference_data()
    data["demo"]["input_cost_per_token_above_200k_tokens"] = .000002
    price = pricing.reference_index(source(data))[("openai", "demo")]
    assert price["tiers"] == [{"field": "input_cost_per_token_above_200k_tokens", "per_million": 2}]


def test_failed_refresh_keeps_old_prices_explicitly_stale(monkeypatch):
    loader = Mock(side_effect=[{"data": []}, RuntimeError("network unavailable")])
    monkeypatch.setattr(pricing, "_load_source", loader)
    first = pricing.snapshot("openrouter")
    assert not first["stale"]
    assert pricing.snapshot("openrouter") is first
    failed = pricing.snapshot("openrouter", refresh=True)
    assert failed["stale"] and failed["data"] == first["data"]
    assert failed["fetched_at"] == first["fetched_at"]
    assert loader.call_count == 2


def test_first_source_failure_has_no_fake_price_or_timestamp(monkeypatch):
    monkeypatch.setattr(pricing, "_load_source", Mock(side_effect=RuntimeError("private-error")))
    result = pricing.snapshot("reference")
    assert result["data"] == {} and result["fetched_at"] is None and result["stale"]
    assert "private-error" not in json.dumps(result)


def response(data, status=200):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(data).encode()
    result._content_consumed = True
    return result


def test_public_reference_fetch_never_uses_saved_keys_or_netrc(monkeypatch):
    credentials.store.set("OPENROUTER_API_KEY", "private-test-key")
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    session.get.return_value = response({"demo": {}})
    monkeypatch.setattr(requests, "Session", Mock(return_value=session))
    assert pricing.fetch_public_json(pricing.REFERENCE_URL) == {"demo": {}}
    assert session.trust_env is False
    assert session.get.call_args.kwargs["headers"] == {"Accept": "application/json, text/html"}
    assert session.get.call_args.kwargs["allow_redirects"] is False
    assert "private-test-key" not in str(session.get.call_args)


def test_price_source_rejects_arbitrary_urls_before_network(monkeypatch):
    constructor = Mock()
    monkeypatch.setattr(requests, "Session", constructor)
    with pytest.raises(ValueError):
        pricing.fetch_public_json("https://attacker.invalid/prices")
    constructor.assert_not_called()


def test_openrouter_pagination_collects_all_pages(monkeypatch):
    get = Mock(side_effect=[{"data": [{"id": "a"}], "links": {"next": "?offset=1"}}, {"data": [{"id": "b"}], "links": {"next": None}}])
    monkeypatch.setattr(pricing, "fetch_public_json", get)
    data = pricing._load_source("openrouter")
    assert [row["id"] for row in data["data"]] == ["a", "b"]
    assert get.call_args.args == (pricing.OPENROUTER_URL + "?offset=1",)


def test_public_http_redirect_is_not_followed(monkeypatch):
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    session.get.return_value = response({}, status=302)
    monkeypatch.setattr(requests, "Session", Mock(return_value=session))
    with pytest.raises(RuntimeError):
        pricing.fetch_public_json(pricing.OPENROUTER_URL)
    assert session.get.call_count == 1


def test_comparison_keeps_reference_and_live_rates_distinct(monkeypatch):
    router = source({"data": [{"id": "vendor/demo", "pricing": {"prompt": "0.000007", "completion": "0.000009"}}]}, stale=True)
    monkeypatch.setattr(pricing, "snapshot", lambda name, *args: router if name == "openrouter" else source(reference_data()))
    result = pricing.comparison_catalog()
    rows = {(row["backend"], row["id"]): row["pricing"] for row in result["models"]}
    assert rows[("openrouter", "vendor/demo")]["input_per_million"] == 7
    assert rows[("openrouter", "vendor/demo")]["stale"]
    assert rows[("together", "vendor/demo")]["input_per_million"] == 5
    assert rows[("together", "vendor/demo")]["status"] == "reference"
    assert rows[("lm_studio", "Installed / self-hosted models")]["input_per_million"] is None


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "ENV_PATH", tmp_path / ".env")
    return TestClient(server.app, base_url="http://127.0.0.1", headers={"X-Playpen-Token": server.API_TOKEN})


def test_models_response_preserves_names_and_adds_prices(client, monkeypatch):
    models = pricing.ModelCatalog("openrouter", [{"id": "vendor/demo", "pricing": {"prompt": "0", "completion": "0.000001"}}])
    monkeypatch.setattr(server, "_fetch_models", lambda *args: models)
    data = client.get("/api/models?backend=openrouter").json()
    assert data["models"] == ["vendor/demo"]
    assert data["model_details"][0]["pricing"]["input_per_million"] == 0
    assert data["model_details"][0]["pricing"]["output_per_million"] == 1
    assert client.get("/model-prices").status_code == 200


def test_price_catalog_requires_local_session():
    client = TestClient(server.app, base_url="http://127.0.0.1")
    assert client.get("/api/model-prices").status_code == 403


def test_unsupported_backend_is_rejected(client):
    assert client.get("/api/models?backend=unknown").status_code == 400


def test_official_openai_parser_selects_standard_only_and_preserves_conditions():
    from html import escape
    def island(tier, amount):
        props = {"tier": [0, tier], "rows": [1, [[1, [[0, "demo (<200K context length)"], [0, amount], [0, .1], [0, .5], [0, 3]]]]]}
        return '<astro-island component-export="TextTokenPricingTables" props="' + escape(json.dumps(props), quote=True) + '"></astro-island>'
    prices = pricing.parse_official_page("openai", island("batch", .01) + island("standard", 1) + island("fast", 5))
    assert prices["demo"]["input_per_million"] == 1
    assert prices["demo"]["output_per_million"] == 3
    assert prices["demo"]["cache_write_per_million"] == .5
    assert "200K" in " ".join(prices["demo"]["notes"])


def test_official_together_parser_keeps_token_units_and_skips_media():
    html = '''<table><tr><th>API model string</th><th>Input pricing (per 1M tokens)</th><th>Cached input pricing (per 1M tokens)</th><th>Output pricing (per 1M tokens)</th></tr>
    <tr><td>vendor/demo</td><td>$0.20</td><td>-</td><td>Free</td></tr></table>
    <table><tr><th>Model string for API</th><th>Price per image</th></tr><tr><td>vendor/image</td><td>$0.50</td></tr></table>'''
    prices = pricing.parse_official_page("together", html)
    assert list(prices) == ["vendor/demo"]
    assert prices["vendor/demo"]["input_per_million"] == .2
    assert prices["vendor/demo"]["output_per_million"] == 0
    assert prices["vendor/demo"]["cache_read_per_million"] is None


def test_official_groq_contact_sales_overrides_an_old_reference(monkeypatch):
    html = '''<table><tr><th>MODEL ID</th><th>PRICE PER 1M TOKENS</th></tr><tr><td><a href="/docs/model/demo">Demo</a></td><td>Contact Sales</td></tr></table>'''
    prices = pricing.parse_official_page("groq", html)
    monkeypatch.setattr(pricing, "snapshot", lambda name: source(prices) if name == "official_groq" else source(reference_data()))
    detail = pricing.model_details("groq", ["demo"])[0]["pricing"]
    assert detail["input_per_million"] is None and detail["status"] == "account_specific"
    assert detail["source_url"] == pricing.OFFICIAL_PAGES["groq"]


def test_official_anthropic_parser_uses_explicit_model_link_and_cache_window():
    html = '''<table><tr><th>Model</th><th>Base tokens</th><th>Prompt caching</th></tr><tr><th>Name</th><th>Input</th><th>Output</th><th>5m writes</th><th>1h writes</th><th>Hits</th></tr>
    <tr><td><a href="/docs/en/models/sonnet-9-1/overview">Claude Sonnet 9.1</a></td><td>$2 / MTok</td><td>$10 / MTok</td><td>$2.50 / MTok</td><td>$4 / MTok</td><td>$0.20 / MTok</td></tr></table>'''
    prices = pricing.parse_official_page("anthropic", html)
    assert list(prices) == ["claude-sonnet-9-1"]
    assert prices["claude-sonnet-9-1"]["input_per_million"] == 2
    assert prices["claude-sonnet-9-1"]["cache_read_per_million"] == .2


def test_unrecognized_official_layout_fails_to_reference_without_zeroes(monkeypatch):
    monkeypatch.setattr(pricing, "fetch_public_text", lambda url: '<html><p>New layout</p></html>')
    result = pricing.snapshot("official_openai")
    assert result["data"] == {} and result["stale"] and result["fetched_at"] is None
