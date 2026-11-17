const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const {JSDOM, VirtualConsole} = require(path.resolve('.test-tmp/ui-test/node_modules/jsdom'));
(async () => {
  const errors = [], timers = []; let stopped = false;
  const console = new VirtualConsole(); console.on('jsdomError', e => errors.push(e.message));
  const dom = new JSDOM(fs.readFileSync('.test-tmp/baseline_controlled_study.html', 'utf8'), {
    url: 'http://127.0.0.1:8765/controlled-tests/' + 'a'.repeat(32), runScripts: 'dangerously', virtualConsole: console,
    beforeParse(w) {
      w.setTimeout = fn => {timers.push(fn); return timers.length;};
      w.fetch = async (url, opts) => {
        assert.equal(opts.headers['X-Playpen-Token'], 'test-session-token');
        if (url.endsWith('/stop')) {stopped = true; return {ok: true, json: async () => ({status: 'stopping'})};}
        return {ok: true, json: async () => ({status: 'running', completed: 7, scheduled: 1200,
          current: {round: 1, task: 'B03', provider: 'groq', model: 'model <img src=x>', seed: 2, arm: 'B', latest_event: {content: 'Waiting for response'}},
          rows: [{round: 1, task: 'B03', provider: 'groq', model: '<script>bad</script>', A_correct: 1, A_completed: 2, B_correct: 0, B_completed: 2, A_categories: {diagnostic_correct: 1}, B_categories: {provider_quota_unavailable: 2}}]})};
      };
    }
  });
  try {
    await new Promise(r => setTimeout(r, 30));
    const d = dom.window.document;
    assert.match(d.getElementById('status').textContent, /7\/1200/);
    assert.match(d.getElementById('current').textContent, /B03/);
    assert.match(d.getElementById('table').textContent, /B03/);
    assert.match(d.getElementById('current').textContent, /Waiting for response/);
    assert.equal(d.querySelector('#table script'), null);
    assert.equal(d.querySelector('#current img'), null);
    assert.match(d.getElementById('table').textContent, /provider_quota_unavailable/);
    d.getElementById('stop').click();
    await new Promise(r => setTimeout(r, 10));
    assert(stopped); assert.match(d.getElementById('status').textContent, /Stop requested/);
    assert.deepEqual(errors, []);
    process.stdout.write('Controlled study UI: progress, outcome categories, safe text and stop passed.\n');
  } finally {dom.window.close();}
})().catch(e => {console.error(e); process.exitCode = 1;});
