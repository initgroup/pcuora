const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const root=path.resolve(__dirname,'../..'),out=fs.mkdtempSync(path.join(os.tmpdir(),'mission-csv-ui-')),pause=ms=>new Promise(r=>setTimeout(r,ms));
const server=spawn(path.join(root,'.venv/Scripts/python.exe'),['-B',path.join(__dirname,'mission_csv_preview_server.py')],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
let serverErrors='';server.stderr.on('data',c=>serverErrors+=c);const url=new Promise((resolve,reject)=>{let s='';server.stdout.on('data',c=>{s+=c;const m=s.match(/CSV_QA_URL=(http:\/\/127\.0\.0\.1:\d+)/);if(m)resolve(m[1])});server.on('error',reject);server.on('exit',code=>reject(new Error('Fixture exit '+code+' '+serverErrors)))});
const profile=path.join(out,'profile'),browser=spawn('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});let ws;
(async()=>{const pf=path.join(profile,'DevToolsActivePort');for(let i=0;i<100&&!fs.existsSync(pf);i++)await pause(100);const port=fs.readFileSync(pf,'utf8').split('\n')[0],tabs=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();ws=new WebSocket(tabs.find(t=>t.type==='page').webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});let seq=0;const pending=new Map(),errors=[];ws.onmessage=e=>{const d=JSON.parse(e.data);if(d.method==='Runtime.exceptionThrown')errors.push(d.params.exceptionDetails.exception?.description||d.params.exceptionDetails.text);if(d.id){const p=pending.get(d.id);pending.delete(d.id);d.error?p.reject(d.error):p.resolve(d.result)}};const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))});const ev=async expression=>{const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});assert.ok(!r.exceptionDetails,JSON.stringify(r.exceptionDetails));return r.result.value};const until=async expression=>{for(let i=0;i<150;i++){if(await ev(expression))return;await pause(50)}throw new Error('Timed out '+expression+' '+JSON.stringify(errors)+' '+JSON.stringify(await ev('({status:document.getElementById("mission-csv-status")?.textContent,rows:document.querySelectorAll("#mission-csv-rows tbody tr").length,request:missionCsvRequest,key:missionCsvKey,open:document.getElementById("mission-csv-dialog")?.open,html:document.getElementById("mission-csv-rows")?.innerHTML.slice(0,100),basic:document.getElementById("basic-csv-status")?.textContent})')))};const size=width=>call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});const shot=async name=>{const s=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(s.data,'base64'))};await call('Page.enable');await call('Runtime.enable');await call('Emulation.setFocusEmulationEnabled',{enabled:true});await call('Page.bringToFront');await size(1440);await call('Page.navigate',{url:(await url)+'/mission'});await until('typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"');assert.equal(await ev('assignmentState.ready'),false);assert.equal(await ev('document.querySelectorAll("[data-mission-preview]").length'),12);
if(process.argv.includes('--paging-only')){
 const results=[];
 for(const prefix of ['mission','basic']){
  await call('Page.navigate',{url:(await url)+'/'+prefix});
  await until(prefix==='mission'?'typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"':'typeof basicCsvKind!=="undefined"&&person?.db_user==="QA"&&!refreshing');
  await ev('HelpWindow.closeAll();dismissMessage();window.qaCsvApi=api;window.qaHoldCsv=false;api=async(...args)=>{const result=await qaCsvApi(...args);if(qaHoldCsv&&args[0].includes("/preview?"))await new Promise(resolve=>window.qaCsvRelease=resolve);return result}');
  const ready=()=>until('document.querySelector("#'+prefix+'-csv-rows table")&&!document.getElementById("'+prefix+'-csv-rows").hasAttribute("aria-busy")');
  const measure=()=>ev('(()=>{const d=document.getElementById("'+prefix+'-csv-dialog"),r=document.getElementById("'+prefix+'-csv-rows"),p=d.querySelector(".mission-csv-pagination"),t=d.querySelector(".mission-csv-toolbar");return {dialogTop:d.getBoundingClientRect().top,dialogHeight:d.getBoundingClientRect().height,scroll:d.scrollTop,full:d.scrollHeight,pageTop:p.getBoundingClientRect().top,rowsHeight:r.getBoundingClientRect().height,row:r.scrollTop,left:r.scrollLeft,maxLeft:r.scrollWidth-r.clientWidth,maxRow:r.scrollHeight-r.clientHeight,toolbar:t.getBoundingClientRect().height,outer:scrollY,rows:r.querySelectorAll("tbody tr").length}})()');
  const stable=(before,after,label)=>{
   for(const key of ['dialogTop','dialogHeight','scroll','full','pageTop','rowsHeight','toolbar','outer'])assert.ok(Math.abs(before[key]-after[key])<=1,label+' '+key+' '+JSON.stringify({before,after}));
  };
  const delayed=async(action,label)=>{
   const before=await measure();
   await ev('window.qaHoldCsv=true;window.qaCsvRelease=null;'+action);
   await until('!!window.qaCsvRelease');
   const during=await measure();stable(before,during,label+' loading');
   assert.equal(during.rows,before.rows,'Previous rows stay present during loading');
   await ev('qaHoldCsv=false;qaCsvRelease()');await ready();await pause(80);
   const after=await measure();stable(before,after,label+' loaded');
   assert.equal(after.left,Math.min(before.left,after.maxLeft),'Horizontal position preserved within new columns');
   assert.equal(after.row,Math.min(before.row,after.maxRow),'Table vertical position preserved within new rows');
   results.push({prefix,label,before,during,after});
  };
  for(const [width,height,font] of [[1440,900,16],[1440,720,16],[768,900,16],[390,900,16],[320,720,22]]){
   await call('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<600});
   await ev('fontSize('+font+');'+(prefix==='mission'?'openMissionCsv("greenhouse")':'openBasicCsv()'));
   await ready();await pause(80);
   await ev('(()=>{const d=document.getElementById("'+prefix+'-csv-dialog"),r=document.getElementById("'+prefix+'-csv-rows");d.scrollTop=d.scrollHeight;r.scrollTop=80;r.scrollLeft=50;})()');
   await delayed('document.getElementById("'+prefix+'-csv-next").focus({preventScroll:true});document.getElementById("'+prefix+'-csv-next").click()',width+'x'+height+'-'+font+' next');
   assert.ok(await ev('document.getElementById("'+prefix+'-csv-page").textContent.startsWith("2 /")'));
   assert.ok(await ev('document.activeElement.id==="'+prefix+'-csv-next"'),'Keyboard focus returns without scrolling');
   await delayed('document.getElementById("'+prefix+'-csv-prev").focus({preventScroll:true});document.getElementById("'+prefix+'-csv-prev").click()',width+'x'+height+'-'+font+' previous');
   await delayed('document.getElementById("'+prefix+'-csv-refresh").click()',width+'x'+height+'-'+font+' refresh');
   await ev('(()=>{const d=document.getElementById("'+prefix+'-csv-dialog"),t=d.querySelector(".mission-csv-toolbar");d.scrollTop+=t.getBoundingClientRect().top-d.getBoundingClientRect().top-d.querySelector(".dialog-top").getBoundingClientRect().height-12;})()');
   await delayed('document.querySelector("[data-'+prefix+'-csv-kind=prediction]").click()',width+'x'+height+'-'+font+' prediction tab');
   assert.equal((await measure()).rows,30);
   await delayed('document.querySelector("[data-'+prefix+'-csv-kind=training]").click()',width+'x'+height+'-'+font+' training tab');
   assert.equal((await measure()).rows,50);
   if(width===1440&&height===900||width===390)await shot('paging-'+prefix+'-'+width);
   await ev('HelpWindow.close(document.getElementById("'+prefix+'-csv-dialog"))');
  }
 }
 assert.deepEqual(errors,[]);
 fs.writeFileSync(path.join(root,'runtime/csv-paging-verification.json'),JSON.stringify({ok:true,real_database:false,results,out},null,2));
 console.log(JSON.stringify({ok:true,viewers:2,delayed_transitions:results.length,geometry_and_scroll_preserved:true,out}));
 return;
}
const verifySchema=async(prefix,schema)=>{
  const rows=await ev('Array.from(document.querySelectorAll("#'+prefix+'-schema-columns tbody tr"),row=>({role:row.dataset.columnRole,badge:row.querySelector(".mission-column-role")?.textContent,colors:Array.from(row.cells,cell=>getComputedStyle(cell).backgroundColor)}))');
  const legend=await ev('Object.fromEntries(Array.from(document.querySelectorAll("#'+prefix+'-schema-columns .mission-column-legend li"),item=>[item.dataset.columnRole,{label:item.textContent,color:getComputedStyle(item).backgroundColor}]))');
  assert.equal(Object.keys(legend).length,4);
  assert.equal(new Set(Object.values(legend).map(item=>item.color)).size,4);
  assert.deepEqual(rows.map(row=>row.role),schema.columns.map(column=>column.role));
  for(const row of rows){assert.equal(row.badge,legend[row.role].label);assert.ok(row.colors.every(color=>color===legend[row.role].color),'Entire schema row uses its role color');}
  assert.ok(schema.sql.includes('COMMENT ON TABLE '+schema.name+' IS '));
  for(const column of schema.columns)assert.ok(schema.sql.includes('COMMENT ON COLUMN '+schema.name+'.'+column.name+' IS '));
  await ev('Object.defineProperty(navigator,"clipboard",{configurable:true,value:{writeText:async text=>{window.qaSchemaCopied=text}}});window.qaSchemaCopied=null;document.getElementById("copy-'+prefix+'-schema").click()');
  await until('window.qaSchemaCopied!==null');
  assert.equal(await ev('qaSchemaCopied'),schema.sql,'Copied CREATE and comments exactly match displayed SQL');
};
const lessonCatalog=JSON.parse(fs.readFileSync(path.join(root,'data/catalog.json'),'utf8')),lessonTexts={};
const verifyContext=async(prefix,item)=>{
  const content=await ev('(()=>{const root=document.getElementById('+JSON.stringify(prefix+'-learning')+');return {key:root.dataset.mission,text:root.textContent,facts:[...root.querySelectorAll(".mission-context-fact p")].map(p=>p.textContent),features:[...root.querySelectorAll(".mission-feature-card")].map(card=>({name:card.dataset.field,text:card.textContent})),qualityOpen:root.querySelector(".mission-quality").open,rules:root.querySelectorAll(".mission-quality-rules>div").length}})()');
  assert.equal(content.key,item.key);
  assert.deepEqual(content.facts,[item.learning.purpose,item.learning.use_case]);
  assert.equal(content.features.length,3);assert.equal(content.qualityOpen,false);assert.equal(content.rules,4);
  for(const [index,field] of item.layout.slice(1,4).entries()){
    assert.equal(content.features[index].name,field.name);
    for(const value of [field.korean_name,field.meaning,field.low_meaning,field.high_meaning])assert.ok(content.features[index].text.includes(value));
  }
  assert.ok(content.text.includes(item.layout.find(f=>f.name==='label').meaning));
  for(const word of ['0과 100도 유효','unknown','999999','TEST 300행'])assert.ok(content.text.includes(word));
  if(prefix==='mission-csv')lessonTexts[item.key]=content.text;else assert.equal(content.text,lessonTexts[item.key],'Data/schema layers reuse identical mission context');
};
const actionRows=await ev('[...document.querySelectorAll(".mission-card-buttons")].map(row=>[...row.querySelectorAll("button")].map(b=>({kind:b.hasAttribute("data-mission-schema")?"schema":b.hasAttribute("data-mission-preview")?"preview":"select",label:b.textContent,color:getComputedStyle(b).color,background:getComputedStyle(b).backgroundColor})))');
assert.equal(actionRows.length,12);
for(const row of actionRows){
  assert.deepEqual(row.map(b=>b.kind),['schema','preview','select']);
  assert.deepEqual(row.map(b=>b.label),['스키마 조회','데이터 조회','이 미션 선택']);
  assert.notEqual(row[2].background,row[0].background);assert.equal(row[2].color,'rgb(255, 255, 255)');
}
for(const key of JSON.parse(fs.readFileSync(path.join(root,'data/catalog.json'),'utf8')).map(item=>item.key)){await ev(`document.querySelector('[data-mission-preview="${key}"]').focus();document.querySelector('[data-mission-preview="${key}"]').click()`);await until('document.querySelectorAll("#mission-csv-rows tbody tr").length===50&&!document.getElementById("mission-csv-rows").hasAttribute("aria-busy")');assert.ok(await ev('document.getElementById("mission-csv-key").textContent.includes("case_id")'));assert.ok(await ev('document.getElementById("mission-csv-target").textContent.includes("label")'));assert.equal(await ev('document.querySelectorAll("#mission-csv-rows th").length'),7);
await verifyContext('mission-csv',lessonCatalog.find(item=>item.key===key));
const headings=await ev('Array.from(document.querySelectorAll("#mission-csv-rows th"),th=>({name:th.querySelector(".mission-column-name").textContent,korean:th.querySelector(".mission-column-korean").textContent,role:th.dataset.columnRole,badge:th.querySelector(".mission-column-role").textContent,bg:getComputedStyle(th).backgroundColor,separate:th.querySelector(".mission-column-label").getBoundingClientRect().top>=th.querySelector(".mission-column-name").getBoundingClientRect().bottom}))');
const headerFields=await ev('missionDatasets.find(item=>item.key===missionCsvKey).layout');
assert.deepEqual(headings.map(h=>h.name),headerFields.map(f=>f.name));
assert.deepEqual(headings.map(h=>h.korean),headerFields.map(f=>f.korean_name));
assert.deepEqual(headings.map(h=>h.role),['identifier','feature','feature','feature','target','metadata','metadata']);
assert.ok(headings.every(h=>h.separate&&h.badge));
assert.equal(new Set(headings.map(h=>h.bg)).size,4);
await ev('document.getElementById("mission-csv-next").click()');await until('document.getElementById("mission-csv-page").textContent.startsWith("2 / 30")');await ev('document.getElementById("mission-csv-split").value="TEST";document.getElementById("mission-csv-split").dispatchEvent(new Event("change"))');await until('document.getElementById("mission-csv-page").textContent.startsWith("1 / 6")');assert.ok(await ev('[...document.querySelectorAll("#mission-csv-rows tbody tr")].every(row=>row.children[5].textContent==="TEST")'));await ev('document.querySelector("[data-mission-csv-kind=prediction]").click()');await until('document.querySelectorAll("#mission-csv-rows tbody tr").length===30');assert.equal(await ev('document.querySelectorAll("#mission-csv-rows th").length'),4);assert.deepEqual(await ev('Array.from(document.querySelectorAll("#mission-csv-rows th"),th=>th.dataset.columnRole)'),['identifier','feature','feature','feature']);assert.ok(await ev('document.getElementById("mission-csv-download").href.endsWith("kind=prediction")'));await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});await until('!document.getElementById("mission-csv-dialog").open');assert.equal(await ev('document.activeElement.dataset.missionPreview'),key);}
await ev('document.querySelector("[data-mission-choice=festival]").click()');await until('document.getElementById("confirm-dialog").open');await ev('document.getElementById("accept-confirm").click()');await until('!missionSelectionSaving');assert.ok(await ev('!document.getElementById("mission-variable-summary").hidden&&document.getElementById("mission-feature-fields").textContent.includes("interest_score")'));assert.equal(await ev('document.getElementById("assignment-import").disabled'),true);
for(const key of ['delivery','appux']){
  await size(1440);await ev('openMissionCsv('+JSON.stringify(key)+')');await until('!document.getElementById("mission-csv-rows").hasAttribute("aria-busy")');
  await ev('document.getElementById("mission-csv-dialog").scrollTop=0');await shot('context-'+key+'-desktop');
  await size(390);await ev('fontSize(22);document.getElementById("mission-csv-dialog").scrollTop=0');
  assert.ok(await ev('(()=>{const d=document.getElementById("mission-csv-dialog"),r=d.getBoundingClientRect();return document.documentElement.scrollWidth<=innerWidth&&d.scrollWidth<=d.clientWidth+1&&r.left>=-1&&r.right<=innerWidth+1})()'));
  await shot('context-'+key+'-mobile');await ev('fontSize(16);HelpWindow.close(document.getElementById("mission-csv-dialog"))');
}
const checks=[];for(const width of [1440,768,390,320]){await size(width);assert.ok(await ev('document.documentElement.scrollWidth<=innerWidth'),'Page overflow '+width);await ev('openMissionCsv("festival")');await until('document.querySelectorAll("#mission-csv-rows tbody tr").length===50');assert.ok(await ev('(()=>{const d=document.getElementById("mission-csv-dialog");return d.scrollWidth<=d.clientWidth+1&&d.getBoundingClientRect().right<=innerWidth})()'),'Dialog overflow '+width);assert.equal(await ev('getComputedStyle(document.getElementById("mission-csv-rows")).overscrollBehaviorY'),'auto');if(width===1440||width===390){await ev('(()=>{const dialog=document.getElementById("mission-csv-dialog"),legend=document.querySelector(".mission-column-legend"),top=dialog.querySelector(".dialog-top");dialog.scrollTop+=legend.getBoundingClientRect().top-dialog.getBoundingClientRect().top-top.getBoundingClientRect().height-10})()');await shot('csv-'+width);}await ev('document.getElementById("close-mission-csv").click()');checks.push(width)}
await ev('window.qaOriginalApi=api;api=async(...args)=>{const data=await qaOriginalApi(...args);if(args[0].includes("kind=training"))await new Promise(r=>setTimeout(r,300));return data};openMissionCsv("festival");document.querySelector("[data-mission-csv-kind=prediction]").click()');await until('document.querySelectorAll("#mission-csv-rows tbody tr").length===30');await pause(400);assert.equal(await ev('document.querySelectorAll("#mission-csv-rows tbody tr").length'),30);await ev('api=qaOriginalApi;HelpWindow.close(document.getElementById("mission-csv-dialog"))');
const catalog=JSON.parse(fs.readFileSync(path.join(root,'data/catalog.json'),'utf8'));
for(const item of catalog){
  await ev("HelpWindow.close(document.getElementById('mission-csv-dialog'))");
  await ev("document.querySelector('[data-mission-schema="+item.key+"]').focus();document.querySelector('[data-mission-schema="+item.key+"]').click()");
  await until('document.getElementById("mission-schema-dialog").open');
  await verifyContext('mission-schema',item);
  for(const kind of ['training','prepared','prediction']){
    await ev("document.querySelector('[data-mission-schema-kind="+kind+"]').click()");
    const schema=await ev('api("/api/assignments/mission/schema?mission='+item.key+'&kind='+kind+'")');
    await until('document.getElementById("mission-schema-code").textContent==='+JSON.stringify(schema.sql));
    assert.equal(await ev('document.getElementById("mission-schema-table").textContent'),schema.name);
    assert.equal(schema.name,'QA.OML_MISSION_'+({training:'DATA',prepared:'PREPARED',prediction:'PREDICT'}[kind]));
    assert.equal(await ev('document.querySelectorAll("#mission-schema-columns tbody tr").length'),schema.columns.length);
    await verifySchema('mission',schema);
    const features=item.layout.filter(f=>f.role.includes('\uC124\uBA85\uBCC0\uC218')).map(f=>f.name.toUpperCase());
    for(const feature of features)assert.equal(schema.columns.find(c=>c.name===feature).type,kind==='prepared'?'NUMBER':'VARCHAR2(100)');
    if(kind==='training'){
      assert.deepEqual(schema.columns.map(c=>c.name),[...item.columns.map(c=>c.toUpperCase()),'UPDATED_AT']);
      assert.ok(schema.columns.find(c=>c.name==='SPLIT').rules.includes("NOT NULL CHECK (SPLIT IN ('TRAIN', 'TEST'))"));
    }
    if(kind==='prediction')assert.deepEqual(schema.columns.map(c=>c.name),['CASE_ID',...features,'UPDATED_AT']);
    if(kind==='prepared'){
      assert.ok(schema.constraints.includes('PRIMARY KEY (PREP_MODE, SOURCE_KIND, CASE_ID)'));
      for(const label of item.layout.find(f=>f.name==='label').valid.split(' / '))assert.ok(schema.sql.includes("'"+label+"'"));
    }
    assert.equal(await ev('document.getElementById("mission-schema-code").textContent'),schema.sql);
    assert.ok(schema.sql.includes("WHERE TABLE_NAME = '"+schema.name.split('.')[1]+"'"));
    assert.ok(schema.sql.includes("IF USER <> 'QA'"));
    assert.ok(schema.sql.includes("WHENEVER SQLERROR EXIT SQL.SQLCODE ROLLBACK"));
    assert.deepEqual([...schema.sql.matchAll(/DROP TABLE ([A-Z0-9_]+\.[A-Z0-9_]+)/g)].map(m=>m[1]),[schema.name]);
    assert.ok(schema.sql.indexOf('END;\n/')<schema.sql.indexOf('CREATE TABLE'));
    assert.equal(await ev('document.getElementById("mission-schema-reset")'),null);
  }
  await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
  await until('!document.getElementById("mission-schema-dialog").open');
  assert.equal(await ev('document.activeElement.dataset.missionSchema'),item.key);
}

for(const width of [1440,768,390,320]){
  await size(width);
  for(const font of [16,22]){
    await ev('fontSize('+font+')');
    const cards=await ev('Array.from(document.querySelectorAll(".mission-example-card"),card=>({buttons:Array.from(card.querySelectorAll(".mission-card-buttons button"),b=>({y:b.getBoundingClientRect().top,bottom:b.getBoundingClientRect().bottom})),downloads:card.querySelector(".mission-card-downloads").getBoundingClientRect().top}))');
    assert.equal(cards.length,12);
    for(const card of cards){
      assert.equal(card.buttons.length,3);
      assert.ok(Math.max(...card.buttons.map(b=>b.y))-Math.min(...card.buttons.map(b=>b.y))<1,'Three buttons on a row '+width+' '+font);
      assert.ok(card.downloads>=Math.max(...card.buttons.map(b=>b.bottom)),'Downloads below buttons');
    }
    assert.ok(await ev('document.documentElement.scrollWidth<=innerWidth'),'Mission card overflow '+width+' '+font);
  }
  await ev('fontSize(16);document.querySelector(".mission-examples").scrollIntoView({block:"start"})');
  if(width===1440||width===390)await shot('mission-cards-'+width);
}
await ev('selectMissionDataset("wifi")');
assert.ok(await ev('!document.getElementById("mission-baseline").hidden&&!document.getElementById("mission-baseline").textContent.includes("%")'));
for(const width of [1440,768,390,320]){
  await size(width);await ev('openMissionSchema("festival")');
  await until('Boolean(missionSchemaSql)');
  assert.ok(await ev('(()=>{const d=document.getElementById("mission-schema-dialog");return d.scrollWidth<=d.clientWidth+1&&d.getBoundingClientRect().right<=innerWidth})()'),'Schema overflow '+width);
  if(width===1440||width===390)await shot('schema-'+width);
  await ev('HelpWindow.close(document.getElementById("mission-schema-dialog"))');
}

await ev('HelpWindow.closeAll();void saveMissionSelection("festival")');
if(await ev('document.getElementById("confirm-dialog").open'))await ev('document.getElementById("accept-confirm").click()');
await until('!missionSelectionSaving');
assert.equal(await ev('missionSelectionCurrent'),'festival');
await call('Page.reload');
await until('typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"&&missionSelectionCurrent==="festival"');
assert.equal(await ev('document.querySelector("[data-mission-choice=festival]").getAttribute("aria-pressed")'),'true');
assert.equal(await ev('document.getElementById("mission-dataset").value'),'festival');
await ev('window.qaSavedPerson=person;person=null;renderPerson()');
assert.equal(await ev('document.getElementById("mission-dataset").value'),'');
await ev('person=qaSavedPerson;renderPerson();restoreMissionSelection()');
await until('missionSelectionCurrent==="festival"');
await ev('window.qaSelectionApi=api;api=async(path,body)=>{if(path.endsWith("/selection")&&body!==undefined)throw Error("fixture save failure");return qaSelectionApi(path,body)};document.getElementById("mission-dataset").value="bike";document.getElementById("mission-dataset").dispatchEvent(new Event("change"))');
await until('document.getElementById("confirm-dialog").open');await ev('document.getElementById("accept-confirm").click()');
await until('!missionSelectionSaving');
assert.equal(await ev('document.getElementById("mission-dataset").value'),'festival');
await ev('api=qaSelectionApi');
await ev('HelpWindow.closeAll();window.qaLinkCalls=0;window.qaLinkApi=api;api=async(path,...args)=>{if(path==="/api/assignments/mission/link")window.qaLinkCalls++;return qaLinkApi(path,...args)};document.getElementById("assignment-check").click()');
await until('document.getElementById("confirm-dialog").open');await ev('document.getElementById("accept-confirm").click()');
await until('!assignmentBusy&&qaLinkCalls===1');
await ev('api=qaLinkApi');
assert.ok(await ev('Array.from(document.querySelectorAll("[data-manual-action]")).every(button=>button.disabled)'),'Mission object/data/model changes require direct SQL');


await ev('HelpWindow.closeAll();dismissMessage();document.querySelector(".assignment-tabs [data-assignment-tab=home]").click()');
assert.deepEqual(await ev('Array.from(document.querySelectorAll("[data-mission-schema-kind]"),b=>b.dataset.missionSchemaKind)'),['training','prepared','prediction','procedure']);
for(const [tab,operation] of [['home','setup'],['data','prepare'],['models','initial-train'],['predictions','predict']]){
  await ev('document.querySelector(".assignment-tabs [data-assignment-tab='+tab+']").click()');
  await ev('openExecution(document.querySelector("[data-code='+operation+']"))');
  assert.ok(await ev('document.getElementById("execution-context").textContent.includes("캠퍼스 축제 혼잡도")'));
  assert.ok(await ev('!document.getElementById("execution-code").textContent.includes("RETURN_PCT")'));
  assert.deepEqual(await ev('Array.from(document.querySelectorAll("#execution-flow [data-flow-stage]"),button=>button.dataset.flowStage)'),['ui','event','api','service','database','sql']);
  await ev('document.querySelector("#execution-flow [data-flow-stage=sql]").click()');
  const flowGuide=await ev('api("/api/coding-help?assignment=mission&operation='+operation+'&variant=RAW")');
  const sqlItems=flowGuide.flow.stages.find(stage=>stage.id==='sql').items.map(item=>({...item,content:flowGuide.flow.files[item.file_id].content}));
  assert.ok(sqlItems.some(item=>item.content.includes('INTEREST_SCORE')),'Selected mission SQL remains accessible in flow');
  for(const item of sqlItems){
    await ev('document.querySelector('+JSON.stringify('[data-flow-item="'+item.id+'"]')+').click()');
    assert.equal(await ev('document.getElementById("execution-code").textContent'),item.content,'Flow source is exact');
  }
  const current=sqlItems.find(item=>operation==='setup'?item.content.includes('CREATE OR REPLACE PROCEDURE QA.OML_MISSION_RUN'):operation==='prepare'?item.content.includes('PREPARE'):true);
  if(current)await ev('document.querySelector('+JSON.stringify('[data-flow-item="'+current.id+'"]')+').click()');
  if(operation==='setup')assert.ok(await ev('document.getElementById("execution-code").textContent.includes("CREATE OR REPLACE PROCEDURE QA.OML_MISSION_RUN")'));
  if(operation==='prepare')assert.ok(await ev('document.getElementById("execution-code").textContent.includes("PREPARE")'));
  if(tab==='models')await shot('selected-mission-model-guide');
  await ev('HelpWindow.close(document.getElementById("execution-dialog"))');
}
await ev('document.querySelector(".assignment-tabs [data-assignment-tab=models]").click()');
for(const width of [1440,390]){await size(width);await ev('scrollTo(0,0)');await shot('mission-manual-models-'+width);}
await call('Page.navigate',{url:(await url)+'/creative'});
await until('document.body.dataset.page==="creative"&&typeof assignmentPhase!=="undefined"&&assignmentPhase!=="unchecked"');
assert.equal(await ev('document.querySelectorAll("[data-code]").length'),0);
assert.equal(await ev('document.querySelectorAll(".code-help").length'),0);
assert.equal(await ev('document.getElementById("assignment-predict-call")'),null);
assert.ok(await ev('Array.from(document.querySelectorAll("[data-manual-action]")).every(button=>button.disabled)'),'Creative DDL, preparation, reset and model changes require direct SQL');
assert.ok(await ev('document.getElementById("assignment-check").textContent.includes("연계")'));

await ev('document.querySelector("[data-custom-schema]").click()');
await until('document.getElementById("assignment-schema-status").textContent.includes("DB actions disabled")');
assert.ok(await ev('document.getElementById("assignment-schema-dialog").open&&document.querySelectorAll("#assignment-schema-columns tbody tr").length===0&&!document.querySelector("#assignment-schema-dialog pre")'),'Creative schema lookup failure is visible and never supplies SQL');
assert.deepEqual(await ev('Array.from(document.querySelectorAll("[data-custom-schema-kind]"),b=>b.dataset.customSchemaKind)'),['training','prepared','prediction']);
await ev('HelpWindow.close(document.getElementById("assignment-schema-dialog"))');
for(const width of [1440,390]){await size(width);await ev('scrollTo(0,0)');await shot('creative-card-'+width);}
await call('Page.navigate',{url:(await url)+'/basic#home'});
await until('typeof basicCsvKind!=="undefined"&&person?.db_user==="QA"&&!refreshing');
await ev('HelpWindow.closeAll();dismissMessage()');
assert.ok(await ev('document.querySelectorAll("#basic-home [data-basic-preview]").length===1&&document.querySelectorAll("#basic-data [data-basic-preview]").length===1&&document.querySelectorAll("#basic-home [data-basic-schema]").length===1&&!document.querySelector("[data-mission-choice]")'),'Basic dataset is fixed and has preview/schema actions');
for(const width of [1440,390]){await size(width);await ev('scrollTo(0,0)');await shot('basic-card-'+width);}
await ev('window.qaBasicApi=api;window.qaBasicWrites=[];api=async(path,body)=>{if(body!==undefined)qaBasicWrites.push(path);return qaBasicApi(path,body)};document.querySelector("[data-basic-preview]").focus();document.querySelector("[data-basic-preview]").click()');
await until('document.querySelectorAll("#basic-csv-rows tbody tr").length===50&&!document.getElementById("basic-csv-rows").hasAttribute("aria-busy")');
const basicHeaders=await ev('Array.from(document.querySelectorAll("#basic-csv-rows th"),th=>({name:th.querySelector(".mission-column-name").textContent,role:th.dataset.columnRole,bg:getComputedStyle(th).backgroundColor,separate:th.querySelector(".mission-column-label").getBoundingClientRect().top>=th.querySelector(".mission-column-name").getBoundingClientRect().bottom}))');
assert.deepEqual(basicHeaders.map(h=>h.role),['identifier','feature','feature','feature','feature','feature','target','metadata','metadata','metadata']);
assert.equal(new Set(basicHeaders.map(h=>h.bg)).size,4);
assert.ok(basicHeaders.every(h=>h.separate));
assert.ok(await ev('document.getElementById("basic-csv-status").textContent.includes("720")&&document.getElementById("basic-csv-page").textContent.startsWith("1 / 15")'));
await ev('document.getElementById("basic-csv-next").click()');await until('document.getElementById("basic-csv-page").textContent.startsWith("2 / 15")');
await ev('document.getElementById("basic-csv-split").value="TEST";document.getElementById("basic-csv-split").dispatchEvent(new Event("change"))');
await until('document.getElementById("basic-csv-page").textContent.startsWith("1 / 8")');
assert.ok(await ev('(()=>{const keys=Array.from(document.querySelectorAll("#basic-csv-rows th .mission-column-name"),n=>n.textContent);return Array.from(document.querySelectorAll("#basic-csv-rows tbody tr")).every(row=>row.children[keys.indexOf("split")].textContent==="TEST")})()'));
await ev('document.querySelector("[data-basic-csv-kind=prediction]").click()');
await until('document.querySelectorAll("#basic-csv-rows tbody tr").length===30');
assert.ok(await ev('document.getElementById("basic-csv-split-label").hidden&&document.getElementById("basic-csv-download").getAttribute("href")==="/download/prediction.csv"'));
await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
await until('!document.getElementById("basic-csv-dialog").open');
assert.ok(await ev('document.activeElement.hasAttribute("data-basic-preview")'));
await ev('document.querySelector("[data-basic-schema]").focus();document.querySelector("[data-basic-schema]").click()');
assert.deepEqual(await ev('Array.from(document.querySelectorAll("[data-basic-schema-kind]"),b=>b.dataset.basicSchemaKind)'),['training','prepared','prediction']);
for(const kind of ['training','prepared','prediction']){
  await ev('document.querySelector("[data-basic-schema-kind='+kind+']").click()');
  const schema=await ev('api("/api/basic/dataset/schema?kind='+kind+'")');
  await until('document.getElementById("basic-schema-code").textContent==='+JSON.stringify(schema.sql));
  assert.equal(await ev('document.getElementById("basic-schema-table").textContent'),'QA.OML_BASIC_'+({training:'DATA',prepared:'PREPARED',prediction:'PREDICT'}[kind]));
  assert.equal(await ev('document.querySelectorAll("#basic-schema-columns tbody tr").length'),schema.columns.length);
  await verifySchema('basic',schema);
  if(kind==='training'){await ev('fontSize(16)');await size(1440);await shot('basic-schema-colors');}
  assert.ok(schema.sql.includes('CREATE TABLE QA.OML_BASIC_'));
}
await ev('HelpWindow.close(document.getElementById("basic-schema-dialog"))');
for(const width of [1440,768,390,320]){
  await size(width);
  for(const dialog of ['csv','schema']){
    await ev(dialog==='csv'?'openBasicCsv()':'openBasicSchema()');
    await until(dialog==='csv'?'document.querySelectorAll("#basic-csv-rows tbody tr").length===50':'Boolean(basicSchemaSql)');
    assert.ok(await ev('(()=>{const d=document.getElementById("basic-'+dialog+'-dialog");return d.scrollWidth<=d.clientWidth+1&&d.getBoundingClientRect().right<=innerWidth})()'),'Basic '+dialog+' overflow '+width);
    if(width===1440||width===390)await shot('basic-'+dialog+'-'+width);
    await ev('HelpWindow.close(document.getElementById("basic-'+dialog+'-dialog"))');
  }
  assert.ok(await ev('document.documentElement.scrollWidth<=innerWidth'),'Basic page overflow '+width);
}
assert.deepEqual(await ev('qaBasicWrites'),[],'Basic viewers never execute DB mutations');
await ev('api=qaBasicApi');

assert.deepEqual(errors,[]);console.log(JSON.stringify({ok:true,fixture_database_unready:true,real_database:false,missions:catalog.length,training_test_prediction:true,downloads_checked_by_unit_tests:true,paging:true,escape_focus:true,stale_response:true,schema_missions:catalog.length,schema_tables:3,basic_fixed_dataset:true,basic_schema_tables:3,basic_viewers_read_only:true,manual_assignment_actions:true,three_buttons_per_row:true,header_line_breaks:true,column_role_colors:true,font_sizes:[16,22],widths:checks,out}));})().catch(e=>{console.error(e);process.exitCode=1}).finally(()=>{ws?.close();browser.kill();server.kill()});
