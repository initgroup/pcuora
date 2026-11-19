const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const root=path.resolve(__dirname,'../..'),out=fs.mkdtempSync(path.join(os.tmpdir(),'session-ui-')),pause=ms=>new Promise(r=>setTimeout(r,ms));
const server=spawn(path.join(root,'.venv/Scripts/python.exe'),['-B',path.join(__dirname,'session_preview_server.py')],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
let serverErrors='';server.stderr.on('data',c=>serverErrors+=c);const url=new Promise((resolve,reject)=>{let s='';server.stdout.on('data',c=>{s+=c;const m=s.match(/CSV_QA_URL=(http:\/\/127\.0\.0\.1:\d+)/);if(m)resolve(m[1])});server.on('error',reject);server.on('exit',code=>reject(new Error('Fixture exit '+code+' '+serverErrors)))});
const profile=path.join(out,'profile'),browser=spawn('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});let ws;
(async()=>{const pf=path.join(profile,'DevToolsActivePort');for(let i=0;i<100&&!fs.existsSync(pf);i++)await pause(100);const port=fs.readFileSync(pf,'utf8').split('\n')[0],tabs=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();ws=new WebSocket(tabs.find(t=>t.type==='page').webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});let seq=0;const pending=new Map(),errors=[];ws.onmessage=e=>{const d=JSON.parse(e.data);if(d.method==='Runtime.exceptionThrown')errors.push(d.params.exceptionDetails.exception?.description||d.params.exceptionDetails.text);if(d.id){const p=pending.get(d.id);pending.delete(d.id);d.error?p.reject(d.error):p.resolve(d.result)}};const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))});const ev=async expression=>{const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});assert.ok(!r.exceptionDetails,JSON.stringify(r.exceptionDetails));return r.result.value};const until=async expression=>{for(let i=0;i<150;i++){if(await ev(expression))return;await pause(50)}throw new Error('Timed out '+expression+' '+JSON.stringify(errors)+' '+JSON.stringify(await ev('({status:document.getElementById("mission-csv-status").textContent,rows:document.querySelectorAll("#mission-csv-rows tbody tr").length,request:missionCsvRequest,key:missionCsvKey,open:document.getElementById("mission-csv-dialog").open,html:document.getElementById("mission-csv-rows").innerHTML.slice(0,100)})')))};const size=width=>call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});const shot=async name=>{const s=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(s.data,'base64'))};await call('Page.enable');await call('Runtime.enable');await call('Emulation.setFocusEmulationEnabled',{enabled:true});await call('Page.bringToFront');await size(1440);await call('Page.navigate',{url:(await url)+'/mission'});await until('typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"');assert.equal(await ev('assignmentState.ready'),false);assert.equal(await ev('document.querySelectorAll("[data-mission-preview]").length'),10);

assert.equal(await ev('document.getElementById("session-tools").hidden'),false);
assert.match(await ev('document.getElementById("session-remaining").textContent'),/^29:|^30:/);
const beforeReads=(await(await fetch((await url)+'/qa/state')).json()).reads;
await pause(1250);
assert.equal((await(await fetch((await url)+'/qa/state')).json()).reads,beforeReads,'Display timer must not keep session alive');
await ev('document.getElementById("extend-session").click()');
await until('!document.getElementById("extend-session").disabled');
assert.equal((await(await fetch((await url)+'/qa/state')).json()).extensions,1);
assert.match(await ev('document.getElementById("session-remaining").textContent'),/^30:00|^29:59/);
for(const width of [1440,768,390,320]){
  await size(width);
  assert.ok(await ev('document.documentElement.scrollWidth<=innerWidth'),'Page overflow '+width);
  assert.ok(await ev('(()=>{const t=document.getElementById("session-tools").getBoundingClientRect();return t.left>=0&&t.right<=innerWidth})()'),'Session controls overflow '+width);
  if(width===1440||width===390)await shot('header-'+width);
}
await fetch((await url)+'/qa/expire');
await ev('sessionDeadline=Date.now()-10;sessionLastCheck=0;renderSessionTime()');
await until('document.getElementById("session-expired-dialog").open');
assert.ok(await ev('document.getElementById("session-expired-description").textContent.includes("만료")'));
assert.equal(await ev('Boolean(document.getElementById("identity-dialog"))'),false);
assert.equal(await ev('location.pathname'),'/mission','Must show reason before navigation');
assert.equal(await ev('document.activeElement.id'),'session-expired-accept');
for(const width of [1440,390,320]){
  await size(width);
  assert.ok(await ev('(()=>{const d=document.getElementById("session-expired-dialog");return d.scrollWidth<=d.clientWidth+1&&d.getBoundingClientRect().right<=innerWidth})()'));
  if(width!==320)await shot('timeout-'+width);
}
await ev('document.getElementById("session-expired-accept").click()');
await until('location.pathname==="/"&&document.body.dataset.auth==="locked"&&typeof initialized!=="undefined"');
await pause(300);assert.equal(await ev('document.getElementById("session-expired-dialog").open'),false);
await fetch((await url)+'/qa/reset');await call('Page.navigate',{url:(await url)+'/mission'});
await until('typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"');
await fetch((await url)+'/qa/expire');
await ev('Promise.allSettled([api("/api/session/extend",{}),api("/api/session/extend",{})])');
assert.equal(await ev('document.querySelectorAll("#session-expired-dialog[open]").length'),1);
assert.equal(await ev('Boolean(document.getElementById("identity-dialog"))'),false);
await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
await until('location.pathname==="/"&&document.body.dataset.auth==="locked"');
assert.deepEqual(errors,[]);
console.log(JSON.stringify({ok:true,countdown:true,no_automatic_extension:true,manual_extension:true,timer_expiry:true,api_401_expiry:true,notice_before_navigation:true,acknowledge_and_escape:true,widths:[1440,768,390,320],out}));
})().catch(e=>{console.error(e);process.exitCode=1}).finally(()=>{ws?.close();browser.kill();server.kill()});
