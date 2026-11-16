// Render production templates first: python tests/render_baseline_ui.py
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM,VirtualConsole}=require(path.resolve('.test-tmp/ui-test/node_modules/jsdom'));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function waitFor(fn){for(let i=0;i<150;i++){if(fn())return;await sleep(10);}throw new Error('Baseline feedback timed out');}
(async()=>{
 const old='a'.repeat(32),fresh='b'.repeat(32),requested='c'.repeat(32),errors=[],scheduled=[];let phase='saved',launches=0,polls=0,releaseCheck,releaseLaunch,needsSetup=false,offline=false;
 const virtualConsole=new VirtualConsole();virtualConsole.on('jsdomError',e=>errors.push(e.message));
 function attempt(pass){return {task:'B01',config_index:0,repetition:0,status:'completed',evaluation:{passed:pass,checks:{valid_json:pass}},agents:[{agent_id:'agent-1',status:pass?'success':'error',error_type:pass?undefined:'APITimeoutError',answer:pass?'42':'Invalid answer <img src=x>',trace:[{type:'response',content:'Saved activity'}]}]};}
 function record(id){const running=id===fresh&&phase==='running',passed=phase==='passed';return {id,status:running?'running':'completed',progress:{completed:running?0:1,scheduled:1},configs:[{name:'one model',agents:[{backend:'lm_studio',model:'actual-model'}]}],repeats:1,selected_tasks:['B01'],summaries:[],attempts:running?[]:[attempt(passed)],events:running?[{type:'model_request',agent_id:'agent-1',content:'Waiting for local model'}]:[]};}
 const dom=new JSDOM(fs.readFileSync('.test-tmp/baseline_baselines.html','utf8'),{url:'http://127.0.0.1:8765/baselines?run='+requested,runScripts:'dangerously',virtualConsole,beforeParse(w){
  w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;};
  const nativeTimeout=w.setTimeout.bind(w);w.setTimeout=(fn,ms,...args)=>ms>=1500?(scheduled.push(fn),scheduled.length):nativeTimeout(fn,ms,...args);
  w.fetch=async(resource,options={})=>{const url=new URL(resource,'http://127.0.0.1:8765');assert.equal(new Headers(options.headers).get('X-Playpen-Token'),'test-session-token');let data;
   if(url.pathname==='/api/model-picker')data={models:[{id:'actual-model',loaded:true}],active_models:['actual-model']};
   else if(url.pathname==='/api/benchmarks'&&options.method==='POST'){launches++;return await new Promise(resolve=>releaseLaunch=()=>resolve({ok:true,json:async()=>({id:fresh,status:'running'})}));}
   else if(url.pathname==='/api/benchmarks')data=[{id:old,created_at:'2026-11-15T17:00:00-08:00',status:'completed',completed:1,scheduled:1,passed:0}];
   else if(url.pathname==='/api/benchmarks/'+old||url.pathname==='/api/benchmarks/'+requested)data=record(requested);
   else if(url.pathname==='/api/benchmarks/'+fresh){polls++;if(phase==='offline')throw new Error('Temporary connection loss');data=record(fresh);}
   else if(url.pathname==='/api/readiness'){if(offline)throw new Error('Setup service unavailable');if(needsSetup)data={ready:false,providers:[],blocking:[]};else return await new Promise(resolve=>releaseCheck=()=>resolve({ok:true,json:async()=>({ready:true,providers:[],blocking:[]})}));}
   else throw new Error('Unexpected API '+url.pathname);
   return {ok:true,json:async()=>data};
  };
 }});
 try{
  const d=dom.window.document,msg=()=>d.getElementById('baseline-message').textContent,run=d.getElementById('baseline-run');
  await waitFor(()=>msg().includes('Run completed'));assert.ok(msg().includes('0 passed'));assert.ok(d.getElementById('baseline-outcome').textContent.includes('model request timed out'));assert.equal(d.getElementById('baseline-status-panel').dataset.state,'failed');assert.ok(d.getElementById('baseline-evidence').textContent.includes('Failed checks: valid_json'));assert.ok(d.getElementById('baseline-activity').textContent.includes('Saved activity'));assert.equal(d.querySelector('#baseline-evidence img'),null);assert.ok(dom.window.location.search.includes(requested));
  run.click();assert.equal(run.disabled,true);assert.ok(msg().includes('Checking baseline setup'));run.click();assert.equal(launches,0);
  await waitFor(()=>releaseCheck);releaseCheck();await waitFor(()=>releaseLaunch);assert.ok(msg().includes('Starting baseline tests'));assert.equal(launches,1);
  phase='running';releaseLaunch();await waitFor(()=>msg().includes('Running baseline tests'));assert.equal(d.getElementById('baseline-progress').value,0);assert.equal(d.getElementById('baseline-stop').disabled,false);assert.ok(d.getElementById('baseline-activity').textContent.includes('Waiting for local model'));
  phase='offline';scheduled.shift()();await waitFor(()=>msg().includes('Retrying automatically'));assert.equal(run.disabled,true);
  phase='passed';scheduled.shift()();await waitFor(()=>msg().includes('All selected tests passed'));assert.equal(run.disabled,false);assert.equal(d.getElementById('baseline-progress').value,1);assert.equal(d.getElementById('baseline-status-panel').dataset.state,'passed');assert.equal(d.querySelectorAll('#baseline-exports button').length,4);assert.ok(polls>=3);
  needsSetup=true;run.click();await waitFor(()=>msg().includes('Not started'));assert.equal(run.disabled,false);assert.equal(launches,1);assert.ok(d.getElementById('baseline-run-detail').textContent.includes('No experiment was launched'));
  needsSetup=false;offline=true;d.getElementById('pp-close-secrets').click();run.click();await waitFor(()=>msg().includes('Baseline launch failed'));assert.equal(run.disabled,false);assert.equal(launches,1);
  assert.deepEqual(errors,[]);
 }finally{dom.window.close();}
 process.stdout.write('Baseline feedback passed: automatic saved results, visible failures/answers, immediate acknowledgement, duplicate protection, live progress, status retry, success, setup block and launch failure.\n');
})().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1;});
