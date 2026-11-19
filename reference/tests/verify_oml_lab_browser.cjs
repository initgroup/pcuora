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
  ws.onmessage=event=>{const d=JSON.parse(event.data);if(d.method==='Runtime.exceptionThrown')errors.push(d.params.exceptionDetails.exception?.description||d.params.exceptionDetails.text);if(d.id){const p=pending.get(d.id);pending.delete(d.id);d.error?p.reject(d.error):p.resolve(d.result);}};
  await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
  call=(method,params={})=>new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
  const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw new Error('Browser assertion: '+(r.exceptionDetails.exception?.description||r.exceptionDetails.text).split('\n')[0]);return r.result.value;};
  const until=async expression=>{for(let i=0;i<200;i++){if(await evaluate(expression))return;await pause(100);}throw new Error('Browser timed out: '+expression+' '+JSON.stringify(await evaluate('({notice:document.getElementById("notice")?.textContent,feedback:[...document.querySelectorAll(".action-feedback")].map(e=>e.textContent),page,refreshing,person:!!person})'))+' '+JSON.stringify(errors));};
  const size=(width,height)=>call('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<600});
  const shot=async name=>{await evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');const r=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(runtime,name),Buffer.from(r.data,'base64'));};
  const chooseMode=async(id,mode)=>evaluate(`(()=>{const radio=document.querySelector('#${id} input[type=radio][value=${mode}]');radio.checked=true;radio.dispatchEvent(new Event('change',{bubbles:true}));})()`);
  const checkModes=async id=>{
    const modeGroup=await evaluate(`(()=>{const group=document.getElementById('${id}'),radios=[...group.querySelectorAll('input[type=radio]')];return {fieldset:group.tagName==='FIELDSET',legend:!!group.querySelector('legend')?.textContent.trim(),values:radios.map(r=>r.value),checked:radios.filter(r=>r.checked).length,visible:radios.every(r=>r.getBoundingClientRect().width>0&&r.labels.length>0),select:!!group.querySelector('select')};})()`);
    assert.deepEqual(modeGroup,{fieldset:true,legend:true,values:['RAW','CLEAN'],checked:1,visible:true,select:false},'Both labeled mode choices remain visible: '+id);
  };
  const flowData=async()=>{
    await until('document.getElementById("execution-dialog").open&&typeof executionFlow!=="undefined"&&executionFlow?.stages.length===6');
    const flow=await evaluate('executionFlow');
    assert.deepEqual(flow.stages.map(stage=>stage.id),['ui','event','api','service','database','sql']);
    assert.equal(await evaluate('document.querySelectorAll("[data-code-tab],[data-code-panel]").length'),0,'Old coding tabs are absent');
    return flow;
  };
  const selectFlowSource=async(stageId,predicate)=>{
    const flow=await flowData(),stage=flow.stages.find(entry=>entry.id===stageId),item=stage.items.find(predicate);
    assert.ok(item,'Requested source exists in '+stageId+' flow');
    await evaluate('document.querySelector('+JSON.stringify('[data-flow-stage="'+stageId+'"]')+').click()');
    await evaluate('document.querySelector('+JSON.stringify('[data-flow-item="'+item.id+'"]')+').click()');
    assert.equal(await evaluate('document.getElementById("execution-code").textContent'),item.content,'Selected source preserves exact text');
    assert.ok((await evaluate('document.getElementById("execution-code-source").textContent')).includes(item.path),'Source path is visible');
    if(item.origin==='source'){
      const lines=fs.readFileSync(path.join(root,item.path),'utf8').replace(/^\uFEFF/,'').split(/\r?\n/);
      assert.equal(item.content,lines.slice(item.line-1,item.end_line).join('\n'),'Exact original contiguous source range');
    }else{
      assert.equal(item.line,null);assert.equal(item.end_line,null,'Generated SQL has no fabricated file lines');
    }
    return item;
  };
  const checkCodeBoxes=async()=>assert.ok(await evaluate('(()=>{const code=document.getElementById("execution-code"),s=getComputedStyle(code);return !document.getElementById("execution-source-panel").hidden&&!["transparent","rgba(0, 0, 0, 0)"].includes(s.backgroundColor)&&parseFloat(s.borderTopWidth)>0&&parseFloat(s.paddingLeft)>0;})()'),'Selected code has a background, border and padding');
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

  if(process.argv.includes('--recreate-fixture-only')){
    const fixture=source=>evaluate('(async()=>{'+source+'})()');
    await evaluate("document.querySelector('[data-code=initialize]').click()");
    await selectFlowSource('sql',item=>item.path==='sql/classifier.sql'&&item.content.includes('CREATE OR REPLACE PROCEDURE'));
    await evaluate("$('execution-code').scrollTop=$('execution-code').scrollHeight;$('close-execution').click();selectedFile=new File(['QA fixture only'],'QA-reload.csv',{type:'text/csv'});document.querySelector('[data-code=recreate]').click()");
    const recreateFlow=await flowData(),sourcePaths=recreateFlow.stages.find(stage=>stage.id==='sql').items.map(item=>item.path);
    assert.ok(sourcePaths.indexOf('sql/recreate_training.sql')<sourcePaths.indexOf('sql/schema.sql')&&sourcePaths.indexOf('sql/schema.sql')<sourcePaths.indexOf('sql/queries/insert_training.sql'),'Recreate flow orders DROP, CREATE and CSV VALUES sources');
    const drop=await selectFlowSource('sql',item=>item.path==='sql/recreate_training.sql');
    assert.ok(drop.content.includes('DROP TABLE OML_BASIC_DATA')&&!drop.content.includes('OML_BASIC_PREDICT'),'DROP only targets original DATA');
    assert.ok(await evaluate("$('execution-code').scrollTop===0&&$('execution-code').scrollLeft===0"),'Source selection resets code scroll');
    const create=await selectFlowSource('sql',item=>item.path==='sql/schema.sql');
    assert.ok(create.content.includes('CREATE TABLE OML_BASIC_DATA')&&!create.content.includes('CREATE TABLE OML_BASIC_PREDICT')&&!create.content.includes('CREATE OR REPLACE PROCEDURE'),'DATA definition stays separate');
    const insert=await selectFlowSource('sql',item=>item.path==='sql/queries/insert_training.sql');
    assert.ok(insert.content.includes('INSERT INTO OML_BASIC_DATA')&&insert.content.includes('VALUES')&&insert.content.includes(':case_id'),'CSV rows use VALUES bindings');
    const handler=await selectFlowSource('event',item=>item.content.includes('async function importTraining('));
    assert.ok(handler.content.includes('selectedFile'),'Actual handler reads the selected CSV');
    const importApi=await selectFlowSource('api',item=>item.content.includes('def import_data('));
    assert.ok(importApi.content.indexOf('parse_csv(')<importApi.content.indexOf('recreate_training.sql')&&importApi.content.includes('load_csv('),'CSV validation precedes DROP and recreation precedes loading');
    assert.equal(await evaluate('selectedFile.name'),'QA-reload.csv','Selected CSV remains intact during help');
    const recreateHelp=await evaluate("api('/api/coding-help?operation=recreate&assignment=basic')");
    assert.ok(recreateHelp.script.includes('DROP TABLE '+person.db_user+'.OML_BASIC_DATA')&&recreateHelp.application.summary.includes('메모리')&&recreateHelp.application.summary.includes('INSERT VALUES'),'Owner-qualified direct reference explains CSV origin');
    await selectFlowSource('sql',item=>item.path==='sql/queries/insert_training.sql');
    for(const width of [1440,768,390,320]){await size(width,900);assert.ok(await evaluate('document.documentElement.scrollWidth<=innerWidth'),'Recreate help overflow '+width);}
    await size(1440,900);await shot('recreate-help-desktop.png');
    await evaluate("$('close-execution').click()");
    await fixture(`window.qaRealApi=api;window.qaStatus=await api('/api/status');window.qaConfirm=askConfirmation;
      window.qaStatus.state.total_rows=0;window.qaStatus.state.train_rows=0;window.qaStatus.state.test_rows=0;
      window.qaStatus.preparation={};window.qaStatus.models=window.qaStatus.models.map(m=>({...m,is_current:0,is_confirmed:0}));
      window.qaStatusCalls=0;window.qaImportCalls=0;
      askConfirmation=async message=>{window.qaConfirmText=message;return true;};
      api=async(path,...args)=>{if(path==='/api/data/import'){window.qaImportCalls++;const error=new Error('QA: INSERT failed after DROP');error.diagnostic={title:'QA 격리 응답 · 재생성 INSERT 실패',message:'원본 삭제 완료 · 이전 원본은 롤백되지 않습니다.',steps:['같은 CSV를 일반 교체 적재하세요.']};throw error;}if(path==='/api/status'){window.qaStatusCalls++;return structuredClone(window.qaStatus);}return window.qaRealApi(path,...args);};
      await importTraining('recreate',$('recreate-training'));`);
    assert.ok(await evaluate("window.qaImportCalls===1&&window.qaStatusCalls===1&&state.total_rows===0&&$('storage-rows').textContent==='0행'"),'Failed recreation reloads actual status rather than retaining the old row count');
    assert.ok(await evaluate("window.qaConfirmText.includes('DROP → CREATE')&&window.qaConfirmText.includes('INSERT VALUES')&&window.qaConfirmText.includes('롤백되지 않습니다')&&$('prepare-data').disabled"),'Confirmation and post-failure controls distinguish irreversible drop from missing source rows');
    await fixture("api=window.qaRealApi;askConfirmation=window.qaConfirm;selectedFile=null;await refresh();");
    assert.deepEqual(errors,[]);
    const report={ok:true,help_scroll_reset:true,drop_create_csv_values:true,selected_csv_reader_traced:true,failure_status_reloaded:true,responsive_widths:[1440,768,390,320],database_changes:false};
    fs.writeFileSync(path.join(runtime,'recreate-browser-verification.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));return;
  }

  // 표시 회귀 검증: 브라우저 안의 응답만 교체하며 DB 변경 API는 호출하지 않습니다.
  if(process.argv.includes('--status-fixtures-only')){
    const fixture=source=>evaluate('(async()=>{'+source+'})()');
    await fixture(`activateBasic('home')`);await until("page==='home'&&!refreshing&&!basicSwitching&&activeTasks===0");
    await fixture(`window.qaRealApi=api;window.qaStatus=await api('/api/status');window.qaInitCalls=0;
      window.qaStatus.initialized=true;window.qaStatus.state.total_rows=720;
      window.qaStatus.models=['RAW','CLEAN'].map(variant=>({variant,model_name:'OML_BASIC_'+variant+'_MODEL',exists:0,is_current:0,is_confirmed:0}));
      window.qaStatus.preparation={RAW:{ready:false,rows:0,fit_rows:0,test_rows:0}};
      api=async(path,...args)=>{if(path==='/api/status')return structuredClone(window.qaStatus);if(path==='/api/initialize'){window.qaInitCalls++;return {};}return window.qaRealApi(path,...args);};
      await refresh();`);
    assert.ok(await evaluate("!$('initialize-basic').disabled&&$('basic-objects-state').textContent==='준비 완료'&&$('initialize-basic').textContent==='프로시저 다시 등록'"),'Completed preparation stays available for explicit SQL reapply');
    await fixture("$('initialize-basic').click()");await until("$('confirm-dialog').open");await evaluate("$('accept-confirm').click()");await until('activeTasks===0');
    assert.ok(await evaluate("window.qaInitCalls===1&&!$('initialize-basic').disabled&&statusPhase==='ready'"),'Initialize refreshes status inside its mutation and unlocks afterwards');
    await fixture("api=async path=>path==='/api/status'?new Promise(resolve=>window.qaResolve=resolve):{};window.qaPending=refresh();void 0;");
    assert.ok(await evaluate("$('initialize-basic').disabled&&$('basic-objects-state').textContent==='확인 중'"),'Pending status has an explicit temporary reason');
    await fixture("window.qaResolve(structuredClone(window.qaStatus));await window.qaPending;");
    assert.ok(await evaluate("!$('initialize-basic').disabled"),'Refresh restores the preparation button');
    await fixture("renderModelLifecycle()");
    assert.ok(await evaluate("$('model-initial').disabled&&$('model-initial-status').textContent.includes('전처리 저장 필요')&&!$('model-lifecycle-state').textContent.includes('최초 생성 가능')"),'Unprepared data never claims first training is available');
    await fixture("preparation.RAW={ready:true,rows:690,fit_rows:330,test_rows:360};renderModelLifecycle()");
    assert.ok(await evaluate("!$('model-initial').disabled&&$('model-retrain').disabled&&$('model-delete-status').textContent.includes('삭제할 대상')"),'New and existing model actions have distinct prerequisites');
    await fixture("models[0].exists=1;models[0].is_current=1;renderModelLifecycle()");
    assert.ok(await evaluate("$('model-initial-status').textContent.includes('이미 생성됨')&&!$('model-retrain').disabled&&!$('model-delete').disabled"),'Completed initial training explains why it is disabled');
    await fixture("preparation.RAW.fit_rows=0;renderModelLifecycle()");
    assert.ok(await evaluate("$('model-retrain').disabled&&$('model-retrain-status').textContent.includes('0행')"),'Zero fit rows blocks training with a visible reason');
    await fixture("api=async()=>{throw new Error('QA status failure');};try{await refresh();}catch{};renderModelLifecycle()");
    assert.ok(await evaluate("$('basic-objects-state').textContent==='확인 미완료'&&$('model-lifecycle-state').textContent.includes('조회 실패')&&!$('model-lifecycle-state').textContent.includes('모델 없음')"),'Failed status is unknown, never a missing model');
    await fixture("api=async()=>structuredClone(window.qaStatus);await refresh();");
    assert.ok(await evaluate("!$('initialize-basic').disabled&&statusPhase==='ready'"),'Successful retry clears the failure');
    await size(1440,900);await shot('status-basic-ready.png');
    await fixture("page='predictions';renderBasicWorkspace();models[0].exists=1;models[0].is_current=1;models[0].is_confirmed=1;state.confirmed_current=1;predictionStorage.rows=0;renderPredictionStorage();");
    assert.ok(await evaluate("!$('confirm-prediction-model')&&$('prediction-model-help').textContent.includes('바로 실행')&&$('run').disabled&&$('prediction-ready').textContent.includes('입력 없음')"),'Already confirmed and missing prediction input have separate explanations');
    await fixture("predictionStorage.rows=30;renderPredictionStorage()");
    assert.ok(await evaluate("!$('run').disabled&&$('prediction-ready').textContent.includes('준비 완료')"),'Confirmed model plus input enables prediction');
    await fixture("statusPhase='error';renderPredictionStorage()");
    assert.ok(await evaluate("$('run').disabled&&$('prediction-ready').textContent.includes('조회 실패')&&$('prediction-storage-state').textContent==='확인 미완료'"),'Prediction query failure is unknown, not missing input');
    await fixture("page='data';renderBasicWorkspace();renderStorage()");
    assert.ok(await evaluate("$('query-data').disabled&&$('data-action-status').textContent.includes('조회 실패')&&$('storage-state').textContent==='확인 미완료'"),'Training data page explains failed queries');
    for(const key of ['mission','creative']){
      await call('Page.navigate',{url:base+'/'+key});
      await until("typeof assignmentPhase!=='undefined'&&assignmentPhase==='ready'&&!assignmentBusy");
      await fixture(`window.qaRealApi=api;window.qaAssignment=await api('/api/assignments/${key}/status');
        window.qaAssignment.ready=true;window.qaAssignment.missing=[];window.qaAssignment.issues=[];
        window.qaAssignment.objects=Object.entries(window.qaAssignment.config).map(([field,object_name])=>({object_name,object_type:field==='procedure_name'?'PROCEDURE':'TABLE',status:'VALID'}));
        window.qaAssignment.models=['RAW','CLEAN'].map(variant=>({variant,exists:0,is_current:0}));
        window.qaAssignment.preparation={RAW:{ready:false,rows:0,fit_rows:0,test_rows:0}};
        api=async()=>structuredClone(window.qaAssignment);await loadAssignmentReadiness();`);
      assert.ok(await evaluate("!$('assignment-check').disabled&&$('assignment-initial').disabled&&$('assignment-model-preparation').textContent.includes('전처리 저장 필요')"),key+' object readiness and preparation are distinct');
      await fixture("assignmentState.preparation.RAW={ready:true,rows:690,fit_rows:330,test_rows:360};renderAssignmentControls()");
      assert.ok(await evaluate("Array.from(document.querySelectorAll('[data-manual-action]')).every(button=>button.disabled)&&!$('assignment-check').disabled"),key+' preparation is visible while creation stays in direct SQL');
      await fixture("assignmentState.models[0].exists=1;assignmentState.models[0].is_current=1;renderAssignmentControls()");
      assert.ok(await evaluate("$('assignment-initial').disabled&&$('assignment-model-state').textContent.includes('연계 확인됨')&&!$('assignment-evaluate').disabled&&!$('assignment-predict').disabled"),key+' completed model and current actions');
      await fixture("assignmentState.models[0].is_current=0;renderAssignmentControls()");
      assert.ok(await evaluate("$('assignment-evaluate').disabled&&$('assignment-predict').disabled&&$('assignment-predict-status').textContent.includes('최신이 아닙니다')"),key+' stale model explanation');
      await fixture("api=async()=>{throw new Error('QA readiness failure');};try{await loadAssignmentReadiness();}catch{};");
      assert.ok(await evaluate("!$('assignment-check').disabled&&$('assignment-prepared-status').textContent.includes('조회 실패')&&$('assignment-model-state').textContent.includes('조회 실패')&&$('assignment-predict-status').textContent.includes('조회 실패')"),key+' failure is retryable and never presented as unprepared');
      await fixture("api=async()=>structuredClone(window.qaAssignment);await loadAssignmentReadiness();");
      for(const step of ['home','data','models','predictions']){
        await fixture(`document.querySelector('[data-assignment-tab="${step}"]').click()`);
        for(const width of [1440,768,390,320]){await size(width,900);assert.ok(await evaluate('document.documentElement.scrollWidth<=innerWidth'),key+' status overflow '+step+' '+width);}
      }
      await size(1440,900);await shot('status-'+key+'-prediction.png');
    }
    assert.deepEqual(errors,[]);
    const report={ok:true,basic_refresh_unlock:true,initialize_refresh:true,missing_vs_unknown:true,zero_fit_rows:true,model_action_reasons:true,assignment_retry:true,responsive_widths:[1440,768,390,320],database_changes:false};
    fs.writeFileSync(path.join(runtime,'status-browser-verification.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));return;
  }


  const checks=[];
  for(const pageName of (process.argv.includes('--prepared-fixture-only')?['data']:['home','data','models','predictions'])){
    await evaluate(`activateBasic('${pageName}')`);await until(`page==='${pageName}'&&!refreshing&&!basicSwitching`);
    assert.ok(await evaluate("![...document.querySelectorAll('[data-basic-panel]:not([hidden]) h2,[data-basic-panel]:not([hidden]) h3,#model-mode-effect,#prediction-mode-rule')].some(e=>/\\?{2,}/.test(e.textContent))"),'Korean operation headings and conditions remain readable');
    if(pageName==='home')assert.ok(await evaluate("(()=>{const fields=[...document.querySelectorAll('.basic-object-panel .object-name-fields input')];return fields.length===4&&fields.every(e=>e.readOnly)&&fields.some(e=>e.value===person.db_user+'.OML_BASIC_PREPARED');})()"),'Home shows the source, prepared, prediction tables and procedure');
    if(pageName==='data'){
      assert.ok(await evaluate("!document.querySelector('#add-row,#row-form,[data-edit],[data-delete]')"),'Row mutation controls removed');
      await checkModes('preparation-mode');
      for(const mode of ['RAW','CLEAN']){
        await chooseMode('preparation-mode',mode);
        await evaluate("document.querySelector('[data-code=prepare]').click()");
        await selectFlowSource('sql',item=>item.origin==='source'&&item.content.includes('INSERT INTO OML_BASIC_PREPARED')&&item.content.includes("PREP_MODE = '"+mode+"'"));
        const preparationCall=await selectFlowSource('sql',item=>item.origin==='generated'&&item.content.includes("OML_BASIC_RUN('PREPARE', '"+mode+"'"));
        assert.ok(preparationCall.content.includes(person.db_user+'.OML_BASIC_RUN'),'Preparation direct call preserves owner and radio mode');
        await checkCodeBoxes();await evaluate("document.getElementById('close-execution').click()");
      }
      await size(1440,900);await evaluate('scrollTo(0,0)');
      assert.ok(await evaluate("document.getElementById('prepared-data').getBoundingClientRect().top<innerHeight&&document.getElementById('prepare-data').getBoundingClientRect().bottom<innerHeight"),'Preparation conditions, execution and result table stay together');
      // 데이터가 아직 없는 실제 DB를 바꾸지 않고 표 가독성만 합성 행으로 확인합니다.
      await until('activeTasks===0&&!refreshing&&!preparing');
      for(const width of [1440,768,390,320]){
        await size(width,900);
        await evaluate("(()=>{++preparedRequest;const fixture=[{case_id:900001,prep_mode:'CLEAN',source_kind:'TRAIN',fit_yn:'Y',exclude_reason:null,return_pct:1.25,range_pct:2.5,volume_change_pct:null,close_price:0,stock:'  <QA>&'+String.fromCharCode(10)+'  ',signal:'BUY',week_ending:'2011-01-07',use_yn:'Y',probability:0.123456789,custom_feature:'unknown'},{case_id:900002,prep_mode:'CLEAN',source_kind:'TRAIN',fit_yn:'N',exclude_reason:'표시 검증용 제외 사유',return_pct:null,range_pct:2.5,volume_change_pct:null,close_price:100,stock:'QA_SAMPLE',signal:'SELL',week_ending:'2011-01-07',use_yn:'N'}];table('prepared-data',fixture,preparedColumns(fixture),{database:true});text('prepared-status','QA 합성 행 · 표 표시만 검증 · 실제 DB 결과 아님');document.getElementById('prepared-data').scrollIntoView({block:'center'});})()");
        assert.equal(await evaluate("document.querySelectorAll('#prepared-data tbody tr').length"),2,'Synthetic fixture remains visible without a stale query overwriting it');
        assert.deepEqual(await evaluate("[...document.querySelectorAll('#prepared-data thead .column-name')].slice(0,3).map(e=>e.textContent)"),['CASE_ID','FIT_YN','EXCLUDE_REASON']);
        assert.deepEqual(await evaluate("[...document.querySelectorAll('#prepared-data thead .column-description')].slice(0,3).map(e=>e.textContent)"),['사례번호','학습 제공 여부','제외 사유']);
        assert.deepEqual(await evaluate("(()=>{const keys=[...document.querySelectorAll('#prepared-data thead .column-name')].map(e=>e.textContent),rows=[...document.querySelectorAll('#prepared-data tbody tr')],cell=(row,key)=>rows[row].children[keys.indexOf(key)].textContent;return [cell(0,'SIGNAL'),cell(1,'SIGNAL'),cell(0,'VOLUME_CHANGE_PCT'),cell(0,'CLOSE_PRICE'),cell(0,'PROBABILITY'),cell(0,'STOCK'),cell(0,'CUSTOM_FEATURE')];})()"),['BUY','SELL','','0','0.123456789','  <QA>&\n  ','unknown'],'DB values retain labels, NULL, zero, precision, whitespace and custom fields');
        assert.ok(await evaluate("![...document.querySelectorAll('#prepared-data tbody td')].some(cell=>cell.children.length)&&getComputedStyle(document.querySelector('#prepared-data tbody td')).whiteSpace==='pre'"),'Raw cells preserve whitespace without splitting values or creating HTML labels');
        await shot(`oml-lab-prepared-fixture-${width}.png`);assert.ok(await evaluate('document.documentElement.scrollWidth<=innerWidth'));
      }
      await evaluate('loadPreparedRows()');await evaluate('renderPreparation()');
      if(process.argv.includes('--prepared-fixture-only')){console.log(JSON.stringify({ok:true,prepared_fixture_rows:2,original_column_headers:true,raw_cell_values:true,widths:[1440,768,390,320],database_changes:false}));return;}
    }
    if(pageName==='models'){
      await checkModes('model-lifecycle-mode');
      await chooseMode('model-lifecycle-mode','RAW');
      await evaluate("document.querySelector('#model-lifecycle-mode input[value=RAW]').focus()");
      await call('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39});
      await call('Input.dispatchKeyEvent',{type:'keyUp',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39});
      assert.ok(await evaluate("document.querySelector('#model-lifecycle-mode input[value=CLEAN]').checked&&document.getElementById('model-lifecycle-name').textContent.includes('CLEAN')"),'Keyboard radio navigation updates the target model');
      assert.equal(await evaluate("document.querySelectorAll('.model-action-bar button[id]').length"),4);
      assert.ok(await evaluate("!document.querySelector('#model-add-file,#train-both,[data-train]')"));
      for(const mode of ['RAW','CLEAN'])for(const operation of ['initial-train','retrain','append-train','delete-model']){
        await chooseMode('model-lifecycle-mode',mode);
        assert.ok(await evaluate(`document.getElementById('model-lifecycle-name').textContent.includes('OML_BASIC_${mode}_MODEL')`),'Target model follows the selected radio');
        assert.ok(await evaluate(`(()=>{const exists=models.find(m=>m.variant==='${mode}')?.exists===1,ready=Boolean(preparation['${mode}']?.ready);return document.getElementById('model-initial').disabled===(!ready||exists)&&['model-retrain'].every(id=>document.getElementById(id).disabled===(!ready||!exists))&&document.getElementById('model-delete').disabled===!exists;})()`),'Training requires prepared rows; deleting requires only an existing model');
        assert.ok(await evaluate(`document.getElementById('model-training-condition').textContent.includes("PREP_MODE = '${mode}'")&&document.getElementById('model-training-condition').textContent.includes("FIT_YN = 'Y'")`),'Visible training condition matches selected prepared partition');
        await evaluate(`document.querySelector('[data-code="${operation}"]').click()`);
        const flow=await flowData(),sqlItems=flow.stages.find(stage=>stage.id==='sql').items;
        const command=await selectFlowSource('sql',item=>item.origin==='source'&&item.content.includes('DBMS_DATA_MINING.')&&item.content.includes('OML_BASIC_'+mode+'_MODEL'));
        assert.ok(command.content.includes('OML_BASIC_'+mode+'_MODEL'),'Oracle command targets selected model');
        const expectedSections=await evaluate("api('/api/coding-help?operation="+operation+"&variant="+mode+"&assignment=basic').then(help=>help.oracle_sections)");
        for(const section of expectedSections){
          const matching=sqlItems.find(item=>item.origin==='source'&&item.path===section.path&&item.line===section.line&&item.end_line===section.end_line&&item.content===section.content);
          assert.ok(matching,'Every original Oracle section remains accessible');
          await selectFlowSource('sql',item=>item.id===matching.id);
        }
        assert.ok(await evaluate("!$('execution-code-source').hidden&&$('execution-code-source').textContent.includes('sql/classifier.sql:')&&$('copy-execution').textContent==='이 구간 복사'"),'File positions and copying distinguish excerpts from generated calls');
        if(operation==='initial-train'){
          const query=await selectFlowSource('sql',item=>item.title.startsWith('실행 3')&&item.content.includes('p_sql :='));
          assert.ok(query.content.includes("PREP_MODE = '"+mode+"'"),'INIT assigns selected prepared SQL');
          const action=await selectFlowSource('sql',item=>item.title.startsWith('실행 4')&&item.content.includes('validate_prepared;'));
          assert.ok(action.content.trimEnd().endsWith('END IF;')&&action.content.includes('OPEN p_result FOR'),'INIT preserves complete validation/action/result branch');
        }
        const direct=await selectFlowSource('sql',item=>item.origin==='generated'&&item.content.includes(':executed_sql'));
        assert.ok(direct.content.includes(person.db_user+'.OML_BASIC_RUN')&&!direct.content.includes('def append_training')&&direct.content.includes("'"+mode+"'"),'Direct call preserves owner and selected mode without unrelated Python');
        await checkCodeBoxes();
        await evaluate("document.getElementById('close-execution').click()");
      }
      await evaluate("document.querySelector('[data-code=evaluate][data-variant=BOTH]').click()");
      const comparisonCall=await selectFlowSource('sql',item=>item.origin==='generated'&&item.content.includes("OML_BASIC_RUN('EVALUATE', 'RAW',"));
      assert.ok(comparisonCall.content.includes("OML_BASIC_RUN('EVALUATE', 'CLEAN',")&&(comparisonCall.content.match(/OML_BASIC_RUN\('EVALUATE'/g)||[]).length===2,'Comparison supplies both actual evaluation calls');
      assert.ok(await evaluate('document.getElementById("execution-context").textContent.includes("BOTH")'),'Comparison context keeps both models');
      await evaluate("document.getElementById('close-execution').click()");
      await size(1440,1000);
      await evaluate("document.querySelector('[data-code=initial-train]').click()");await selectFlowSource('sql',item=>item.origin==='source'&&item.content.includes('CREATE_MODEL2'));await shot('oml-lab-help.png');await evaluate("document.getElementById('close-execution').click()");
      await size(1440,900);await evaluate('scrollTo(0,0)');
      const core=await evaluate("(()=>{const actions=[...document.querySelectorAll('.model-action-bar button[id]')].map(e=>e.getBoundingClientRect()),comparison=document.getElementById('model-comparison').getBoundingClientRect(),accuracy=document.getElementById('accuracy-RAW').closest('tr').getBoundingClientRect(),visibleBottom=Math.min(innerHeight,document.getElementById('model-comparison').closest('.table-wrap').getBoundingClientRect().bottom);return {actionBottom:Math.max(...actions.map(r=>r.bottom)),comparisonTop:comparison.top,accuracyBottom:accuracy.bottom,comparisonBottom:comparison.bottom,visibleBottom};})()");
      await shot('oml-lab-basic-models-compact-1440.png');
      assert.ok(core.actionBottom<900&&core.comparisonTop<900&&core.comparisonBottom<=core.visibleBottom+1,'Mode, operations and complete core comparison visible together: '+JSON.stringify(core));
    }else if(pageName!=='home') {
      const tableName=cfg.user+'.'+(pageName==='data'?'OML_BASIC_DATA':'OML_BASIC_PREDICT');
      assert.ok(await evaluate(`[...document.querySelectorAll('code')].some(e=>e.textContent.trim()==='${tableName}'&&e.getBoundingClientRect().width>0)`),'Visible actual table name: '+tableName);
      if(pageName==='predictions'){
        assert.ok(await evaluate("!!document.getElementById('prediction-model-select')&&!document.getElementById('confirm-prediction-model')"),'Model selection exists only in stage 3');
        assert.ok(await evaluate("document.getElementById('prediction-model-help').textContent.length>0"),'Prediction shows the confirmed model or the stage 3 action');
        await size(1440,900);await evaluate('scrollTo(0,0)');
        assert.ok(await evaluate("document.getElementById('results').getBoundingClientRect().top<innerHeight"),'Prediction inputs, run button and result area stay together');
        await shot('oml-lab-basic-predictions-compact-1440.png');
      }
    }
    for(const width of [1440,768,390,320]){
      await size(width,1000);assert.ok(await evaluate('document.documentElement.scrollWidth<=innerWidth'),'Basic overflow '+pageName+' '+width);
      if(width===1440||width===390)await shot(`oml-lab-basic-${pageName}-${width}.png`);checks.push('basic '+pageName+' '+width);
    }
  }
  for(const key of ['mission','creative']){
    await call('Page.navigate',{url:base+'/'+key});await until("typeof assignmentState!=='undefined'&&assignmentState!==null&&!assignmentBusy");
    assert.ok(await evaluate("[...document.querySelectorAll('#assignment-connection input')].every(e=>e.readOnly)"));
    assert.ok(await evaluate("!document.getElementById('assignment-save')"));
    for(const step of ['home','data','models','predictions']){
      await evaluate(`document.querySelector('[data-assignment-tab="${step}"]').click()`);
      assert.ok(await evaluate("![...document.querySelectorAll('[data-assignment-panel]:not([hidden]) h2,[data-assignment-panel]:not([hidden]) h3,#assignment-mode-effect')].some(e=>/\\?{2,}/.test(e.textContent))"),'Korean assignment conditions remain readable');
      if(step==='home'){
        assert.equal(await evaluate("document.querySelectorAll('#assignment-connection input').length"),4,'All four fixed DB objects are visible');
        if(key==='mission'){
          assert.ok(await evaluate("document.querySelectorAll('[data-mission-card]').length===10&&document.querySelectorAll('[data-mission-card] a[href^=\"/download/datasets/\"]').length===20&&document.querySelectorAll('#mission-dataset option').length===11"),'Ten numbered examples and both CSV links are available before object preparation');
          const examples=await evaluate('missionDatasets.map(item=>({key:item.key,title:item.title}))');
          for(const item of examples){
            await evaluate(`document.querySelector('[data-mission-choice="${item.key}"]').click()`);
            if(await evaluate("$('confirm-dialog').open"))await evaluate("$('accept-confirm').click()");
            await until("!missionSelectionSaving");
            assert.ok(await evaluate(`$('mission-dataset').value===${JSON.stringify(item.key)}&&$('mission-selection-note').textContent.includes(${JSON.stringify(item.title)})&&$('mission-data-selection').textContent.includes(${JSON.stringify(item.title)})&&$('mission-prediction-selection').textContent.includes(${JSON.stringify(item.title)})&&document.querySelectorAll('[data-mission-choice][aria-pressed="true"]').length===1`),'Home selection stays consistent with data and prediction: '+item.key);
          }
          await evaluate("$('mission-dataset').value='esports';$('mission-dataset').dispatchEvent(new Event('change'))");
          if(await evaluate("$('confirm-dialog').open"))await evaluate("$('accept-confirm').click()");
          await until("!missionSelectionSaving");
          assert.ok(await evaluate("document.querySelector('[data-mission-choice=esports]').getAttribute('aria-pressed')==='true'&&$('mission-download').getAttribute('href')==='/download/datasets/esports?kind=training'&&!$('mission-download').hidden"),'Data selection synchronizes the home card and download');
        }
      }
      if(step==='data'){
        await checkModes('assignment-preparation-mode');await chooseMode('assignment-preparation-mode','CLEAN');
        assert.ok(await evaluate("document.getElementById('assignment-prepare').disabled&&document.getElementById('assignment-prepare').hasAttribute('data-manual-action')"),key+' prepares only through direct SQL');
        if(key==='mission'){
          await evaluate("document.querySelector('[data-code=prepare]').click()");
          const missionPreparation=await selectFlowSource('sql',item=>item.origin==='generated'&&item.content.includes("OML_MISSION_RUN('PREPARE', 'CLEAN'"));
          assert.ok(missionPreparation.content.includes(person.db_user+'.OML_MISSION_RUN'),'Mission preparation keeps owner and CLEAN mode');
          await checkCodeBoxes();await evaluate("document.getElementById('close-execution').click()");
        }else assert.equal(await evaluate("document.querySelectorAll('[data-code]').length"),0,'Creative provides no query help');
        await size(1440,900);await evaluate('scrollTo(0,0)');
        assert.ok(await evaluate("document.getElementById('assignment-prepared-rows').getBoundingClientRect().top<innerHeight"),key+' preparation actions and results stay together');
      }
      if(step==='models'){
        await checkModes('assignment-mode');
        assert.equal(await evaluate("document.querySelectorAll('.model-action-bar button[id]').length"),4);
        await chooseMode('assignment-mode','CLEAN');
        assert.ok(await evaluate("Array.from(document.querySelectorAll('.model-action-bar button[data-manual-action]')).every(button=>button.disabled)"),key+' model creation and deletion stay in direct SQL');
        if(key==='mission'){
          await evaluate("document.querySelector('[data-code=initial-train]').click()");
          const missionModel=await selectFlowSource('sql',item=>item.origin==='generated'&&item.content.includes('CREATE_MODEL2'));
          assert.ok(missionModel.content.includes(person.db_user+'.OML_MISSION_CLEAN_MODEL'),'Selected mission definition keeps owner-qualified CLEAN model');
          const missionCall=await selectFlowSource('sql',item=>item.origin==='generated'&&item.content.includes("OML_MISSION_RUN('INIT', 'CLEAN'"));
          assert.ok(missionCall.content.includes(person.db_user+'.OML_MISSION_RUN'),'Mission INIT is an owner-qualified generated manual call');
          await checkCodeBoxes();await evaluate("document.getElementById('close-execution').click()");
        }else assert.equal(await evaluate("document.querySelectorAll('[data-code]').length"),0,'Creative provides no model SQL');
      }
      if(step==='predictions'){
        await checkModes('assignment-predict-mode');
        await size(1440,900);await evaluate('scrollTo(0,0)');
        assert.ok(await evaluate("document.getElementById('assignment-predictions').getBoundingClientRect().top<innerHeight"),key+' prediction inputs, run button and result area stay together');
        await shot(`oml-lab-${key}-predictions-compact-1440.png`);
      }
      for(const width of [1440,768,390,320]){
        await size(width,1000);assert.ok(await evaluate('document.documentElement.scrollWidth<=innerWidth'),key+' '+step+' overflow '+width);checks.push(key+' '+step+' '+width);
        if(width!==320)await shot(`oml-lab-${key}-${step}-${width}.png`);
      }
    }
  }
  await evaluate("assignmentHistory=[];assignmentPreviousPrediction=null;recordAssignmentLab('predict','RAW',[{case_id:1,predicted:'A',probability:0.8}],'same');recordAssignmentLab('predict','CLEAN',[{case_id:1,predicted:'B',probability:0.9}],'same')");
  assert.ok(await evaluate("assignmentHistory[0].comparison.includes('예측 1행 변경')"));
  await evaluate("recordAssignmentLab('predict','CLEAN',[{case_id:1,predicted:'B',probability:0.9}],'changed')");
  assert.ok(await evaluate("assignmentHistory[0].comparison.includes('비교하지 않음')"));
  await evaluate('resetAssignmentWorkspace()');
  assert.deepEqual(errors,[]);
  const report={ok:true,real_login_and_metadata:true,row_editor_removed:true,fixed_assignment_names:true,oracle_flow_commands:true,direct_call_examples:true,table_and_model_banners:true,visible_radio_modes:true,keyboard_radio_navigation:true,preparation_controls_and_conditions:true,code_examples_boxed:true,all_four_steps_checked:true,compact_model_actions_and_comparison:true,responsive_checks:checks,console_errors:errors};
  fs.writeFileSync(path.join(runtime,'oml-lab-browser-verification.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
})().catch(error=>{console.error(error.message);process.exitCode=1;}).finally(async()=>{
  try{if(call)await call('Browser.close');}catch{}ws?.close();for(let i=0;i<30&&browser.exitCode===null;i++)await pause(100);if(browser.exitCode===null)browser.kill();
  preview.kill();
  assert.ok(path.resolve(profile).startsWith(path.resolve(runtime)+path.sep+'design-browser-'));try{fs.rmSync(profile,{recursive:true,force:true,maxRetries:10,retryDelay:200});}catch{}
});
