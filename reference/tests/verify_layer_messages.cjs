// 전용 Headless Edge를 열어 실제 실행 중인 이 프로젝트의 화면과 Oracle 응답을 확인합니다.
// 적재·모델 생성은 하지 않습니다. 인증 값과 실제 명단은 출력·보고서에 쓰지 않습니다.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {spawn,spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'../..'),runtime=path.join(root,'runtime');
const profile=fs.mkdtempSync(path.join(runtime,'design-browser-'));
const pause=ms=>new Promise(r=>setTimeout(r,ms));
const edge=process.env.EDGE_EXE||'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const browser=spawn(edge,['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--remote-debugging-address=127.0.0.1','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
let ws,call;
const preview=spawn(path.join(root,'.venv/Scripts/python.exe'),['-u',path.join(__dirname,'design_preview_server.py')],{cwd:root,windowsHide:true,stdio:['ignore','pipe','ignore']});
const previewUrl=new Promise((resolve,reject)=>{let buffer='';preview.stdout.on('data',chunk=>{buffer+=chunk;const m=buffer.match(/RESEARCH_QA_URL=(http:\/\/127\.0\.0\.1:\d+)/);if(m)resolve(m[1]);});preview.on('error',reject);preview.on('exit',code=>reject(new Error('Isolated preview exited '+code)));});
browser.on('error',error=>{console.error('Browser launch failed:',error.code);process.exitCode=1;});
(async()=>{
  const config=spawnSync(path.join(root,'.venv/Scripts/python.exe'),['-c',"import json; from backend.db import student_settings; c=student_settings(); print(json.dumps({'user':c['DB_USER'],'password':c['DB_PASSWORD']}))"],{cwd:root,encoding:'utf8',windowsHide:true});
  assert.equal(config.status,0,'Local configuration unavailable');
  const cfg=JSON.parse(config.stdout),people=JSON.parse(fs.readFileSync(path.join(root,'security/students.json'),'utf8').replace(/^\uFEFF/,''));
  const person=people.find(p=>p.db_user.toUpperCase()===cfg.user.toUpperCase());assert.ok(person);
  const info=JSON.parse(fs.readFileSync(path.join(runtime,'service.json'),'utf8').replace(/^\uFEFF/,''));
  assert.equal(path.resolve(info.root),root,'Running server must belong to this project');
  const base=await previewUrl;
  const portFile=path.join(profile,'DevToolsActivePort');
  for(let i=0;i<200&&!fs.existsSync(portFile);i++)await pause(100);
  assert.ok(fs.existsSync(portFile),'Headless browser did not start');
  const port=fs.readFileSync(portFile,'utf8').split('\n')[0];
  const tabs=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();
  ws=new WebSocket(tabs.find(t=>t.type==='page').webSocketDebuggerUrl);
  let sequence=0;const pending=new Map(),errors=[];
  ws.onmessage=event=>{const d=JSON.parse(event.data);if(d.method==='Runtime.exceptionThrown')errors.push(d.params.exceptionDetails.text);if(d.id){const p=pending.get(d.id);pending.delete(d.id);d.error?p.reject(d.error):p.resolve(d.result);}};
  await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
  call=(method,params={})=>new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
  const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw new Error('Browser assertion: '+(r.exceptionDetails.exception?.description||r.exceptionDetails.text).split('\n')[0]);return r.result.value;};
  const until=async expression=>{for(let i=0;i<200;i++){if(await evaluate(expression))return;await pause(100);}throw new Error('Browser timed out: '+expression+' '+JSON.stringify(await evaluate('({notice:document.getElementById("notice")?.textContent,feedback:[...document.querySelectorAll(".action-feedback")].map(e=>e.textContent),page,refreshing,person:!!person})'))+' '+JSON.stringify(errors));};
  const size=(width,height)=>call('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<600});
  const shot=async name=>{await evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');const r=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(runtime,name),Buffer.from(r.data,'base64'));};
  await call('Page.enable');await call('Runtime.enable');await call('Emulation.setFocusEmulationEnabled',{enabled:true});await call('Page.bringToFront');await size(1440,1000);
  await call('Page.navigate',{url:base+'/basic#data'});
  await until('typeof csrf!=="undefined"&&csrf&&document.getElementById("top-login")');
  assert.equal(await evaluate('document.getElementById("identity-dialog").open'),false,'Initial visit shows intro only');
  assert.ok(await evaluate('document.body.dataset.auth==="locked"&&getComputedStyle(document.querySelector(".workspace")).display==="none"&&document.querySelector(".workspace").inert'));
  const introChecks=[];
  for(const width of [1440,1255,1024,768,390,320])for(const font of [16,22]){
    await size(width,1000);await evaluate(`fontSize(${font})`);
    const shape=await evaluate('(()=>{const content=document.querySelector(".login-gate-content").getBoundingClientRect(),button=document.getElementById("gate-login").getBoundingClientRect();return {width:content.width,center:content.x+content.width/2,viewport:document.body.getBoundingClientRect().width,buttonWidth:button.width,scroll:document.documentElement.scrollWidth};})()');
    assert.ok(shape.width<=720&&Math.abs(shape.center-shape.viewport/2)<=2,'Centered intro '+width+' '+JSON.stringify(shape));
    assert.ok(shape.buttonWidth<=240&&shape.scroll<=width,'Compact intro '+width);
    assert.equal(await evaluate('document.getElementById("identity-dialog").open'),false);
    introChecks.push({width,font,centered:true});
  }
  await size(1440,1000);await evaluate('fontSize(16)');await shot('research-intro-desktop.png');
  await size(390,844);await shot('research-intro-mobile.png');await size(1440,1000);
  await evaluate('document.getElementById("gate-login").click()');await until('document.getElementById("identity-dialog").open');
  assert.ok(await evaluate('!document.getElementById("cancel-identity").hidden'));
  await shot('research-login-desktop.png');
  await evaluate('document.getElementById("cancel-identity").click()');await until('!document.getElementById("identity-dialog").open');
  assert.ok(await evaluate('document.body.dataset.auth==="locked"&&document.activeElement.id==="gate-login"'));
  await evaluate('document.getElementById("gate-login").click();document.getElementById("close-identity").click()');
  await until('!document.getElementById("identity-dialog").open');
  assert.equal(await evaluate('document.getElementById("top-login").textContent'),'로그인');
  await until("document.getElementById('top-login')&&!document.getElementById('top-login').hidden");await evaluate("document.getElementById('gate-login').click()");await until("document.getElementById('identity-dialog')?.open");
  await evaluate(`document.getElementById('login-id').value=${JSON.stringify(String(person.student_id))};document.getElementById('login-name').value=${JSON.stringify(person.name)};document.getElementById('login-password').value=${JSON.stringify(cfg.password)};document.getElementById('login-submit').click()`);
  await until("!document.getElementById('identity-dialog').open&&!refreshing&&rows.length===720");


  const nativeDialogs=[];ws.addEventListener('message',event=>{const item=JSON.parse(event.data);if(item.method==='Page.javascriptDialogOpening'){nativeDialogs.push(item.params.type);call('Page.handleJavaScriptDialog',{accept:false});}});
  await evaluate(`window.qaWrites=[];window.qaWriteBodies=[];window.qaOriginalApi=api;api=async(path,body)=>{if(body!==undefined){window.qaWrites.push(path);window.qaWriteBodies.push(body);return {message:'검증용 완료',operation:'replaced',loaded_rows:720,storage:{qualified_name:storage?.qualified_name||'OML_BASIC_DATA',object_id:storage?.object_id}};}return window.qaOriginalApi(path,body);};modelAction=async(button,fn)=>{window.qaModelButton=button?.id;await fn();};`);
  const closed=async()=>{await until("!document.getElementById('confirm-dialog').open&&pendingLayerConfirmation===null");await evaluate('new Promise(r=>requestAnimationFrame(r))');};
  const open=async code=>{await evaluate('(()=>{'+code+';})()');await until("document.getElementById('confirm-dialog').open");assert.equal(await evaluate('document.activeElement.id'),'cancel-confirm','Cancel receives initial focus');};
  const cancel=async method=>{if(method==='Escape')await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'});else await evaluate(`document.getElementById('${method}').click()`);await closed();};
  const exercise=async(code,path)=>{
    for(const method of ['cancel-confirm','close-confirm','Escape']){const before=await evaluate('window.qaWrites.length');await open(code);await cancel(method);assert.equal(await evaluate('window.qaWrites.length'),before,'Cancellation must not mutate '+path);}
    const before=await evaluate('window.qaWrites.length');await open(code);await evaluate("document.getElementById('accept-confirm').click()");await closed();await until(`window.qaWrites.length===${before+1}&&activeTasks===0`);assert.equal(await evaluate('window.qaWrites.at(-1)'),path,'Exactly one intercepted mutation after confirmation');
  };
  assert.ok(await evaluate("!document.querySelector('[data-delete],[data-edit],#add-row')"),'No row editor');
  await evaluate("selectedFile=new File(['CASE_ID\\n1\\n'],'layer-test.csv',{type:'text/csv'})");
  await exercise("window.qaAction=importTraining('replace',document.getElementById('import-submit'))",'/api/data/import');
  await evaluate("document.getElementById('recreate-training').closest('details').open=true");
  await exercise("window.qaAction=importTraining('recreate',document.getElementById('recreate-training'))",'/api/data/import');
  await evaluate("document.querySelector('#preparation-mode input[value=CLEAN]').checked=true");
  await exercise("window.qaAction=prepareTraining(document.getElementById('prepare-data'))",'/api/data/prepare');
  assert.equal(await evaluate('window.qaWriteBodies.at(-1).variant'),'CLEAN','Preparation preserves the selected mode across confirmation');
  await evaluate("activateBasic('predictions')");await until("page==='predictions'&&!refreshing&&!basicSwitching");
  await evaluate("selectedPrediction=new File(['CASE_ID\\n1\\n'],'prediction-test.csv',{type:'text/csv'});predictionStorage={...predictionStorage,rows:30,qualified_name:'OML_BASIC_PREDICT'}");
  await exercise("window.qaAction=importPrediction(document.getElementById('prediction-import-submit'))",'/api/predictions/import');
  await evaluate("activateBasic('models')");await until("page==='models'&&!refreshing&&!basicSwitching");
  await evaluate("document.querySelector('#model-lifecycle-mode input[value=CLEAN]').checked=true;document.querySelector('#model-lifecycle-mode input[value=CLEAN]').dispatchEvent(new Event('change',{bubbles:true}))");
  await exercise("document.getElementById('model-delete').dispatchEvent(new MouseEvent('click',{bubbles:true}))",'/api/models/delete');
  assert.equal(await evaluate('window.qaModelButton'),'model-delete','Async handler preserves event button reference');
  assert.equal(await evaluate('window.qaWriteBodies.at(-1).variant'),'CLEAN','Deletion uses the selected radio mode');
  await exercise("document.getElementById('model-retrain').dispatchEvent(new MouseEvent('click',{bubbles:true}))",'/api/models/train');
  assert.deepEqual(await evaluate('window.qaWriteBodies.at(-1)'),{variant:'CLEAN',action:'RETRAIN'},'Full retraining uses the selected radio mode');
  assert.deepEqual(await evaluate('window.qaWriteBodies.at(-1)'),{variant:'CLEAN',action:'ADD_TRAIN'},'Additional TRAIN rebuilds only the selected radio mode');
  // 중복 확인은 실행하지 않고 원래 요청의 취소·확인만 기다립니다.
  await open("window.qaDecision=askConfirmation('중복 확인 테스트',{title:'레이어 메시지 검증',opener:document.getElementById('query-models')})");
  assert.equal(await evaluate("askConfirmation('duplicate')"),false);await cancel('cancel-confirm');assert.equal(await evaluate('window.qaDecision'),false);
  for(const width of [1440,390,320])for(const font of [16,22]){
    await size(width,900);await evaluate(`fontSize(${font})`);
    await open("window.qaDecision=askConfirmation(('선택 모델을 삭제합니다. 데이터와 다른 모델은 유지됩니다.\\n').repeat(20),{title:'선택 모델 삭제 확인',accept:'모델 삭제',danger:true})");
    const before=await evaluate("document.getElementById('confirm-dialog').getBoundingClientRect().toJSON()");
    await evaluate("document.querySelector('#confirm-dialog [data-window-drag]').focus()");await call('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowRight',code:'ArrowRight'});
    assert.ok(await evaluate(`(()=>{const d=document.getElementById('confirm-dialog'),r=d.getBoundingClientRect(),b=document.getElementById('accept-confirm').getBoundingClientRect();return r.x>=${before.x}&&r.right<=innerWidth&&r.height<=innerHeight*.85+1&&b.bottom<=r.bottom&&document.documentElement.scrollWidth<=innerWidth;})()`),'Movable responsive confirmation '+width+' '+font);
    if(font===16)await shot('layer-confirm-'+width+'.png');await cancel('Escape');
  }
  // 추가 내용 없는 알림은 자세히 보기를 표시하거나 빈 상세 창을 열지 않습니다.
  await size(1440,1000);await evaluate("fontSize(16);notice('같은 내용만 있는 알림',true)");
  assert.ok(await evaluate("document.getElementById('operation-status-detail').hidden"),'A one-line message has no details button');
  await evaluate('showMessageDetails()');
  assert.equal(await evaluate("document.getElementById('message-dialog').open"),false,'Calling details for a simple notice is harmless');
  await evaluate("presentMessage('같은 내용만 있는 알림','error','<p>같은 내용만 있는 알림</p>')");
  assert.ok(await evaluate("document.getElementById('operation-status-detail').hidden"),'Wrapping the same message in markup does not make it additional detail');
  await evaluate("presentMessage('다음 작업을 확인하세요','warning','<p>다음 작업을 확인하세요</p><ol><li>OML_MISSION_DATA 테이블을 생성하세요.</li><li>01_tables.sql을 SQL Developer에서 F5 실행하세요.</li></ol>')");
  assert.equal(await evaluate("document.getElementById('operation-status-detail').hidden"),false,'A concrete object and repair steps enable details');
  await evaluate("showMessageDetails();document.querySelector('#message-dialog [data-window-drag]').focus()");
  assert.ok(await evaluate("document.getElementById('notice').textContent.includes('OML_MISSION_DATA')&&document.getElementById('notice').textContent.includes('01_tables.sql')"),'The detail view contains information beyond the toast');
  const detailBefore=await evaluate("document.getElementById('message-dialog').getBoundingClientRect().x");await call('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowRight',code:'ArrowRight'});assert.ok(await evaluate(`document.getElementById('message-dialog').getBoundingClientRect().x>${detailBefore}`));
  await evaluate("document.getElementById('close-message').click();notice('하단 알림 이동 확인');document.getElementById('operation-status-text').focus()");
  const toastBefore=await evaluate("document.getElementById('operation-status').getBoundingClientRect().x");await call('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowLeft',code:'ArrowLeft'});assert.ok(await evaluate(`document.getElementById('operation-status').getBoundingClientRect().x<${toastBefore}`));
  await evaluate('dismissMessage()');
  const fixtures=spawnSync(path.join(root,'.venv/Scripts/python.exe'),['-c',"import json,sys; sys.path.insert(0,'reference/tests'); from test_oml_lab import OmlLabTests,tasks; t=OmlLabTests(); result={};\nfor key in ('mission','creative'):\n result[key]={}\n for label,options in [('missing',{'absent':('training_table','prediction_table','prepared_table','procedure_name')}),('invalid',{'invalid':('procedure_name',),'errors':({'line':7,'text':'PLS-00103: test compile error'},)}),('arguments',{'bad_arguments':True})]:\n  state=t.assignment_readiness(key,**options); state.update(diagnostic=tasks.diagnostic(key,'status',state),models=[],preparation={}); result[key][label]=state\nprint(json.dumps(result))"],{cwd:root,encoding:'utf8',windowsHide:true});
  assert.equal(fixtures.status,0,'Readiness fixtures use production diagnostics with mocked metadata');
  const readinessCases=JSON.parse(fixtures.stdout);
  for(const assignment of ['mission','creative']){
    await call('Page.navigate',{url:base+'/'+assignment});await until("typeof assignmentTask==='function'&&person&&!assignmentBusy");
    await until("assignmentState!==null&&document.getElementById('connection').textContent.includes('연결됨')");
    await evaluate('window.qaStatusOriginalApi=api;window.qaStatusFixture=null;window.qaStatusFailure=null;api=async(path,body)=>{if(path===`/api/assignments/${assignmentKey}/status`){if(window.qaStatusFailure){const e=new Error(window.qaStatusFailure.title);e.diagnostic=window.qaStatusFailure;throw e;}if(window.qaStatusFixture)return window.qaStatusFixture;}return window.qaStatusOriginalApi(path,body);};');
    for(const [kind,fixture] of Object.entries(readinessCases[assignment])){
      await evaluate(`window.qaStatusFixture=${JSON.stringify(fixture)};loadAssignmentReadiness()`);
      assert.ok(await evaluate("document.getElementById('connection').textContent.includes('연결됨')&&!document.getElementById('connection').classList.contains('bad')"),'Object '+kind+' is not a failed DB connection');
      const statusText=await evaluate("document.getElementById('assignment-readiness-table').textContent");
      assert.ok(statusText.includes('OML_'+assignment.toUpperCase()+'_RUN'));
      assert.ok(!/DB 접속 오류|접속 실패/.test(await evaluate("document.getElementById('assignment-readiness-summary').textContent+' '+document.getElementById('assignment-next-description').textContent")));
      assert.ok(statusText.includes(kind==='missing'?'미생성':kind==='invalid'?'컴파일':'인자'),'Object repair reason remains visible: '+kind);
      if(kind==='missing'){
        await evaluate("document.getElementById('assignment-diagnostic').click()");
        assert.equal(await evaluate("document.getElementById('operation-status-detail').hidden"),false);
        await evaluate('showMessageDetails()');
        assert.ok(await evaluate("document.getElementById('notice').textContent.includes('CREATE TABLE OML_'+assignmentKey.toUpperCase()+'_DATA')&&document.getElementById('notice').textContent.includes('CREATE OR REPLACE PROCEDURE OML_'+assignmentKey.toUpperCase()+'_RUN')"),'Explicit setup details contain executable examples');
        for(const width of [1440,390,320]){
          await size(width,900);
          assert.ok(await evaluate("document.documentElement.scrollWidth<=innerWidth&&document.getElementById('message-dialog').getBoundingClientRect().right<=innerWidth"),'Creation examples stay inside the viewport '+width);
        }
        await size(1440,1000);await evaluate("document.getElementById('close-message').click()");
      }
    }
    for(const category of ['query','connection']){
      const failure={category,db_connected:category==='query',title:category==='query'?'과제 상태 조회를 마치지 못했습니다.':'DB에 연결하지 못했습니다.',code:category==='query'?'READINESS-QUERY':'DPY-6005',steps:[category==='query'?'객체 상태 조회를 다시 실행하세요.':'네트워크와 DB 실행 상태를 확인하세요.']};
      await evaluate(`window.qaStatusFailure=${JSON.stringify(failure)};loadAssignmentReadiness().catch(operationNotice)`);
      const label=await evaluate("document.getElementById('connection').textContent");
      assert.ok(category==='query'?label.includes('연결됨'):!label.includes('연결됨'),'Connection and query failure have different connection badges');
      assert.ok(await evaluate("!document.getElementById('assignment-readiness-table').textContent.includes('PLS-00103')&&document.getElementById('assignment-predict').disabled"),'Failed refresh clears old diagnostics and blocks work');
    }
    await evaluate('api=window.qaStatusOriginalApi;loadAssignmentReadiness();dismissMessage()');
    await until("assignmentState!==null&&document.getElementById('connection').textContent.includes('연결됨')");
    await evaluate("document.querySelector('[data-assignment-tab=models]').click()");
    await evaluate("window.qaAssignmentActions=[];window.qaAssignmentVariants=[];assignmentTask=async(button,action,file,variant)=>{window.qaAssignmentActions.push(action);window.qaAssignmentVariants.push(variant);window.qaAssignmentButton=button?.id;};");
    await open("document.getElementById('assignment-delete-model').dispatchEvent(new MouseEvent('click',{bubbles:true}))");await cancel('close-confirm');assert.equal(await evaluate('window.qaAssignmentActions.length'),0);
    await open("document.getElementById('assignment-delete-model').dispatchEvent(new MouseEvent('click',{bubbles:true}))");await evaluate("document.getElementById('accept-confirm').click()");await closed();assert.deepEqual(await evaluate('window.qaAssignmentActions'),['delete-model']);assert.equal(await evaluate('window.qaAssignmentButton'),'assignment-delete-model');
    await evaluate("document.querySelector('[data-assignment-tab=data]').click();window.qaAssignmentActions=[];document.querySelector('#assignment-preparation-mode input[value=CLEAN]').checked=true");
    for(const method of ['cancel-confirm','close-confirm','Escape']){
      await open("document.getElementById('assignment-prepare').dispatchEvent(new MouseEvent('click',{bubbles:true}))");await cancel(method);
      assert.equal(await evaluate('window.qaAssignmentActions.length'),0,'Canceled preparation cannot write');
    }
    await open("document.getElementById('assignment-prepare').dispatchEvent(new MouseEvent('click',{bubbles:true}))");await evaluate("document.getElementById('accept-confirm').click()");await closed();
    assert.deepEqual(await evaluate('window.qaAssignmentActions'),['prepare']);assert.equal(await evaluate('window.qaAssignmentVariants.at(-1)'),'CLEAN');
  }
  assert.deepEqual(nativeDialogs,[]);assert.deepEqual(errors,[]);
  const report={ok:true,native_dialogs:0,confirmation_flows:11,cancel_close_escape:true,duplicate_suppressed:true,explicit_accept_only:true,selected_radio_mode_preserved:true,preparation_confirmation_all_tasks:true,duplicate_details_hidden:true,repair_details_visible:true,assignment_failure_cases:10,creation_example_viewports:6,responsive_cases:6,movable_confirmation_details_and_notifications:true,db_mutations_intercepted:true};
  fs.writeFileSync(path.join(runtime,'layer-messages-verification.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
})().catch(error=>{console.error(error.message);process.exitCode=1;}).finally(async()=>{
  try{if(call)await call('Browser.close');}catch{}ws?.close();for(let i=0;i<30&&browser.exitCode===null;i++)await pause(100);if(browser.exitCode===null)browser.kill();
  preview.kill();
  assert.ok(path.resolve(profile).startsWith(path.resolve(runtime)+path.sep+'design-browser-'));try{fs.rmSync(profile,{recursive:true,force:true,maxRetries:10,retryDelay:200});}catch{}
});
