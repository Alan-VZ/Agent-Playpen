// Render first: python tests/render_baseline_ui.py
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM,VirtualConsole}=require(path.resolve('.test-tmp/ui-test/node_modules/jsdom'));
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function waitFor(fn){for(let n=0;n<100;n++){if(fn())return;await sleep(15);}throw new Error('Model UI state timed out');}
(async()=>{
 const errors=[],mutations=[];let loaded=false;
 const console=new VirtualConsole();console.on('jsdomError',e=>errors.push(e.message));
 const dom=new JSDOM(fs.readFileSync('.test-tmp/baseline_index.html','utf8'),{url:'http://127.0.0.1:8765/',runScripts:'dangerously',virtualConsole:console,beforeParse(window){
  window.Headers=Headers;window.TextDecoder=TextDecoder;window.AbortController=AbortController;
  window.fetch=async(resource,options={})=>{const route=new URL(resource,'http://127.0.0.1:8765').pathname;let value;
   if(route==='/api/defaults')value={backend:'lm_studio',model:'chosen-model',tools:['calculator']};
   else if(route==='/api/keys')value={};
   else if(route==='/api/models')value={models:['chosen-model'],source:'live'};
   else if(route==='/api/local-models/status')value={loaded,model:loaded?'chosen-instance':'chosen-model',message:loaded?'Loaded in LM Studio: chosen-instance.':'Available on disk, but not loaded in LM Studio.'};
   else if(route==='/api/local-models/load'){const payload=JSON.parse(options.body);assert.equal(payload.model,'chosen-model');mutations.push(payload);loaded=true;value={loaded:true,model:'chosen-instance',message:'Loaded in LM Studio: chosen-instance.'};}
   else throw new Error('Unexpected request '+route);
   return {ok:true,json:async()=>value};
  };
 }});
 try{
  const d=dom.window.document;
  await waitFor(()=>d.getElementById('backend').value==='lm_studio'&&d.getElementById('model').value==='chosen-model');
  assert.equal(d.getElementById('load-models').textContent,'Refresh model list');
  const buttons=Array.from(d.querySelectorAll('#local-model-controls button'));
  assert.equal(mutations.length,0);
  buttons.find(b=>b.textContent==='Check loaded status').click();await waitFor(()=>d.querySelector('#local-model-controls p').textContent.includes('Available on disk'));
  assert.equal(mutations.length,0);
  buttons.find(b=>b.textContent==='Load selected model in LM Studio').click();await waitFor(()=>d.getElementById('model').value==='chosen-instance');
  assert.equal(mutations.length,1);assert.equal(mutations[0].replace_loaded,true);assert.ok(d.querySelector('#local-model-controls input[type=checkbox]').checked);assert.ok(d.querySelector('#local-model-controls p').textContent.includes('Loaded in LM Studio'));
  d.getElementById('backend').value='openrouter';d.getElementById('backend').dispatchEvent(new dom.window.Event('change'));assert.equal(d.getElementById('local-model-controls').hidden,true);
  assert.deepEqual(errors,[]);
 }finally{dom.window.close();}
 process.stdout.write('Discovery/status remain read-only; explicit load, verified instance selection, and backend visibility checks passed.\n');
})().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1;});
