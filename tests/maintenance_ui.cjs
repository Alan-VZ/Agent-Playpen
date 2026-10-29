// First: python tests/render_maintenance_ui.py
// Then: node tests/maintenance_ui.cjs (uses the existing .test-tmp/ui-test jsdom install).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM, VirtualConsole } = require(path.resolve('.test-tmp/ui-test/node_modules/jsdom'));
const errors = [];
const virtualConsole = new VirtualConsole();
virtualConsole.on('jsdomError', error => errors.push(error));
const calls = [];
const state = { keys: {}, history: { providers: {}, events: [{ at: 'now', provider: 'serper', event: '<img src=x onerror=alert(1)>', status: null }] } };
for (const key of ['OPENROUTER_API_KEY', 'SERPER_API_KEY', 'TAVILY_API_KEY']) state.keys[key] = { set: false, encrypted: false, storage_available: true };
const popup = { opener: {}, location: { href: 'about:blank' }, close() {} };
async function fakeFetch(url, options) {
  assert.equal(options.headers['X-Playpen-Token'], 'test-session-token');
  const payload = options.body ? JSON.parse(options.body) : null;
  calls.push({ url, payload });
  let result;
  if (url === '/api/maintenance') result = state;
  else if (url === '/api/save-key') {
    state.keys[payload.name] = { set: !!payload.value, encrypted: !!payload.value, storage_available: true };
    result = { message: 'Credential saved in encrypted OS storage.' };
  } else if (url === '/api/maintenance/check') {
    state.history.providers[payload.provider] = { check_status: 'verified', last_check: '2026-10-29T12:00:00Z' };
    result = { status: 'verified', message: 'Access checked', usage: { usage: 5 } };
  } else if (url === '/api/maintenance/review') {
    state.history.providers[payload.provider] = { ...state.history.providers[payload.provider], ...payload };
    result = { message: 'Review saved' };
  } else if (url === '/api/maintenance/openrouter/start') result = { authorization_url: 'https://openrouter.ai/auth?state=fake-state' };
  else throw new Error('Unexpected maintenance request');
  return { ok: true, json: async () => JSON.parse(JSON.stringify(result)) };
}
const dom = new JSDOM(fs.readFileSync('.test-tmp/maintenance.html', 'utf8'), {
  url: 'http://127.0.0.1:8765/maintenance', runScripts: 'dangerously', virtualConsole,
  beforeParse(window) { window.fetch = fakeFetch; window.open = () => popup; }
});
const document = dom.window.document;
const byId = id => document.getElementById(id);
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function waitFor(predicate) {
  for (let i = 0; i < 100; i++) { if (predicate()) return; await sleep(20); }
  throw new Error('Timed out waiting for maintenance state');
}
function changeProvider(provider) { byId('provider').value = provider; byId('provider').dispatchEvent(new dom.window.Event('change')); }
function submit(id) { byId(id).dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true })); }
(async () => {
  let callback;
  try {
    await waitFor(() => byId('overview').children.length > 0);
    assert.equal(document.querySelector('#events img'), null);
    assert.ok(byId('events').textContent.includes('<img'));
    changeProvider('serper');
    byId('api-key').value = 'fake-serper-secret'; submit('key-form');
    await waitFor(() => !byId('provider').disabled && byId('api-key').value === '');
    assert.deepEqual(calls.find(call => call.url === '/api/save-key').payload, { name: 'SERPER_API_KEY', value: 'fake-serper-secret' });
    assert.equal(byId('test-search').disabled, true);
    byId('test-search').click();
    assert.equal(calls.filter(call => call.url === '/api/maintenance/check').length, 0);
    byId('allow-billable').checked = true; byId('allow-billable').dispatchEvent(new dom.window.Event('change'));
    byId('test-search').click(); await waitFor(() => !byId('provider').disabled);
    assert.deepEqual(calls.find(call => call.url === '/api/maintenance/check').payload, { provider: 'serper', allow_billable: true });
    assert.equal(byId('allow-billable').checked, false);
    byId('portal-ready').checked = true; byId('billing-reviewed').checked = true; byId('next-review').value = '2026-11-29'; submit('review-form');
    await waitFor(() => !byId('provider').disabled);
    assert.equal(state.history.providers.serper.next_review, '2026-11-29');
    byId('api-key').value = 'unsaved-secret'; changeProvider('tavily');
    assert.equal(byId('api-key').value, '');
    assert.equal(byId('billable-label').hidden, true);
    byId('check-access').click(); await waitFor(() => !byId('provider').disabled);
    assert.deepEqual(calls.filter(call => call.url === '/api/maintenance/check').at(-1).payload, { provider: 'tavily', allow_billable: false });
    assert.equal(byId('usage').textContent, 'usage: 5');
    changeProvider('openrouter'); byId('connect').click();
    await waitFor(() => !byId('provider').disabled);
    assert.equal(popup.opener, null);
    assert.ok(popup.location.href.startsWith('https://openrouter.ai/auth?'));
    assert.equal(byId('authorization-link').hidden, false);
    callback = new JSDOM(fs.readFileSync('.test-tmp/maintenance_callback.html', 'utf8'), {
      url: 'http://127.0.0.1:8765/maintenance/oauth-callback?state=private-state&code=private-code', runScripts: 'dangerously', virtualConsole,
      beforeParse(window) { window.fetch = async (url, options) => {
        assert.equal(window.location.search, '');
        assert.equal(url, '/api/maintenance/openrouter/finish');
        assert.deepEqual(JSON.parse(options.body), { state: 'private-state', code: 'private-code' });
        assert.equal(options.headers['X-Playpen-Token'], 'test-session-token');
        return { json: async () => ({ message: 'Saved in encrypted OS storage.' }) };
      }; }
    });
    await waitFor(() => callback.window.document.getElementById('result').textContent.includes('Saved'));
    assert.equal(callback.window.location.search, '');
    assert.equal(callback.window.document.body.textContent.includes('private-code'), false);
    assert.equal(errors.length, 0, errors.map(error => error.stack).join('\n'));
    process.stdout.write('Maintenance DOM smoke passed: correct key routing, secret-field clearing, billable-test consent, review persistence, OAuth portal launch, and callback URL scrubbing.\n');
  } finally { dom.window.close(); if (callback) callback.window.close(); }
})().catch(error => { process.stderr.write(error.stack + '\n'); process.exitCode = 1; });
