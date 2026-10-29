// Optional DOM smoke test: npm install --prefix .test-tmp/ui-test --ignore-scripts jsdom
// Run from the project root: node tests/dashboard_ui.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM, VirtualConsole } = require(path.resolve('.test-tmp/ui-test/node_modules/jsdom'));

const template = fs.readFileSync('debugging/dashboard/templates/index.html', 'utf8')
  .replaceAll('{{ session_token }}', 'test-session-token');
const jsErrors = [];
const console = new VirtualConsole();
console.on('jsdomError', error => jsErrors.push(error));
const requests = [];
const savedSearchKeys = [];

async function mockFetch(resource, options = {}) {
  const url = new URL(resource, 'http://127.0.0.1:8765');
  assert.equal(new Headers(options.headers).get('X-Playpen-Token'), 'test-session-token');
  assert.equal(url.searchParams.has('api_key'), false);
  requests.push(url.pathname);
  const json = data => new Response(JSON.stringify(data), { headers: { 'Content-Type': 'application/json' } });
  if (url.pathname === '/api/defaults') return json({ backend: 'lm_studio', model: 'demo', tools: ['calculator'] });
  if (url.pathname === '/api/keys') return json({});
  if (url.pathname === '/api/save-key') {
    savedSearchKeys.push(JSON.parse(options.body));
    return json({ status: 'saved', message: 'Credential saved in encrypted OS storage.' });
  }
  if (url.pathname === '/api/models') return json({ models: ['demo'], source: 'live' });
  assert.equal(url.pathname, '/api/run/stream');
  const task = JSON.parse(options.body).task;
  const timers = [];
  const stream = new ReadableStream({
    start(controller) {
      const encoder = new TextEncoder();
      function emit(event) {
        const bytes = encoder.encode(JSON.stringify(event) + '\n');
        // Exercise line boundaries and UTF-8 decoding across arbitrary chunks.
        for (let i = 0; i < bytes.length; i += 7) controller.enqueue(bytes.slice(i, i + 7));
      }
      emit({ type: 'session', session_id: 'test-session', agent_id: 'agent-1', backend: 'demo', model: 'demo' });
      emit({ type: 'model_request', content: 'Waiting for model', iteration: 0 });
      if (task === 'slow') {
        options.signal.addEventListener('abort', () => {
          timers.forEach(clearTimeout);
          controller.error(new DOMException('Stopped', 'AbortError'));
        }, { once: true });
        return;
      }
      timers.push(setTimeout(() => {
        if (task === 'warning') {
          emit({ type: 'warning', content: 'Search returned no results' });
          emit({ type: 'complete', status: 'success', warning_count: 1, result: 'Could not verify the source', session_id: 'test-session' });
          controller.close();
          return;
        }
        if (task === 'fail') {
          emit({ type: 'error', content: 'Provider unavailable' });
          emit({ type: 'complete', status: 'error', message: 'Provider unavailable', session_id: 'test-session', trace_path: 'saved-failure.json' });
          controller.close();
          return;
        }
        emit({ type: 'act', tool_name: 'calculator', content: 'calculator(6*7)', iteration: 0 });
        emit({ type: 'observe', content: '42 café <img src=x onerror=alert(1)>', iteration: 0 });
        timers.push(setTimeout(() => {
          emit({ type: 'response', content: 'Answer: 42 café' });
          emit({ type: 'complete', status: 'success', result: 'Answer: 42 café', session_id: 'test-session', trace_path: 'saved-success.json' });
          controller.close();
        }, 200));
      }, 100));
    }
  });
  return new Response(stream, { headers: { 'Content-Type': 'application/x-ndjson' } });
}

const dom = new JSDOM(template, {
  url: 'http://127.0.0.1:8765', runScripts: 'dangerously', virtualConsole: console,
  beforeParse(window) {
    window.fetch = mockFetch;
    window.Headers = Headers;
    window.TextDecoder = TextDecoder;
    window.AbortController = AbortController;
  }
});
const { document } = dom.window;
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function waitFor(predicate) {
  for (let i = 0; i < 100; i++) {
    if (predicate()) return;
    await sleep(20);
  }
  throw new Error('Timed out waiting for dashboard state');
}
function submit(task) {
  document.getElementById('task').value = task;
  document.getElementById('agent-form').dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true }));
}

(async () => {
  try {
    await waitFor(() => document.getElementById('backend').options.length > 0);
    await waitFor(() => requests.includes('/api/keys'));
    const searchSelect = document.getElementById('search_provider');
    for (const [provider, key] of Object.entries({ serper: 'SERPER_API_KEY', brave: 'BRAVE_API_KEY', exa: 'EXA_API_KEY', firecrawl: 'FIRECRAWL_API_KEY', openwebninja: 'OPENWEBNINJA_API_KEY' })) {
      searchSelect.value = provider;
      searchSelect.dispatchEvent(new dom.window.Event('change'));
      assert.equal(document.getElementById('manage-search-key').disabled, false);
      document.getElementById('api_key').value = 'unsaved-other-provider-key';
      document.getElementById('manage-search-key').click();
      assert.equal(document.getElementById('credential_name').value, key);
      assert.equal(document.getElementById('api_key').value, '');
      document.getElementById('api_key').value = 'fake-search-key';
      document.getElementById('save-key').click();
      await waitFor(() => savedSearchKeys.some(item => item.name === key));
      await waitFor(() => document.getElementById('api_key').value === '');
      assert.equal(savedSearchKeys.at(-1).value, 'fake-search-key');
    }
    searchSelect.value = 'crossref';
    searchSelect.dispatchEvent(new dom.window.Event('change'));
    assert.equal(document.getElementById('manage-search-key').disabled, true);
    document.getElementById('credential_name').value = '';
    submit('success');
    await waitFor(() => document.getElementById('activity-log').children.length >= 2);
    assert.equal(document.getElementById('run-agent').disabled, true);
    assert.equal(document.getElementById('stop-agent').disabled, false);
    assert.equal(document.getElementById('result-output').textContent.includes('Answer: 42'), false);
    await waitFor(() => document.getElementById('result-output').textContent === 'Answer: 42 café');
    await waitFor(() => !document.getElementById('run-agent').disabled);
    assert.equal(document.querySelector('#activity-log img'), null);
    assert.ok(document.getElementById('activity-log').textContent.includes('<img'));
    assert.ok(document.getElementById('meta-output').textContent.includes('saved-success.json'));

    submit('fail');
    await waitFor(() => document.getElementById('result-output').textContent === 'Provider unavailable');
    await waitFor(() => !document.getElementById('run-agent').disabled);
    assert.ok(document.getElementById('activity-log').textContent.includes('Provider unavailable'));
    assert.ok(document.getElementById('meta-output').textContent.includes('saved-failure.json'));

    submit('warning');
    await waitFor(() => document.getElementById('result-output').textContent === 'Could not verify the source');
    await waitFor(() => !document.getElementById('run-agent').disabled);
    assert.ok(document.getElementById('status').classList.contains('warning'));
    assert.ok(document.getElementById('status').textContent.includes('tool warnings'));

    submit('slow');
    await waitFor(() => !document.getElementById('stop-agent').disabled);
    document.getElementById('stop-agent').click();
    await waitFor(() => !document.getElementById('run-agent').disabled);
    assert.ok(document.getElementById('result-output').textContent.includes('Stop requested'));
    assert.equal(jsErrors.length, 0, jsErrors.map(error => error.stack).join('\n'));
    process.stdout.write('Dashboard DOM smoke passed: live progress, UTF-8 chunking, final/error states, escaped tool output, and Stop Run.\n');
  } finally {
    dom.window.close();
  }
})().catch(error => { process.stderr.write(error.stack + '\n'); process.exitCode = 1; });
