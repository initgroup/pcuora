// Synthetic-only UI checks; never reads a real login, wallet or Oracle account.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const largeText=process.argv.includes('--large-text'),cleanupOnly=process.argv.includes('--guide-cleanup-only'),executionOnly=process.argv.includes('--execution-only'),learningOnly=process.argv.includes('--learning-data-only');
const root=path.resolve(__dirname,'../..'),out=fs.mkdtempSync(path.join(os.tmpdir(),'workspace-visual-ui-')),pause=ms=>new Promise(r=>setTimeout(r,ms));
const server=spawn(path.join(root,'.venv/Scripts/python.exe'),['-B',path.join(__dirname,'workspace_visual_preview_server.py')],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
let serverErrors='';server.stderr.on('data',c=>serverErrors+=c);
const basePromise=new Promise((resolve,reject)=>{let buffer='';server.stdout.on('data',c=>{buffer+=c;const match=buffer.match(/VISUAL_QA_URL=(http:\/\/127\.0\.0\.1:\d+)/);if(match)resolve(match[1])});server.on('error',reject);server.on('exit',code=>reject(new Error('Fixture exited '+code+' '+serverErrors)))});
const profile=path.join(out,'profile'),browser=spawn('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
let ws,call;const issues=[],views=[],contrasts=[],errors=[],badResponses=[];
(async()=>{
 const portFile=path.join(profile,'DevToolsActivePort');for(let i=0;i<150&&!fs.existsSync(portFile);i++)await pause(100);
 const port=fs.readFileSync(portFile,'utf8').split('\n')[0],tabs=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();
 ws=new WebSocket(tabs.find(tab=>tab.type==='page').webSocketDebuggerUrl);
 await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject});
 let seq=0;const pending=new Map();
 ws.onmessage=event=>{const r=JSON.parse(event.data);if(r.method==='Runtime.exceptionThrown')errors.push(r.params.exceptionDetails.exception?.description||r.params.exceptionDetails.text);if(r.method==='Network.responseReceived'&&r.params.response.status>=400&&!r.params.response.url.endsWith('/favicon.ico'))badResponses.push({url:r.params.response.url,status:r.params.response.status});if(r.id){const p=pending.get(r.id);pending.delete(r.id);r.error?p.reject(r.error):p.resolve(r.result)}};
 call=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))});
 const ev=async expression=>{const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});assert.ok(!r.exceptionDetails,JSON.stringify(r.exceptionDetails));return r.result.value};
 const until=async expression=>{for(let i=0;i<180;i++){if(await ev(expression))return;await pause(50)}throw new Error('Timed out '+expression+' '+JSON.stringify(errors)+' '+serverErrors)};
 const size=width=>call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});
 const shot=async name=>{await ev('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');const r=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(r.data,'base64'))};
 const click=selector=>ev('(()=>{const e=document.querySelector('+JSON.stringify(selector)+');if(!e)throw new Error("Missing selector: "+'+JSON.stringify(selector)+');e.focus();e.click();})()');
 const screen=async(label,selector)=>{
   for(const width of (largeText||cleanupOnly?[1440,390]:[1440,768,390,320])){
     await size(width);
     if(selector)await ev('document.querySelector('+JSON.stringify(selector)+').scrollIntoView({block:"start"})');else await ev('scrollTo(0,0)');
     await ev('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');
     const metrics=await ev('({viewport:innerWidth,scroll:document.documentElement.scrollWidth,dialog:[...document.querySelectorAll("dialog[open]")].map(d=>{const r=d.getBoundingClientRect();return{id:d.id,left:r.left,right:r.right,top:r.top,bottom:r.bottom,scroll:d.scrollWidth,client:d.clientWidth}})})');
     if(metrics.scroll>width)issues.push({label,width,problem:'Document horizontal overflow',metrics});
     for(const box of metrics.dialog)if(box.left<0||box.right>width+1||box.top<0||box.bottom>901||box.scroll>box.client+1)issues.push({label,width,problem:'Dialog outside viewport or horizontal overflow',box});
     views.push({label,width,...metrics});
     if(width===1440||width===390)await shot(label+'-'+width);
   }
   await size(1440);
 };
 const codeContrast=async(label)=>{
   const values=await ev('(()=>{const p=document.getElementById("execution-code"),s=getComputedStyle(p);return {background:s.backgroundColor,text:s.color,font:s.fontSize,tokens:[...p.querySelectorAll("span")].map(e=>({class:e.className,color:getComputedStyle(e).color})).filter((v,i,a)=>a.findIndex(t=>t.class===v.class)===i),padding:s.padding,border:s.borderTopWidth}})()');
   const luminance=color=>{const nums=color.match(/[\d.]+/g).slice(0,3).map(Number).map(v=>{v/=255;return v<=.04045?v/12.92:Math.pow((v+.055)/1.055,2.4)});return nums[0]*.2126+nums[1]*.7152+nums[2]*.0722};
   const ratio=color=>{const a=luminance(values.background),b=luminance(color);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05)};
   values.ratios=[{class:'code-text',ratio:ratio(values.text)},...values.tokens.map(t=>({class:t.class,ratio:ratio(t.color)}))];
   contrasts.push({label,...values});for(const t of values.ratios)if(t.ratio<4.5)issues.push({label,problem:'Code contrast below 4.5:1',...t});
 };
 await call('Page.enable');await call('Page.bringToFront');await call('Runtime.enable');await call('Network.enable');await call('Emulation.setFocusEmulationEnabled',{enabled:true});await size(1440);
 const base=await basePromise;
 if(learningOnly){
   const tables=[];
   const inspect=async(id,expected)=>{
     await until('document.querySelector("#'+id+' tbody tr")!==null');
     const result=await ev('(()=>{const root=document.getElementById('+JSON.stringify(id)+'),t=root.querySelector("table"),heads=[...t.querySelectorAll("thead th")];return{headers:heads.map(h=>({key:h.querySelector(".column-name").textContent.toLowerCase(),role:h.dataset.columnRole,badge:h.querySelector(".mission-column-role").textContent,bg:getComputedStyle(h).backgroundColor})),rows:[...t.tBodies[0].rows].map(r=>[...r.cells].map(c=>({text:c.textContent,role:c.dataset.columnRole,bg:getComputedStyle(c).backgroundColor}))),legend:[...root.querySelectorAll(".mission-column-legend li")].map(e=>e.textContent)}})()');
     assert.deepEqual(result.legend,['식별자','설명변수','타깃변수','기타']);
     for(const [i,h] of result.headers.entries()){
       assert.equal(h.role,expected[h.key]||'metadata',id+' '+h.key);
       for(const row of result.rows)assert.equal(row[i].role,h.role,'Body must match header role');
     }
     const roleColors=new Map(result.headers.map(h=>[h.role,h.bg]));
     assert.equal(new Set(roleColors.values()).size,roleColors.size,'Header roles use different colors');
     tables.push({id,...result});
     return result;
   };
   await call('Page.navigate',{url:base+'/basic#data'});
   await until('typeof statusPhase!=="undefined"&&statusPhase==="ready"&&!refreshing&&page==="data"');
   await click('#query-prepared-data');
   const basicRoles={case_id:'identifier',return_pct:'feature',range_pct:'feature',volume_change_pct:'feature',close_price:'feature',stock:'feature',signal:'target'};
   const prepared=await inspect('prepared-data',basicRoles);
   const emptyIndex=prepared.headers.findIndex(h=>h.key==='exclude_reason');
   assert.ok(prepared.rows.every(row=>row[emptyIndex].text===''),'NULL remains an empty cell');
   const controls=await ev('(()=>{const s=document.getElementById("prepared-source-kind"),b=document.getElementById("query-prepared-data");return {select:getComputedStyle(s).backgroundColor,button:getComputedStyle(b).backgroundColor,arrow:getComputedStyle(s).backgroundImage,group:s.closest(".query-controls")===b.closest(".query-controls"),prepareSeparate:!s.closest(".query-controls").contains(document.getElementById("prepare-data"))}})()');
   assert.notEqual(controls.select,controls.button);assert.notEqual(controls.arrow,'none');
   assert.ok(controls.group&&controls.prepareSeparate,'Query conditions are separated from mutation action');
   await screen('basic-learning-roles','.preparation-workbench');
   await ev('document.getElementById("original-data-detail").open=true');
   await click('#query-data');
   const original=await inspect('data-table',basicRoles);
   const apiRows=(await(await fetch(base+'/api/data')).json()).rows;
   assert.deepEqual(original.rows.map(row=>row.map(c=>c.text)),apiRows.map(row=>original.headers.map(h=>row[h.key]==null?'':String(row[h.key]))),'Original DB values remain unchanged');
   await call('Page.navigate',{url:base+'/mission'});
   await until('typeof assignmentState!=="undefined"&&assignmentState?.ready&&missionSelectionCurrent==="festival"');
   await click('.assignment-tabs [data-assignment-tab="data"]');
   await click('#assignment-prepared-data');
   const missionRoles={case_id:'identifier',interest_score:'feature',reservation_score:'feature',promotion_score:'feature',label:'target'};
   const mission=await inspect('assignment-prepared-rows',missionRoles);
   assert.ok(mission.headers.some(h=>h.key==='interest_score'&&h.badge==='설명변수'));
   await screen('mission-learning-roles','.preparation-workbench');
   await ev('document.getElementById("assignment-original-detail").open=true');
   await click('#assignment-data-refresh');
   await inspect('assignment-data',missionRoles);
   await call('Page.navigate',{url:base+'/creative'});
   await until('typeof assignmentState!=="undefined"&&assignmentState?.ready');
   await click('.assignment-tabs [data-assignment-tab="data"]');
   await click('#assignment-prepared-data');
   await inspect('assignment-prepared-rows',{case_id:'identifier'});
   await screen('creative-learning-roles','.preparation-workbench');
   const qa=await(await fetch(base+'/qa/state')).json();
   assert.deepEqual(qa.mutations,[],'Read-only role and condition check must not mutate data');
   assert.deepEqual(qa.blocked,[]);assert.deepEqual(errors,[]);assert.deepEqual(badResponses,[]);assert.deepEqual(issues,[]);
   const report={ok:true,synthetic_data_only:true,real_database_access:false,tables,controls,views,issues,screenshots:out};
   fs.writeFileSync(path.join(root,'runtime/learning-data-visual-verification.json'),JSON.stringify(report,null,2));
   console.log(JSON.stringify({ok:true,tables:tables.length,layouts:views.length,screenshots:out}));
   return;
 }
 if(executionOnly){
   await fetch(base+'/qa/enable-execution');
   const count=async target=>(await(await fetch(base+'/qa/state')).json()).mutations.filter(path=>path===target).length;
   const confirmations=[];
   const checkConfirmation=async(selector,target)=>{
     await until('!document.querySelector('+JSON.stringify(selector)+').disabled');
     const before=await count(target);
     for(const action of ['cancel','escape','close','accept']){
       console.log('Confirmation check: '+target+' '+action);
       await click(selector);await until('document.getElementById("confirm-dialog").open');
       assert.equal(await count(target),before,'No request before confirmation '+target);
       if(action==='escape'){
         await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
         await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
       }else await click(action==='accept'?'#accept-confirm':action==='close'?'#close-confirm':'#cancel-confirm');
       await until('!document.getElementById("confirm-dialog").open&&pendingLayerConfirmation===null');
       if(action==='accept')await until('activeTasks===0');
       assert.equal(await count(target),before+(action==='accept'?1:0),'Cancel/ESC/close must not execute; accept once '+target);
     }
     confirmations.push(target);
   };
   await call('Page.navigate',{url:base+'/basic'});
   await until('typeof statusPhase!=="undefined"&&statusPhase==="ready"&&!refreshing');
   await checkConfirmation('#initialize-basic','/api/initialize');
   await click('[data-code="initialize"]');await until('document.getElementById("execution-dialog").open&&document.querySelectorAll("[data-flow-stage]").length===6');
   await click('[data-flow-stage="sql"]');await screen('explorer-sql');
   const geometry=await ev('(()=>{const a=document.getElementById("execution-stage-detail").getBoundingClientRect(),b=document.getElementById("execution-source-panel").getBoundingClientRect();return{left:a.left,right:a.right,codeLeft:b.left,top:a.top,codeTop:b.top}})()');
   assert.ok(geometry.right<geometry.codeLeft&&Math.abs(geometry.top-geometry.codeTop)<2,'Explorer sits left of source '+JSON.stringify(geometry));
   await codeContrast('explorer-code');
   await click('#close-execution');
   await click('[data-basic-schema]');await until('document.getElementById("basic-schema-dialog").open&&document.getElementById("basic-schema-code").textContent.includes("CREATE TABLE")');
   await ev('document.getElementById("basic-schema-ddl").open=true');
   await screen('basic-schema-colors');await click('#close-basic-schema');
   await click('#basic-workflow [data-basic-tab="data"]');await until('page==="data"&&!refreshing');
   await checkConfirmation('#prepare-data','/api/data/prepare');
   await fetch(base+'/qa/no-raw-model');
   await click('#basic-workflow [data-basic-tab="models"]');await until('page==="models"&&!refreshing');
   await checkConfirmation('#model-initial','/api/models/train');
   await checkConfirmation('[data-confirm="RAW"]','/api/models/confirm');
   await click('#basic-workflow [data-basic-tab="predictions"]');await until('page==="predictions"&&!refreshing');
   await ev('document.querySelector("#prediction-model-select input[value=CLEAN]").checked=true;document.querySelector("#prediction-model-select input[value=CLEAN]").dispatchEvent(new Event("change",{bubbles:true}))');
   await checkConfirmation('#run','/api/predictions/run');
   await call('Page.navigate',{url:base+'/mission'});await until('typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"&&!assignmentBusy');
   await checkConfirmation('#assignment-check','/api/assignments/mission/link');
   await checkConfirmation('[data-mission-choice="esports"]','/api/assignments/mission/selection');
   await click('[data-mission-schema="esports"]');await until('document.getElementById("mission-schema-dialog").open&&document.getElementById("mission-schema-code").textContent.includes("CREATE TABLE")');
   await ev('document.getElementById("mission-schema-ddl").open=true');
   const tabColors=await ev('Array.from(document.querySelectorAll("[data-mission-schema-kind]"),button=>({active:button.getAttribute("aria-pressed"),background:getComputedStyle(button).backgroundColor,color:getComputedStyle(button).color}))');
   assert.equal(tabColors.filter(tab=>tab.active==="true").length,1);assert.notEqual(tabColors[0].background,tabColors[1].background);
   const colors=await ev('(()=>{const pre=document.getElementById("mission-schema-code"),style=getComputedStyle(pre);return{background:style.backgroundColor,text:style.color,comment:getComputedStyle(pre.querySelector(".syntax-comment")).color,keyword:getComputedStyle(pre.querySelector(".syntax-keyword")).color}})()');
   assert.equal(colors.background,'rgb(20, 43, 64)');assert.notEqual(colors.comment,colors.background);assert.notEqual(colors.keyword,colors.background);
   await screen('mission-schema-colors');
   await screen('mission-schema-ddl','#mission-schema-ddl');
   for(const kind of ['prepared','prediction','training']){await click('[data-mission-schema-kind="'+kind+'"]');assert.equal(await ev('document.querySelector("[data-mission-schema-kind][aria-pressed=true]").dataset.missionSchemaKind'),kind)}
   await click('#close-mission-schema');
   const selectionCalls=await count('/api/assignments/mission/selection');
   await ev('window.qaPendingPerson=person;void saveMissionSelection("bike")');await until('document.getElementById("confirm-dialog").open');
   await ev('person=null;renderPerson()');await until('pendingLayerConfirmation===null');
   assert.equal(await ev('missionSelectionCurrent'),'','Logout cancels pending mission selection without restoring old identity');
   assert.equal(await count('/api/assignments/mission/selection'),selectionCalls,'Logout does not save a pending selection');
   const qa=await(await fetch(base+'/qa/state')).json();
   assert.deepEqual(qa.blocked,[]);assert.deepEqual(errors,[]);assert.deepEqual(badResponses,[]);assert.deepEqual(issues,[]);
   const report={ok:true,synthetic_data_only:true,real_database_access:false,confirmations,views,contrasts,issues,colors,screenshots:out};
   fs.writeFileSync(path.join(root,'runtime/execution-workspace-verification.json'),JSON.stringify(report,null,2));
   console.log(JSON.stringify({ok:true,confirmation_actions:confirmations.length,layout_checks:views.length,screenshots:out}));return;
 }
 if(cleanupOnly){
   for(const key of ['basic','mission','creative']){
     await call('Page.navigate',{url:base+'/'+key});
     await until(key==='basic'?'typeof statusPhase!=="undefined"&&statusPhase==="ready"&&!refreshing':'typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"&&!assignmentBusy');
     assert.equal(await ev('document.querySelectorAll("#open-help,[data-open-help],#help-content,[data-help-tab],#sql-help-template").length'),0);
     await screen(key+'-guide-cleanup');
     await click('#open-menu');assert.equal(await ev('document.querySelector("#mobile-menu [data-open-help]")'),null);await click('#close-menu');
     if(key==='basic'){
       await click('#basic-workflow [data-basic-tab="models"]');
       await until('page==="models"&&!refreshing');
       await click('[data-code="initial-train"]');await until('document.getElementById("execution-dialog").open&&document.querySelectorAll("[data-flow-stage]").length===6');
       await click('#close-execution');await until('!document.getElementById("execution-dialog").open');
       await ev('operationNotice({message:"격리 소스 확인",diagnostic:{code:"QA-SOURCE",title:"관련 파일 확인",sources:["service"]}})');
       await click('#operation-status-detail');await until('document.getElementById("message-dialog").open');
       await click('#notice [data-source="service"]');
       await until('document.getElementById("help-dialog").open&&document.getElementById("source-code").textContent.includes("def run_model")');
       assert.equal(await ev('document.getElementById("help-title").textContent'),'관련 소스');
       assert.equal(await ev('document.getElementById("source-path").textContent'),'backend/service.py');
       await screen('diagnostic-source');
       await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
       await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
       await until('!document.getElementById("help-dialog").open');
       await until('document.activeElement.dataset.source==="service"');
       await click('#close-message');
     }
   }
   const qa=await(await fetch(base+'/qa/state')).json();
   assert.deepEqual(qa.blocked,[]);assert.deepEqual(errors,[]);assert.deepEqual(badResponses,[]);assert.deepEqual(issues,[]);
   assert.ok(!qa.reads.includes('/api/help'));
   const report={ok:true,synthetic_data_only:true,real_database_access:false,views,issues,console_errors:errors,screenshots:out};
   fs.writeFileSync(path.join(root,'runtime/guide-cleanup-browser-verification.json'),JSON.stringify(report,null,2));
   console.log(JSON.stringify({ok:true,checks:views.length,screenshots:out}));return;
 }
 for(const key of (largeText?['basic','mission']:['basic','mission','creative'])){
   await call('Page.navigate',{url:base+'/'+key});
   await until(key==='basic'?'typeof statusPhase!=="undefined"&&statusPhase==="ready"&&!refreshing':'typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"&&!assignmentBusy');
   if(largeText)await ev('fontSize(22)');
   for(const step of (largeText?(key==='basic'?['models']:['home']):['home','data','models','predictions'])){
     if(key==='basic'){await click('#basic-workflow [data-basic-tab="'+step+'"]');await until('page==='+JSON.stringify(step)+'&&!refreshing&&statusPhase==="ready"')}
     else await click('.assignment-tabs [data-assignment-tab="'+step+'"]');
     if(key!=='basic'&&step==='data'){
       await click('#assignment-data-refresh');await until('!assignmentBusy&&document.querySelector("#assignment-data tbody tr")');
       await click('#assignment-prepared-data');await until('!assignmentBusy&&document.querySelector("#assignment-prepared-rows tbody tr")');
     }
     if(key!=='basic'&&step==='models'){await click('#assignment-evaluate');await until('!assignmentBusy&&document.querySelector("#assignment-evaluation tbody tr")')}
     if(step==='predictions'){
       if(key==='basic'){await ev('(()=>{const r=document.querySelector("#prediction-model-select input[value=CLEAN]");r.checked=true;r.dispatchEvent(new Event("change",{bubbles:true}));})()');await click('#run');await until('document.getElementById("confirm-dialog").open');await click('#accept-confirm');await until('!predictionRunning&&document.querySelector("#results tbody tr")')}
       else {await click('#assignment-predict');await until('document.getElementById("confirm-dialog").open');await click('#accept-confirm');await until('!assignmentBusy&&document.querySelector("#assignment-predictions tbody tr")')}
     }
     await screen(key+'-'+step);
     if(step==='data')await screen(key+'-prepared-result',key==='basic'?'#prepared-data':'#assignment-prepared-rows');
     if(step==='models'&&key!=='creative'){
       await click('[data-code="initial-train"]');await until('document.getElementById("execution-dialog").open&&document.getElementById("execution-code").textContent.length>80');
       await screen(key+'-coding-help');
       await codeContrast(key+'-coding-help');
       if(key==='basic'){
         await ev('document.getElementById("execution-dialog").scrollTop=140');
         await click('#execution-dialog [data-window-action="minimize"]');
         assert.ok(await ev('HelpWindow.isMinimized(document.getElementById("execution-dialog"))&&!document.getElementById("execution-dialog").open'),'Help minimize');
         await click('#help-window-dock .help-minimized:not([hidden]) button');
         assert.ok(await ev('document.getElementById("execution-dialog").open'),'Help restore');
         await click('#execution-dialog [data-window-action="maximize"]');
         assert.ok(await ev('document.getElementById("execution-dialog").classList.contains("help-maximized")'),'Help maximize');
         await click('#execution-dialog [data-window-action="maximize"]');
         assert.ok(await ev('!document.getElementById("execution-dialog").classList.contains("help-maximized")'),'Help restore size');
         await ev('document.getElementById("execution-drag").focus()');
         const left=await ev('document.getElementById("execution-dialog").getBoundingClientRect().left');
         await call('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39});
         await call('Input.dispatchKeyEvent',{type:'keyUp',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39});
         assert.equal(await ev('document.getElementById("execution-dialog").getBoundingClientRect().left'),left+10,'Keyboard move');
       }
       await click('#execution-flow [data-flow-stage="event"]');await screen(key+'-coding-source');
       await click('#close-execution');await until('!document.getElementById("execution-dialog").open');assert.ok(await ev('document.activeElement?.dataset.code==="initial-train"'),'Code help focus restoration');
     }
     if(step==='models'&&key==='creative')assert.equal(await ev('document.querySelectorAll("[data-code]").length'),0,'Creative must not gain SQL answers');
   }
   assert.equal(await ev('document.querySelectorAll("#open-help,[data-open-help],#help-content,[data-help-tab],#sql-help-template").length'),0,'Duplicate practice guide removed');

   if(key==='mission'&&!largeText){
     await click('.assignment-tabs [data-assignment-tab="home"]');
     await click('[data-mission-schema="festival"]');await until('document.getElementById("mission-schema-dialog").open&&document.getElementById("mission-schema-code").textContent.includes("CREATE TABLE")');
     await screen('mission-schema');
     await ev('document.getElementById("mission-schema-ddl").open=true;document.getElementById("mission-schema-ddl").scrollIntoView({block:"start"})');
     await screen('mission-schema-sql','#mission-schema-ddl');await click('#close-mission-schema');
     await click('[data-mission-preview="festival"]');await until('document.getElementById("mission-csv-dialog").open&&document.querySelector("#mission-csv-rows tbody tr")');
     await screen('mission-csv');await click('#close-mission-csv');
   }
 }
 const qa=await(await fetch(base+'/qa/state')).json();
 assert.deepEqual(qa.blocked,[],'All fixture API access must be explicitly configured');
 if(errors.length)issues.push({problem:'JavaScript exceptions',errors});
 if(badResponses.length)issues.push({problem:'HTTP errors',badResponses});
 const report={ok:issues.length===0,font_size:largeText?22:16,synthetic_data_only:true,real_database_access:false,widths:largeText?[1440,390]:[1440,768,390,320],height:900,views,contrasts,issues,console_errors:errors,requests:qa.reads,screenshots:out};
 fs.writeFileSync(path.join(root,largeText?'runtime/workspace-large-text-verification.json':'runtime/workspace-visual-browser-verification.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify({ok:report.ok,checks:views.length,issues,console_errors:errors,screenshots:out,report:largeText?'runtime/workspace-large-text-verification.json':'runtime/workspace-visual-browser-verification.json'}));
 if(issues.length)process.exitCode=1;
})().catch(error=>{console.error(error.message);console.error('Screenshots: '+out);process.exitCode=1}).finally(async()=>{try{if(call)await call('Browser.close')}catch{}ws?.close();browser.kill();server.kill()});

