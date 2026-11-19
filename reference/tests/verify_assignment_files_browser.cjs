// Isolated native file-picker regression; the fixture forbids real Oracle access.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const root=path.resolve(__dirname,'../..'),out=fs.mkdtempSync(path.join(os.tmpdir(),'assignment-files-ui-')),pause=ms=>new Promise(r=>setTimeout(r,ms));
const server=spawn(path.join(root,'.venv/Scripts/python.exe'),['-B',path.join(__dirname,'mission_csv_preview_server.py')],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
let serverErrors='';
server.stderr.on('data',c=>serverErrors+=c);
const url=new Promise((resolve,reject)=>{let s='';server.stdout.on('data',c=>{s+=c;const m=s.match(/CSV_QA_URL=(http:\/\/127\.0\.0\.1:\d+)/);if(m)resolve(m[1]);});server.on('error',reject);server.on('exit',code=>reject(new Error('Fixture exit '+code+' '+serverErrors)));});
const profile=path.join(out,'profile'),browser=spawn('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
const uploads=process.argv.includes('--upload');
let ws;
(async()=>{
 const pf=path.join(profile,'DevToolsActivePort');for(let i=0;i<120&&!fs.existsSync(pf);i++)await pause(100);
 const port=fs.readFileSync(pf,'utf8').split('\n')[0],tabs=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();
 ws=new WebSocket(tabs.find(t=>t.type==='page').webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});
 let seq=0;const pending=new Map(),errors=[],choosers=[],writes=[],layouts=[];
 ws.onmessage=e=>{const d=JSON.parse(e.data);
  if(d.method==='Runtime.exceptionThrown')errors.push(d.params.exceptionDetails.exception?.description||d.params.exceptionDetails.text);
  if(d.method==='Page.fileChooserOpened')choosers.push(d.params);
  if(d.method==='Network.requestWillBeSent'&&d.params.request.method==='POST')writes.push(new URL(d.params.request.url).pathname);
  if(d.id){const p=pending.get(d.id);if(!p)return;pending.delete(d.id);d.error?p.reject(d.error):p.resolve(d.result);}
 };
 const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
 const ev=async expression=>{const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true,userGesture:true});assert.ok(!r.exceptionDetails,JSON.stringify(r.exceptionDetails));return r.result.value;};
 const until=async expression=>{for(let i=0;i<150;i++){if(await ev(expression))return;await pause(50);}throw new Error('Timed out '+expression+' '+JSON.stringify(errors)+' '+serverErrors);};
 const tab=async name=>ev('document.querySelector(".assignment-tabs [data-assignment-tab='+name+']").click()');
 const choose=async(id,file)=>{
  assert.equal(await ev('document.getElementById('+JSON.stringify(id)+').disabled'),false);
  const before=choosers.length;
  await ev('document.getElementById('+JSON.stringify(id)+').focus();document.getElementById('+JSON.stringify(id)+').click()');
  for(let i=0;i<80&&choosers.length===before;i++)await pause(25);
  assert.equal(choosers.length,before+1,'Click must open native file chooser for '+id);
  await call('DOM.setFileInputFiles',{files:[path.join(root,file)],backendNodeId:choosers.at(-1).backendNodeId});
  await until('document.getElementById('+JSON.stringify(id)+').files.length===1');
  const state=id+'-state';
  assert.ok((await ev('document.getElementById('+JSON.stringify(state)+').textContent')).includes(path.basename(file)));
  assert.ok((await ev('document.getElementById('+JSON.stringify(state)+').textContent')).includes('파일 선택 완료'));
 };
 await call('Page.enable');await call('Runtime.enable');await call('Network.enable');
 await call('Page.setInterceptFileChooserDialog',{enabled:true});
 await call('Emulation.setFocusEmulationEnabled',{enabled:true});
 await call('Page.bringToFront');
 for(const assignment of ['mission','creative']){
  await fetch((await url)+'/qa/upload',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:false})});
  await call('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false});
  await call('Page.navigate',{url:(await url)+'/'+assignment});
  await until('typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"');
  assert.equal(await ev('assignmentState.ready'),false,'Fixture must keep objects uncreated');
  if(assignment==='mission')await ev("selectMissionDataset('ott')");
  await tab('data');await choose('assignment-file','data/examples/ott.csv');
  if(uploads){
   assert.equal(await ev('document.getElementById("assignment-import").disabled'),true,'Missing target table blocks upload');
   await fetch((await url)+'/qa/upload',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:true})});
   if(assignment==='mission')await ev('api("/api/assignments/mission/selection",{key:"ott"})');
   await ev('loadAssignmentReadiness()');
   assert.equal(await ev('assignmentState.ready'),false,'Missing RUN must not prevent CSV upload');
   assert.equal(await ev('document.getElementById("assignment-import").disabled'),false,'File + target table enables upload');
   const count=writes.filter(p=>p.endsWith('/csv')).length;
   await ev('document.getElementById("assignment-import").click()');
   await until('document.getElementById("confirm-dialog").open');
   await ev('document.getElementById("cancel-confirm").click()');
   await until('!assignmentBusy');
   assert.equal(writes.filter(p=>p.endsWith('/csv')).length,count,'Cancel sends no upload');
   await ev('document.getElementById("assignment-import").click()');
   await until('document.getElementById("confirm-dialog").open');
   assert.ok(await ev('document.getElementById("confirm-dialog").textContent.includes("ott.csv")'));
   await ev('document.getElementById("accept-confirm").click()');
   await until('!assignmentBusy&&document.getElementById("assignment-file-state").textContent.includes("1,500행 적재 완료")');
   assert.equal(writes.filter(p=>p.endsWith('/csv')).length,count+1);
   await ev('document.getElementById("assignment-data-refresh").click()');
   await until('document.querySelectorAll("#assignment-data tbody tr").length===1');
  }
  await ev("assignmentPhase='error';renderAssignmentControls()");
  assert.equal(await ev('document.getElementById("assignment-file").disabled'),false,'DB readiness failure must not block local selection');
  await ev("assignmentPhase='ready';assignmentBusy=true;renderAssignmentControls()");
  assert.equal(await ev('document.getElementById("assignment-file").disabled'),true,'Busy guard');
  await ev('assignmentBusy=false;renderAssignmentControls()');
  await tab('predictions');await choose('assignment-prediction-file','data/examples/ott_prediction.csv');
  if(uploads){
   assert.equal(await ev('document.getElementById("assignment-prediction-import").disabled'),false);
   await ev('document.getElementById("assignment-prediction-import").click()');
   await until('document.getElementById("confirm-dialog").open');
   await ev('document.getElementById("accept-confirm").click()');
   await until('!assignmentBusy&&document.getElementById("assignment-prediction-file-state").textContent.includes("30행 적재 완료")');
   if(assignment==='mission'){
    const flow=await ev('api("/api/coding-help?assignment=mission&operation=import&variant=RAW")');
    assert.equal(flow.flow.mode,'web-execution');
    assert.ok(Object.values(flow.flow.files).some(f=>f.path==='app.py'&&f.content.includes('async def assignment_csv')));
    assert.ok(Object.values(flow.flow.files).some(f=>f.path==='static/js/assignment-template.js'&&f.content.includes('async function importAssignmentCsv')));
   }
  }
  assert.ok(await ev('Array.from(document.querySelectorAll("[data-manual-action]")).every(b=>b.disabled)'),'Manual database actions stay manual');
  if(assignment==='creative')assert.equal(await ev('document.querySelectorAll("[data-code]").length'),0,'Creative must not receive SQL guides');
  for(const width of [1440,390,320]){
   await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});
   for(const pane of ['data','predictions']){
    await tab(pane);
    const result=await ev('({width:innerWidth,scroll:document.documentElement.scrollWidth,disabled:document.getElementById("'+(pane==='data'?'assignment-file':'assignment-prediction-file')+'").disabled})');
    assert.ok(result.scroll<=width+1,JSON.stringify({assignment,pane,...result}));assert.equal(result.disabled,false);
    layouts.push({assignment,pane,...result});
    if(width!==320){const shot=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(out,assignment+'-'+pane+'-'+width+'.png'),Buffer.from(shot.data,'base64'));}
   }
  }
  if(assignment==='mission'){
   await ev("selectMissionDataset('esports')");
   assert.equal(await ev('document.getElementById("assignment-file").files.length+document.getElementById("assignment-prediction-file").files.length'),0,'New mission clears old files');
   await tab('data');await choose('assignment-file','data/examples/esports.csv');
   await ev('document.getElementById("assignment-file").value="";document.getElementById("assignment-file").dispatchEvent(new Event("change",{bubbles:true}))');
   await until('document.getElementById("assignment-file-state").textContent==="선택한 파일이 없습니다."');
  }
  await ev('person=null;renderPerson()');
  assert.equal(await ev('document.getElementById("assignment-file").disabled&&document.getElementById("assignment-prediction-file").disabled'),true);
  assert.equal(await ev('document.getElementById("assignment-file").files.length+document.getElementById("assignment-prediction-file").files.length'),0,'Logout clears both files');
 }
 const csvWrites=writes.filter(p=>p.endsWith('/csv'));
 if(uploads)assert.equal(csvWrites.length,4,'One confirmed training and prediction upload per assignment');
 else assert.deepEqual(writes,[],'File selection must not upload or modify database data');
 assert.deepEqual(errors,[]);
 const report={ok:true,assignments:2,native_file_choosers:choosers.length,objects_uncreated:true,db_error_selection:true,busy_auth_guards:true,mission_change_clears_files:true,file_clear_updates_name:true,uploads,confirmed_csv_uploads:csvWrites.length,requests:writes,real_database:false,layouts,screenshots:out};
 fs.writeFileSync(path.join(root,uploads?'runtime/assignment-upload-browser-verification.json':'runtime/assignment-files-browser-verification.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify({ok:true,assignments:2,native_file_choosers:choosers.length,layout_checks:layouts.length,uploads,confirmed_csv_uploads:csvWrites.length,real_database:false,screenshots:out}));
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>{ws?.close();browser.kill();server.kill();});
