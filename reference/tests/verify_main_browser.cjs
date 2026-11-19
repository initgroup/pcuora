const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const root=path.resolve(__dirname,'../..'),out=fs.mkdtempSync(path.join(os.tmpdir(),'main-login-ui-')),pause=ms=>new Promise(r=>setTimeout(r,ms));
const server=spawn(path.join(root,'.venv/Scripts/python.exe'),['-B',path.join(__dirname,'main_preview_server.py'),...(process.argv.includes('--hosted-login')?['--hosted-login']:[])],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
let serverErrors='';server.stderr.on('data',c=>serverErrors+=c);
const basePromise=new Promise((resolve,reject)=>{let buffer='';server.stdout.on('data',c=>{buffer+=c;const match=buffer.match(/MAIN_QA_URL=(http:\/\/127\.0\.0\.1:\d+)/);if(match)resolve(match[1])});server.on('error',reject);server.on('exit',code=>reject(new Error('Fixture exited '+code+' '+serverErrors)))});
const profile=path.join(out,'profile'),browser=spawn('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
let ws;
(async()=>{
 const portFile=path.join(profile,'DevToolsActivePort');for(let i=0;i<150&&!fs.existsSync(portFile);i++)await pause(100);
 const port=fs.readFileSync(portFile,'utf8').split('\n')[0],tabs=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();
 ws=new WebSocket(tabs.find(tab=>tab.type==='page').webSocketDebuggerUrl);
 await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject});
 let seq=0;const pending=new Map(),errors=[],requests=[];
 ws.onmessage=event=>{const result=JSON.parse(event.data);if(result.method==='Runtime.exceptionThrown')errors.push(result.params.exceptionDetails.exception?.description||result.params.exceptionDetails.text);if(result.method==='Network.requestWillBeSent')requests.push(result.params.request.url);if(result.id){const promise=pending.get(result.id);pending.delete(result.id);result.error?promise.reject(result.error):promise.resolve(result.result)}};
 const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))});
 const ev=async expression=>{const result=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true,userGesture:true});assert.ok(!result.exceptionDetails,JSON.stringify(result.exceptionDetails));return result.result.value};
 const until=async expression=>{for(let i=0;i<180;i++){if(await ev(expression))return;await pause(50)}throw new Error('Timed out '+expression+' '+JSON.stringify(errors)+' '+JSON.stringify(await ev('({auth:document.body.dataset.auth,identityError:document.getElementById("identity-error")?.textContent,connectionCheck:document.getElementById("connection-check")?.textContent,invalid:Array.from(document.querySelectorAll("#identity-form input:invalid")).map(a=>a.id),connection:document.getElementById("main-account")?.dataset.connection,notice:document.getElementById("operation-status")?.textContent})'))+' '+serverErrors)};
 const size=width=>call('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width<600});
 const shot=async name=>{const result=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(result.data,'base64'))};
 const click=selector=>ev('document.querySelector('+JSON.stringify(selector)+').click()');
 const fill=async(id='QA2026',name='홍길동')=>ev("document.getElementById('login-id').value="+JSON.stringify(id)+";document.getElementById('login-name').value="+JSON.stringify(name)+";document.getElementById('login-password').value='FixturePassword';document.getElementById('login-name').dispatchEvent(new Event('change'));");
 const login=async(id,name)=>{await fill(id,name);await until('Boolean(document.getElementById("login-db-user").value)&&!document.getElementById("login-submit").disabled');await click('#login-submit');await until('document.body.dataset.auth==="ready"&&!document.getElementById("main-account").hidden&&document.getElementById("main-account").dataset.connection==="success"')};
 await call('Page.enable');await call('Runtime.enable');await call('Network.enable');await call('Emulation.setFocusEmulationEnabled',{enabled:true});
 await size(1440);const base=await basePromise;
 if(process.argv.includes('--guide-file-only')){
   const guide=path.join(root,'downloads','COM22417_과제설명및평가.html');
   await call('Page.navigate',{url:require('node:url').pathToFileURL(guide).href});
   await until('Boolean(document.getElementById("render-db-troubleshooting"))');
   const walletPlaceholder='WALLET_PASSWORD="본인의_Wallet_다운로드_암호"';
   assert.ok(!fs.readFileSync(guide,'utf8').includes('Pcuora2026'));
   for(const selector of ['#personal-settings pre','#render-environment pre'])assert.ok(await ev('document.querySelector('+JSON.stringify(selector)+').textContent.includes('+JSON.stringify(walletPlaceholder)+')'));
   const layouts=[];
   for(const width of [1440,768,390,320])for(const font of [16,22]){
     await size(width);await ev('document.documentElement.style.setProperty("--size","'+font+'px");document.documentElement.style.scrollBehavior="auto";document.getElementById("render-db-troubleshooting").scrollIntoView()');
     await ev('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
     await ev('document.getElementById("render-db-troubleshooting").scrollIntoView()');
     await ev('window.scrollTo(0,scrollY)');
     const layout=await ev('({requested:'+width+',font:'+font+',width:innerWidth,client:document.documentElement.clientWidth,x:scrollX,scroll:document.documentElement.scrollWidth,steps:document.querySelectorAll("#render-db-troubleshooting ol>li").length,overflow:[...document.querySelectorAll("body *")].filter(e=>!e.closest(".table-shell")&&e.getBoundingClientRect().right>'+width+'+1).slice(0,8).map(e=>({tag:e.tagName,cls:e.className,text:e.textContent.slice(0,70),right:e.getBoundingClientRect().right}))})');
     if(layout.scroll>width+1)layout.textOverflow=await ev('(()=>{const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),out=[];let n;while(n=walker.nextNode()){if(n.parentElement.closest(".table-shell,script,style"))continue;const r=document.createRange();r.selectNodeContents(n);if([...r.getClientRects()].some(b=>b.right>'+width+'+1))out.push({text:n.textContent.slice(0,160),tag:n.parentElement.tagName,cls:n.parentElement.className});}return out.slice(0,8)})()');
     assert.ok(layout.scroll<=width+1,JSON.stringify(layout));assert.equal(layout.steps,5);layouts.push({font,...layout});
     if(width===1440||width===320)await shot('render-db-guide-'+width+'-'+font);
   }
   assert.doesNotMatch(fs.readFileSync(guide,'utf8'),/ppt|powerpoint|보고서|submit\.ps1|submission\//i);
   assert.ok(await ev('document.querySelector("#lms-submission-example pre").textContent.includes("https://your-service.onrender.com")'));
   assert.ok(await ev('document.querySelector("#submit h2").textContent.includes("LMS")'));
   assert.equal(await ev('document.querySelectorAll("#lms-submission-steps>li").length'),4);
   assert.ok(await ev('document.getElementById("submission-checks").textContent.includes("메인 주소")'));
   assert.ok(await ev('document.querySelector("#deployment .section-title").textContent.includes("평가 사이트 배포")'));
   for(const width of [1440,768,390,320])for(const font of [16,22]){
     await size(width);await ev('document.documentElement.style.setProperty("--size","'+font+'px");document.getElementById("submit").scrollIntoView()');
     await ev('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
     await ev('document.getElementById("submit").scrollIntoView()');
     const layout=await ev('({section:"submit",requested:'+width+',font:'+font+',width:innerWidth,scroll:document.documentElement.scrollWidth})');
     assert.ok(layout.scroll<=width+1,JSON.stringify(layout));layouts.push(layout);
     assert.ok(await ev('document.querySelector("#submit h2").getBoundingClientRect().top>=document.querySelector(".quick-nav").getBoundingClientRect().bottom-1'));
     if(width<760)assert.ok(await ev('document.querySelector("#submit tbody th").getBoundingClientRect().width>innerWidth*.7'));
     if(width===1440||width===320)await shot('submission-guide-'+width+'-'+font);
   }
   assert.deepEqual(errors,[]);
   const report={ok:true,standalone_guide:true,layouts,wallet_password_placeholder:true,wallet_password_value_absent:true,render_url_submission_to_lms:true,presentation_and_file_submission_removed:true,real_database_access:false,screenshots:out};
   fs.writeFileSync(path.join(root,'runtime/assignment-guide-render-verification.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));return;
 }
 await call('Page.navigate',{url:base+'/'});await until('typeof csrf!=="undefined"&&csrf&&document.body.dataset.auth==="locked"');
 if(process.argv.includes('--hosted-login')){
   await click('#gate-login');await until('!document.getElementById("main-login").hidden');
   assert.ok(await ev('document.getElementById("login-password").type==="password"&&document.getElementById("login-password").required'));
   await ev('document.getElementById("login-id").value="QA2026";document.getElementById("login-name").value="홍길동";document.getElementById("login-name").dispatchEvent(new Event("change"));document.getElementById("remember-identity").checked=true');
   await until('document.getElementById("login-db-user").value==="STUDENT_QA"');
   assert.deepEqual(await ev('loginPayload("QA2026","홍길동","entered")'),{student_id:"QA2026",name:"홍길동",db_password:"entered"});
   await ev('localStorage.setItem(rememberedKey,JSON.stringify({student_id:"QA2026",name:"홍길동",db_password:"OldSavedPassword"}));rememberedIdentity()');
   assert.ok(await ev('!Object.hasOwn(JSON.parse(localStorage.getItem(rememberedKey)),"db_password")'));
   await ev('document.getElementById("login-password").value="WrongPassword"');
   await click('#test-connection');await until('!document.getElementById("test-connection").disabled');
   assert.ok(await ev('document.getElementById("connection-check").textContent.includes("일치하지")'));
   await click('#login-submit');await until('!document.getElementById("login-submit").disabled');
   assert.ok(await ev('document.body.dataset.auth==="locked"&&document.getElementById("identity-error").textContent.includes("일치하지")'));
   assert.equal((await(await fetch(base+'/qa/state')).json()).checks,0);
   await ev('document.getElementById("login-password").value="FixturePassword"');
   await click('#test-connection');await until('!document.getElementById("test-connection").disabled');
   assert.ok(await ev('document.getElementById("connection-check").textContent.includes("LAB_DB")'));
   await shot('hosted-login-1440');
   await click('#login-submit');await until('document.body.dataset.auth==="ready"');
   assert.deepEqual(await ev('JSON.parse(localStorage.getItem(rememberedKey))'),{student_id:"QA2026",name:"홍길동"});
   assert.equal(await ev('document.getElementById("main-db-owner").textContent'),'STUDENT_QA');
   await click('#logout');await until('document.body.dataset.auth==="locked"&&!signingOut');
   await click('#gate-login');await until('!document.getElementById("main-login").hidden');
   assert.equal(await ev('document.getElementById("login-password").value'),'');
   for(const width of [390,320]){await size(width);assert.ok(await ev('document.documentElement.scrollWidth<=innerWidth'));await shot('hosted-login-'+width)}
   assert.deepEqual(errors,[]);
   const report={ok:true,json_db_user:true,environment_password:true,required_password_field:true,password_mismatch_blocks_db:true,remember_only_id_and_name:true,widths:[1440,390,320],no_real_database:true,screenshots:out};
   fs.writeFileSync(path.join(root,'runtime/hosted-login-browser.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));return;
 }
 if(process.argv.includes('--guide-menu-only')){
   await click('#gate-login');await until('!document.getElementById("main-login").hidden');await login();
   assert.ok(await ev('document.getElementById("instructor-lecture-link").hidden&&document.getElementById("mobile-instructor-lecture-link").hidden'));
   for(const id of ['assignment-guide-link','mobile-assignment-guide-link']){
     assert.deepEqual(await ev('(()=>{const a=document.getElementById('+JSON.stringify(id)+');return [a.textContent.trim().replace(/\\s*↗$/,""),a.getAttribute("href"),a.target,a.rel,a.hidden]})()'),['과제 설명 및 평가','/download/assignment-guide.html','_blank','noopener',false]);
   }
   const opened=[];
   async function openGuide(selector){
     const old=new Set((await call('Target.getTargets')).targetInfos.map(t=>t.targetId));
     await click(selector);let target;
     for(let i=0;i<100&&!target;i++){target=(await call('Target.getTargets')).targetInfos.find(t=>!old.has(t.targetId)&&t.url===base+'/download/assignment-guide.html');if(!target)await pause(50)}
     assert.ok(target,'Link must open a new tab');opened.push(target.targetId);
     const tabs=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();
     const socket=new WebSocket(tabs.find(t=>t.id===target.targetId).webSocketDebuggerUrl);
     await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject});
     let sequence=0;const waiting=new Map();
     socket.onmessage=event=>{const message=JSON.parse(event.data);if(message.id){const item=waiting.get(message.id);waiting.delete(message.id);message.error?item.reject(message.error):item.resolve(message.result)}};
     const command=(method,params={})=>new Promise((resolve,reject)=>{const id=++sequence;waiting.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}))});
     const evaluate=async expression=>{const result=await command('Runtime.evaluate',{expression,returnByValue:true});assert.ok(!result.exceptionDetails,JSON.stringify(result.exceptionDetails));return result.result.value};
     try{
       for(let i=0;i<100;i++){if(await evaluate('document.readyState==="complete"&&document.querySelectorAll(".command-head button").length>0'))break;await pause(50)}
       assert.ok(await evaluate('document.body.textContent.includes("COM22417")'));
       assert.ok(await evaluate('document.querySelectorAll(".command-head button").length>0'),'Hashed inline script must run');
       const before=Number(await evaluate('document.getElementById("font-size").value'));
       await evaluate('document.getElementById("font-plus").click()');
       assert.equal(Number(await evaluate('document.getElementById("font-size").value')),Math.min(22,before+2));
       await evaluate('document.getElementById("font-minus").click()');
       if(opened.length===1){
         assert.deepEqual(await evaluate('[...document.querySelectorAll(".quick-nav .links a")].map(a=>a.getAttribute("href"))'),['#setup','#run','#assessment','#deployment']);
         assert.deepEqual(await evaluate('[...document.querySelectorAll("a[href^=\\\"#\\\"]")].filter(a=>!document.getElementById(a.hash.slice(1))).map(a=>a.hash)'),[]);
         assert.equal(await evaluate('document.body.textContent.includes("COM22417_개발환경설정.html")'),false);
         for(const width of [1440,390,320])for(const font of [16,22]){
           await command('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width<600});
           await evaluate('document.documentElement.style.setProperty("--size","'+font+'px");document.documentElement.style.scrollBehavior="auto"');
           assert.ok(await evaluate('document.documentElement.scrollWidth<=innerWidth+1'),'Guide page overflow '+width+' '+font);
           for(const section of ['setup','personal-settings','settings-handoff','run','assessment','deployment','render-environment']){
             await evaluate('document.getElementById('+JSON.stringify(section)+').scrollIntoView()');
             const capture=await command('Page.captureScreenshot',{format:'png'});
             fs.writeFileSync(path.join(out,'guide-'+section+'-'+width+'-'+font+'.png'),Buffer.from(capture.data,'base64'));
           }
         }
       }
       const screenshot=await command('Page.captureScreenshot',{format:'png'});
       fs.writeFileSync(path.join(out,'assignment-guide-'+opened.length+'.png'),Buffer.from(screenshot.data,'base64'));
     }finally{socket.close();await call('Target.closeTarget',{targetId:target.targetId})}
   }
   await size(1440);await openGuide('#assignment-guide-link');await shot('student-sidebar-1440');
   for(const width of [390,320]){
     await size(width);await ev('document.documentElement.style.setProperty("--size","22px")');
     await click('#open-menu');await until('document.getElementById("mobile-menu").open');
     assert.ok(await ev('(()=>{const a=document.getElementById("mobile-assignment-guide-link").getBoundingClientRect();return a.left>=0&&a.right<=innerWidth&&a.height>=40})()'));
     await shot('student-mobile-'+width);
     if(width===320)await openGuide('#mobile-assignment-guide-link');
     await click('#close-menu');
   }
   await size(1440);await click('#logout');await until('document.body.dataset.auth==="locked"');await click('#gate-login');await login('V01041','테스트강사');
   assert.ok(await ev('!document.getElementById("instructor-lecture-link").hidden&&!document.getElementById("mobile-instructor-lecture-link").hidden'));
   assert.ok(await ev('document.getElementById("instructor-lecture-link").nextElementSibling.id==="assignment-guide-link"'));
   await shot('instructor-sidebar-1440');
   assert.equal((await fetch(base+'/download/assignment-guide.html')).status,401);
   assert.deepEqual(errors,[]);
   const report={ok:true,common_student_menu:true,instructor_menu_restricted:true,guide_below_instructor:true,new_tabs:opened.length,guide_script_runs_under_csp:true,mobile_widths:[390,320],large_font:22,no_real_database:true,screenshots:out};
   fs.writeFileSync(path.join(root,'runtime/assignment-guide-menu-browser.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));return;
 }
 assert.equal(await ev('Boolean(document.getElementById("basic-workflow"))'),false);
 assert.ok(await ev('document.querySelector(".login-gate").textContent.includes("2026년")&&document.querySelector(".login-gate").textContent.includes("2학기")'));
 assert.ok(await ev('document.querySelector(".gate-course-path").textContent.includes("배재대학교")'));
 assert.ok(await ev('document.querySelector(".gate-oml-name").textContent.includes("Oracle Machine Learning")'));
 assert.equal(await ev('document.body.textContent.includes("목원대학교")'),false);
 await until('document.querySelector(".gate-campus img").complete&&document.querySelector(".gate-campus img").naturalWidth>0');
 for(const width of [1440,1024,768,390,320]){
   await size(width);
   assert.ok(await ev('document.documentElement.scrollWidth<=innerWidth'),'Intro overflow '+width);
   if(width===1440||width===390||width===320)await shot('campus-intro-'+width);
 }
 await size(1440);
 await click('#gate-login');await until('!document.getElementById("main-login").hidden');
 assert.equal(await ev('document.querySelectorAll("dialog[open]").length'),0);
 assert.equal(await ev('document.querySelector(".workspace").inert'),false);
 await shot('inline-login-1440');
 await fill();await click('#test-connection');await until('!document.getElementById("test-connection").disabled');
 assert.ok(await ev('document.getElementById("connection-check").textContent.includes("LAB_DB")'));
 assert.equal(await ev('person'),null,'Connection test must not log in');
 await login();
 assert.equal(await ev('location.pathname'),'/');
 assert.equal(await ev('document.querySelectorAll("#open-help,[data-open-help],#help-content,[data-help-tab],#sql-help-template").length'),0,'Duplicate guide entries and content removed');
 assert.ok(!requests.some(url=>url.includes('/api/help')),'Main does not request the removed guide');
 assert.equal(await ev('document.getElementById("main-db-owner").textContent'),'STUDENT_QA');
 assert.ok(await ev('document.getElementById("main-web-address").textContent===location.origin+"/"'));
 assert.ok(await ev('!document.getElementById("main-account").textContent.includes("FixturePassword")'));
 assert.ok(!requests.some(url=>url.endsWith('/api/status')||url.includes('/api/models')),'Main must not load basic assignment');
 for(const width of [1920,1440,768,390,320]){
   await size(width);assert.ok(await ev('document.documentElement.scrollWidth<=innerWidth'),'Overflow '+width);
   const layout=await ev('(()=>{const box=s=>{const r=document.querySelector(s).getBoundingClientRect();return{left:r.left,right:r.right,height:r.height}};return{title:box(".page-heading"),card:box("#main-account"),links:box("#main-task-links"),heading:box(".main-card-heading"),headingBackground:getComputedStyle(document.querySelector(".main-card-heading")).backgroundColor,headingImage:getComputedStyle(document.querySelector(".main-card-heading")).backgroundImage}})()');
   for(const item of [layout.card,layout.links])assert.ok(Math.abs(item.left-layout.title.left)<1&&Math.abs(item.right-layout.title.right)<1,'Main body aligns with title '+width+' '+JSON.stringify(layout));
   assert.equal(layout.headingBackground,'rgb(255, 255, 255)');assert.equal(layout.headingImage,'none');
   if(width>=768)assert.ok(layout.heading.height<64,'Main card has a compact white header');
   if(width===1920||width===1440||width===390)await shot('main-card-'+width);
 }
 await size(1440);
 const before=(await(await fetch(base+'/qa/state')).json()).checks;await pause(1200);
 assert.equal((await(await fetch(base+'/qa/state')).json()).checks,before,'No idle connection polling');
 await fetch(base+'/qa/fail');await click('#main-test-connection');await until('document.getElementById("main-account").dataset.connection==="failure"');
 assert.equal(await ev('document.getElementById("main-db-name").textContent'),'—','Failed test must clear previous success');
 await fetch(base+'/qa/recover');await click('#main-test-connection');await until('document.getElementById("main-account").dataset.connection==="success"');
 for(let repeat=0;repeat<2;repeat++){
   await click('#logout');await until('document.body.dataset.auth==="locked"&&!signingOut');
   assert.equal(await ev('location.pathname'),'/');
   await click('#gate-login');await until('!document.getElementById("main-login").hidden');
   assert.equal(await ev('document.querySelectorAll("dialog[open]").length'),0);
   await login();
 }
 await call('Page.navigate',{url:base+'/mission'});await until('typeof assignmentPhase!=="undefined"&&assignmentPhase==="ready"');
 await click('#account-button');await until('location.pathname==="/"&&document.body.dataset.entry==="login"&&typeof csrf!=="undefined"&&csrf');
 await click('#cancel-identity');await until('!document.getElementById("main-account").hidden');
 await click('#account-button');await login('QA2027','김학생');
 assert.equal(await ev('document.getElementById("main-person-name").textContent'),'김학생');
 assert.equal(await ev('document.getElementById("main-db-owner").textContent'),'STUDENT_QB');
 await fetch(base+'/qa/expire');await click('#main-test-connection');await until('document.getElementById("session-expired-dialog").open');
 assert.equal(await ev('document.getElementById("main-account").hidden'),true);
 await click('#session-expired-accept');await until('location.pathname==="/"&&document.body.dataset.auth==="locked"&&typeof csrf!=="undefined"&&csrf&&!sessionEnding');
 await click('#gate-login');await until('!document.getElementById("main-login").hidden');
 for(const width of [390,320]){await size(width);assert.ok(await ev('document.documentElement.scrollWidth<=innerWidth'));if(width===390)await shot('inline-login-390')}
 assert.deepEqual(errors,[]);
 const report={ok:true,duplicate_guide_removed:true,main_body_matches_title_width:true,single_emphasized_title:true,paichai_intro:true,semester_and_oml:true,campus_image_loaded:true,inline_login:true,main_not_basic:true,connection_test_before_login:true,repeat_logout_without_refresh:2,account_switch:true,session_expiry:true,failed_test_clears_success:true,no_idle_polling:true,no_password_in_card:true,widths:[1920,1440,768,390,320],screenshots:out};
 fs.writeFileSync(path.join(root,'runtime/main-browser-verification.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
})().catch(error=>{console.error(error);process.exitCode=1}).finally(()=>{ws?.close();browser.kill();server.kill()});
