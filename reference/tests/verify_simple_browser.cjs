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
  // FLOW는 화면 버튼 원본부터 시작하므로 검증할 단계와 파일을 명시적으로 선택합니다.
  const waitFlow=async(operation,assignment='basic')=>{
    await until("document.getElementById('execution-dialog').open&&executionFlow?.operation==="+JSON.stringify(operation)+"&&executionFlow.assignment==="+JSON.stringify(assignment)+"&&document.querySelector('.coding-flow-workspace').getAttribute('aria-busy')==='false'");
    assert.deepEqual(await evaluate('executionFlow.stages.map(stage=>stage.id)'),['ui','event','api','service','database','sql']);
    assert.equal(await evaluate("document.querySelector('#execution-flow [aria-pressed=true]').dataset.flowStage"),'ui','Help starts at the clicked screen source');
    assert.equal(await evaluate("document.querySelectorAll('[data-code-tab],[data-code-panel]').length"),0,'Flow replaces the former tabs');
    return evaluate('executionFlow');
  };
  const selectFlowSource=async(stage,criteria={})=>{
    const source=await evaluate("(()=>{const stage=executionFlow.stages.find(entry=>entry.id==="+JSON.stringify(stage)+"),criteria="+JSON.stringify(criteria)+";return stage?.items.find(item=>(!criteria.id||item.id===criteria.id)&&(!criteria.path||item.path===criteria.path)&&(!criteria.contains||item.content.includes(criteria.contains))&&(!criteria.origin||item.origin===criteria.origin))||null;})()");
    assert.ok(source,'Registered flow source '+stage+' '+JSON.stringify(criteria));
    await evaluate("(()=>{[...document.querySelectorAll('[data-flow-stage]')].find(button=>button.dataset.flowStage==="+JSON.stringify(stage)+").click();[...document.querySelectorAll('[data-flow-item]')].find(button=>button.dataset.flowItem==="+JSON.stringify(source.id)+").click();})()");
    assert.equal(await evaluate("document.getElementById('execution-code').textContent"),source.content,'Source equals its exact original range');
    assert.ok(await evaluate("!document.getElementById('execution-source-panel').hidden&&document.querySelector('#execution-items [aria-pressed=true]').dataset.flowItem==="+JSON.stringify(source.id)),'Selected source is active');
    const location=await evaluate("document.getElementById('execution-code-source').textContent");
    assert.ok(location.includes(source.path),'Source file is displayed');
    if(source.origin==='source')assert.ok(location.includes(':'+source.line),'Actual source line is displayed');
    return source;
  };
  const copyFlowSource=async source=>{
    await evaluate("document.getElementById('copy-execution').click()");
    await until("window.qaCopiedCode==="+JSON.stringify(source.content));
  };
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

  const checks=[];
  await evaluate("activateBasic('home')");await until("page==='home'&&!refreshing&&!basicSwitching");
  assert.ok(await evaluate("(()=>{const fields=[...document.querySelectorAll('.basic-object-panel .object-name-fields input')];return fields.length===3&&fields.every(input=>input.readOnly)&&fields[0].value===storage.name&&fields[1].value===predictionStorage.name&&fields[2].value==='OML_BASIC_RUN';})()"),'Basic assignment displays its actual fixed object names in the same three fields');
  await evaluate("document.querySelector('.basic-object-panel .object-naming-guide').open=true");
  assert.equal(await evaluate("document.querySelectorAll('.basic-object-panel .object-naming-guide tbody tr').length"),3,'Common naming table includes all assignments');
  await shot('basic-object-names-desktop.png');
  for(const width of [768,390,320]){await size(width,1000);assert.ok(await evaluate('document.documentElement.scrollWidth<=innerWidth'),'Object names and rules contained '+width);}
  await shot('basic-object-names-mobile.png');await size(1440,1000);
  await evaluate("document.querySelector('.basic-object-panel .object-naming-guide').open=false;activateBasic('data')");await until("page==='data'&&!refreshing&&!basicSwitching");
  const checkStepper=async()=>{
    assert.equal(await evaluate("document.querySelectorAll('.basic-tabs .workflow-tab').length"),4);
    assert.equal(await evaluate("document.querySelectorAll('.basic-tabs .workflow-next').length"),3);
    assert.ok(await evaluate("[...document.querySelectorAll('.basic-tabs .workflow-tab')].every(e=>parseFloat(getComputedStyle(e).fontSize)>=16&&Number(getComputedStyle(e).fontWeight)>=700)"),'Readable step typography');
  };
  await checkStepper();
  for(const next of ['data','models','predictions']){await evaluate(`document.querySelector('.basic-tabs [data-step-next="${next}"]').click()`);await until(`page==='${next}'&&!refreshing&&!basicSwitching`);}
  await evaluate("activateBasic('data')");await until("page==='data'&&!refreshing&&!basicSwitching");
  await shot('stepper-basic-desktop.png');
  await evaluate("activateBasic('models')");await until("page==='models'&&!refreshing&&!basicSwitching");
  assert.equal(await evaluate("document.querySelectorAll('.model-action-bar button[id]').length"),4,'Four distinct lifecycle operations');
  assert.ok(await evaluate("(()=>{const exists=models.find(m=>m.variant===document.querySelector('#model-lifecycle-mode input:checked').value)?.exists===1;return document.getElementById('model-initial').disabled===exists&&document.getElementById('model-retrain').disabled===!exists;})()"),'Initial/retrain availability follows actual model existence');
  await shot('model-lifecycle-desktop.png');
  for(const mode of ['RAW','CLEAN']){
    await evaluate(`document.querySelector('#model-lifecycle-mode input[value=${mode}]').checked=true;document.querySelector('#model-lifecycle-mode input[value=${mode}]').dispatchEvent(new Event('change',{bubbles:true}))`);
    assert.ok(await evaluate(`document.getElementById('model-lifecycle-name').textContent==='OML_BASIC_${mode}_MODEL'&&parseFloat(getComputedStyle(document.getElementById('model-lifecycle-name')).fontSize)>=18`),'Prominent selected model name');
    assert.ok(await evaluate("!document.querySelector('#model-dictionary-results details')"),'Switching model clears previous dictionary');
    await evaluate("document.getElementById('query-model-dictionary').click()");
    await until("document.querySelectorAll('#model-dictionary-results>details').length===6&&!dictionaryBusy");
    assert.ok(await evaluate(`document.querySelector('#model-dictionary-results>h3').textContent==='OML_BASIC_${mode}_MODEL'&&document.getElementById('model-dictionary-results').textContent.includes('USER_MINING_MODEL_XFORMS')`),'Six actual dictionary result groups');
    await evaluate("document.querySelector('[data-code=model-dictionary]').click()");
    const dictionaryFlow=await waitFlow('model-dictionary');
    const dictionarySql=dictionaryFlow.stages.find(stage=>stage.id==='sql').items;
    for(const name of ['USER_MINING_MODEL_ATTRIBUTES','SETTING_TYPE','USER_MINING_MODEL_VIEWS'])assert.ok(dictionarySql.some(item=>item.content.includes(name)),'Dictionary source contains '+name);
    await selectFlowSource('sql',{origin:'generated',contains:'OML_BASIC_'+mode+'_MODEL'});
    assert.ok(await evaluate("!document.getElementById('execution-warning').textContent.includes('자동 커밋')"),'Dictionary help shows read-only SQL');
    if(mode==='CLEAN')await shot('model-dictionary-help.png');
    await evaluate("document.getElementById('close-execution').click()");
  }
  await evaluate("document.querySelector('.model-target').scrollIntoView({block:'start'})");await shot('model-target-prominent.png');
  await evaluate("document.querySelector('.model-dictionary-panel').scrollIntoView({block:'start'})");await shot('model-dictionary-results.png');
  await evaluate("document.querySelector('#model-lifecycle-mode input[value=RAW]').checked=true;document.querySelector('#model-lifecycle-mode input[value=RAW]').dispatchEvent(new Event('change',{bubbles:true}))");
  for(const [op,needle] of [['initial-train',"'INIT'"],['retrain',"'RETRAIN'"],['append-train',"'ADD_TRAIN'"],['delete-model','DBMS_DATA_MINING.DROP_MODEL']]){
    await evaluate(`document.querySelector('.model-action-bar [data-code="${op}"]').click()`);await waitFlow(op);
    await selectFlowSource('sql',{contains:needle,...(op==='delete-model'?{origin:'source'}:{origin:'generated'})});
    await evaluate("document.getElementById('close-execution').click()");
  }
  for(const mode of ['RAW','CLEAN']){
    await evaluate(`document.querySelector('[data-code="confirm"][data-variant="${mode}"]').click()`);
    await waitFlow('confirm');
    assert.ok((await evaluate("document.getElementById('execution-context').textContent")).includes(mode),'Selected confirmation model is retained');
    await selectFlowSource('api',{path:'app.py',contains:'service.confirm_model(conn,'});
    await selectFlowSource('service',{path:'backend/service.py',contains:"saved['confirmed']=mode;write_state(conn,saved)"});
    assert.ok(await evaluate("document.getElementById('execution-source-kind').textContent.includes('Python')&&!!document.querySelector('#execution-code .syntax-keyword')"),'Confirmation shows actual Python saving code');
    assert.ok(await evaluate("!document.getElementById('execution-warning').textContent.includes('자동 커밋')&&!document.getElementById('execution-context').textContent.includes('현재 필터')"));
    if(mode==='CLEAN')await shot('confirmation-python-help.png');
    await evaluate("document.getElementById('close-execution').click()");
  }
  await evaluate("activateBasic('predictions')");await until("page==='predictions'&&!refreshing&&!basicSwitching");
  assert.ok(await evaluate("!!document.getElementById('prediction-model-select')&&!document.getElementById('confirm-prediction-model')"),'Model selection is owned by stage 3');
  await evaluate("activateBasic('data')");await until("page==='data'&&!refreshing&&!basicSwitching");
  // 실제 코드의 주석·키워드 색상과 원문/복사값을 함께 확인합니다.
  await evaluate(`Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async value=>{window.qaCopiedCode=value;}}})`);
  const checkIcons=async label=>{
    const result=await evaluate(`(()=>{const list=[...document.querySelectorAll('.code-help[data-code],.code-help[data-execution]')].filter(e=>e.getBoundingClientRect().width);return list.map(e=>{const r=e.getBoundingClientRect(),w=e.parentElement.getBoundingClientRect();return {question:e.textContent.trim()==='?',independent:e.previousElementSibling?.tagName==='BUTTON',enabled:!e.disabled,label:!!e.getAttribute('aria-label'),tooltip:!!document.getElementById(e.getAttribute('aria-describedby')),width:r.width,height:r.height,right:r.right,wrapperRight:w.right};});})()`);
    if(label.startsWith('creative ')){assert.equal(result.length,0,'Creative assignment has no coding-help icons');return;}
    assert.ok(result.length,label+' icons present');
    for(const icon of result){assert.ok(icon.question&&icon.independent&&icon.enabled&&icon.label&&icon.tooltip,label+' contextual help');assert.ok(icon.width>=24&&icon.width<=40&&icon.height>=24&&icon.height<=40,label+' icon size');assert.ok(Math.abs(icon.right-icon.wrapperRight)<2,label+' upper right icon');}
  };

  await evaluate("document.getElementById('filter-use').value='Y';document.getElementById('filter-split').value='TRAIN';document.getElementById('query-data').click()");
  await until('rows.length===330');

  await evaluate("document.querySelector('[data-code=\"data\"]').focus()");
  assert.equal(await evaluate("getComputedStyle(document.querySelector('[data-code=\"data\"]').nextElementSibling).visibility"),'visible','Keyboard tooltip');
  const floatingTip=await evaluate(`(()=>{const button=document.querySelector('[data-code="data"]'),tip=button.nextElementSibling,wrapper=button.parentElement,oldOverflow=wrapper.style.overflow;wrapper.style.overflow='hidden';const box=tip.getBoundingClientRect(),cover=document.createElement('div');Object.assign(cover.style,{position:'fixed',left:box.x+'px',top:box.y+'px',width:box.width+'px',height:box.height+'px',zIndex:'2147483647',background:'red'});document.body.append(cover);tip.style.pointerEvents='auto';const hit=document.elementFromPoint(box.x+box.width/2,box.y+box.height/2),result={open:tip.matches(':popover-open'),above:hit===tip,hit:hit?.className,box:box.toJSON(),viewport:innerWidth};cover.remove();tip.style.pointerEvents='';wrapper.style.overflow=oldOverflow;return result;})()`);
  assert.ok(floatingTip.open&&floatingTip.above&&floatingTip.box.left>=8&&floatingTip.box.right<=floatingTip.viewport-8,'Tooltip top layer survives ancestor clipping and higher-z sibling '+JSON.stringify(floatingTip));
  await shot('help-tooltip-top-layer.png');
  await evaluate("document.querySelector('[data-code=\"data\"]').click()");
  const dataFlow=await waitFlow('data');
  const filteredSql=await selectFlowSource('sql',{origin:'generated',contains:"'TRAIN'"});
  assert.ok(filteredSql.content.includes("'Y'"),'Current filter values are reflected in SQL');
  assert.ok(await evaluate(`(async()=>{const result=await api('/api/coding-help?operation=data&assignment=basic&variant=RAW&use_yn=Y&split=TRAIN');window.qaHelp=result;return document.getElementById('execution-code').textContent===result.script;})()`),'Selected generated SQL preserves exact API text');
  assert.ok(await evaluate(`(()=>{const root=document.getElementById('execution-code'),comment=root.querySelector('.syntax-comment'),keyword=root.querySelector('.syntax-keyword'),string=root.querySelector('.syntax-string');return root.tagName==='PRE'&&comment&&keyword&&string&&getComputedStyle(comment).color!==getComputedStyle(keyword).color&&getComputedStyle(keyword).color!==getComputedStyle(root).color;})()`),'Selected SQL comment/keyword/string coloring');
  await evaluate("document.getElementById('copy-execution').click()");
  await until("window.qaCopiedCode===document.getElementById('execution-code').textContent");
  await shot('simple-colored-plan.png');
  for(const stage of dataFlow.stages)for(const item of stage.items){
    const actual=await selectFlowSource(stage.id,{id:item.id});
    assert.equal(actual.content,item.content,'Flow retains SQL/Python/HTML/JavaScript source ranges');
  }
  const querySource=await selectFlowSource('sql',{path:'sql/queries/training_rows.sql',origin:'source'});
  assert.ok(await evaluate("!!document.querySelector('#execution-code .syntax-comment')&&!!document.querySelector('#execution-code .syntax-keyword')"),'Source SQL syntax colors are retained');
  await copyFlowSource(querySource);
  const serviceSource=await selectFlowSource('service',{path:'backend/service.py',origin:'source'});
  await copyFlowSource(serviceSource);
  const selectedFlowItem=serviceSource.id;
  await shot('simple-colored-source.png');
  assert.deepEqual(await evaluate("[...document.querySelectorAll('[data-flow-stage]')].map(button=>button.dataset.flowStage)"),['ui','event','api','service','database','sql']);
  assert.equal(await evaluate("document.querySelector('[data-code-panel=log]')===null&&document.getElementById('execution-log')===null"),true,'Legacy log panel is absent');
  assert.ok(await evaluate("!document.getElementById('execution-warning').textContent.includes('기록 탭')"));
  const bounds=await evaluate("document.getElementById('execution-dialog').getBoundingClientRect().toJSON()");
  await evaluate("document.getElementById('execution-drag').focus()");
  await call('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowRight',code:'ArrowRight'});
  const moved=await evaluate("document.getElementById('execution-dialog').getBoundingClientRect().toJSON()");
  assert.ok(moved.x>=bounds.x,'Keyboard popup move');
  await shot('simple-coding-help-desktop.png');
  // 최소화는 모달 차단을 풀고 선택 FLOW 단계·파일·코드·최대화 상태를 보존합니다.
  const checkWindow=async id=>{
    await evaluate(`(()=>{const d=document.getElementById('${id}');d.scrollTop=80;d.querySelector('[data-window-action=maximize]').click();window.qaWindowCode=d.textContent;window.qaWindowScroll=d.scrollTop;})()`);
    assert.ok(await evaluate(`(()=>{const d=document.getElementById('${id}'),r=d.getBoundingClientRect();return d.classList.contains('help-maximized')&&r.left>=0&&r.right<=innerWidth&&r.height>=innerHeight-20;})()`),'Maximized help fits viewport');
    await shot(id+'-maximized.png');
    await evaluate(`document.getElementById('${id}').querySelector('[data-window-action=minimize]').click()`);
    await until(`!document.getElementById('${id}').open`);
    assert.ok(await evaluate(`HelpWindow.isMinimized(document.getElementById('${id}'))&&!document.querySelector('dialog:modal')&&!!document.querySelector('.help-minimized:not([hidden])')`),'Minimized help releases modal blocking');
    await evaluate(`document.querySelector('.help-minimized:not([hidden]) button').click()`);await until(`document.getElementById('${id}').open`);
    assert.ok(await evaluate(`document.getElementById('${id}').classList.contains('help-maximized')&&document.getElementById('${id}').textContent===window.qaWindowCode&&Math.abs(document.getElementById('${id}').scrollTop-window.qaWindowScroll)<2`),'Restore preserves help content, scroll and maximized mode');
    await evaluate(`document.getElementById('${id}').querySelector('[data-window-action=maximize]').click()`);
    assert.ok(await evaluate(`!document.getElementById('${id}').classList.contains('help-maximized')`),'Restore previous window size');
  };
  await checkWindow('execution-dialog');
  assert.equal(await evaluate("document.querySelector('#execution-flow [aria-pressed=true]').dataset.flowStage"),'service','Selected stage survives restore');
  assert.equal(await evaluate("document.querySelector('#execution-items [aria-pressed=true]').dataset.flowItem"),selectedFlowItem,'Selected source survives restore');
  await evaluate("document.getElementById('execution-apply').open=true");
  assert.ok(await evaluate("document.getElementById('execution-apply-details').textContent.includes('USER_SOURCE')&&document.getElementById('execution-apply-command').textContent.includes('db-init.ps1')"),'DB application and verification guidance available');
  await size(390,844);assert.ok(await evaluate('document.documentElement.scrollWidth<=innerWidth'));
  for(const width of [390,320]){await size(width,844);await evaluate("document.querySelector('#execution-dialog [data-window-action=maximize]').click()");assert.ok(await evaluate("document.getElementById('execution-dialog').getBoundingClientRect().right<=innerWidth&&document.getElementById('execution-dialog').scrollWidth<=document.getElementById('execution-dialog').clientWidth+1"),'Maximized mobile content contained '+width);await evaluate("document.querySelector('#execution-dialog [data-window-action=maximize]').click()");}
  await shot('simple-coding-help-mobile.png');
  await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'});
  await until("!document.getElementById('execution-dialog').open");
  await until("document.activeElement.dataset.code==='data'");
  await size(1440,1000);
  assert.equal(await evaluate('document.querySelectorAll("#open-help,[data-open-help],#help-content,[data-help-tab]").length'),0,'Duplicate practice guide removed');
  for(const screen of ['home','data','models','predictions']){
    await evaluate(`activateBasic('${screen}')`);await until('!refreshing&&!basicSwitching');
    for(const width of [1440,1255,1024,768,390,320])for(const font of [16,22]){
      await size(width,1000);await evaluate(`fontSize(${font})`);
      const shape=await evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})');
      assert.ok(shape.scroll<=shape.width,screen+' overflow '+width+' font '+font);
      await checkIcons(screen+' '+width+' '+font);
      if(screen==='predictions')assert.ok(await evaluate('!!document.querySelector(".prediction-contract")'),'Prediction column contract visible');
      checks.push({screen,width,font});
    }
    await evaluate('fontSize(16)');
  }

  await size(320,1000);await evaluate('fontSize(22);document.querySelector(".prediction-contract").scrollIntoView()');await shot('simple-prediction-contract-mobile.png');
  await size(1440,1000);await evaluate('fontSize(16)');await shot('simple-prediction-contract-desktop.png');
  await size(1440,1000);await evaluate("document.querySelector('[data-execution=\"predict\"]').click()");
  await waitFlow('predict');
  const predictionMode=await evaluate("selectedMode('prediction-model-select')");
  await selectFlowSource('sql',{contains:'OML_BASIC_'+predictionMode+'_MODEL'});
  await evaluate("document.getElementById('close-execution').click()");
  const predictionReady=await evaluate("!document.getElementById('run').disabled");
  if(predictionReady){await evaluate("document.getElementById('run').click()");await until("!predictionRunning&&document.getElementById('result-state').textContent==='완료'");}
  else assert.ok(await evaluate("document.getElementById('prediction-ready').textContent.length>0"),'Missing confirmation is explained without changing the selected model');

  await evaluate("document.getElementById('close-execution').click()");
  for(const key of ['mission','creative']){
    await call('Page.navigate',{url:base+'/'+key});await until("typeof assignmentState!=='undefined'&&assignmentState!==null");
    assert.ok(await evaluate("!assignmentState.ready&&document.getElementById('assignment-ready-badge').dataset.state==='pending'"));
    assert.equal(await evaluate("document.querySelectorAll('#assignment-readiness-table tbody tr').length"),3,'One real readiness row per object');
    assert.ok(await evaluate("document.getElementById('operation-status').hidden"),'Initial missing objects show readiness without automatic error toast');
    assert.ok(await evaluate("document.getElementById('assignment-train').disabled"));
    assert.ok(await evaluate("document.getElementById('connection').textContent.includes('DB 연결됨')"),'DB connection success is distinct from missing assignment objects');
    await size(1440,1000);await shot('assignment-'+key+'-home-desktop.png');
    await checkStepper();
    for(const next of ['data','models','predictions']){await evaluate(`document.querySelector('.assignment-tabs [data-step-next="${next}"]').click()`);assert.equal(await evaluate("document.querySelector('.assignment-tabs [aria-current=step]').dataset.assignmentTab"),next,'Arrow advances '+key);}
    await evaluate("assignmentBusy=true;document.querySelector('.assignment-tabs [data-step-next=data]').click()");
    assert.equal(await evaluate("document.querySelector('.assignment-tabs [aria-current=step]').dataset.assignmentTab"),'predictions','Arrow respects DB operation guard');
    await evaluate("assignmentBusy=false;dismissMessage();document.querySelector('[data-assignment-tab=home]').click()");
    await size(390,1000);await shot('assignment-'+key+'-home-mobile.png');
    for(const tab of ['home','data','models','predictions']){
      await evaluate(`document.querySelector('[data-assignment-tab="${tab}"]').click()`);
      if(tab==='models'){
        await evaluate("document.getElementById('assignment-initial').closest('details').open=true");
        assert.ok(await evaluate("document.getElementById('assignment-initial').disabled&&document.getElementById('assignment-retrain').disabled"),'Optional lifecycle waits for assignment implementation');
      }
      await until(`(()=>{const active=document.querySelector('.assignment-tabs [aria-current=step]'),other=document.querySelector('.assignment-tabs [aria-current=false]');return active.dataset.assignmentTab==='${tab}'&&getComputedStyle(active).borderBottomColor!==getComputedStyle(other).borderBottomColor;})()`);
      assert.ok(await evaluate(`(()=>{const active=document.querySelector('.assignment-tabs [aria-current=step]'),other=document.querySelector('.assignment-tabs [aria-current=false]');return active.dataset.assignmentTab==='${tab}'&&document.querySelectorAll('.assignment-tabs [aria-current=step]').length===1&&getComputedStyle(active).borderBottomColor!==getComputedStyle(other).borderBottomColor;})()`),'Distinct selected tab '+key+' '+tab);
      for(const width of [1440,1255,1024,768,390,320])for(const font of [16,22]){await size(width,1000);await evaluate(`fontSize(${font})`);assert.ok(await evaluate('document.documentElement.scrollWidth<=innerWidth'),key+' '+tab+' overflow '+width+' font '+font);await checkIcons(key+' '+tab+' '+width+' '+font);checks.push({screen:key+'-'+tab,width,font});}
      await evaluate('fontSize(16)');
    }
    if(key==='mission'){
      await evaluate(`document.querySelector('[data-assignment-tab=data]').click()`);
      await until("document.getElementById('mission-dataset').options.length===11");
      await evaluate("document.getElementById('mission-dataset').selectedIndex=1;document.getElementById('mission-dataset').dispatchEvent(new Event('change'))");
      assert.ok(await evaluate("!document.getElementById('mission-fields').hidden&&!document.getElementById('mission-download').hidden&&!document.getElementById('mission-prediction-download').hidden&&document.querySelectorAll('#mission-fields tbody tr').length>5"),'Mission catalog data and field descriptions');
      await size(1440,1000);await shot('assignment-mission-data-desktop.png');
      await size(320,1000);assert.ok(await evaluate('document.documentElement.scrollWidth<=innerWidth'),'Selected mission fields contained on mobile');
    }
    await evaluate(`document.querySelector('[data-assignment-tab=home]').click();document.getElementById('assignment-diagnostic').click()`);
    assert.ok(await evaluate("!document.getElementById('operation-status').hidden&&document.getElementById('notice').textContent.includes('02_procedure.sql')"),'Explicit diagnostic provides assignment SQL path');
    await evaluate("dismissMessage();document.querySelector('[data-assignment-tab=predictions]').click()");
    if(key==='mission'){
      await evaluate("document.querySelector('[data-code=\"predict\"]').click()");await waitFlow('predict','mission');
      await selectFlowSource('sql',{origin:'generated',contains:'_MODEL'});
      await selectFlowSource('sql',{path:'sql/custom/mission/02_procedure.sql',origin:'generated'});
      await shot('simple-'+key+'-help.png');await evaluate("document.getElementById('close-execution').click()");
    }else assert.equal(await evaluate("document.querySelectorAll('[data-code],[data-execution]').length"),0,'Creative assignment does not expose coding examples');
  }
  // 강사 교재의 실제 발췌와 모바일 레이아웃도 확인합니다.
  await call('Page.navigate',{url:base+'/instructor/python-web-lecture.html'});
  for(let i=0;i<100;i++){if(await evaluate('!!document.getElementById("source-manifest")'))break;await pause(100);}
  assert.equal(await evaluate('document.querySelectorAll("[data-snippet]").length'),20);
  assert.equal(await evaluate('document.querySelectorAll(".chapter").length'),13);
  for(const width of [1440,768,390,320]){await size(width,1000);assert.ok(await evaluate('document.documentElement.scrollWidth<=innerWidth'),'lecture overflow '+width);}
  await size(1440,1000);await shot('simple-instructor-lecture.png');
  const sourceUrl=await evaluate('document.querySelector("[data-lecture-source=call]").href');
  assert.ok(sourceUrl.endsWith('/instructor/lecture-source/call'));
  await call('Page.navigate',{url:sourceUrl});
  for(let i=0;i<100;i++){if(await evaluate("document.body.textContent.includes('def run_model(')"))break;await pause(100);}
  assert.ok(await evaluate("document.body.textContent.includes('def run_model(')"));
  assert.deepEqual(errors,[]);
  const report={ok:true,real_database:true,prediction_executed:predictionReady,tooltip_above_clipping_and_overlays:true,coding_flow_source_colors:true,framework_flow_groups:true,legacy_code_tabs_removed:true,exact_source_and_copy_text:true,question_icon_tooltip:true,disabled_action_help:true,prediction_contract:true,layout_checks:checks.length,sql_filter_values:true,drag_keyboard_escape_focus:true,missing_assignment_guidance:true,assignment_readiness_rows_and_active_tabs:true,mission_catalog:true,instructor_excerpts:20,instructor_responsive:true,console_errors:errors.length};
  fs.writeFileSync(path.join(runtime,'simple-browser-verification.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
})().catch(error=>{console.error(error.message);process.exitCode=1;}).finally(async()=>{
  try{if(call)await call('Browser.close');}catch{}ws?.close();for(let i=0;i<30&&browser.exitCode===null;i++)await pause(100);if(browser.exitCode===null)browser.kill();
  preview.kill();
  assert.ok(path.resolve(profile).startsWith(path.resolve(runtime)+path.sep+'design-browser-'));try{fs.rmSync(profile,{recursive:true,force:true,maxRetries:10,retryDelay:200});}catch{}
});
