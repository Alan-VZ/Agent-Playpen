// python tests/render_pricing_ui.py && node tests/model_prices_ui.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM, VirtualConsole } = require(path.resolve('.test-tmp/ui-test/node_modules/jsdom'));
const errors = [];
const virtualConsole = new VirtualConsole(); virtualConsole.on('jsdomError', error => errors.push(error));
const calls = [];
function price(input, output, status = 'published') {
  return { input_per_million: input, output_per_million: output, cache_read_per_million: null, cache_write_per_million: null,
    status, source_label: status === 'reference' ? 'Community reference estimate' : 'Provider catalog', source_url: 'https://example.org/source',
    official_url: 'https://example.org/prices', fetched_at: 'test-time', stale: false, notes: [], tiers: [] };
}
const catalog = [
  { backend: 'openrouter', id: 'free', pricing: price(0, 0) },
  { backend: 'openrouter', id: 'expensive <img src=x onerror=alert(1)>', pricing: { ...price(2, 4), stale: true, source_url: 'javascript:alert(1)' } },
  { backend: 'openai', id: 'demo', pricing: price(1, 3, 'reference') },
  { backend: 'azure_openai', id: 'deployment', pricing: price(null, null, 'account_specific') },
];
const dom = new JSDOM(fs.readFileSync('.test-tmp/model_prices.html', 'utf8'), {
  url: 'http://127.0.0.1:8765/model-prices', runScripts: 'dangerously', virtualConsole,
  beforeParse(window) { window.fetch = async (resource, options) => {
    assert.equal(options.headers['X-Playpen-Token'], 'test-session-token');
    const url = new URL(resource, 'http://127.0.0.1:8765'); calls.push(url);
    assert.equal(url.searchParams.has('api_key'), false);
    const result = url.pathname === '/api/model-prices' ? { models: catalog, sources: {}, message: 'Public comparison' } :
      { model_details: [{ backend: 'together', id: 'vendor/account-model', pricing: price(.2, .8) }], source: 'live', message: 'Loaded account models' };
    return { ok: true, json: async () => result };
  }; }
});
const document = dom.window.document;
const byId = id => document.getElementById(id);
const rows = () => Array.from(byId('table-body').children);
async function waitFor(predicate) { for (let i = 0; i < 100; i++) { if (predicate()) return; await new Promise(resolve => setTimeout(resolve, 20)); } throw new Error('Timed out waiting for price UI'); }
function change(id, value, event = 'change') { byId(id).value = value; byId(id).dispatchEvent(new dom.window.Event(event)); }
(async () => {
  try {
    await waitFor(() => rows().length === 4);
    assert.equal(document.querySelector('#table-body img'), null);
    assert.equal(document.querySelector('a[href^="javascript:"]'), null);
    assert.ok(byId('table-body').textContent.includes('<img'));
    assert.ok(byId('table-body').textContent.includes('STALE'));
    const quote = rows().find(row => row.textContent.includes('deployment'));
    assert.equal(quote.children[1].textContent, 'Unavailable');
    assert.equal(quote.children[5].textContent, 'Unavailable');
    change('sort', 'input');
    assert.ok(rows()[0].textContent.includes('free'));
    assert.equal(rows()[0].children[5].textContent, '$0');
    assert.equal(rows().find(row => row.textContent.includes('expensive')).children[5].textContent, '$0.006');
    change('source', 'reference');
    assert.equal(rows().length, 1); assert.ok(rows()[0].textContent.includes('Reference estimate'));
    change('input-tokens', '', 'input');
    assert.equal(rows()[0].children[5].textContent, 'Unavailable');
    change('input-tokens', '2000', 'input');
    assert.equal(rows()[0].children[5].textContent, '$0.005');
    change('source', 'all'); change('query', 'demo', 'input'); assert.equal(rows().length, 1);
    change('query', '', 'input'); change('backend', 'together');
    assert.equal(rows().length, 0); assert.equal(byId('load-account').disabled, false);
    byId('load-account').click(); await waitFor(() => rows().length === 1 && !byId('refresh').disabled);
    assert.ok(rows()[0].textContent.includes('vendor/account-model'));
    assert.equal(calls.at(-1).pathname, '/api/models');
    assert.equal(calls.at(-1).searchParams.get('backend'), 'together');
    assert.equal(errors.length, 0, errors.map(error => error.stack).join('\n'));
    process.stdout.write('Model-price DOM smoke passed: units, genuine zero vs missing prices, filtering/sorting, base estimates, stale/reference labels, safe text/links, and selected-account model loading.\n');
  } finally { dom.window.close(); }
})().catch(error => { process.stderr.write(error.stack + '\n'); process.exitCode = 1; });
