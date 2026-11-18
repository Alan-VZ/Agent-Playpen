// Render first: python tests/render_baseline_ui.py
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {JSDOM,VirtualConsole}=require(path.resolve('.test-tmp/ui-test/node_modules/jsdom'));
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function waitFor(fn){for(let n=0;n<100;n++){if(fn())return;await sleep(15);}throw new Error('UI state timed out');}
async function check(page){
 const errors=[],launches=[];
 const console=new VirtualConsole();console.on('jsdomError',error=>errors.push(error.message));
 const url=page==='baselines'?'http://127.0.0.1:8765/baselines?tasks=B01,B05&backend=lm_studio&model=chosen-model&temperature=0&max_iterations=12&max_output_tokens=1024&models='+encodeURIComponent(JSON.stringify([{backend:'lm_studio',model:'chosen-model'},{backend:'openrouter',model:'hosted-model'}])):'http://127.0.0.1:8765/';
 const dom=new JSDOM(fs.readFileSync('.test-tmp/baseline_'+page+'.html','utf8'),{url,runScripts:'dangerously',virtualConsole:console,beforeParse(window){
  window.Headers=Headers;window.TextDecoder=TextDecoder;window.AbortController=AbortController;
  window.fetch=async(resource,options={})=>{const route=new URL(resource,url).pathname;let value;
   if(route==='/api/defaults')value={backend:'lm_studio',model:'chosen-model',tools:['calculator'],temperature:0};
   else if(route==='/api/model-picker')value={models:[{id:'chosen-model',loaded:true}],active_models:['chosen-model'],source:'live'};
   else if(route==='/api/keys')value={};
   else if(route==='/api/readiness')value={ready:true,providers:[],blocking:[]};
   else if(route==='/api/benchmarks'&&options.method==='POST'){launches.push(JSON.parse(options.body));value={id:'b'.repeat(32),status:'running'};}
   else if(route==='/api/benchmarks')value=[];
   else if(route==='/api/benchmarks/'+'b'.repeat(32))value={status:'completed',progress:{completed:2,scheduled:2},summaries:[],attempts:[],configs:launches[0].configs,repeats:1,selected_tasks:launches[0].tasks,events:[]};
   else throw new Error('Unexpected API '+route);
   return {ok:true,json:async()=>value};
  };
 }});
 try{
  const d=dom.window.document,picker=dom.window.playpenBaselineTasks;
  assert.equal(d.querySelectorAll('input[name=baseline_tasks]').length,5);
  if(page==='index'){
   await waitFor(()=>d.getElementById('backend').options.length>0);
   assert.equal(picker.ids().length,0);
   assert.equal(d.getElementById('temperature').value,'0');
   for(const [id,value] of [['max_iterations','15'],['temperature','0.25'],['max_tokens','4096']]){
    const field=d.getElementById(id);assert.equal(field.type,'text');field.value='';field.dispatchEvent(new dom.window.Event('input',{bubbles:true}));assert.equal(field.checkValidity(),false);
    field.value=value;field.dispatchEvent(new dom.window.Event('input',{bubbles:true}));assert.equal(field.value,value);assert.equal(field.checkValidity(),true);
   }
   const temp=d.getElementById('temperature');temp.value='3';temp.dispatchEvent(new dom.window.Event('input'));assert.equal(temp.checkValidity(),false);temp.value='0';temp.dispatchEvent(new dom.window.Event('input'));assert.equal(temp.checkValidity(),true);

   d.getElementById('planner').value='cot';
   d.querySelector('input[name=baseline_tasks][value=B01]').click();assert.ok(d.getElementById('task').value.includes('B01 路 Data reconciliation'));
   assert.equal(d.getElementById('planner').value,'react');assert.equal(d.getElementById('planner').disabled,true);
   assert.deepEqual(Array.from(d.querySelectorAll('input[name=baseline_tools]:checked')).map(i=>i.value),['read_fixture','calculator']);
   d.querySelector('input[name=baseline_tasks][value=B01]').click();assert.equal(d.getElementById('task').value,'');
   assert.equal(d.getElementById('planner').value,'cot');assert.equal(d.getElementById('planner').disabled,false);
   d.getElementById('task').value='My custom task';
   d.querySelector('input[name=baseline_tasks][value=B01]').click();d.querySelector('input[name=baseline_tasks][value=B05]').click();
   assert.equal(d.getElementById('task').value,'My custom task','checking boxes should not overwrite a custom task');
   d.getElementById('baseline-load-tasks').click();
   assert.ok(d.getElementById('task').value.includes('B01 路 Data reconciliation'));
   assert.ok(d.getElementById('task').value.includes('B05 路 Conflicting evidence'));
   assert.ok(!d.getElementById('task').value.includes('B02 路 Research'));
   assert.equal(picker.runLoaded(),true);
   const count=d.getElementById('workspace-model-count');count.value=3;count.dispatchEvent(new dom.window.Event('change'));await waitFor(()=>dom.window.playpenModelSlots.get().every(m=>m.model==='chosen-model'));
   assert.equal(d.querySelectorAll('.workspace-model-card').length,3);
   assert.equal(d.querySelectorAll('#model-summary-body tr').length,3);
   assert.equal(d.getElementById('planner').selectedOptions[0].textContent,'ReAct');
   assert.ok(!d.body.textContent.includes('鈥'));assert.ok(!d.body.textContent.includes('鈫'));
   const defaultSeconds=d.querySelector('#model-defaults [data-setting="timeout_seconds"]');defaultSeconds.value='600';defaultSeconds.dispatchEvent(new dom.window.Event('input'));defaultSeconds.dispatchEvent(new dom.window.Event('change'));
   d.getElementById('apply-model-defaults').click();assert.ok(dom.window.playpenModelSlots.get().every(slot=>slot.timeout_seconds===600));assert.equal(JSON.parse(dom.window.localStorage.getItem('playpen-model-defaults')).timeout_seconds,600);
   const thirdSeconds=d.querySelector('#model-summary-body tr[data-model="3"] [data-setting="timeout_seconds"]');thirdSeconds.value='450';thirdSeconds.dispatchEvent(new dom.window.Event('input'));thirdSeconds.dispatchEvent(new dom.window.Event('change'));assert.equal(dom.window.playpenModelSlots.get()[2].timeout_seconds,450);

   const second=d.querySelector('[data-slot="2"] [data-parameter="temperature"]');second.value='0.4';second.dispatchEvent(new dom.window.Event('input'));
   const tokens=d.querySelector('[data-slot="2"] [data-parameter="max_tokens"]');tokens.value='8192';tokens.dispatchEvent(new dom.window.Event('input'));
   count.value=2;count.dispatchEvent(new dom.window.Event('change'));count.value=3;count.dispatchEvent(new dom.window.Event('change'));
   assert.equal(dom.window.playpenModelSlots.get()[1].temperature,0.4);assert.equal(dom.window.playpenModelSlots.get()[1].max_tokens,8192);
   const destination=new URL(picker.destination(),url);
   assert.equal(JSON.parse(destination.searchParams.get('models')).length,3);
   assert.equal(destination.searchParams.get('tasks'),'B01,B05');assert.equal(destination.searchParams.get('model'),'chosen-model');assert.equal(destination.searchParams.has('api_key'),false);
   d.getElementById('workspace-baseline-repeats').value='5';const started=await picker.launch();assert.equal(started.id,'b'.repeat(32));assert.equal(launches.length,1);assert.equal(launches[0].repeats,5);assert.equal(launches[0].configs.length,3);assert.equal(launches[0].configs[0].agents.length,1);assert.deepEqual(launches[0].tasks,['B01','B05']);assert.deepEqual(launches[0].configs[0].agents[0].tools,['read_fixture','calculator']);assert.equal(launches[0].configs[0].agents[0].tool_calling_mode,'auto');assert.equal(launches[0].configs[0].timeout_seconds,600);assert.equal(launches[0].configs[2].timeout_seconds,450);assert.equal(launches[0].configs[1].agents[0].temperature,0.4);assert.equal(launches[0].configs[1].max_output_tokens,8192);
   d.getElementById('task').value='An edited custom task';assert.equal(picker.runLoaded(),false);
   d.getElementById('baseline-clear-selection').click();assert.equal(d.getElementById('baseline-load-tasks').disabled,true);
  }else{
   assert.deepEqual(Array.from(picker.ids()),['B01','B05']);
   const configs=JSON.parse(d.getElementById('baseline-config').value),config=configs[0];assert.equal(configs.length,2);assert.equal(config.agents.length,1);assert.equal(configs[1].agents[0].model,'hosted-model');assert.equal(configs[1].agents[0].backend,'openrouter');assert.equal(config.agents[0].model,'chosen-model');assert.equal(config.max_iterations,12);assert.equal(config.max_output_tokens,1024);assert.equal(config.timeout_seconds,210);
   assert.equal(config.agents[0].planner,'react');assert.equal(config.agents[0].tool_calling_mode,'auto');assert.deepEqual(config.agents[0].tools,['read_fixture','calculator']);
   const automatic=d.querySelector('.baseline-builder label.checkbox-option input');assert.equal(automatic.checked,true);assert.equal(dom.window.getComputedStyle(automatic.parentElement).flexDirection,'row');assert.equal(dom.window.getComputedStyle(automatic).width,'17px');assert.equal(d.querySelector('.baseline-tools input').disabled,true);
   automatic.click();assert.equal(d.querySelector('.baseline-tools input').disabled,false);
   const readBox=d.querySelector('.baseline-tools input');readBox.click();assert.ok(!JSON.parse(d.getElementById('baseline-config').value)[0].agents[0].tools.includes('read_fixture'));
   d.querySelector('.baseline-builder label.checkbox-option input').click();assert.equal(d.querySelector('.baseline-tools input').disabled,true);assert.ok(JSON.parse(d.getElementById('baseline-config').value)[0].agents[0].tools.includes('read_fixture'));
   const sharedTasks=d.querySelector('.baseline-builder fieldset input');assert.equal(sharedTasks.checked,true);sharedTasks.click();
   const taskB03=d.querySelector('.baseline-builder fieldset input[data-task="B03"]');taskB03.click();assert.ok(JSON.parse(d.getElementById('baseline-config').value)[0].selected_tasks.includes('B03'));
   assert.ok(JSON.parse(d.getElementById('baseline-config').value)[0].agents[0].tools.includes('write_artifact'));
   d.querySelector('.baseline-builder fieldset input').click();assert.equal(JSON.parse(d.getElementById('baseline-config').value)[0].selected_tasks,undefined);
   picker.select(['B03']);assert.deepEqual(JSON.parse(d.getElementById('baseline-config').value)[0].agents[0].tools,['read_fixture','write_artifact']);
   d.getElementById('baseline-clear-selection').click();d.getElementById('baseline-run').click();await waitFor(()=>d.getElementById('baseline-message').textContent.includes('at least one'));assert.equal(launches.length,0);
   picker.select(['B01','B05']);d.getElementById('baseline-repeats').value='1';d.getElementById('baseline-run').click();await waitFor(()=>launches.length===1);assert.deepEqual(launches[0].tasks,['B01','B05']);
   await waitFor(()=>d.getElementById('baseline-exports').children.length===4);
   picker.select(['B02']);Array.from(d.querySelectorAll('#baseline-exports button')).find(b=>b.textContent.includes('Use these settings')).click();assert.deepEqual(Array.from(picker.ids()),['B01','B05']);
  }
  assert.deepEqual(errors,[]);
 }finally{dom.window.close();}
}
(async()=>{await check('index');await check('baselines');process.stdout.write('Baseline checkboxes, task loading, workspace transfer, empty-selection guard, selected-run payload, and rerun restoration passed.\n');})().catch(error=>{process.stderr.write(error.stack+'\n');process.exitCode=1;});
