const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM,VirtualConsole}=require(path.resolve('.test-tmp/ui-test/node_modules/jsdom'));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function wait(fn){for(let n=0;n<100;n++){if(fn())return;await sleep(10);}throw new Error('UI timed out');}
async function main(){
 const errors=[],requests=[];let release;
 const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));
 const dom=new JSDOM(fs.readFileSync('.test-tmp/baseline_scientific_calculator.html','utf8'),{url:'http://127.0.0.1:8765/scientific-calculator',runScripts:'dangerously',virtualConsole:vc,beforeParse(w){
  w.URL.createObjectURL=()=> 'blob:local-graph';w.URL.revokeObjectURL=()=>{};
  w.fetch=async(url,options={})=>{assert.equal(options.headers['X-Playpen-Token'],'test-session-token');
   if(url.endsWith('/status'))return {ok:true,json:async()=>({message:'Qalculate ready'})};
   if(url.endsWith('/plot.svg'))return {ok:true,blob:async()=>new w.Blob(['<svg/>'],{type:'image/svg+xml'})};
   const body=JSON.parse(options.body);requests.push(body);
   await new Promise(r=>{release=r;});
   if(body.expression==='1/0')return {ok:false,json:async()=>({error:{message:'Division by zero'}})};
   return {ok:true,json:async()=>body.operation==='plot'?{operation:'plot',plot_id:'a'.repeat(32),finite_samples:5,points:5,engine_version:'qalc test'}:{operation:'evaluate',result:'60 km/h',precision_digits:80,engine_version:'qalc test'}};
  };
 }});
 try{const w=dom.window,d=w.document,$=id=>d.getElementById(id);await wait(()=>$('engine').textContent==='Qalculate ready');
 $('calculator').dispatchEvent(new w.Event('submit',{cancelable:true}));await wait(()=>release);assert.equal($('run').disabled,true);assert.match($('status').textContent,/Running/);release();await wait(()=>!$('run').disabled);assert.equal($('result').textContent,'60 km/h');assert.match($('status').textContent,/Completed successfully/);
 $('operation').value='plot';$('operation').dispatchEvent(new w.Event('change'));assert.equal($('plot-options').hidden,false);$('expression').value='sin(x)';$('variables').value='{}';release=null;$('calculator').dispatchEvent(new w.Event('submit',{cancelable:true}));await wait(()=>release);assert.equal('mode' in requests[1],false);release();await wait(()=>!$('run').disabled);assert.equal($('plot').hidden,false);assert.equal($('downloads').children.length,3);assert.match($('status').textContent,/Graph completed/);
 $('operation').value='evaluate';$('expression').value='1/0';release=null;$('calculator').dispatchEvent(new w.Event('submit',{cancelable:true}));await wait(()=>release);release();await wait(()=>!$('run').disabled);assert.match($('status').textContent,/Failed: Division by zero/);assert.equal($('plot').hidden,true);
 assert.deepEqual(errors,[]);process.stdout.write('Scientific UI running/result/graph/download/error checks passed.\n');
 }finally{dom.window.close();}
}
main().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1;});
