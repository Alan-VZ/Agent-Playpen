// python tests/render_baseline_ui.py; node tests/baseline_ui.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM,VirtualConsole} = require(path.resolve('.test-tmp/ui-test/node_modules/jsdom'));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function waitFor(fn){for(let n=0;n<100;n++){if(fn())return;await sleep(15);}throw new Error('DOM condition timed out');}
async function main(){
 for(const page of ['api_inventory','baselines']){
  const errors=[], calls=[],saved=[];let present=false, checked=false;
  const console=new VirtualConsole();console.on('jsdomError',e=>errors.push(e.message));
  const row=()=>({provider:'openrouter',name:'OpenRouter',key_name:'OPENROUTER_API_KEY',portal:'https://openrouter.ai/workspaces/default/keys',required_by:['agent-1: model'],present,status:checked?'verified':present?'unchecked':'missing',checked_at:checked?'2026-11-15T12:00:00+00:00':null,stale:!checked,next_review:null,review_due:false,readonly_check:true,search_test:false});
  const dom=new JSDOM(fs.readFileSync('.test-tmp/baseline_'+page+'.html','utf8'),{url:'http://127.0.0.1:8765',runScripts:'dangerously',virtualConsole:console,beforeParse(window){
   window.HTMLDialogElement.prototype.showModal=function(){this.open=true;};window.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new window.Event('close'));};
   window.fetch=async(resource,options={})=>{const url=new URL(resource,'http://127.0.0.1:8765');assert.equal(new Headers(options.headers).get('X-Playpen-Token'),'test-session-token');calls.push(url.pathname);const payload=options.body?JSON.parse(options.body):{};let value;
    if(url.pathname==='/api/readiness')value={ready:present,providers:[row()],blocking:present?[]:['openrouter']};
    else if(url.pathname==='/api/save-key'){saved.push(payload);present=true;checked=false;value={status:'saved'};}
    else if(url.pathname==='/api/readiness/check'){assert.equal(payload.allow_billable,false);checked=true;value={status:'verified',message:'Account endpoint accepted the key.'};}
    else if(url.pathname==='/api/readiness/review')value={status:'saved'};
    else if(url.pathname==='/api/benchmarks'&&options.method==='POST')value={id:'a'.repeat(32),status:'running'};
    else if(url.pathname==='/api/benchmarks')value=[];
    else if(url.pathname==='/api/benchmarks/'+'a'.repeat(32))value={status:'completed',progress:{completed:5,scheduled:5},summaries:[],configs:[],repeats:1,attempts:[],events:[]};
    else throw new Error('Unexpected request '+url.pathname);
    return {ok:true,json:async()=>value};};
  }});
  try{
   const d=dom.window.document;
   d.getElementById('pp-menu-toggle').click();assert.equal(d.getElementById('pp-dropdown').hidden,false);assert.equal(d.getElementById('pp-menu-toggle').getAttribute('aria-expanded'),'true');
   d.getElementById('pp-open-secrets').click();await waitFor(()=>d.querySelector('#pp-provider-list details'));
   assert.equal(d.getElementById('pp-secrets').open,true);assert.ok(d.querySelector('#pp-provider-list summary').textContent.includes('Missing key'));
   const link=d.querySelector('#pp-provider-list a');assert.equal(link.target,'_blank');assert.match(link.href,/openrouter\.ai/);
   const input=d.querySelector('#pp-provider-list input[type=password]');assert.equal(input.autocomplete,'off');input.value='test-secret-never-export';
   const save=Array.from(d.querySelectorAll('#pp-provider-list button')).find(b=>b.textContent==='Save securely');save.click();await waitFor(()=>saved.length===1);await waitFor(()=>d.querySelector('#pp-provider-list summary').textContent.includes('Saved; unchecked'));
   assert.equal(d.querySelector('#pp-provider-list input[type=password]').value,'');assert.equal(calls.filter(p=>p==='/api/readiness/check').length,0);assert.equal(dom.window.localStorage.length,0);
   Array.from(d.querySelectorAll('#pp-provider-list button')).find(b=>b.textContent==='Check again').click();await waitFor(()=>d.querySelector('#pp-provider-list summary').textContent.includes('Access verified'));
   d.getElementById('pp-close-secrets').click();assert.equal(d.getElementById('pp-secrets').open,false);
   if(page==='baselines'){
    d.getElementById('team-preset').click();const configs=JSON.parse(d.getElementById('baseline-config').value);assert.equal(configs.length,2);assert.equal(configs[1].agents.length,3);assert.equal(configs[0].token_reservation_limit,configs[1].token_reservation_limit);
    d.getElementById('baseline-run').click();await waitFor(()=>d.getElementById('baseline-message').textContent.includes('completed'));assert.equal(d.querySelectorAll('#baseline-exports button').length,4);
   }
   assert.deepEqual(errors,[]);
  }finally{dom.window.close();}
 }
 process.stdout.write('Inventory accordion, secure entry, explicit checks, team presets, launch and export UI checks passed.\n');
}
main().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1;});
