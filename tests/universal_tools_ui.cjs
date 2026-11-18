const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM,VirtualConsole}=require(path.resolve('.test-tmp/ui-test/node_modules/jsdom'));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function wait(fn){for(let n=0;n<150;n++){if(fn())return;await sleep(10);}throw new Error('UI condition timed out');}
async function main(){let release;const errors=[],calls=[];const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));
 const spec={name:'calculator',description:'Calculate <img src=x>',inputSchema:{type:'object',properties:{expression:{type:'string'}},required:['expression']},readiness:{status:'configured_unverified'},source:'fixture',version:'1',replay_safe:true};
 const record={execution_id:'a'.repeat(32),tool:'calculator',status:'succeeded',ok:true,result:'42 <script>bad()</script>',duration_ms:2,arguments_redacted:false};
 const dom=new JSDOM(fs.readFileSync('.test-tmp/baseline_tools.html','utf8'),{url:'http://127.0.0.1:8765/tools',runScripts:'dangerously',virtualConsole:vc,beforeParse(w){w.fetch=async(url,options={})=>{assert.equal(options.headers['X-Playpen-Token'],'test-session-token');calls.push(url);let value;
 if(url==='/api/tool-gateway')value={gateway_version:'uacp-tools-v1',tools:[spec],history:[]};
 else if(url==='/api/tool-gateway/call'){await new Promise(r=>{release=r;});value=record;}
 else if(url.includes('/replay/'))value={...record,replay_of:record.execution_id};
 else if(url.endsWith('/mcp/connect'))value={connected:['fixture'],errors:{}};
 else throw new Error('Unexpected route '+url);
 return {ok:true,json:async()=>value};};}});
 try{const w=dom.window,d=w.document,$=id=>d.getElementById(id);await wait(()=>$('tool').options.length===1);assert.match($('status').textContent,/1 tools registered/);assert.equal(d.querySelectorAll('#description img').length,0);assert.equal(JSON.parse($('arguments').value).expression,'6*7');
 $('call').dispatchEvent(new w.Event('submit',{cancelable:true}));await wait(()=>release);assert.equal($('run').disabled,true);assert.match($('status').textContent,/Running/);release();await wait(()=>!$('run').disabled);assert.match($('result').textContent,/42 <script>/);assert.equal(d.querySelectorAll('#result script').length,0);assert.equal($('replay').disabled,false);
 $('replay').click();await wait(()=>$('result').textContent.includes('replay_of'));$('connect').click();await wait(()=>$('status').textContent.includes('connected'));assert.deepEqual(errors,[]);process.stdout.write('Universal tool UI catalog, schema, acknowledgement, verified result, replay, connection and escaping checks passed.\n');}finally{dom.window.close();}}
 main().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1;});
