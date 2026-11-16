let stopRequested=false;
const runButton=document.getElementById('baseline-run'),stopButton=document.getElementById('baseline-stop');
const panel=document.getElementById('baseline-status-panel'),detail=document.getElementById('baseline-run-detail');
const progress=document.getElementById('baseline-progress'),outcome=document.getElementById('baseline-outcome');
function announce(state,text){panel.dataset.state=state;message.textContent=text;panel.style.borderColor=['error','failed','needs_setup'].includes(state)?'#ffb088':state==='passed'?'#83dfb3':'#79baff';}
function focusStatus(){if(panel.scrollIntoView)panel.scrollIntoView({behavior:'smooth',block:'start'});}
function clearResults(){document.getElementById('baseline-exports').replaceChildren();document.getElementById('baseline-table').replaceChildren();document.getElementById('baseline-evidence').replaceChildren();outcome.textContent='';document.getElementById('baseline-activity').textContent='Waiting for agent activity…';progress.value=0;}
function stopPolling(){clearTimeout(timer);timer=null;version++;}
function remember(id){const url=new URL(window.location.href);url.searchParams.set('run',id);window.history.replaceState(null,'',url);}
function showTable(result){
 const table=el('table',''),header=el('tr','');table.setAttribute('aria-label','Baseline comparison results');
 for(const h of ['Configuration','Agents','B01','B02','B03','B04','B05','Passes / scheduled','Min quality','Median / p95 seconds','Actual tokens','Reserved tokens','Tool calls','Reserved USD','Violations'])header.append(el('th',h));table.append(header);
 for(const row of result.summaries||[]){const tr=el('tr','');const values=[row.name,row.agents,...['B01','B02','B03','B04','B05'].map(t=>row.tasks[t].scheduled?row.tasks[t].passed+'/'+row.tasks[t].scheduled:'Not selected'),row.passed+'/'+row.scheduled,row.minimum_quality,row.median_seconds+' / '+row.p95_seconds,row.actual_tokens,row.reserved_tokens,row.tool_requests,row.estimated_reserved_usd,row.violations];for(const v of values)tr.append(el('td',v===null?'Unknown':String(v)));table.append(tr);}
 document.getElementById('baseline-table').replaceChildren(...((result.summaries||[]).length?[table]:[el('p','Comparison results will appear here after the first attempt finishes.')]));
}
function failureReason(attempt){
 if(attempt.status==='timeout')return 'The task reached its time limit before finishing.';
 const agent=(attempt.agents||[]).find(a=>a.error_type||a.status==='error');
 if(agent){
  const messages={APITimeoutError:'The model request timed out before a response arrived. Check the model server and its response time.',TimeoutError:'Execution reached its time limit.',APIConnectionError:'Playpen could not connect to the model server. Check that it is running and reachable.'};
  const codes={401:'The model provider rejected the API credential.',402:'The model provider reported insufficient credit.',403:'The model provider denied model access.',429:'The model provider rate limit was reached.'};
  return codes[agent.http_status]||messages[agent.error_type]||((agent.error_type?agent.error_type+': ':'')+(agent.message||'The model did not finish successfully.'));
 }
 const failed=Object.entries(attempt.evaluation?.checks||{}).filter(([,ok])=>!ok).map(([name])=>name);
 return failed.length?'The answer failed required checks: '+failed.join(', '):'The attempt did not complete every required check.';
}
function showEvidence(result){
 const evidence=document.getElementById('baseline-evidence');evidence.replaceChildren();
 if((result.attempts||[]).length)evidence.append(el('h3','Individual test results — expand to see answers and failed checks'));
 for(const attempt of result.attempts||[]){const details=el('details','');const passed=attempt.evaluation?.passed;
 details.append(el('summary',attempt.task+' · configuration '+(attempt.config_index+1)+' · repeat '+(attempt.repetition+1)+' · '+(passed?'PASS':'FAIL')+' · '+attempt.status));
 const failed=Object.entries(attempt.evaluation?.checks||{}).filter(([,ok])=>!ok).map(([name])=>name);
 if(!passed)details.append(el('p',failureReason(attempt)));
 if(failed.length)details.append(el('p','Failed checks: '+failed.join(', ')));
 for(const agent of attempt.agents||[]){details.append(el('h4',agent.agent_id+' · '+agent.status),el('pre',agent.answer||agent.message||'No final answer was returned.'));}
 const raw=el('details','');raw.append(el('summary','Full recorded evidence'),el('pre',JSON.stringify(attempt,null,2)));details.append(raw);evidence.append(details);
 }
}
function showExports(result,id){
 const exports=document.getElementById('baseline-exports');exports.replaceChildren();
 const reuse=el('button','Use these settings for a new run');reuse.type='button';reuse.addEventListener('click',()=>{configInput.value=JSON.stringify(result.configs,null,2);rebuild();window.playpenBaselineTasks.select(result.selected_tasks||['B01','B02','B03','B04','B05']);document.getElementById('baseline-repeats').value=String(result.repeats||5);detail.textContent='Saved settings loaded for your next run. The results below still belong to run '+id+'.';});exports.append(reuse);
 for(const kind of ['html','csv','json']){const button=el('button','Download '+kind.toUpperCase());button.type='button';button.addEventListener('click',async()=>{try{const response=await fetch('/api/benchmarks/'+id+'/export/'+kind,{headers:{'X-Playpen-Token':token}});if(!response.ok)throw new Error('Export unavailable.');const blob=await response.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='baseline-comparison.'+kind;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){announce('error',e.message);}});exports.append(button);}
}
async function poll(){
 const id=job,requestVersion=version;if(!id)return;clearTimeout(timer);
 try{
  const result=await api('/api/benchmarks/'+id);if(id!==job||requestVersion!==version)return;
  const attempts=result.attempts||[],done=result.progress?.completed??attempts.length,total=result.progress?.scheduled??0;
  const passed=attempts.filter(a=>a.evaluation?.passed).length,failed=attempts.length-passed;
  progress.max=Math.max(1,total);progress.value=done;
  const events=result.events?.length?result.events:attempts.flatMap(a=>(a.agents||[]).flatMap(agent=>(agent.trace||[]).map(e=>({...e,task:a.task,agent_id:agent.agent_id})))).slice(-200);
  document.getElementById('baseline-activity').textContent=events.length?events.map(e=>(e.task||'')+' '+(e.agent_id||'')+' '+e.type+': '+(e.content||'')).join('\n'):'Waiting for the model server to prepare a model or return its first response…';
  const latest=events.at(-1);detail.textContent='Viewing run '+id+' · '+(result.configs||[]).map(c=>c.name+': '+(c.agents||[]).map(a=>a.backend+' / '+a.model).join(', ')).join('; ')+(latest?' · Latest activity: '+(latest.content||latest.type):'')+(startedAt?' · '+Math.max(0,Math.floor((Date.now()-startedAt)/1000))+' seconds since launch':'');
  outcome.textContent=attempts.length?passed+' passed · '+failed+' failed / incomplete · '+Math.max(0,total-done)+' remaining. A finished attempt counts as a pass only when all required checks succeed.':'No attempts have finished yet. This does not mean the run is idle.';
  const lastFailure=attempts.filter(a=>!a.evaluation?.passed).at(-1);if(lastFailure)outcome.textContent+=' Latest failure: '+failureReason(lastFailure);
  showTable(result);showEvidence(result);
  if(result.status==='running'){
   announce(stopRequested?'stopping':'running',(stopRequested?'Stopping baseline tests · ':'Running baseline tests · ')+done+'/'+total+' attempts finished · '+passed+' passed · '+failed+' failed / incomplete');runButton.disabled=true;stopButton.disabled=stopRequested;document.getElementById('baseline-live-details').open=true;timer=setTimeout(poll,1500);
  }else{
   runButton.disabled=false;stopButton.disabled=true;
   if(result.status==='completed')announce(failed||passed<total?'failed':'passed','Run completed · '+done+'/'+total+' attempts processed · '+passed+' passed · '+failed+' failed / incomplete'+(passed===total&&total?' · All selected tests passed.':' · The baseline did not pass all selected tests.'));
   else announce('error','Run '+result.status+' · '+done+'/'+total+' attempts finished. Completed results are preserved below.');
   if(result.status==='needs_setup')window.playpenSecrets.open({agents:(result.configs||[]).flatMap(c=>c.agents||[])});
   showExports(result,id);history(false);
  }
 }catch(e){if(id!==job||requestVersion!==version)return;announce('error','Cannot retrieve run status: '+e.message+' Retrying automatically; the run may still be active.');timer=setTimeout(poll,3000);}
}
function viewRun(id){stopRequested=false;stopPolling();job=id;startedAt=null;remember(id);clearResults();announce('loading','Loading saved run results…');poll();}
runButton.addEventListener('click',async()=>{
 if(launching)return;launching=true;runButton.disabled=true;stopButton.disabled=true;
 stopRequested=false;stopPolling();job=null;startedAt=null;clearResults();announce('checking','Checking baseline setup…');detail.textContent='Your launch request has been received. Checking required APIs and configuration.';focusStatus();
 try{
  const tasks=window.playpenBaselineTasks.ids();if(!tasks.length)throw new Error('Select at least one baseline task.');
  const configs=JSON.parse(configInput.value);if(!Array.isArray(configs)||!configs.length)throw new Error('Enter a nonempty array of configurations.');
  if(!await window.playpenSecrets.preflight({agents:configs.flatMap(c=>c.agents||[])})){announce('needs_setup','Not started — required API setup needs attention.');detail.textContent='Complete setup in the API inventory, close it, then click Run baseline tests again. No experiment was launched.';return;}
  announce('starting','Starting baseline tests…');
  const result=await api('/api/benchmarks',{configs,tasks,repeats:Number(document.getElementById('baseline-repeats').value)});
  job=result.id;startedAt=Date.now();remember(job);stopButton.disabled=false;announce('running','Run accepted · preparing the selected models and tasks…');detail.textContent='Run '+job+' has started. Results appear as each attempt finishes.';document.getElementById('baseline-live-details').open=true;
  await poll();
 }catch(e){announce('error','Baseline launch failed: '+e.message);detail.textContent='No new run was confirmed. Check the message above before retrying.';}
 finally{launching=false;if(!job||!timer)runButton.disabled=false;}
});
stopButton.addEventListener('click',async()=>{try{stopRequested=true;stopButton.disabled=true;announce('stopping','Stop requested · waiting for the current attempt to finish or stop.');await api('/api/benchmarks/'+job+'/stop',{});await poll();}catch(e){announce('error',e.message);stopButton.disabled=false;}});
document.getElementById('single-preset').addEventListener('click',()=>presets(false));document.getElementById('team-preset').addEventListener('click',()=>presets(true));
async function history(autoOpen=true){
 try{const results=await api('/api/benchmarks');const list=document.getElementById('baseline-history-list');list.replaceChildren();
  for(const result of results){const date=new Date(result.created_at);const button=el('button',(Number.isNaN(date.valueOf())?result.created_at:date.toLocaleString())+' · '+result.status+' · '+result.completed+'/'+result.scheduled+' attempts'+(result.passed!==undefined?' · '+result.passed+' passed':''));button.type='button';button.addEventListener('click',()=>{if(launching)return;viewRun(result.id);focusStatus();});list.append(button);}
  if(!results.length)list.append(el('p','No saved baseline runs yet.'));
  if(autoOpen&&!job&&!launching&&results.length){const requested=new URLSearchParams(window.location.search).get('run');viewRun(results.find(r=>r.id===requested)?.id||results.find(r=>r.status==='running')?.id||results[0].id);}
 }catch(e){listHistoryError(e);}
}
function listHistoryError(e){document.getElementById('baseline-history-list').textContent='Could not load saved runs: '+e.message;}
document.getElementById('baseline-history').addEventListener('click',()=>history(true));history();
