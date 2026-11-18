// Render first: python tests/render_baseline_ui.py
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM,VirtualConsole}=require(path.resolve('.test-tmp/ui-test/node_modules/jsdom'));
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function waitFor(fn){for(let n=0;n<150;n++){if(fn())return;await sleep(15);}throw new Error('Model UI state timed out');}
(async()=>{
 const errors=[],mutations=[],inventoryReads=[],intervals=[];let active='actual-loaded-instance',reject=false;
 const console=new VirtualConsole();console.on('jsdomError',e=>errors.push(e.message));
 const dom=new JSDOM(fs.readFileSync('.test-tmp/baseline_index.html','utf8'),{url:'http://127.0.0.1:8765/',runScripts:'dangerously',virtualConsole:console,beforeParse(window){
  const nativeInterval=window.setInterval.bind(window);window.setInterval=(fn,ms)=>{intervals.push(ms);return nativeInterval(fn,ms);};
  window.HTMLDialogElement.prototype.showModal=function(){this.open=true;};window.HTMLDialogElement.prototype.close=function(){this.open=false;};
  window.Headers=Headers;window.TextDecoder=TextDecoder;window.AbortController=AbortController;
  window.fetch=async(resource,options={})=>{const route=new URL(resource,'http://127.0.0.1:8765').pathname;let value;
   if(route==='/api/defaults')value={backend:'lm_studio',model:'local-model',tools:['calculator']};
   else if(route==='/api/keys')value={};
   else if(route==='/api/model-picker'&&options.method==='POST'){const payload=JSON.parse(options.body);mutations.push(payload);if(reject)return {ok:false,json:async()=>({detail:'Could not release previous model'})};if(['lm_studio','ollama'].includes(payload.backend))active=payload.model;value={model:payload.model,loaded:payload.backend==='lm_studio'};}
   else if(route==='/api/model-picker'){inventoryReads.push(resource);value={models:[{id:active,loaded:true},{id:'replacement-model',loaded:false}],active_models:[active],source:'live'};}
   else throw new Error('Unexpected request '+route);
   return {ok:true,json:async()=>value};
  };
 }});
 try{
  const d=dom.window.document;
  await waitFor(()=>d.getElementById('model').value===active);
  assert.equal(d.getElementById('load-models').textContent,'Choose model');assert.equal(d.getElementById('model').readOnly,true);
  assert.ok(!d.body.textContent.includes('Check loaded status'));assert.ok(!d.body.textContent.includes('Load selected model in LM Studio'));assert.equal(mutations.length,0);assert.equal(inventoryReads.length,1);assert.ok(!intervals.includes(15000));
  d.getElementById('load-models').click();await waitFor(()=>d.querySelector('dialog[open] .pp-model-options button'));
  Array.from(d.querySelectorAll('dialog[open] .pp-model-options button')).find(b=>b.textContent==='replacement-model').click();
  await waitFor(()=>d.getElementById('model').value==='replacement-model');assert.equal(mutations.length,1);assert.equal(mutations[0].backend,'lm_studio');
  const count=d.getElementById('workspace-model-count');count.value=10;count.dispatchEvent(new dom.window.Event('change'));
  await waitFor(()=>d.querySelectorAll('#workspace-extra-models section').length===9);assert.equal(dom.window.playpenModelSlots.get().length,10);assert.equal(inventoryReads.length,1);
  const second=d.querySelector('#workspace-extra-models section select');second.value='openrouter';second.dispatchEvent(new dom.window.Event('change'));
  d.querySelector('#workspace-extra-models section .pp-model-choose').click();await waitFor(()=>d.querySelector('dialog[open] .pp-model-options button'));
  d.querySelector('dialog[open] .pp-model-options button').click();await waitFor(()=>mutations.length===2&&!d.querySelector('dialog[open]'));
  assert.equal(mutations[1].backend,'openrouter');assert.equal(dom.window.playpenModelSlots.get()[1].backend,'openrouter');assert.equal(d.getElementById('model').value,'replacement-model');
  count.value=20;count.dispatchEvent(new dom.window.Event('change'));assert.equal(count.value,'10');
  const parameter=d.querySelector('[data-slot="2"] [data-parameter="max_iterations"]');parameter.value='7';parameter.dispatchEvent(new dom.window.Event('input'));assert.equal(dom.window.playpenModelSlots.get()[1].max_iterations,7);
  const remove=Array.from(d.querySelectorAll('[data-slot="3"] button')).find(b=>b.textContent==='Remove model 3');remove.click();assert.equal(count.value,'9');assert.equal(dom.window.playpenModelSlots.get()[1].max_iterations,7);
  Array.from(d.querySelectorAll('button')).find(b=>b.textContent==='Add model').click();assert.equal(count.value,'10');assert.equal(d.querySelectorAll('.workspace-model-card').length,10);

  count.value=1;count.dispatchEvent(new dom.window.Event('change'));assert.equal(dom.window.playpenModelSlots.get().length,1);
  reject=true;dom.window.playpenModelPicker.refreshAll();await sleep(30);assert.equal(d.getElementById('model').value,'replacement-model');assert.equal(inventoryReads.length,2);
  d.getElementById('load-models').click();await waitFor(()=>d.querySelector('dialog[open] .pp-model-options button'));
  Array.from(d.querySelectorAll('dialog[open] .pp-model-options button')).find(b=>b.textContent==='actual-loaded-instance').click();
  await waitFor(()=>d.querySelector('dialog[open]').textContent.includes('Could not release'));assert.equal(d.getElementById('model').value,'replacement-model');
  assert.deepEqual(errors,[]);
 }finally{dom.window.close();}
 process.stdout.write('Unified picker passed: actual active model, one-step switch, failed switch, 1–10 mixed-provider slots and removed manual lifecycle buttons.\n');
})().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1;});
