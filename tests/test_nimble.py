"""Nimble trial-safe contracts; no live account calls."""
from unittest.mock import Mock

import pytest
import requests

from config import credentials
from debugging.dashboard import maintenance, server
from tools.packs.web.nimble_extract import NimbleExtractTool
from tools.packs.web.search_tool import WebSearchTool


def test_nimble_registered_in_dashboard_and_maintenance():
    assert 'nimble_extract' in server.TOOL_CHOICES
    assert isinstance(server._tool_factory('nimble_extract', server.AgentConfig(task='test')), NimbleExtractTool)
    assert maintenance.CATALOG['nimble']['key_name'] == 'NIMBLE_API_KEY'
    assert maintenance.CATALOG['nimble']['readonly_check'] is False


def test_search_lite_contract_cache_and_limit(monkeypatch):
    credentials.store.set('NIMBLE_API_KEY', 'fake-nimble-key')
    request = Mock(return_value=Mock(status_code=200, json=Mock(return_value={'results': [
        {'title': 'Paper', 'url': 'https://example.org/paper', 'description': 'Research paper'}]})))
    monkeypatch.setattr(requests, 'request', request)
    tool = WebSearchTool('nimble')
    tool.run(query='paper')
    assert 'Cache hit' in tool.run(query='paper')
    assert request.call_count == 1
    assert request.call_args.kwargs['json'] == {'query': 'paper', 'max_results': 5,
        'search_depth': 'lite', 'full_content': False, 'focus': 'general'}
    for i in range(4):
        tool.run(query=f'paper {i}')
    with pytest.raises(RuntimeError, match='limit reached'):
        tool.run(query='one too many')
    assert request.call_count == 5


def test_auto_never_spends_nimble_credits(monkeypatch):
    credentials.store.set('NIMBLE_API_KEY', 'fake-key')
    request = Mock()
    monkeypatch.setattr(requests, 'request', request)
    monkeypatch.setattr(WebSearchTool, '_ddgs', lambda *args: 'Paper source')
    assert WebSearchTool('auto').run(query='paper') == 'Paper source'
    request.assert_not_called()


def test_extract_basic_contract_cache_bound_redaction(monkeypatch):
    credentials.store.set('NIMBLE_API_KEY', 'fake-nimble-key')
    request = Mock(return_value=Mock(status_code=200, json=Mock(return_value={
        'status': 'success', 'data': {'markdown': 'fake-nimble-key ' + 'x' * 20000}})))
    monkeypatch.setattr(requests, 'post', request)
    tool = NimbleExtractTool()
    result = tool.run(url='https://example.org/page')
    assert 'fake-nimble-key' not in result and len(result) < 12500
    assert 'Cache hit' in tool.run(url='https://example.org/page')
    assert request.call_count == 1
    assert request.call_args.args == ('https://sdk.nimbleway.com/v2/extract',)
    options = request.call_args.kwargs
    assert options['json'] == {'url': 'https://example.org/page', 'formats': ['markdown'], 'render': False, 'driver': 'vx6'}
    assert options['allow_redirects'] is False
    for i in range(4):
        tool.run(url=f'https://example.org/{i}')
    with pytest.raises(RuntimeError, match='limit reached'):
        tool.run(url='https://example.org/extra')
    assert request.call_count == 5


@pytest.mark.parametrize('url', ['http://example.org', 'https://localhost', 'https://127.0.0.1',
    'https://10.0.0.1', 'https://user:pass@example.org', 'file:///secrets', 'https://host.internal'])
def test_extract_rejects_nonpublic_targets_without_network(monkeypatch, url):
    request = Mock()
    monkeypatch.setattr(requests, 'post', request)
    with pytest.raises(ValueError):
        NimbleExtractTool().run(url=url)
    request.assert_not_called()


@pytest.mark.parametrize('payload', [{}, {'status': 'failed', 'error': 'private detail'},
    {'status': 'success', 'data': {'markdown': ''}}])
def test_extract_unusable_response_does_not_upgrade_or_leak(monkeypatch, payload):
    credentials.store.set('NIMBLE_API_KEY', 'fake-key')
    request = Mock(return_value=Mock(status_code=200, json=Mock(return_value=payload)))
    monkeypatch.setattr(requests, 'post', request)
    with pytest.raises(RuntimeError, match='no usable Markdown') as error:
        NimbleExtractTool().run(url='https://example.org')
    assert 'private detail' not in str(error.value)
    assert request.call_count == 1
