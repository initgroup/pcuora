// Isolated flow UI verification. Synthetic identity only; all real DB access is forbidden.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const workspaceFlowOnly=process.argv.includes('--workspace-flow-only'),runtimeOnly=process.argv.includes('--runtime-only'),schemaOnly=process.argv.includes('--schema-only'),evidenceOnly=process.argv.includes('--evidence-only'),selectionOnly=process.argv.includes('--selection-only'),comparisonOnly=process.argv.includes('--comparison-only')||process.argv.includes('--assignment-comparison-only'),lifecycleOnly=process.argv.includes('--lifecycle-only'),guidanceOnly=process.argv.includes('--guidance-only'),contextOnly=process.argv.includes('--context-only'),importOnly=process.argv.includes('--import-only'),layoutOnly=process.argv.includes('--layout-only'),allButtons=process.argv.includes('--all-buttons');
const taskMarkersOnly=process.argv.includes('--task-markers-only');
const root=path.resolve(__dirname,'../..'),out=fs.mkdtempSync(path.join(os.tmpdir(),'coding-flow-ui-')),pause=ms=>new Promise(r=>setTimeout(r,ms));
const server=spawn(path.join(root,'.venv/Scripts/python.exe'),['-B',path.join(__dirname,'workspace_visual_preview_server.py')],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
let serverErrors='';server.stderr.on('data',c=>serverErrors+=c);
const basePromise=new Promise((resolve,reject)=>{let buffer='';server.stdout.on('data',c=>{buffer+=c;const match=buffer.match(/VISUAL_QA_URL=(http:\/\/127\.0\.0\.1:\d+)/);if(match)resolve(match[1])});server.on('error',reject);server.on('exit',code=>reject(new Error('Fixture exited '+code+' '+serverErrors)))});
const profile=path.join(out,'profile'),browser=spawn('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
let ws,call;const errors=[],requests=[],views=[],cases=[],sourcePaths=new Set(),sourceRanges=new Set(),verifiedItems=new Set();let checkedItems=0,generatedSqlChecks=0;
(async()=>{
 const portFile=path.join(profile,'DevToolsActivePort');for(let i=0;i<150&&!fs.existsSync(portFile);i++)await pause(100);
 const port=fs.readFileSync(portFile,'utf8').split('\n')[0],tabs=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();
 ws=new WebSocket(tabs.find(tab=>tab.type==='page').webSocketDebuggerUrl);await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject});
 let seq=0;const pending=new Map();
 ws.onmessage=event=>{const r=JSON.parse(event.data);if(r.method==='Runtime.exceptionThrown')errors.push(r.params.exceptionDetails.exception?.description||r.params.exceptionDetails.text);if(r.method==='Network.requestWillBeSent'&&new URL(r.params.request.url).pathname.startsWith('/api/'))requests.push({url:r.params.request.url,method:r.params.request.method});if(r.id){const p=pending.get(r.id);if(!p)return;pending.delete(r.id);r.error?p.reject(r.error):p.resolve(r.result)}};
 call=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;const timer=setTimeout(()=>{pending.delete(id);reject(new Error('CDP command timeout: '+method))},20000);pending.set(id,{resolve:value=>{clearTimeout(timer);resolve(value)},reject:error=>{clearTimeout(timer);reject(error)}});ws.send(JSON.stringify({id,method,params}))});
 const ev=async expression=>{const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});assert.ok(!r.exceptionDetails,JSON.stringify(r.exceptionDetails));return r.result.value};
 const until=async expression=>{for(let i=0;i<180;i++){if(await ev(expression))return;await pause(50)}throw new Error('Timed out '+expression+' '+JSON.stringify(errors)+' '+serverErrors)};
 const click=selector=>ev('(()=>{const e=document.querySelector('+JSON.stringify(selector)+');if(!e)throw new Error("Missing selector: "+'+JSON.stringify(selector)+');e.closest("details")?.setAttribute("open","");e.focus();e.click();})()');
 const size=width=>call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});
 const shot=async name=>{await ev('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');const r=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(r.data,'base64'))};
 const layout=async(label,width,font=16)=>{await size(width);await ev('fontSize('+font+');document.getElementById("execution-dialog").scrollTop=0');await ev('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');const box=await ev('(()=>{const d=document.getElementById("execution-dialog"),r=d.getBoundingClientRect();return{document:document.documentElement.scrollWidth,width:innerWidth,left:r.left,right:r.right,top:r.top,bottom:r.bottom,scroll:d.scrollWidth,client:d.clientWidth,codeTop:document.getElementById("execution-code").getBoundingClientRect().top}})()');assert.ok(box.document<=width+1&&box.left>=-1&&box.right<=width+1&&box.top>=-1&&box.bottom<=901&&box.scroll<=box.client+1,'Flow overflow '+label+' '+width+' '+font+' '+JSON.stringify(box));if(width===1440&&font===16)assert.ok(box.bottom-box.codeTop>=100,'Initial fold must show code lines '+JSON.stringify(box));views.push({label,width,font,...box});await shot(label+'-'+width+'-'+font)};
 const inspectGuidance=async(label)=>{
   const app=await ev('qaApplication');
   assert.equal(await ev('document.getElementById("execution-apply").open'),false);
   assert.equal(await ev('document.querySelectorAll("#execution-apply details[open]").length'),0);
   assert.equal(await ev('document.querySelectorAll("#execution-apply-steps>li").length'),3);
   assert.equal(await ev('document.getElementById("execution-apply-summary").textContent'),app.summary);
   assert.ok((await ev('document.getElementById("execution-apply-owner").textContent')).includes(app.owner));
   assert.equal(await ev('document.getElementById("execution-find")'),null);
   await ev('document.querySelector("#execution-apply>summary").click()');
   assert.equal(await ev('document.getElementById("execution-apply").open'),true);
   const widths=label.endsWith('initial-train')||label==='mission-import'?[1440,390,320]:[1440];
   for(const width of widths){
     await size(width);await ev('fontSize('+ (width===320?22:16) +')');
     await ev('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
     await ev('(()=>{const dialog=document.getElementById("execution-dialog"),area=document.getElementById("execution-apply");dialog.scrollTop+=area.getBoundingClientRect().top-dialog.getBoundingClientRect().top-dialog.querySelector(".dialog-top").getBoundingClientRect().height-16})()');
     const boxes=await ev('(()=>{const d=document.getElementById("execution-dialog");return{width:innerWidth,scroll:d.scrollWidth,client:d.clientWidth,rows:[...document.querySelectorAll("#execution-apply-steps>li")].map(e=>({top:e.getBoundingClientRect().top,left:e.getBoundingClientRect().left,right:e.getBoundingClientRect().right}))}})()');
     assert.ok(boxes.scroll<=boxes.client+1,JSON.stringify(boxes));
     if(width===1440)assert.ok(Math.max(...boxes.rows.map(r=>r.top))-Math.min(...boxes.rows.map(r=>r.top))<1);
     else assert.ok(boxes.rows[1].top>boxes.rows[0].top&&boxes.rows.every(r=>r.left>=0&&r.right<=width));
     views.push({label,width});await shot(label+'-guidance-'+width);
   }
   if(app.command){
     await ev('document.querySelector("#execution-apply-command>summary").click()');
     assert.equal(await ev('document.getElementById("execution-apply-command").open'),true);
     assert.equal(await ev('document.querySelector("#execution-apply-command code").textContent'),app.command);
     assert.equal(await ev('document.getElementById("execution-command-title").textContent'),app.command_title);
   }
   if(app.verification){
     await ev('document.querySelector("#execution-verify-code summary").click()');
     assert.equal(await ev('document.querySelector("#execution-verify-code details").open'),true);
     assert.equal(await ev('document.querySelector("#execution-verify-code pre").textContent'),app.verification);
   }
   await ev('fontSize(16)');await size(1440);
   cases.push({label,guidance:true,steps:3});return;
 };
 const inspectFlow=async(label)=>{
   await until('window.qaFlow&&document.getElementById("execution-flow").querySelectorAll("[data-flow-stage]").length===6');
   if(guidanceOnly)return inspectGuidance(label);
   const flow=await ev('qaFlow');
   assert.equal(flow.version,2);
   for(const stage of flow.stages)for(const item of stage.items){
     assert.equal(item.content,undefined,'Do not repeat file content in navigation items');
     const file=flow.files[item.file_id];
     item.content=item.origin==='source'?file.content.split('\n').slice(item.line-1,item.end_line).join('\n'):file.content;
   }
   await ev('if(!window.qaPaintHook){window.qaPaintHook=true;window.qaPaints=0;const original=CodeHighlight.paint;CodeHighlight.paint=(...args)=>{window.qaPaints++;return original(...args)}}');
   for(const stage of flow.stages)for(const item of stage.items){if(item.origin==='source'){sourcePaths.add(item.path);sourceRanges.add(item.path+':'+item.line+'-'+item.end_line)}else if(item.origin==='generated')generatedSqlChecks++}
   assert.deepEqual(await ev('Array.from(document.querySelectorAll("#execution-flow [data-flow-stage]"),e=>e.dataset.flowStage)'),['ui','event','api','service','database','sql']);
   assert.equal(await ev('document.querySelectorAll("[data-code-tab],[data-code-panel]").length'),0,'Legacy tabs removed');
   assert.equal(await ev('document.querySelector("#execution-flow [aria-pressed=true]").dataset.flowStage'),'ui','Flow opens at clicked UI source');
   if(label.endsWith('initial-train'))await layout(label+'-ui',1440);
   await click('#execution-flow [data-flow-stage="ui"]');
   await call('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39});
   await call('Input.dispatchKeyEvent',{type:'keyUp',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39});
   assert.equal(await ev('document.querySelector("#execution-flow [aria-pressed=true]").dataset.flowStage'),'event','Flow keyboard navigation');
   for(const stage of flow.stages){
     if(contextOnly&&stage.id!=='sql')continue;
     await click('#execution-flow [data-flow-stage="'+stage.id+'"]');
     assert.equal(await ev('document.querySelector("#execution-flow [aria-pressed=true]").dataset.flowStage'),stage.id,'Stage active state');
     if(!stage.items.length){assert.ok(await ev('document.getElementById("execution-source-panel").hidden'),'Empty stage explains absence without stale code');continue}
     assert.deepEqual(await ev('Array.from(document.querySelectorAll("#execution-items [data-flow-item]"),e=>e.dataset.flowItem)'),[...new Set(stage.items.map(item=>item.file_id))].flatMap(id=>stage.items.filter(item=>item.file_id===id).map(item=>item.id)));
     assert.equal(await ev('document.querySelectorAll("#execution-items .coding-file-group").length'),new Set(stage.items.map(item=>item.file_id)).size,'One file group per unique file');
     for(const item of stage.items){
       if(contextOnly&&!(item.path==='sql/classifier.sql'&&item.title.startsWith('실행 ')))continue;
       if(allButtons){const key=JSON.stringify([item.path,item.line,item.end_line,item.content]);if(verifiedItems.has(key))continue;verifiedItems.add(key);}
       if(importOnly)console.log(JSON.stringify({item:item.id,stage:stage.id,length:item.content.length,phase:'select'}));
       const before=await ev('({file:document.getElementById("execution-code").dataset.fileId,paints:qaPaints})');
       await click('#execution-items [data-flow-item="'+item.id+'"]');
       await ev('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
       assert.equal(await ev('qaPaints'),before.paints+(before.file===item.file_id?0:1),'Same file navigates without repaint; different file replaces content');
       assert.equal(await ev('document.querySelector("#execution-items [aria-pressed=true]").dataset.flowItem'),item.id,'Item active state');
       assert.equal(await ev('document.getElementById("execution-code").textContent'),flow.files[item.file_id].content,'Complete file text '+label+' '+item.id);
       if(item.origin==='source'){
         const visible=await ev('(()=>{const pre=document.getElementById("execution-code"),mark=pre.querySelector(".code-source-focus"),r=mark?.getClientRects()[0],box=pre.getBoundingClientRect();return !!r&&r.bottom>=box.top&&r.top<box.bottom})()');
         assert.ok(visible,'Selected source scrolls inside code viewer '+label+' '+item.id);
       }
       if(flow.files[item.file_id].content.length>64000)assert.ok(await ev('document.getElementById("execution-code").dataset.highlight==="plain"'),'Large files preserve plain text without token expansion');
       assert.ok((await ev('document.getElementById("execution-code-source").textContent')).includes(item.path),'Visible source path '+item.path);
       if(item.origin==='source')assert.ok((await ev('document.getElementById("execution-code-source").textContent')).includes(String(item.line)),'Visible original line');
       await click('#copy-execution');await until('window.qaCopied!==null');
       assert.equal(await ev('qaCopied'),item.content,'Copy selected source only');
       await ev('qaCopied=null');await click('#copy-execution-file');await until('window.qaCopied!==null');
       assert.equal(await ev('qaCopied'),flow.files[item.file_id].content,'Copy full file preserves all context');
       await ev('qaCopied=null');checkedItems++;
       if(importOnly)console.log(JSON.stringify({item:item.id,phase:'verified'}));
     }
   }
   await click('#execution-flow [data-flow-stage="sql"]');
   if(flow.stages.at(-1).items.length){
     assert.equal(await ev('document.querySelector("#execution-flow [data-flow-stage=sql]").dataset.flowKind'),'sql');
     const colors=await ev('["ui","sql"].map(id=>{const s=getComputedStyle(document.querySelector("#execution-flow [data-flow-stage="+id+"]"));return[s.backgroundColor,s.backgroundImage,s.borderTopColor].join("|")})');
     assert.notEqual(colors[0],colors[1],'SQL stage uses a distinct visual treatment');
   }
   if(label==='basic-initial-train'){
     const target=flow.stages.at(-1).items.find(item=>item.path==='sql/classifier.sql'&&item.title.includes('실행 3'));
     assert.ok(target);
     await click('#execution-items [data-flow-item="'+target.id+'"]');
     await ev('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
     assert.ok(await ev('document.getElementById("execution-code").scrollTop>100'),'Classifier navigates to selected lines in the complete file');
     await layout('classifier-file-context',1440);
     // Collapse a different file and verify keyboard navigation stays in visible file sections.
     await ev('document.querySelector("#execution-items .coding-file-group").open=false');
     await click('#execution-items [data-flow-item="'+target.id+'"]');
     await call('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowDown',code:'ArrowDown',windowsVirtualKeyCode:40});
     await call('Input.dispatchKeyEvent',{type:'keyUp',key:'ArrowDown',code:'ArrowDown',windowsVirtualKeyCode:40});
     assert.ok(await ev('document.activeElement.matches("[data-flow-item]")&&document.activeElement.getClientRects().length>0'),'Keyboard selects only visible file items');
   }
   cases.push({label,mode:flow.mode,stages:flow.stages.length,items:flow.stages.reduce((n,s)=>n+s.items.length,0)});
 };
 await call('Page.enable');await call('Runtime.enable');await call('Network.enable');await call('Emulation.setFocusEmulationEnabled',{enabled:true});await size(1440);
 const base=await basePromise;
 if(process.argv.includes('--manual-actions-only')){
   for(const assignment of ['mission','creative']){
     await call('Page.navigate',{url:base+'/'+assignment});await until('typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"&&!assignmentBusy');
     await click('.assignment-tabs [data-assignment-tab=models]');
     for(const mode of ['RAW','CLEAN']){
       await ev('setWorkMode("assignment-mode","'+mode+'");assignmentState.models.find(m=>m.variant==="'+mode+'").exists=0;renderAssignmentControls()');
       assert.deepEqual(await ev('["initial","retrain","delete-model"].map(id=>document.getElementById("assignment-"+id).disabled)'),[false,true,true]);
       await click('#assignment-initial');await until('document.getElementById("execution-dialog").open&&executionStage?.id==="sql"');
       assert.ok(await ev('!document.getElementById("execution-manual-note").hidden&&document.getElementById("execution-manual-note").textContent.includes(person.db_user)'));
       assert.equal(await ev('executionItem.id'),await ev('executionStage.items[0].id'));
       const sql=await ev('flowItemContent(executionItem)');
       assert.ok(sql.includes('OML_'+assignment.toUpperCase()+"_RUN('INIT', '"+mode+"'"));
       assert.ok(sql.includes('CURRENT_SCHEMA')&&sql.includes('PRINT result'));
       await ev('window.manualCopied=null;navigator.clipboard.writeText=async value=>{window.manualCopied=value}');
       await click('#copy-execution');assert.equal(await ev('manualCopied'),sql);
       if(mode==='RAW')for(const width of [1440,390,320]){await layout(assignment+'-manual',width,width===320?22:16);}
       await size(1440);await ev('fontSize(16)');await click('#close-execution');
       await ev('assignmentState.models.find(m=>m.variant==="'+mode+'").exists=1;renderAssignmentControls()');
       assert.deepEqual(await ev('["initial","retrain","delete-model"].map(id=>document.getElementById("assignment-"+id).disabled)'),[true,false,false]);
       for(const [id,action] of [['retrain','RETRAIN'],['delete-model','DELETE']]){
         await click('#assignment-'+id);await until('executionStage?.id==="sql"&&document.getElementById("execution-dialog").open');
         assert.ok((await ev('flowItemContent(executionItem)')).includes("_RUN('"+action+"', '"+mode+"'"));await click('#close-execution');
       }
       await ev('assignmentState.preparation.'+mode+'.ready=false;renderAssignmentControls()');
       assert.deepEqual(await ev('["initial","retrain","delete-model"].map(id=>document.getElementById("assignment-"+id).disabled)'),[true,true,false]);
       await ev('assignmentState.preparation.'+mode+'.ready=true;assignmentState.preparation.'+mode+'.fit_rows=0;renderAssignmentControls()');
       assert.equal(await ev('document.getElementById("assignment-retrain").disabled'),true);
       await ev('assignmentState.preparation.'+mode+'.fit_rows=330;renderAssignmentControls()');
     }
     await click('#assignment-retrain + .code-help');await until('executionStage?.id==="ui"&&document.getElementById("execution-dialog").open');
     assert.equal(await ev('document.getElementById("execution-manual-note").hidden'),true);await click('#close-execution');
     await click('.assignment-tabs [data-assignment-tab=data]');
     await click('#assignment-prepare');await until('executionStage?.id==="sql"&&document.getElementById("execution-dialog").open');
     assert.ok((await ev('flowItemContent(executionItem)')).includes("_RUN('PREPARE'"));await click('#close-execution');
     await ev('assignmentState.state.total_rows=0;renderAssignmentControls()');assert.equal(await ev('document.getElementById("assignment-prepare").disabled'),true);
     await ev('assignmentBusy=true;renderAssignmentControls()');assert.equal(await ev('document.getElementById("assignment-delete-model").disabled'),true);
     await ev('assignmentBusy=false;assignmentState.ready=false;renderAssignmentControls()');assert.equal(await ev('document.getElementById("assignment-initial").disabled'),true);
     if(assignment==='mission'){
       await ev('assignmentState.ready=true;missionSelectionCurrent="";renderAssignmentControls()');
       assert.ok(await ev('[...document.querySelectorAll("[data-manual-action]")].every(button=>button.disabled)'));
     }
     await ev('clearCodingHelp()');assert.equal(await ev('document.getElementById("execution-manual-note").hidden'),true);
   }
   const qa=await(await fetch(base+'/qa/state')).json();assert.deepEqual(qa.blocked,[]);assert.deepEqual(qa.mutations,[]);assert.deepEqual(errors,[]);
   const report={ok:true,assignments:2,modes:2,manual_buttons_open_sql:true,help_buttons_open_flow:true,availability_matches_basic:true,exact_copy:true,no_db_execution:true,layouts:views.length,screenshots:out};
   fs.writeFileSync(path.join(root,'runtime/manual-actions-verification.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));return;
 }
 if(process.argv.includes('--feedback-layout-only')){
   await call('Page.navigate',{url:base+'/basic'});await until('document.body.dataset.auth==="ready"&&!refreshing&&!activeTasks');
   const checks=[];
   for(const [width,font] of [[1440,16],[390,16],[320,22]]){
     await size(width);await ev('fontSize('+font+');document.body.dataset.auth="checking";document.getElementById("auth-check").hidden=false');
     const auth=await ev('(()=>{const r=document.querySelector("#auth-check>div").getBoundingClientRect();return {left:r.left,right:r.right,document:document.documentElement.scrollWidth,width:innerWidth}})()');
     assert.ok(auth.left>=-1&&auth.right<=width+1&&auth.document<=width+1,JSON.stringify(auth));
     await shot('auth-check-'+width);
     await ev('document.body.dataset.auth="ready";document.getElementById("auth-check").hidden=true;window.qaProgress=RequestProgress.begin("CSV 파일을 전송하고 DB에 적재하고 있습니다.");void 0');
     await until('!document.getElementById("request-progress").hidden');
     const progress=await ev('(()=>{const r=document.getElementById("request-progress").getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:innerWidth,document:document.documentElement.scrollWidth}})()');
     assert.ok(progress.left>=-1&&progress.right<=width+1&&progress.document<=width+1&&progress.top>=0&&progress.bottom<=900,JSON.stringify(progress));
     await shot('request-progress-'+width);await ev('RequestProgress.end(qaProgress)');
     checks.push({width,font,auth,progress});
   }
   await call('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
   assert.equal(await ev('getComputedStyle(document.querySelector(".loading-track>span")).animationName'),'none');
   assert.deepEqual(errors,[]);
   fs.writeFileSync(path.join(root,'runtime/feedback-layout-verification.json'),JSON.stringify({ok:true,checks,reduced_motion:true,screenshots:out},null,2));
   console.log(JSON.stringify({ok:true,layouts:checks.length,reduced_motion:true,screenshots:out}));return;
 }
 if(process.argv.includes('--feedback-only')){
   const configure=async data=>fetch(base+'/qa/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
   await configure({session_delay:.8,authenticated:true,session_failure:false});
   await call('Page.addScriptToEvaluateOnNewDocument',{source:'window.authFrames=[];function observeAuth(){const b=document.body,g=document.querySelector(".login-gate");if(b&&g&&authFrames.length<600)authFrames.push({state:b.dataset.auth,gate:!g.hidden&&getComputedStyle(g).display!=="none",workspace:getComputedStyle(document.querySelector(".workspace")).display!=="none"});requestAnimationFrame(observeAuth)}requestAnimationFrame(observeAuth);'});
   const transitions=[];
   for(const [index,route] of ['/basic','/mission','/creative','/'].entries()){
     if(index===0)await call('Page.navigate',{url:base+route});else await click('.sidebar nav a[href="'+route+'"]');
     await until('document.body.dataset.auth==="checking"&&document.getElementById("auth-check")');
     assert.equal(await ev('document.querySelector(".login-gate").hidden'),true);
     assert.equal(await ev('getComputedStyle(document.querySelector(".workspace")).display'),'none');
     if(index===0)await shot('checking-without-intro');
     await until('document.body.dataset.auth==="ready"&&typeof person!=="undefined"&&person');
     await until('!refreshing&&!activeTasks');
     const frames=await ev('authFrames');
     assert.ok(frames.some(f=>f.state==='checking'));
     assert.ok(frames.every(f=>!f.gate),'No intro frame during authenticated menu navigation');
     assert.ok(frames.filter(f=>f.state==='checking').every(f=>!f.workspace),'No protected UI before session validation');
     transitions.push({route,sampled_frames:frames.length});
   }
   await configure({session_failure:true});
   await call('Page.navigate',{url:base+'/mission'});await until('!document.getElementById("auth-check-retry").hidden');
   assert.equal(await ev('document.body.dataset.auth'),'checking');
   assert.equal(await ev('document.querySelector(".login-gate").hidden'),true,'Network failure is not logout');
   assert.equal(await ev('document.querySelector("#auth-check .loading-track").hidden'),true);
   await configure({session_failure:false,session_delay:.1});await click('#auth-check-retry');
   await until('document.body.dataset.auth==="ready"&&!activeTasks&&!refreshing');
   await configure({authenticated:false,session_delay:.5});
   await call('Page.navigate',{url:base+'/'});await until('document.body.dataset.auth==="locked"');
   assert.equal(await ev('document.querySelector(".login-gate").hidden'),false,'Confirmed guest sees the intro');
   await configure({authenticated:true,session_delay:0,work_delay_path:'/api/data/import',work_delay:.9,work_failure:false});
   await fetch(base+'/qa/lifecycle');
   await call('Page.navigate',{url:base+'/basic#data'});await until('document.body.dataset.auth==="ready"&&!refreshing&&!activeTasks');
   await ev('selectedFile=new File(["case_id,return_pct\\n1,1"],"loading-fixture.csv",{type:"text/csv"});renderStorage()');
   await click('#replace-training');await until('document.getElementById("confirm-dialog").open');
   assert.equal(await ev('document.getElementById("request-progress").hidden'),true,'Confirmation is not executing');
   await click('#accept-confirm');
   const position=await ev('({x:scrollX,y:scrollY})');
   await until('!document.getElementById("request-progress").hidden');
   assert.ok((await ev('document.getElementById("request-progress-label").textContent')).includes('CSV'));
   assert.equal(await ev('document.querySelector("#request-progress [role=progressbar]").hasAttribute("aria-valuenow")'),false,'No invented percentage');
   assert.deepEqual(await ev('({x:scrollX,y:scrollY})'),position,'Progress does not move scroll');
   await shot('csv-upload-progress');await pause(250);
   assert.equal(await ev('document.getElementById("request-progress").hidden'),false,'Progress persists while request is outstanding');
   await until('!importing&&!activeTasks&&document.getElementById("request-progress").hidden');
   assert.equal(await ev('document.getElementById("operation-status").hidden'),false);
   await until('document.getElementById("operation-status").hidden');
   await configure({work_failure:true,work_delay:.35});
   await click('#replace-training');await until('document.getElementById("confirm-dialog").open');await click('#accept-confirm');
   await until('!importing&&!activeTasks&&document.getElementById("operation-status").dataset.state==="error"');
   assert.equal(await ev('document.getElementById("request-progress").hidden'),true,'Failed work cleans up progress');
   await pause(4700);assert.equal(await ev('document.getElementById("operation-status").hidden'),false,'Errors do not auto-dismiss');
   await ev('dismissMessage();notice("정상 완료 · 마우스로 읽는 중")');
   const toast=await ev('(()=>{const r=document.getElementById("operation-status").getBoundingClientRect();return {x:r.left+15,y:r.top+15}})()');
   await call('Input.dispatchMouseEvent',{type:'mouseMoved',x:toast.x,y:toast.y});
   await pause(4700);assert.equal(await ev('document.getElementById("operation-status").hidden'),false,'Hover pauses dismissal');
   await call('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0});await until('document.getElementById("operation-status").hidden');
   await ev('notice("정상 완료 · 키보드로 읽는 중");document.getElementById("operation-status-close").focus({preventScroll:true})');
   await pause(4700);assert.equal(await ev('document.getElementById("operation-status").hidden'),false,'Focus pauses dismissal');
   await ev('document.getElementById("refresh").focus({preventScroll:true})');
   await until('document.getElementById("operation-status").hidden');
   assert.equal(await ev('document.activeElement.id'),'refresh','Automatic dismissal does not move focus');
   await ev('RequestProgress.begin("진행 중 화면 이탈 검증");window.dispatchEvent(new Event("pagehide"))');
   assert.equal(await ev('document.getElementById("request-progress").hidden'),true);
   const qa=await(await fetch(base+'/qa/state')).json();assert.deepEqual(qa.blocked,[]);assert.deepEqual(errors,[]);
   const report={ok:true,real_database:false,transitions,network_failure_keeps_checking:true,guest_intro_only_after_verification:true,real_request_progress:true,error_cleanup:true,normal_auto_dismiss:true,errors_persist:true,hover_and_focus_pause:true,focus_and_scroll_preserved:true,screenshots:out};
   fs.writeFileSync(path.join(root,'runtime/feedback-ui-verification.json'),JSON.stringify(report,null,2));
   console.log(JSON.stringify(report));return;
 }
 if(process.argv.includes('--preparation-link-only')){
   await fetch(base+'/qa/preparation-link');
   const reports=[];
   for(const key of ['mission','creative']){
     await call('Page.navigate',{url:base+'/'+key});
     await until('typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"&&!activeTasks&&practiceEvidenceResult');
     assert.equal(await ev('practiceEvidenceResult.steps[1].completed'),2);
     assert.deepEqual(await ev('[...document.querySelectorAll(".assignment-link-panel>button")].map(e=>({id:e.id,label:e.textContent}))'),['assignment-check','assignment-prepared-link','assignment-model-link','assignment-prediction-link'].map(id=>({id,label:'SQL 실행 결과 연계'})));
     await click('[data-assignment-tab=data]');await until('!document.getElementById("assignment-panel-data").hidden&&!assignmentBusy');
     for(const mode of ['RAW','CLEAN']){
       await ev('setWorkMode("assignment-preparation-mode","'+mode+'");renderAssignmentControls()');
       const status=await ev('document.getElementById("assignment-prepared-status").textContent');
       assert.ok(status.includes('1,500행')&&status.includes('TEST 300행')&&status.includes('DB 데이터 있음')&&status.includes('웹 연계 확인 필요'),status);
       await click('#assignment-prepared-data');await until('!assignmentBusy&&!activeTasks');
       assert.ok(await ev('document.querySelectorAll("#assignment-prepared-rows tbody tr").length>0'));
       assert.equal(await ev('assignmentState.preparation.'+mode+'.ready'),false,'Querying rows must not create a successful link');
     }
     const before=requests.filter(r=>r.url.endsWith('/link')&&r.method==='POST').length;
     await click('#assignment-prepared-link');await until('document.getElementById("confirm-dialog").open');
     assert.ok(await ev('document.getElementById("confirm-dialog").textContent.includes("전처리·학습을 다시 실행하지 않습니다")'));
     await click('#cancel-confirm');await until('!document.getElementById("confirm-dialog").open');
     assert.equal(requests.filter(r=>r.url.endsWith('/link')&&r.method==='POST').length,before,'Cancellation makes no linkage request');
     await click('#assignment-prepared-link');await until('document.getElementById("confirm-dialog").open');
     await click('#accept-confirm');await until('!assignmentBusy&&!activeTasks&&assignmentState.preparation.CLEAN.ready');
     assert.equal(requests.filter(r=>r.url.endsWith('/link')&&r.method==='POST').length,before+1,'Confirmed action uses existing link API exactly once');
     assert.ok((await ev('document.getElementById("assignment-prepared-link-status").textContent')).includes('웹 연계 완료'));
     assert.equal(await ev('practiceEvidenceResult.steps[1].completed'),4,'Confirmed linking refreshes final evidence in the same status response without visiting home');
     for(const [width,font] of [[1440,16],[390,16],[320,22]]){
       await size(width);await ev('fontSize('+font+');document.getElementById("assignment-prepared-link").closest(".assignment-link-panel").scrollIntoView({block:"center"})');
       const box=await ev('(()=>{const r=document.getElementById("assignment-prepared-link").closest(".assignment-link-panel").getBoundingClientRect();return {width:innerWidth,document:document.documentElement.scrollWidth,left:r.left,right:r.right}})()');
       assert.ok(box.document<=width+1&&box.left>=-1&&box.right<=width+1,JSON.stringify(box));
       await shot('preparation-link-'+key+'-'+width);
     }
     await size(1440);await ev('fontSize(16)');await click('[data-assignment-tab=home]');
     await until('!activeTasks&&practiceEvidenceResult?.steps[1].completed===4');
     assert.equal(await ev('practiceEvidenceResult.steps[1].success'),true);
     for(const [tab,id] of [['home','assignment-check'],['models','assignment-model-link'],['predictions','assignment-prediction-link']]){
       await click('[data-assignment-tab='+tab+']');await until('!activeTasks&&!assignmentBusy&&assignmentPhase==="ready"');
       const count=requests.filter(r=>r.url.endsWith('/link')&&r.method==='POST').length;
       await click('#'+id);await until('document.getElementById("confirm-dialog").open');
       await click('#accept-confirm');await until('!assignmentBusy&&!activeTasks');
       assert.equal(requests.filter(r=>r.url.endsWith('/link')&&r.method==='POST').length,count+1,'Every tab links exactly once after confirmation');
       assert.equal(await ev('document.getElementById("assignment-panel-'+tab+'").hidden'),false,'Linking preserves the active tab');
       assert.equal(await ev('practiceEvidenceResult.steps[1].completed'),4);
     }
     if(key==='creative')assert.equal(await ev('document.querySelectorAll("[data-code]").length'),8,'Creative exposes only manual action help');
     reports.push({assignment:key,before:2,after:4,data_already_existed:true,no_prepare_or_train:true});
   }
   const qa=await(await fetch(base+'/qa/state')).json();
   assert.deepEqual(qa.mutations,[...Array(4).fill('/api/assignments/mission/link'),...Array(4).fill('/api/assignments/creative/link')]);
   assert.deepEqual(qa.blocked,[]);assert.deepEqual(errors,[]);
   fs.writeFileSync(path.join(root,'runtime/preparation-link-ui-verification.json'),JSON.stringify({ok:true,synthetic_data_only:true,real_database:false,reports,screenshots:out},null,2));
   console.log(JSON.stringify({ok:true,readable_but_unlinked_reproduced:true,cancel_and_confirm:true,counts_correct_after_link:true,assignments:2,layouts:6,screenshots:out}));return;
 }
 if(workspaceFlowOnly){
   await fetch(base+'/qa/evidence');
   const styleSignatures=[];
   for(const assignment of ['basic','mission','creative']){
     await call('Page.navigate',{url:base+'/'+assignment});
     await until(assignment==='basic'?'typeof statusPhase!=="undefined"&&statusPhase==="ready"&&!refreshing':'typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"&&!assignmentBusy');
     const tab=async name=>{await click(assignment==='basic'?'#basic-workflow [data-basic-tab='+name+']':'.assignment-tabs [data-assignment-tab='+name+']');await until(assignment==='basic'?'page==="'+name+'"&&!refreshing&&!activeTasks':'document.getElementById("assignment-panel-'+name+'").hidden===false&&!assignmentBusy&&!activeTasks')};
     await tab('data');
     assert.deepEqual(await ev('[...document.querySelectorAll("[data-learning-stage]")].map(e=>e.dataset.learningStage)'),['csv','original','prepared']);
     assert.equal(await ev('document.querySelector("[data-learning-stage=original]").open'),true);
     const query=assignment==='basic'?'query-data':'assignment-data-refresh',raw=assignment==='basic'?'data-table':'assignment-data',prep=assignment==='basic'?'query-prepared-data':'assignment-prepared-data';
     assert.equal(await ev('document.getElementById("'+query+'").textContent'),'원본 데이터 조회');
     assert.equal(await ev('document.getElementById("'+prep+'").textContent'),'전처리 데이터 조회');
     assert.ok(await ev('!!(document.getElementById("'+query+'").compareDocumentPosition(document.getElementById("'+raw+'"))&Node.DOCUMENT_POSITION_FOLLOWING)'));
     assert.equal(await ev('document.querySelector("[data-learning-stage=csv] #'+query+'")'),null,'Raw query belongs beside its result, not the upload actions');
     assert.ok(await ev('document.querySelector("[data-learning-stage=prepared]").contains(document.getElementById("'+prep+'"))'));
     styleSignatures.push(await ev('(()=>{const a=getComputedStyle(document.querySelector("[data-learning-stage=csv]")),b=getComputedStyle(document.querySelector(".learning-step-heading h3"));return[a.backgroundColor,a.borderRadius,a.padding,b.fontSize,b.color]})()'));
     for(const [width,font] of [[1440,16],[768,16],[390,16],[320,22]]){
       await size(width);await ev('fontSize('+font+');document.querySelector(".data-workbench").scrollIntoView({block:"start"})');
       const boxes=await ev('(()=>{const stages=[...document.querySelectorAll("[data-learning-stage]")].map(e=>{const r=e.getBoundingClientRect();return {key:e.dataset.learningStage,left:r.left,right:r.right,top:r.top,bottom:r.bottom}});return {width:innerWidth,scroll:document.documentElement.scrollWidth,stages}})()');
       assert.ok(boxes.scroll<=width+1,JSON.stringify(boxes));assert.ok(boxes.stages.every((e,i)=>e.left>=-1&&e.right<=width+1&&(!i||e.top>=boxes.stages[i-1].bottom)),JSON.stringify(boxes));
       views.push({assignment,width,font,...boxes});if(width===1440||width===390)await shot('workflow-'+assignment+'-data-'+width);
     }
     await size(1440);await ev('fontSize(16)');
     await tab('predictions');
     assert.deepEqual(await ev('[...document.querySelectorAll("[data-prediction-stage]")].map(e=>e.dataset.predictionStage)'),['csv','original','predict','result']);
     assert.ok(await ev('document.querySelector("[data-prediction-stage=original]").open'));
     assert.equal(await ev('document.querySelector("[data-prediction-stage=original] summary h3").textContent'),'예측 입력 확인','Count updates preserve shared heading');
     await shot('workflow-'+assignment+'-prediction');
     await tab('models');assert.equal(await ev('document.querySelector(".model-workbench").className'),'panel model-workbench');
     await tab('home');
     await fetch(base+'/qa/evidence/change?kind=proof_missing_run&value=1');await click('#practice-verify');await until('!practiceEvidenceBusy&&practiceEvidenceResult');
     assert.equal(await ev('practiceEvidenceResult.steps[0].completed'),3);assert.equal(await ev('practiceEvidenceResult.steps[0].remaining'),1);
     assert.match(await ev('document.querySelector("[data-proof-step=home]").textContent'),/성공 3개 · 대기 1개/);
     let before=requests.length;await click('[data-proof-step=home]');await until('document.getElementById("practice-detail-dialog").open');
     assert.equal(requests.length,before,'Opening detail uses current verification result without another DB/API request');
     assert.equal(await ev('document.querySelectorAll("#practice-detail-groups li[data-state=success]").length'),3);
     assert.equal(await ev('document.querySelectorAll("#practice-detail-groups li[data-state=pending]").length'),1);
     assert.ok((await ev('document.querySelector("#practice-detail-groups li[data-state=pending]").textContent')).includes('RUN'));
     await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});await until('!document.getElementById("practice-detail-dialog").open');
     assert.ok(await ev('document.activeElement.matches("[data-proof-step=home]")'),'ESC returns focus to originating status');
     await fetch(base+'/qa/evidence/change?kind=proof_missing_run&value=0');await fetch(base+'/qa/evidence/change?kind=proof_clean_pending&value=1');
     await click('#practice-verify');await until('!practiceEvidenceBusy&&practiceEvidenceResult');
     assert.equal(await ev('practiceEvidenceResult.steps[1].completed'),3);assert.equal(await ev('practiceEvidenceResult.steps[1].total'),4);
     await click('[data-proof-step=data]');await until('document.getElementById("practice-detail-dialog").open');
     assert.equal(await ev('document.querySelectorAll("#practice-detail-groups li[data-state=success]").length'),3);
     assert.ok((await ev('document.querySelector("#practice-detail-groups li[data-state=pending]").textContent')).includes('CLEAN'));
     for(const [width,font] of [[1440,16],[390,22],[320,22]]){
       await size(width);await ev('fontSize('+font+')');await ev('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');
       const box=await ev('(()=>{const d=document.getElementById("practice-detail-dialog"),r=d.getBoundingClientRect();return {width:innerWidth,document:document.documentElement.scrollWidth,left:r.left,right:r.right,scroll:d.scrollWidth,client:d.clientWidth}})()');
       assert.ok(box.document<=width+1&&box.left>=-1&&box.right<=width+1&&box.scroll<=box.client+1,JSON.stringify(box));
       await shot('workflow-'+assignment+'-detail-'+width);
     }
     await size(1440);await ev('fontSize(16)');await click('#practice-detail-go');await until('!document.getElementById("practice-detail-dialog").open');
     assert.ok(await ev(assignment==='basic'?'page==="data"':'!document.getElementById("assignment-panel-data").hidden'));
     await until('document.activeElement.matches('+JSON.stringify(assignment==='basic'?'[data-basic-tab=data]':'[data-assignment-tab=data]')+')');
     await tab('home');await click('#practice-seal');await until('document.getElementById("practice-detail-dialog").open');
     assert.equal(await ev('document.querySelectorAll("#practice-detail-groups .practice-check-group").length'),4);
     assert.equal(await ev('document.querySelectorAll("#practice-detail-groups li").length'),await ev('practiceEvidenceResult.steps.flatMap(s=>s.checks).length'));
     await ev('person=null;++sessionGeneration;clearPracticeEvidence("로그인 후 확인하세요.")');
     assert.equal(await ev('document.getElementById("practice-detail-dialog").open'),false);
     assert.equal(await ev('document.getElementById("practice-detail-groups").children.length'),0,'Logout clears old detailed account facts');
     await fetch(base+'/qa/evidence/change?kind=proof_clean_pending&value=0');
   }
   assert.deepEqual(styleSignatures[0],styleSignatures[1]);assert.deepEqual(styleSignatures[0],styleSignatures[2]);
   const qa=await(await fetch(base+'/qa/state')).json();assert.deepEqual(qa.blocked,[]);assert.deepEqual(errors,[]);
   const report={ok:true,synthetic_data_only:true,real_database_access:false,assignments:3,shared_layout:true,raw_before_prepared:true,prediction_input_before_execution:true,partial_checklists:true,no_extra_request_for_details:true,focus_and_logout_cleanup:true,views,screenshots:out};
   fs.writeFileSync(path.join(root,'runtime/workspace-flow-verification.json'),JSON.stringify(report,null,2));
   console.log(JSON.stringify({ok:true,assignments:3,layout_checks:views.length,partial_work_details:true,screenshots:out}));return;
 }
 if(runtimeOnly){
   await fetch(base+'/qa/runtime');
   for(const assignment of ['basic','mission']){
     await call('Page.navigate',{url:base+'/'+assignment});
     await until(assignment==='basic'?'typeof statusPhase!=="undefined"&&statusPhase==="ready"&&!refreshing':'typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"&&!assignmentBusy');
     if(assignment==='basic'){await click('#basic-workflow [data-basic-tab=data]');await until('page==="data"&&!refreshing')}else{await ev('selectMissionDataset("ott")');await fetch(base+'/api/assignments/mission/selection',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:'ott'})});await click('.assignment-tabs [data-assignment-tab=data]');}
     await until('!activeTasks');
     await ev('codingQueryTraces.clear();++codingTraceVersion;Object.defineProperty(navigator,"clipboard",{configurable:true,value:{writeText:async text=>{window.qaCopied=text}}});window.qaCopied=null');
     const group=assignment==='basic'?'preparation-mode':'assignment-preparation-mode',filter=assignment==='basic'?'prepared-source-kind':'assignment-prepared-source-kind';
     await ev('setWorkMode("'+group+'","RAW");document.getElementById("'+filter+'").value="TRAIN"');
     const open=async()=>{
       const start=requests.length;await click('[data-code=prepared-data]');await until('document.getElementById("execution-dialog").open&&executionFlow&&document.getElementById("execution-flow").querySelectorAll("[data-flow-stage]").length===6');
       assert.ok(requests.slice(start).every(r=>new URL(r.url).pathname==='/api/coding-help'&&r.method==='GET'),'Opening runtime help must never query/execute DB');
       await click('[data-flow-stage=sql]');
     };
     const close=async()=>{await click('#close-execution');await until('!document.getElementById("execution-dialog").open')};
     await open();
     const before=await ev('executionStage.items.map(i=>({id:i.id,kind:i.runtime_kind,path:i.source_path}))');
     assert.equal(before.filter(i=>i.kind==='executed').length,0,'No fake last execution before query');
     const selected=before.find(i=>i.kind==='selected'&&i.path==='sql/queries/prepared_rows.sql');assert.ok(selected);
     await click('[data-flow-item="'+selected.id+'"]');
     let script=await ev('document.getElementById("execution-code").textContent');
     assert.ok(script.includes('STUDENT_QA.OML_'+assignment.toUpperCase()+'_PREPARED')&&script.includes("PREP_MODE = 'RAW'")&&script.includes("SOURCE_KIND = 'TRAIN'"));
     assert.ok(!script.includes('{{table}}')&&!script.includes(':variant')&&!script.includes(':source_kind'));
     assert.match(await ev('document.getElementById("execution-source-kind").textContent'),/現在|현재 선택값.*미실행/);
     await click('#copy-execution-file');assert.equal(await ev('qaCopied'),script,'Runtime SQL copy includes complete F5 account guard');
     const original=await ev('executionStage.items.find(i=>i.origin==="source"&&i.path==="sql/queries/prepared_rows.sql").id');
     await click('[data-flow-item="'+original+'"]');await click('#copy-execution-file');
     assert.equal(await ev('qaCopied'),fs.readFileSync(path.join(root,'sql/queries/prepared_rows.sql'),'utf8'),'Original source copy is unchanged');
     await close();
     const request=assignment==='basic'?'api("/api/data/prepared?variant=RAW&source_kind=TRAIN")':'api("/api/assignments/mission/prepared-data",{variant:"RAW",source_kind:"TRAIN"})';
     await ev('('+request+').then(result=>window.qaRuntimeResult=result)');
     assert.equal(await ev('[...codingQueryTraces.values()].filter(e=>e.records.length).length'),1);
     await open();
     const actual=await ev('executionStage.items.find(i=>i.runtime_kind==="executed")');assert.ok(actual);
     await click('[data-flow-item="'+actual.id+'"]');script=await ev('document.getElementById("execution-code").textContent');
     assert.ok(script.includes(await ev('qaRuntimeResult.trace[0].rendered_sql')),'Actual recorded statement is not rewritten');
     assert.ok(script.includes('2026-11-19T09:30:00+00:00'));
     assert.match(await ev('document.getElementById("execution-source-kind").textContent'),/마지막 실제 조회/);
     await click('#copy-execution');assert.equal(await ev('qaCopied'),script);
     await close();
     await ev('document.getElementById("'+filter+'").value="TEST"');
     await open();
     assert.equal(await ev('executionStage.items.filter(i=>i.runtime_kind==="executed").length'),0,'Changing filter excludes previous execution');
     const next=await ev('executionStage.items.find(i=>i.runtime_kind==="selected"&&i.source_path==="sql/queries/prepared_rows.sql").id');
     await click('[data-flow-item="'+next+'"]');assert.ok((await ev('document.getElementById("execution-code").textContent')).includes("SOURCE_KIND = 'TEST'"));
     for(const width of [1440,768,390,320])await layout(assignment+'-runtime-sql',width);
     await layout(assignment+'-runtime-sql',390,22);await ev('fontSize(16)');await size(1440);
     await close();
     // Newer request wins, errors and CSV batches cannot masquerade as successful query source.
     const args=assignment==='basic'?'"/api/data/prepared?variant=RAW&source_kind=TRAIN"':'"/api/assignments/mission/prepared-data",{variant:"RAW",source_kind:"TRAIN"}';
     await ev('(()=>{codingQueryTraces.clear();const old=captureCodingQuery('+args+'),latest=captureCodingQuery('+args+');rememberCodingQuery(old,qaRuntimeResult);window.qaOldTraceCount=[...codingQueryTraces.values()].flatMap(e=>e.records).length;rememberCodingQuery(latest,qaRuntimeResult)})()');
     assert.equal(await ev('qaOldTraceCount'),0);
     assert.equal(await ev('[...codingQueryTraces.values()].flatMap(e=>e.records).length'),1);
     await ev('(()=>{const context=captureCodingQuery('+args+');rememberCodingQuery(context,{trace:qaRuntimeResult.trace.map(t=>({...t,batch_count:500}))})})()');
     assert.equal(await ev('[...codingQueryTraces.values()].flatMap(e=>e.records).length'),0,'No CSV row bindings in trace viewer');
     await ev('(()=>{const context=captureCodingQuery('+args+');rememberCodingQuery(context,{trace:qaRuntimeResult.trace.map(t=>({...t,status:"error"}))})})()');
     assert.equal(await ev('[...codingQueryTraces.values()].flatMap(e=>e.records).length'),0);
     await ev('(()=>{const context=captureCodingQuery('+args+');rememberCodingQuery(context,qaRuntimeResult);clearCodingHelp();rememberCodingQuery(context,qaRuntimeResult)})()');
     assert.equal(await ev('codingQueryTraces.size'),0,'Session clear revokes cache and pending old responses');
     await ev('(()=>{for(const variant of ["RAW","CLEAN"])for(const source_kind of ["ALL","TRAIN","TEST","PREDICT"])captureCodingQuery("/api/data/prepared?"+new URLSearchParams({variant,source_kind}));captureCodingQuery("/api/data?use_yn=Y&split=TEST")})()');
     assert.equal(await ev('codingQueryTraces.size'),8,'Query history has a fixed context cap');
     await ev('(()=>{const context=captureCodingQuery('+args+');captureCodingQuery("/api/data/import",new FormData());rememberCodingQuery(context,qaRuntimeResult)})()');
     assert.equal(await ev('codingQueryTraces.size'),0,'Data mutation revokes pending reads');

   }
   await call('Page.navigate',{url:base+'/creative'});await until('typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"&&!assignmentBusy');
   assert.equal(await ev('document.querySelectorAll("[data-code],[data-execution]").length'),8);
   const qa=await(await fetch(base+'/qa/state')).json();assert.deepEqual(qa.blocked,[]);assert.deepEqual(errors,[]);
   const report={ok:true,synthetic_data_only:true,real_database_access:false,assignments:2,original_and_runtime_copy:true,actual_trace_filtering:true,stale_and_session_guard:true,no_csv_row_expansion:true,views,screenshots:out};
   fs.writeFileSync(path.join(root,'runtime/runtime-sql-browser-verification.json'),JSON.stringify(report,null,2));
   console.log(JSON.stringify({ok:true,assignments:2,layout_checks:views.length,screenshots:out}));return;
 }
 if(schemaOnly){
   await call('Page.navigate',{url:base+'/mission'});
   await until('typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"&&!activeTasks');
   await ev('Object.defineProperty(navigator,"clipboard",{configurable:true,value:{writeText:async text=>{window.qaCopied=text}}});window.qaCopied=""');
   const select=async key=>{
     await click('[data-mission-schema='+key+']');await until('document.getElementById("mission-schema-dialog").open&&missionSchemaSql.includes("CREATE TABLE")');
     assert.deepEqual(await ev('[...document.querySelectorAll("[data-mission-schema-kind]")].map(e=>e.dataset.missionSchemaKind)'),['training','prepared','prediction','procedure']);
     await click('[data-mission-schema-kind=procedure]');await until('missionSchemaSql.includes("CREATE OR REPLACE PROCEDURE")&&!document.getElementById("copy-mission-schema").disabled');
     const expected=await(await fetch(base+'/api/assignments/mission/schema?mission='+key+'&kind=procedure')).json();
     assert.equal(await ev('missionSchemaSql'),expected.sql);
     assert.ok(await ev('document.getElementById("mission-schema-ddl").open&&document.getElementById("mission-schema-columns").hidden&&document.getElementById("mission-schema-table-guide").hidden&&!document.getElementById("mission-schema-procedure-guide").hidden'));
     assert.equal(await ev('document.getElementById("mission-schema-object-label").textContent'),'프로시저명');
     assert.equal(await ev('document.querySelector("[data-mission-schema-kind=procedure]").getAttribute("aria-pressed")'),'true');
     await click('#copy-mission-schema');assert.equal(await ev('qaCopied'),expected.sql);
     return expected;
   };
   let result=await select('esports');assert.ok(result.sql.includes('TEAM_SCORE')&&!result.sql.includes('INTEREST_SCORE'));
   for(const width of [1440,768,390,320]){
     await size(width);await ev('fontSize('+(width===320?22:16)+');document.getElementById("mission-schema-dialog").scrollTop=0');
     const layout=await ev('(()=>{const d=document.getElementById("mission-schema-dialog");return {page:document.documentElement.scrollWidth,width:innerWidth,scroll:d.scrollWidth,client:d.clientWidth}})()');
     assert.ok(layout.page<=layout.width+1&&layout.scroll<=layout.client+1,JSON.stringify(layout));
     views.push({width,...layout});if(width===1440||width===320)await shot('mission-run-schema-'+width);
   }
   await size(1440);await ev('fontSize(16)');
   await click('#close-mission-schema');result=await select('festival');
   assert.ok(result.sql.includes('INTEREST_SCORE')&&!result.sql.includes('TEAM_SCORE'));
   // A late procedure response must not overwrite the selected table.
   await click('[data-mission-schema-kind=training]');await until('missionSchemaSql.includes("CREATE TABLE")');
   await ev('window.schemaOriginalApi=api;window.schemaDelayed=null;api=async(...args)=>{const result=await schemaOriginalApi(...args);if(args[0].includes("kind=procedure"))await new Promise(resolve=>window.schemaDelayed=resolve);return result}');
   await click('[data-mission-schema-kind=procedure]');await until('!!window.schemaDelayed');
   await click('[data-mission-schema-kind=training]');await until('missionSchemaSql.includes("CREATE TABLE")');
   await ev('window.schemaDelayed();api=schemaOriginalApi');await pause(100);
   assert.ok(await ev('missionSchemaKind==="training"&&missionSchemaSql.includes("CREATE TABLE")&&!document.getElementById("mission-schema-columns").hidden'));
   const qa=await(await fetch(base+'/qa/state')).json();assert.deepEqual(qa.mutations,[]);assert.deepEqual(qa.blocked,[]);assert.deepEqual(errors,[]);
   fs.writeFileSync(path.join(root,'runtime/mission-schema-run-verification.json'),JSON.stringify({ok:true,synthetic_data_only:true,real_database_access:false,tab_order:4,full_sql_copy:true,mission_specific:true,stale_response_guard:true,views,screenshots:out},null,2));
   console.log(JSON.stringify({ok:true,procedure_tab:true,exact_full_sql_copy:true,read_only:true,mission_switch_and_stale_response:true,layouts:views.length,screenshots:out}));return;
 }
 if(taskMarkersOnly){
   await fetch(base+'/qa/evidence');
   const snapshots=[];
   const tab=async(key,id)=>{
     await click(key==='basic'?'#basic-workflow [data-basic-tab="'+id+'"]':'.assignment-tabs [data-assignment-tab="'+id+'"]');
     await until(key==='basic'?'page==='+JSON.stringify(id)+'&&!refreshing&&!basicSwitching':'!document.getElementById("assignment-panel-'+id+'").hidden&&!assignmentBusy&&!activeTasks');
   };
   const snapshot=()=>ev('practiceEvidenceResult.steps.map(step=>({id:step.id,success:step.success,completed:step.completed,total:step.total,remaining:step.remaining,overview:document.querySelector("#practice-proof-steps [data-proof-step="+step.id+"]").textContent,header:document.querySelector("[data-practice-stage="+step.id+"] button").textContent,markers:[...document.querySelectorAll(".practice-task-marker[data-proof-step="+step.id+"]")].map(marker=>({index:Number(marker.dataset.proofCheck),state:marker.dataset.state,label:marker.querySelector("span").textContent,slot:marker.closest(".practice-task-anchor")?.querySelector("button:not(.code-help):not(.practice-task-marker),a")?.id||"group"}))}))');
   const checkSnapshot=async()=>{
     const steps=await snapshot();
     for(const step of steps){
       assert.equal(step.header,step.overview);assert.equal(step.markers.length,step.total,JSON.stringify(step));
       assert.deepEqual(step.markers.map(marker=>marker.index).sort((a,b)=>a-b),Array.from({length:step.total},(_,i)=>i));
       assert.equal(step.markers.filter(marker=>marker.state==='success').length,step.completed);
       assert.equal(step.markers.filter(marker=>marker.state==='pending').length,step.remaining);
     }
     assert.ok(await ev('practiceEvidenceResult.steps.every(step=>step.checks.every((check,index)=>{const marker=[...document.querySelectorAll(".practice-task-marker")].find(marker=>marker.dataset.proofStep===step.id&&Number(marker.dataset.proofCheck)===index);return marker.querySelector("span").textContent===check.label}))'));
     assert.ok(await ev('[...document.querySelectorAll(".mode-choice:not([data-mode-stage=predictions])")].every(group=>[...group.querySelectorAll(".mode-option")].every(button=>{const checks=practiceEvidenceResult.steps.find(step=>step.id===group.dataset.modeStage).checks.filter(check=>check.label.startsWith(button.value+" "));return (button.dataset.state==="success")===checks.every(check=>check.success)}))'));
     return steps;
   };
   for(const key of ['basic','mission','creative']){
     await fetch(base+'/qa/evidence/change?kind=proof_work_pending&value=1');await fetch(base+'/qa/evidence/change?kind=input_version&value=1');
     await call('Page.navigate',{url:base+'/'+key});
     await until(key==='basic'?'typeof statusPhase!=="undefined"&&statusPhase==="ready"&&!refreshing&&practiceEvidenceResult':'typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"&&!activeTasks&&practiceEvidenceResult');
     let steps=await checkSnapshot();
     assert.deepEqual(steps.find(step=>step.id==='data').markers.map(marker=>marker.state),['success','success','pending','pending']);
     assert.equal(steps.find(step=>step.id==='models').completed,0);
     assert.equal(steps.find(step=>step.id==='models').remaining,key==='basic'?6:5);
     assert.equal(steps.find(step=>step.id==='predictions').completed,1);assert.equal(steps.find(step=>step.id==='predictions').remaining,4);
     assert.equal(steps.find(step=>step.id==='data').markers.find(marker=>marker.index===0).slot,key==='basic'?'import-submit':'assignment-import');
     for(const id of ['data','models','predictions']){
       await tab(key,id);steps=await checkSnapshot();
       const group=key==='basic'?{data:'preparation-mode',models:'model-lifecycle-mode',predictions:'prediction-model-select'}[id]:{data:'assignment-preparation-mode',models:'assignment-mode',predictions:'assignment-predict-mode'}[id];
       assert.equal(await ev('document.querySelectorAll(".mode-choice input[type=radio]").length'),0);
       const beforeMode=requests.length;
       await click('#'+group+' .mode-option[value=CLEAN]');await until('!activeTasks');
       assert.equal(await ev('selectedMode('+JSON.stringify(group)+')'),'CLEAN');
       assert.equal(await ev('document.querySelectorAll("#'+group+' [aria-pressed=true]").length'),1);
       if(id==='models')assert.ok((await ev('document.getElementById('+JSON.stringify(key==='basic'?'model-lifecycle-name':'assignment-model-name')+').textContent')).includes('CLEAN'));
       await click('#'+group+' .mode-option[value=RAW]');await until('!activeTasks');
       assert.ok(requests.slice(beforeMode).every(request=>request.method==='GET'||new URL(request.url).pathname.endsWith('/prepared-data')),'Mode cards only change the work target: '+JSON.stringify(requests.slice(beforeMode)));
       assert.ok(await ev('(()=>{const panel=document.getElementById('+JSON.stringify(key==='basic'?'basic-'+id:'assignment-panel-'+id)+'),before=panel.getBoundingClientRect().height,hosts=[...panel.querySelectorAll(".practice-task-markers")];const absolute=hosts.every(host=>getComputedStyle(host).position==="absolute");hosts.forEach(host=>host.hidden=true);const after=panel.getBoundingClientRect().height;hosts.forEach(host=>host.hidden=false);return absolute&&before===after})()'),'Task markers must occupy no layout height');
       for(const [width,font] of [[1440,16],[1280,22],[390,16],[320,22]]){
         await size(width);await ev('fontSize('+font+')');await ev('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
         const box=await ev('(()=>{const panel=document.getElementById('+JSON.stringify(key==='basic'?'basic-'+id:'assignment-panel-'+id)+'),header=panel.querySelector("[data-practice-stage]").getBoundingClientRect();return {width:innerWidth,scroll:document.documentElement.scrollWidth,left:header.left,right:header.right,overflow:[...panel.querySelectorAll(".practice-task-marker")].some(marker=>marker.getBoundingClientRect().right>innerWidth+1)}})()');
         assert.ok(box.scroll<=width+1&&box.left>=-1&&box.right<=width+1&&!box.overflow,JSON.stringify({key,id,font,...box}));views.push({key,id,font,...box});
         if(width===1440||width===320){await ev('document.getElementById('+JSON.stringify(key==='basic'?'basic-'+id:'assignment-panel-'+id)+').scrollIntoView()');await shot('task-markers-'+key+'-'+id+'-'+width)}
         const target='.practice-task-marker[data-proof-step='+id+']';
         if(id==='models')assert.ok(await ev('(()=>{for(const marker of document.querySelectorAll(".practice-task-marker[data-proof-step=models]")){marker.scrollIntoView({block:"center"});const r=marker.getBoundingClientRect(),hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);if(!marker.contains(hit))return false}return true})()'),'Every task marker must remain visible and clickable');
         const rect=await ev('(()=>{const marker=document.querySelector('+JSON.stringify(target)+');marker.scrollIntoView({block:"center"});const r=marker.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}})()');
         await call('Input.dispatchMouseEvent',{type:'mouseMoved',...rect});
         await until('document.querySelector(".practice-task-tooltip:popover-open")');
         const tip=await ev('(()=>{const marker=document.querySelector('+JSON.stringify(target)+'),tip=document.getElementById(marker.getAttribute("aria-describedby")),r=tip.getBoundingClientRect();return {color:getComputedStyle(marker).color,left:r.left,right:r.right,top:r.top,bottom:r.bottom,text:tip.textContent}})()');
         assert.equal(tip.color,'rgb(255, 255, 255)');assert.ok(tip.left>=0&&tip.right<=width&&tip.top>=0&&tip.bottom<=900,JSON.stringify(tip));
         if(width===320||width===1440)await shot('task-tooltip-'+key+'-'+id+'-'+width);
         await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'});await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape'});
         assert.equal(await ev('document.querySelector(".practice-task-tooltip:popover-open")'),null);
       }
       await size(1440);await ev('fontSize(16)');
     }
     await tab(key,'data');
     const marker='.practice-task-marker[data-proof-step=data][data-proof-check="3"]',before=requests.length;
     await click(marker);await until('document.getElementById("practice-detail-dialog").open');
     assert.equal(requests.length,before,'Clicking a criterion never executes or rereads DB work');
     assert.ok(await ev('document.querySelector("#practice-detail-groups li[data-focused=true]").textContent.includes("작업 4")&&document.querySelector("#practice-detail-groups li[data-focused=true]").textContent.includes("CLEAN")'));
     await click('#close-practice-detail');assert.ok(await ev('document.activeElement.matches('+JSON.stringify(marker)+')'));
     const help=key==='basic'?'#prepare-data + .code-help':'#assignment-prepare + .code-help';
     const helpRect=await ev('(()=>{const e=document.querySelector('+JSON.stringify(help)+');e.scrollIntoView({block:"center"});const r=e.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}})()');
     await call('Input.dispatchMouseEvent',{type:'mouseMoved',...helpRect});
     await call('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...helpRect});
     await call('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...helpRect});
     await until('document.getElementById("execution-dialog").open&&executionStage');
     await click('#close-execution');
     await tab(key,'models');
     const pointerClick=async selector=>{
       await ev('document.documentElement.style.scrollBehavior="auto";document.querySelector('+JSON.stringify(selector)+').scrollIntoView({block:"center",behavior:"instant"})');
       await ev('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
       const box=await ev('(()=>{const e=document.querySelector('+JSON.stringify(selector)+');e.scrollIntoView({block:"center"});const r=e.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}})()');
       await call('Input.dispatchMouseEvent',{type:'mouseMoved',...box});
       await call('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...box});
       await call('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...box});
     };
     for(const index of [0,2,4]){
       await pointerClick('.practice-task-marker[data-proof-step=models][data-proof-check="'+index+'"]');
       await until('document.getElementById("practice-detail-dialog").open');
       if(index===2){await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'});await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape'});}else await pointerClick('#close-practice-detail');
       const helpSelector=key==='basic'?'#model-initial + .code-help':'#assignment-initial + .code-help';
       await pointerClick(helpSelector);
       await until('document.getElementById("execution-dialog").open&&executionStage');
       await pointerClick('#close-execution');
     }
     await fetch(base+'/qa/evidence/change?kind=proof_work_pending&value=0');
     await click('#refresh');await until('!activeTasks&&!refreshing&&(typeof assignmentBusy==="undefined"||!assignmentBusy)&&practiceEvidenceResult');
     await tab(key,'models');
     if(key==='basic'){await click('#query-models');await until('!activeTasks&&practiceEvidenceResult');}
     else for(const mode of ['RAW','CLEAN']){
       await ev('setWorkMode("assignment-mode","'+mode+'");renderAssignmentControls()');
       await click('#assignment-evaluate');await until('!assignmentBusy&&!activeTasks&&practiceEvidenceResult');
       assert.ok(await ev('practiceEvidenceResult.steps.find(step=>step.id==="models").checks.find(check=>check.label==='+JSON.stringify(mode+' TEST 평가 성공')+').success'));
     }
     steps=await checkSnapshot();assert.equal(steps.find(step=>step.id==='models').remaining,0);
     await pointerClick('.practice-task-marker[data-proof-step=models][data-proof-check="0"]');
     await until('document.getElementById("practice-detail-dialog").open');
     assert.ok(await ev('document.getElementById("close-practice-detail").getBoundingClientRect().width>0&&!document.getElementById("practice-detail-dialog").closest("[hidden]")'));
     await pointerClick('#close-practice-detail');
     await pointerClick(key==='basic'?'#model-initial + .code-help':'#assignment-initial + .code-help');
     await until('document.getElementById("execution-dialog").open&&executionStage');await pointerClick('#close-execution');
     await call('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0});
     assert.ok(await ev('[...document.querySelectorAll(".practice-task-marker[data-state=success]")].every(marker=>getComputedStyle(marker).backgroundColor==="rgb(52, 88, 153)"&&getComputedStyle(marker).color==="rgb(255, 255, 255)")'),'Success markers are blue with white text on every surface');
     await tab(key,'predictions');await click(key==='basic'?'#run':'#assignment-predict');await until('document.getElementById("confirm-dialog").open');
     await click('#accept-confirm');await until('!activeTasks&&!predictionRunning&&(typeof assignmentBusy==="undefined"||!assignmentBusy)&&practiceEvidenceResult');
     steps=await checkSnapshot();assert.equal(steps.find(step=>step.id==='predictions').remaining,0,'Prediction criteria update in the active tab without a home visit');
     snapshots.push({key,steps});
     await fetch(base+'/qa/evidence/change?kind=input_version&value=2');await click('#refresh');await until('!activeTasks&&!refreshing&&(typeof assignmentBusy==="undefined"||!assignmentBusy)&&practiceEvidenceResult');
     steps=await checkSnapshot();assert.equal(steps.find(step=>step.id==='predictions').remaining,1);
     const rows=steps.find(step=>step.id==='predictions').markers;assert.equal(rows.find(marker=>marker.index===3).state,'pending');
     const idle=requests.length;await pause(250);assert.equal(requests.length,idle,'Markers never start DB polling');
     await ev('person=null;++sessionGeneration;clearPracticeEvidence("로그인 후 확인하세요.")');
     assert.ok(await ev('[...document.querySelectorAll("[data-practice-stage] button")].every(button=>button.disabled)&&!document.querySelector(".practice-task-marker")'));
   }
   const qa=await(await fetch(base+'/qa/state')).json();assert.deepEqual(qa.blocked,[]);assert.deepEqual(errors,[]);
   const report={ok:true,assignments:3,real_database_access:false,one_snapshot_for_overview_headers_and_actions:true,numbered_criteria:true,active_tab_updates:true,input_change_revocation:true,detail_without_requests:true,logout_cleanup:true,views,snapshots,screenshots:out};
   fs.writeFileSync(path.join(root,'runtime/practice-task-markers-verification.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({ok:true,assignments:3,layouts:views.length,screenshots:out}));return;
 }
 if(evidenceOnly){
   await fetch(base+'/qa/evidence');
   const tab=async(key,name)=>{
     await click(key==='basic'?'#basic-workflow [data-basic-tab="'+name+'"]':'.assignment-tabs [data-assignment-tab="'+name+'"]');
     await until(key==='basic'?'page==='+JSON.stringify(name)+'&&!refreshing&&!basicSwitching':'!document.getElementById("assignment-panel-'+name+'").hidden&&assignmentPhase==="ready"&&!activeTasks');
   };
   const proof=()=>ev('({state:document.getElementById("practice-proof").dataset.state,passed:document.querySelectorAll("#practice-proof-steps tr[data-state=success]").length,guide:!document.getElementById("practice-capture-guide").hidden,student:document.getElementById("practice-proof-student").textContent,topic:document.getElementById("practice-proof-topic").textContent})');
   const finishPrediction=async key=>{
     await click(key==='basic'?'#run':'#assignment-predict');await until('document.getElementById("confirm-dialog").open');
     await click('#accept-confirm');await until(key==='basic'?'!predictionRunning&&!activeTasks':'!assignmentBusy&&!activeTasks');
   };
   for(const key of ['basic','mission','creative']){
     await call('Page.navigate',{url:base+'/'+key});
     await until(key==='basic'?'typeof statusPhase!=="undefined"&&statusPhase==="ready"&&!refreshing':'typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"&&!activeTasks');
     assert.equal((await proof()).state,'pending');assert.equal((await proof()).guide,false);
     await tab(key,'models');
     if(key!=='basic'){
       for(const mode of ['RAW','CLEAN']){
         await ev('setWorkMode("assignment-mode","'+mode+'");renderAssignmentControls()');
         await click('#assignment-evaluate');await until('!assignmentBusy&&!activeTasks');
       }
     }
     await tab(key,'predictions');await finishPrediction(key);
     assert.ok(await ev('!document.getElementById('+JSON.stringify(key==='basic'?'prediction-proof-return':'assignment-proof-return')+').hidden'),'Verified result links directly to evidence');
     await tab(key,'home');
     await until('document.getElementById("practice-proof").dataset.state==="success"');
     const result=await proof();assert.equal(result.passed,4);assert.equal(result.guide,true);assert.ok(result.student.includes('QA2026'));
     const title={basic:'기본과제',mission:'미션과제',creative:'창의과제'}[key]+' 성공';
     assert.equal(await ev('document.querySelector("#practice-seal .practice-seal-label").textContent'),title);
     assert.equal(await ev('document.getElementById("practice-seal").getAttribute("aria-label")'),title+' · 세부 작업 보기');
     await click('#practice-seal');await until('document.getElementById("practice-detail-dialog").open');
     assert.equal(await ev('document.querySelectorAll("#practice-detail-groups .practice-check-group").length'),4);
     await click('#close-practice-detail');assert.ok(await ev('document.activeElement.id==="practice-seal"'));
     assert.deepEqual(await ev('[...document.querySelectorAll("#practice-proof-steps .practice-step-stamp")].map(e=>e.textContent)'),['✓ 오브젝트 생성 성공','✓ 학습자료 적재 성공','✓ 모델생성 평가 성공','✓ 모델예측 실행 성공']);
     assert.ok(await ev('document.getElementById("practice-proof-owner").textContent==="STUDENT_QA"'));
     assert.ok(await ev('document.getElementById("practice-proof-time").textContent!=="확인 전"'));
     if(key==='mission')assert.ok(result.topic.includes('캠퍼스 축제'));
     for(const [width,font] of [[1440,16],[1280,22],[390,16],[320,22]]){
       await size(width);await ev('fontSize('+font+');document.getElementById("practice-proof").scrollIntoView({block:"start"})');
       const box=await ev('(()=>{const e=document.getElementById("practice-proof");return {width:document.documentElement.scrollWidth,inner:innerWidth,height:e.getBoundingClientRect().height,overflow:getComputedStyle(e).overflowY}})()');
       assert.ok(box.width<=box.inner+1,JSON.stringify(box));assert.ok(!['auto','scroll'].includes(box.overflow));
       if(width===1440)assert.ok(box.height<700,'Capture card fits a desktop view: '+JSON.stringify(box));
       views.push({key,width,font,...box});if(width===1440||width===320)await shot('proof-'+key+'-'+width);
     }
     await size(1440);await ev('fontSize(16)');
     await call('Page.reload');await until('typeof person!=="undefined"&&person&&document.getElementById("practice-proof").dataset.state==="success"');
     assert.equal((await proof()).passed,4,'Current server receipt survives reload');
     const before=requests.filter(r=>r.method==='POST').length;
     await fetch(base+'/qa/evidence/change?kind=input_version&value=2');
     await click('#practice-verify');await until('!practiceEvidenceBusy');
     assert.equal((await proof()).passed,3);assert.equal((await proof()).guide,false);
     assert.equal(await ev('document.querySelector("#practice-seal .practice-seal-label")'),null,'Revoked success removes the assignment stamp');
     assert.equal(requests.filter(r=>r.method==='POST').length,before,'Final check does not execute work SQL');
     await fetch(base+'/qa/evidence/change?kind=input_version&value=1');
     await fetch(base+'/qa/evidence/change?kind=evidence_error&value=1');
     await click('#practice-verify');await until('!practiceEvidenceBusy');
     assert.equal((await proof()).state,'pending');assert.equal((await proof()).guide,false);assert.equal((await proof()).passed,0);
     await fetch(base+'/qa/evidence/change?kind=evidence_error&value=0');
     await ev('dismissMessage()');
   }
   // A delayed result from an earlier identity cannot restore a success stamp after logout.
   await click('#practice-verify');await until('!practiceEvidenceBusy');
   const result=await ev('api("/api/practice/creative/evidence")');
   await ev('window.proofApi=api;window.pendingProof=null;api=()=>new Promise(resolve=>window.pendingProof=resolve);void verifyPracticeEvidence()');
   await until('practiceEvidenceBusy&&!!window.pendingProof');
   await ev('person=null;++sessionGeneration;clearPracticeEvidence("로그인 후 확인하세요.");window.pendingProof('+JSON.stringify(result)+');api=proofApi');
   await until('!practiceEvidenceBusy');assert.equal((await proof()).guide,false);assert.equal((await proof()).passed,0);
   assert.equal(await ev('document.querySelector("#practice-seal .practice-seal-label")'),null,'Old identity cannot restore a successful stamp');
   const qa=await(await fetch(base+'/qa/state')).json();assert.deepEqual(qa.blocked,[]);assert.deepEqual(errors,[]);
   fs.writeFileSync(path.join(root,'runtime/practice-evidence-browser-verification.json'),JSON.stringify({ok:true,synthetic_data_only:true,real_database_access:false,assignments:3,views,receipt_persistence:true,input_change_revocation:true,failure_and_identity_guard:true,screenshots:out},null,2));
   console.log(JSON.stringify({ok:true,assignments:3,success_only_after_actual_results:true,layouts:views.length,revocation_error_reload_identity:true,screenshots:out}));return;
 }
 if(selectionOnly){
   await fetch(base+'/qa/lifecycle');
   await call('Page.navigate',{url:base+'/basic#predictions'});
   await until('typeof statusPhase!=="undefined"&&statusPhase==="ready"&&!refreshing&&page==="predictions"');
   const tab=async name=>{await click('#basic-workflow [data-basic-tab="'+name+'"]');await until('page==='+JSON.stringify(name)+'&&!refreshing&&!basicSwitching')};
   const qa=async()=>await(await fetch(base+'/qa/state')).json();
   const choose=async mode=>ev('setWorkMode("prediction-model-select","'+mode+'");document.getElementById("prediction-model-select").dispatchEvent(new Event("change",{bubbles:true}))');
   const accept=async selector=>{await click(selector);await until('document.getElementById("confirm-dialog").open');await click('#accept-confirm');await until('!activeTasks&&!activeMutations&&!refreshing&&!modelBusy&&!predictionRunning')};
   const help=async mode=>{
     await ev('window.qaHelpUrl="";window.qaOriginalApi=api;api=async(...args)=>{if(args[0].startsWith("/api/coding-help"))window.qaHelpUrl=args[0];return qaOriginalApi(...args)}');
     await click('[data-execution=predict]');await until('document.getElementById("execution-dialog").open&&executionFlow?.stages.length===6');
     assert.equal(await ev('new URL(qaHelpUrl,location.origin).searchParams.get("variant")'),mode);
     await click('#close-execution');await ev('api=qaOriginalApi');
   };
   assert.equal(await ev('document.querySelectorAll("#prediction-model-select .mode-option").length'),2);
   assert.equal(await ev('document.querySelectorAll("#confirm-prediction-model,#unconfirm-prediction").length'),0);
   assert.equal(await ev('selectedMode("prediction-model-select")'),'CLEAN','Uses the saved model initially');
   assert.equal(await ev('document.getElementById("run").disabled'),false);
   await choose('RAW');assert.equal(await ev('confirmedPredictionModel().variant'),'CLEAN','Selection alone does not save');
   await help('RAW');
   const before=(await qa()).mutations.length;
   await click('#run');await until('document.getElementById("confirm-dialog").open');
   assert.ok(await ev('document.getElementById("confirm-description").textContent.includes("RAW")'));
   await click('#cancel-confirm');assert.equal((await qa()).mutations.length,before);
   assert.equal(await ev('confirmedPredictionModel().variant'),'CLEAN');
   await click('#run');await until('document.getElementById("confirm-dialog").open');
   await choose('CLEAN');await click('#accept-confirm');await until('!predictionRunning&&!activeTasks');
   assert.equal((await qa()).prediction_variants.at(-1),'RAW','Mode is frozen before confirmation');
   assert.equal(await ev('selectedMode("prediction-model-select")'),'RAW');
   assert.equal(await ev('confirmedPredictionModel().variant'),'RAW');
   assert.ok(await ev('document.getElementById("result-caption").textContent.includes("OML_BASIC_RAW_MODEL")'));
   await choose('CLEAN');await help('CLEAN');await accept('#run');
   assert.equal((await qa()).prediction_variants.at(-1),'CLEAN');
   assert.equal(await ev('confirmedPredictionModel().variant'),'CLEAN');
   await call('Page.reload');await until('typeof statusPhase!=="undefined"&&statusPhase==="ready"&&!refreshing&&page==="predictions"');
   assert.equal(await ev('selectedMode("prediction-model-select")'),'CLEAN','Successful selection survives reload');
   await tab('models');await accept('#unconfirm-model');await tab('predictions');
   assert.equal(await ev('state.confirmed_current'),0);
   assert.equal(await ev('document.getElementById("run").disabled'),false,'Direct selection works without a saved default');
   await accept('#run');assert.equal(await ev('confirmedPredictionModel().variant'),'CLEAN');
   await choose('RAW');await ev('models.find(m=>m.variant==="RAW").is_current=0;renderPredictionStorage()');
   assert.equal(await ev('document.getElementById("run").disabled'),true);
   assert.equal(await ev('document.querySelector("#prediction-model-select .mode-option[value=RAW]").disabled'),true);
   await choose('CLEAN');assert.equal(await ev('document.getElementById("run").disabled'),false);
   await ev('predictionStorage.rows=0;renderPredictionStorage()');assert.equal(await ev('document.getElementById("run").disabled'),true);
   await ev('predictionStorage.rows=30;renderPredictionStorage()');
   for(const [width,font] of [[1440,16],[1280,22],[390,16],[320,22]]){
     await size(width);await ev('fontSize('+font+');dismissMessage();document.querySelector(".prediction-model-panel").scrollIntoView({block:"start"})');
     assert.ok(await ev('document.documentElement.scrollWidth<=innerWidth'),'No overflow at '+width);
     await shot('prediction-choice-'+width);
   }
   const report=await qa();assert.deepEqual(report.blocked,[]);assert.deepEqual(errors,[]);
   fs.writeFileSync(path.join(root,'runtime/model-selection-verification.json'),JSON.stringify({ok:true,synthetic_data_only:true,real_database_access:false,direct_stage4_choice:true,confirmed_modes:report.prediction_variants,cancel_frozen_reload_unconfirmed_stale:true,screenshots:out},null,2));
   console.log(JSON.stringify({ok:true,direct_stage4_choice:true,selected_model_used_for_prediction_and_help:true,cancel_frozen_reload_unconfirmed_stale:true,layouts:4,screenshots:out}));return;
 }
 if(comparisonOnly){
   let message='';
   if(!process.argv.includes('--assignment-comparison-only')){
   await call('Page.navigate',{url:base+'/basic#models'});
   await until('typeof statusPhase!=="undefined"&&statusPhase==="ready"&&!refreshing&&page==="models"');
   assert.equal(await ev('document.getElementById("model-append")'),null);
   assert.equal(await ev('document.querySelectorAll(".model-action-bar .model-action").length'),3);
   await click('#model-retrain');await until('document.getElementById("confirm-dialog").open');
   message=await ev('document.getElementById("confirm-description").textContent');
   assert.ok(message.includes('TRAIN 전체')&&message.includes('전처리 저장')&&message.includes('데이터를 추가'));
   await ev('document.getElementById("cancel-confirm").click()');await until('!pendingLayerConfirmation');
   for(const width of [1440,1280,768,390,320])for(const font of [16,22]){
      await size(width);await ev('fontSize('+font+');document.getElementById("model-comparison").scrollIntoView({block:"center"})');
      const result=await ev('(()=>{const table=document.getElementById("model-comparison"),box=table.parentElement,r=box.getBoundingClientRect(),rows=[...table.rows],last=rows.at(-1).getBoundingClientRect();return{width:innerWidth,pageWidth:document.documentElement.scrollWidth,scrollWidth:box.scrollWidth,clientWidth:box.clientWidth,scrollHeight:box.scrollHeight,clientHeight:box.clientHeight,maxHeight:getComputedStyle(box).maxHeight,overflow:getComputedStyle(box).overflow,complete:last.bottom<=r.bottom+1,rows:rows.length,overflowItems:[...box.querySelectorAll("*")].filter(e=>getComputedStyle(e).display!=="none"&&e.getBoundingClientRect().right>r.right+1).map(e=>({tag:e.tagName,id:e.id,classes:e.className,right:e.getBoundingClientRect().right,limit:r.right}))}})()');
      assert.ok(result.pageWidth<=width+1&&result.scrollWidth<=result.clientWidth+1,JSON.stringify(result));
      assert.ok(result.complete,JSON.stringify(result));
      assert.equal(result.overflow,'visible');
      assert.equal(await ev('(()=>{const box=document.getElementById("model-comparison").parentElement;box.scrollTop=999;return box.scrollTop})()'),0,'No internal vertical scrolling');
      assert.equal(result.maxHeight,'none');assert.equal(result.rows,5);
      views.push({width,font,...result});
      if([1440,390,320].includes(width))await shot('comparison-'+width+'-'+font);
   }
   await ev('fontSize(16)');await size(1440);
   await call('Page.navigate',{url:base+'/mission'});await until('typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"&&!assignmentBusy');
   await click('.assignment-tabs [data-assignment-tab=models]');
   assert.equal(await ev('document.getElementById("assignment-append")'),null);
   assert.ok(await ev('document.getElementById("assignment-retrain").disabled'));
   }
   for(const key of ['mission','creative']){
     await call('Page.navigate',{url:base+'/'+key});await until('typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"&&!assignmentBusy');
     await click('.assignment-tabs [data-assignment-tab=models]');
     await ev('assignmentScores={RAW:[{actual:"A",predicted:"A",n:149},{actual:"A",predicted:"B",n:151}]};renderAssignmentComparison()');
     assert.equal(await ev('document.getElementById("assignment-compare-accuracy-RAW").textContent'),'49.7%');
     assert.equal(await ev('document.getElementById("assignment-compare-accuracy-CLEAN").textContent'),'평가 전');
     assert.equal(await ev('document.getElementById("assignment-compare-errors-RAW").textContent'),'151행');
     assert.equal(await ev('document.getElementById("assignment-compare-state-RAW").textContent'),'생성 완료');
     assert.equal(await ev('document.querySelector("#assignment-comparison thead").textContent.includes("OML_'+key.toUpperCase()+'_RAW_MODEL")'),true);
     for(const width of [1440,390,320])for(const font of [16,22]){
       await size(width);await ev('fontSize('+font+');document.getElementById("assignment-comparison").scrollIntoView({block:"center"})');
       const result=await ev('(()=>{const box=document.getElementById("assignment-comparison"),t=box.querySelector("table"),last=t.rows[t.rows.length-1].getBoundingClientRect();return {width:innerWidth,pageWidth:document.documentElement.scrollWidth,clientWidth:box.clientWidth,scrollWidth:box.scrollWidth,complete:last.bottom<=box.getBoundingClientRect().bottom+1,overflow:getComputedStyle(box).overflow,score:Number.parseFloat(getComputedStyle(t.querySelector("strong")).fontSize),body:Number.parseFloat(getComputedStyle(t.querySelector("td")).fontSize),background:getComputedStyle(t.querySelector("thead th")).backgroundColor,center:getComputedStyle(t.querySelector("td")).textAlign}})()');
       assert.ok(result.pageWidth<=width+1&&result.scrollWidth<=result.clientWidth+1,JSON.stringify(result));
       assert.ok(result.complete&&result.score>result.body,JSON.stringify(result));assert.equal(result.overflow,'visible');assert.equal(result.center,'center');assert.equal(result.background,'rgb(231, 242, 242)');
       views.push({key,font,...result});if(font===16||width===320)await shot(key+'-comparison-'+width+'-'+font);
     }
     await ev('assignmentScores.CLEAN=[{actual:"A",predicted:"A",n:180},{actual:"A",predicted:"B",n:120}];renderAssignmentComparison()');
     assert.equal(await ev('document.getElementById("assignment-compare-accuracy-CLEAN").textContent'),'60.0%');
     await ev('assignmentScores.CLEAN=[];renderAssignmentComparison()');
     assert.equal(await ev('document.getElementById("assignment-compare-accuracy-CLEAN").textContent'),'평가 행 없음');
     await ev('assignmentState.models.find(m=>m.variant==="RAW").is_current=false;renderAssignmentComparison()');
     assert.equal(await ev('document.getElementById("assignment-compare-state-RAW").textContent'),'연계·재학습 확인 필요');
     assert.equal(await ev('document.getElementById("assignment-compare-accuracy-RAW").textContent'),'평가 전');
     await ev('assignmentState.models.find(m=>m.variant==="RAW").exists=false;renderAssignmentComparison()');
     assert.equal(await ev('document.getElementById("assignment-compare-state-RAW").textContent'),'미생성');
     await ev('resetAssignmentWorkspace()');
     assert.equal(await ev('document.querySelectorAll("#assignment-comparison .compare-table").length'),1);
     assert.equal(await ev('document.getElementById("assignment-compare-state-RAW").textContent'),'확인 전');
     if(key==='creative')assert.equal(await ev('document.querySelectorAll("#assignment-panel-models [data-code]").length'),3);
   }
   const qa=await(await fetch(base+'/qa/state')).json();assert.deepEqual(qa.blocked,[]);assert.deepEqual(qa.mutations,[]);assert.deepEqual(errors,[]);
   fs.writeFileSync(path.join(root,'runtime/model-comparison-verification.json'),JSON.stringify({ok:true,synthetic_data_only:true,real_database_access:false,retrain_message:message,views,screenshots:out},null,2));
   console.log(JSON.stringify({ok:true,comparison_no_internal_scroll:true,layouts:views.length,unified_retrain:!process.argv.includes('--assignment-comparison-only'),confirmation_cancel:!process.argv.includes('--assignment-comparison-only'),screenshots:out}));return;
 }
 if(lifecycleOnly){
   await fetch(base+'/qa/lifecycle');
   await call('Page.navigate',{url:base+'/basic'});
   await until('typeof statusPhase!=="undefined"&&statusPhase==="ready"&&!refreshing');
   const labels=await ev('Object.fromEntries([...document.querySelectorAll("button[id],button[data-confirm]")].map(b=>[b.id||b.dataset.confirm,b.textContent.trim()]))');
   const stable=async()=>{const actual=await ev('Object.fromEntries([...document.querySelectorAll("button[id],button[data-confirm]")].map(b=>[b.id||b.dataset.confirm,b.textContent.trim()]))');for(const key of ['initialize-basic','register-basic','reregister-basic','import-submit','replace-training','prediction-import-submit','replace-prediction' ,'RAW','CLEAN'])assert.equal(actual[key],labels[key],key+' label remains fixed');};
   const tab=async name=>{await click('#basic-workflow [data-basic-tab="'+name+'"]');await until('page==='+JSON.stringify(name)+'&&!refreshing&&statusPhase==="ready"')};
   const count=async()=>{return (await(await fetch(base+'/qa/state')).json()).mutations.length;};
   const accept=async selector=>{
      console.log(JSON.stringify({lifecycle:selector}));
      await click(selector);await until('document.getElementById("confirm-dialog").open');
      await ev('document.getElementById("accept-confirm").click()');
      await until('!activeTasks&&!activeMutations&&!refreshing');await stable();
   };
   assert.equal(await ev('document.getElementById("initialize-basic").disabled'),true);
   assert.equal(await ev('document.getElementById("register-basic").disabled'),true);
   assert.equal(await ev('document.getElementById("reregister-basic").disabled'),false);
   await accept('#reregister-basic');
   let previous=await count();
   await click('#drop-basic-objects');await until('document.getElementById("confirm-dialog").open');
   await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
   await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
   await until('!document.getElementById("confirm-dialog").open&&!pendingLayerConfirmation');
   assert.equal(await count(),previous,'ESC sends no deletion');
   await accept('#drop-basic-objects');
   assert.ok(await ev('!initialized&&models.every(m=>!m.exists)&&!storage.exists'));
   assert.equal(await ev('document.getElementById("register-basic").disabled'),true);
   await shot('lifecycle-empty-home');
   await accept('#initialize-basic');
   assert.ok(await ev('storage.exists&&!initialized'));
   assert.equal(await ev('document.getElementById("register-basic").disabled'),false);
   await accept('#register-basic');assert.equal(await ev('initialized'),true);
   await tab('data');
   assert.equal(await ev('document.getElementById("import-submit").disabled'),false);
   assert.equal(await ev('document.getElementById("replace-training").disabled'),true);
   await click('#choose-sample');await until('!activeTasks');
   await accept('#import-submit');
   assert.equal(await ev('document.getElementById("import-submit").disabled'),true);
   assert.equal(await ev('document.getElementById("replace-training").disabled'),false);
   await accept('#replace-training');
   await accept('#clear-training');assert.equal(await ev('state.total_rows'),0);
   await tab('predictions');
   await click('#choose-prediction');await until('!activeTasks');
   await accept('#prediction-import-submit');
   await accept('#clear-prediction');assert.equal(await ev('predictionStorage.rows'),0);
   await fetch(base+'/qa/lifecycle');await ev('refresh()');await until('!refreshing');
   await tab('models');await accept('#unconfirm-model');assert.equal(await ev('state.confirmed_current'),0);
   await tab('data');
   await ev('setWorkMode("preparation-mode","CLEAN");renderPreparation()');
   await click('#clear-prepared');await until('document.getElementById("confirm-dialog").open');
   await ev('setWorkMode("preparation-mode","RAW")');
   await ev('document.getElementById("accept-confirm").click()');await until('!activeTasks&&!activeMutations');
   const last=(await(await fetch(base+'/qa/state')).json()).mutations.at(-1);assert.equal(last.variant,'CLEAN','Mode frozen before confirmation');
   await tab('models');await accept('#model-delete');
   assert.equal(await ev('models.find(m=>m.variant==="RAW").exists'),0);
   for(const width of [1440,390,320]){
     await size(width);await tab('home');
     assert.ok(await ev('document.documentElement.scrollWidth<=innerWidth'));
     await ev('dismissMessage();document.querySelector(".basic-object-panel").scrollIntoView({block:"start"})');
     await shot('lifecycle-home-'+width);
   }
   // Every new help trigger must resolve to a real source flow without mutating APIs.
   await size(1440);
   for(const step of ['home','data','models','predictions']){
     await tab(step);
     const targets=await ev('[...document.querySelectorAll("[data-basic-lifecycle]")].filter(b=>b.getClientRects().length).map(b=>({id:b.id,op:b.dataset.basicLifecycle}))');
     for(const target of targets){
       previous=await count();
       await ev('openExecution(document.querySelector("#'+target.id+'").closest(".action-with-help").querySelector("[data-code]"))');
       await until('document.getElementById("execution-flow").querySelectorAll("[data-flow-stage]").length===6');
       assert.ok(await ev('document.getElementById("execution-code").textContent.length>0'));
       assert.equal(await count(),previous);
       await click('#close-execution');
     }
   }
   await call('Page.navigate',{url:base+'/mission'});await until('typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"&&!assignmentBusy');
   for(const step of ['home','data']){
     await click('[data-assignment-tab="'+step+'"]');
     const targets=await ev('[...document.querySelectorAll("[data-code]")].filter(b=>b.getClientRects().length&&["drop-objects","clear-training","clear-prepared","clear-prediction"].includes(b.dataset.code)).map(b=>b.dataset.code)');
     for(const op of targets){await ev('openExecution(document.querySelector("[data-code='+op+']"))');assert.equal(await ev('executionFlow.mode'),'manual-guide');await click('#close-execution');}
   }
   await ev('void saveMissionSelection("")');if(await ev('document.getElementById("confirm-dialog").open'))await ev('document.getElementById("accept-confirm").click()');await until('!missionSelectionSaving');
   assert.ok(await ev('[...document.querySelectorAll("[data-mission-choice]")].every(b=>b.textContent.trim()==="이 미션 선택")'));
   await call('Page.navigate',{url:base+'/creative'});await until('typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"&&!assignmentBusy');
   assert.equal(await ev('document.querySelectorAll("[data-code]").length'),0);
   assert.deepEqual(errors,[]);
   const qa=await(await fetch(base+'/qa/state')).json();assert.deepEqual(qa.blocked,[]);
   fs.writeFileSync(path.join(root,'runtime/lifecycle-browser-verification.json'),JSON.stringify({ok:true,synthetic_data_only:true,real_database_access:false,mutations:qa.mutations,screenshots:out},null,2));
   console.log(JSON.stringify({ok:true,lifecycle:true,stable_labels:true,confirmation_cancel:true,mode_frozen:true,read_only_help:true,screenshots:out}));return;
 }
 if(allButtons){
   const inventory=[];
   for(const assignment of ['basic','mission']){
     await call('Page.navigate',{url:base+'/'+assignment});
     await until(assignment==='basic'?'typeof statusPhase!=="undefined"&&statusPhase==="ready"&&!refreshing':'typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"&&!assignmentBusy');
     await ev('window.qaOriginalApi=api;api=async(...args)=>{const result=await qaOriginalApi(...args);if(args[0].startsWith("/api/coding-help"))window.qaFlow=result.flow;if(args[0].startsWith("/api/coding-help"))window.qaApplication=result.application;return result};Object.defineProperty(navigator,"clipboard",{configurable:true,value:{writeText:async text=>{window.qaCopied=text}}});window.qaCopied=null');
     for(const step of ['home','data','models','predictions']){
       if(assignment==='basic'){await click('#basic-workflow [data-basic-tab="'+step+'"]');await until('page==='+JSON.stringify(step)+'&&!refreshing&&statusPhase==="ready"')}else await click('.assignment-tabs [data-assignment-tab="'+step+'"]');
       const targets=await ev('(()=>{for(const d of document.querySelectorAll("details"))if(d.getClientRects().length)d.open=true;return [...document.querySelectorAll("[data-code],[data-execution]")].filter(e=>e.getClientRects().length&&!e.closest("dialog")).map((e,i)=>{const trigger=codingTrigger(e);e.dataset.qaHelp="'+assignment+'-'+step+'-"+i;return{selector:"[data-qa-help="+e.dataset.qaHelp+"]",operation:e.dataset.code||e.dataset.execution,label:trigger.textContent.trim().replace(/\\s+/g," "),id:trigger.id}})})()');
       assert.ok(targets.length,assignment+' '+step+' includes coding help');
       for(const target of targets){
         console.log(JSON.stringify({assignment,step,operation:target.operation,id:target.id,label:target.label}));
         await ev('window.qaFlow=null');const start=requests.length;
         await click(target.selector);await until('document.getElementById("execution-dialog").open&&window.qaFlow');
         assert.equal(await ev('qaFlow.trigger.label'),target.label);
         if(target.id)assert.equal(await ev('qaFlow.trigger.id'),target.id);
         const focus=await ev('({expected:qaFlow.stages[0].items[0].focus_text,actual:document.querySelector("#execution-code .code-source-focus")?.textContent})');
         assert.ok(focus.expected);assert.equal(focus.actual,focus.expected,'Visible focus is the actual template source');
         if(target.id&&focus.actual.startsWith('<button')&&!focus.actual.includes('{{')&&!focus.actual.includes('{%'))assert.ok(focus.actual.includes(target.id),'Literal trigger ID must be present in focused source');
         if(assignment==='mission'&&target.id==='refresh'){
           const stages=await ev('qaFlow.stages.map(stage=>({...stage,items:stage.items.map(item=>({...item,content:flowItemContent(item)}))}))');
           assert.equal(stages[0].items[0].path,'templates/index.html');
           assert.ok(stages[1].items.some(i=>i.path==='static/js/main.js'&&i.content.includes("on('refresh','click'")));
           assert.ok(stages[2].items.every(i=>!i.content.includes('def link_assignment(')),'Header refresh only queries status');
         }
         if(assignment==='basic'&&target.operation==='evaluate'){
           assert.ok(focus.actual.includes('id="query-models"')&&focus.actual.includes(target.label));
           await layout('test-refresh-real-button',1440);await layout('test-refresh-real-button',390);await size(1440);
           assert.ok(await ev('document.getElementById("execution-code").scrollWidth<=document.getElementById("execution-code").clientWidth+1'),'HTML source wraps instead of hiding the button to the right');
         }
         await inspectFlow(assignment+'-'+target.operation);
         assert.ok(requests.slice(start).every(r=>new URL(r.url).pathname==='/api/coding-help'&&r.method==='GET'),'Opening help must only read sources');
         inventory.push({assignment,step,...target});
         await click('#close-execution');await until('!document.getElementById("execution-dialog").open');
       }
       if(assignment==='basic'&&step==='models'){
         await click('#query-model-dictionary');await until('document.querySelectorAll("#model-dictionary-results>details").length===8');
         await ev('for(const d of document.querySelectorAll("#model-dictionary-results>details"))d.open=true;for(const d of document.querySelectorAll(".dictionary-view-code"))d.open=true');
         assert.ok((await ev('document.querySelector(".dictionary-naming").textContent')).includes('DM$ + VC + OML_BASIC_RAW_MODEL'));
         assert.ok((await ev('document.querySelector("#model-dictionary-results").textContent')).includes('현재 등록된 비용 행렬은 0행'));
         assert.equal(await ev('document.querySelectorAll("#model-dictionary-results .dictionary-view-code").length'),4);
         for(const width of [1440,390]){await size(width);await ev('document.querySelector(".dictionary-naming").scrollIntoView({block:"start"})');await shot('dictionary-real-query-layout-'+width);assert.ok(await ev('document.documentElement.scrollWidth<=innerWidth+1'));}
         await size(1440);
       }
     }
   }
   await call('Page.navigate',{url:base+'/creative'});await until('typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"&&!assignmentBusy');
   assert.equal(await ev('document.querySelectorAll("[data-code],[data-execution]").length'),0);
   const qa=await(await fetch(base+'/qa/state')).json();assert.deepEqual(qa.blocked,[]);assert.deepEqual(qa.mutations,[]);assert.deepEqual(errors,[]);
   const report={ok:true,all_rendered_buttons:true,synthetic_data_only:true,real_database_access:false,inventory,cases,source_item_checks:checkedItems,unique_source_files:sourcePaths.size,unique_original_ranges:sourceRanges.size,source_files:[...sourcePaths].sort(),generated_sql_checks:generatedSqlChecks,views,screenshots:out};
   fs.writeFileSync(path.join(root,'runtime/coding-flow-all-buttons-verification.json'),JSON.stringify(report,null,2));
   console.log(JSON.stringify({ok:true,buttons:inventory.length,source_item_checks:checkedItems,unique_source_files:sourcePaths.size,generated_sql_checks:generatedSqlChecks,screenshots:out}));return;
 }
 for(const assignment of (importOnly?['mission']:contextOnly?['basic']:['basic','mission'])){
   await call('Page.navigate',{url:base+'/'+assignment});
   await until(assignment==='basic'?'typeof statusPhase!=="undefined"&&statusPhase==="ready"&&!refreshing':'typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"&&!assignmentBusy');
   await ev('window.qaOriginalApi=api;api=async(...args)=>{const result=await qaOriginalApi(...args);if(args[0].startsWith("/api/coding-help"))window.qaFlow=result.flow;if(args[0].startsWith("/api/coding-help"))window.qaApplication=result.application;return result};Object.defineProperty(navigator,"clipboard",{configurable:true,value:{writeText:async text=>{window.qaCopied=text}}});window.qaCopied=null');
   const scenarios=assignment==='basic'?[['home','create-tables'],['home','register-procedure'],['home','reregister-procedure'],['data','preview'],['data','data'],['data','prepare'],['data','prepared-data'],['models','initial-train'],['models','evaluate'],['models','confirm'],['predictions','predict']]:[['home','setup'],['data','import'],['data','prepare'],['data','prepared-data'],['models','initial-train'],['models','evaluate'],['predictions','predict']];
   for(const [step,operation] of (guidanceOnly?(assignment==='basic'?[['home','create-tables'],['home','register-procedure'],['home','reregister-procedure'],['data','preview'],['data','data'],['data','import'],['models','initial-train']]:[['home','setup'],['data','import'],['data','prepared-data'],['models','initial-train']]):importOnly?[['data','import']]:(layoutOnly||contextOnly)?[['models','initial-train']]:scenarios)){
     if(assignment==='basic'){await click('#basic-workflow [data-basic-tab="'+step+'"]');await until('page==='+JSON.stringify(step)+'&&!refreshing&&statusPhase==="ready"')}else await click('.assignment-tabs [data-assignment-tab="'+step+'"]');
     console.log(JSON.stringify({case:assignment+'-'+operation,phase:'start'}));
     const selector='[data-code="'+operation+'"],[data-execution="'+operation+'"]';
     await ev('window.qaFlow=null');const requestStart=requests.length;
     await click(selector);await until('document.getElementById("execution-dialog").open&&!!window.qaFlow');
     await inspectFlow(assignment+'-'+operation);console.log(JSON.stringify({case:assignment+'-'+operation,phase:'sources-verified'}));
     assert.ok(requests.slice(requestStart).every(r=>new URL(r.url).pathname==='/api/coding-help'&&r.method==='GET'),'Help must not execute APIs '+JSON.stringify(requests.slice(requestStart)));
     if(importOnly){for(const width of [1440,390])await layout('mission-csv-file-loader',width);await size(1440);}
     if(operation==='initial-train'&&!guidanceOnly){
       for(const width of [1440,768,390,320])await layout(assignment+'-model-sql',width);
       await layout(assignment+'-model-sql',390,22);await ev('fontSize(16)');await size(1440);
       const selected=await ev('document.querySelector("#execution-items [aria-pressed=true]")?.dataset.flowItem');
       await click('#execution-dialog [data-window-action="minimize"]');
       assert.ok(await ev('HelpWindow.isMinimized(document.getElementById("execution-dialog"))&&!document.getElementById("execution-dialog").open'));
       await click('#help-window-dock .help-minimized:not([hidden]) button');
       assert.equal(await ev('document.querySelector("#execution-items [aria-pressed=true]")?.dataset.flowItem'),selected,'Restore preserves selected source');
       await click('#execution-dialog [data-window-action="maximize"]');assert.ok(await ev('document.getElementById("execution-dialog").classList.contains("help-maximized")'));await layout(assignment+'-maximized',768);
       await click('#execution-dialog [data-window-action="maximize"]');await size(1440);
     }
     await click('#close-execution');await until('!document.getElementById("execution-dialog").open');
     await until('document.activeElement.matches('+JSON.stringify(selector)+')');
   }
 }
 await call('Page.navigate',{url:base+'/creative'});await until('typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"&&!assignmentBusy');assert.equal(await ev('document.querySelectorAll("[data-code],[data-execution]").length'),8,'Creative exposes only manual action help');
 const qa=await(await fetch(base+'/qa/state')).json();assert.deepEqual(qa.blocked,[]);assert.deepEqual(errors,[]);
 const report={ok:true,synthetic_data_only:true,real_database_access:false,cases,checked_items:checkedItems,source_item_checks:checkedItems,original_snippet_checks:checkedItems-generatedSqlChecks,generated_sql_checks:generatedSqlChecks,unique_source_files:sourcePaths.size,unique_original_ranges:sourceRanges.size,source_files:[...sourcePaths].sort(),views,console_errors:errors,screenshots:out};
 fs.writeFileSync(path.join(root,guidanceOnly?'runtime/coding-guidance-verification.json':contextOnly?'runtime/coding-flow-file-context-verification.json':importOnly?'runtime/coding-flow-import-verification.json':layoutOnly?'runtime/coding-flow-layout-verification.json':'runtime/coding-flow-browser-verification.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify({ok:true,cases:cases.length,source_item_checks:checkedItems,unique_source_files:sourcePaths.size,generated_sql_checks:generatedSqlChecks,layout_checks:views.length,screenshots:out}));
})().catch(error=>{console.error(error.stack);console.error('Screenshots: '+out);process.exitCode=1}).finally(async()=>{try{if(call)await Promise.race([call('Browser.close'),pause(1000)])}catch{}ws?.close();browser.kill();server.kill()});
