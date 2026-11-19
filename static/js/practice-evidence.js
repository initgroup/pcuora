"use strict";
// 서버의 현재 DB 검증 결과만 표시합니다. 클릭 이력으로 성공을 만들지 않습니다.
let practiceEvidenceVersion=0,practiceEvidenceBusy=false,practiceEvidenceResult=null,practiceDetailOpener=null;
const practiceSuccessBadges={home:'오브젝트 생성 성공',data:'학습자료 적재 성공',models:'모델생성 평가 성공',predictions:'모델예측 실행 성공'};
function proofNode(tag,className,value){
 const node=document.createElement(tag);if(className)node.className=className;
 if(value!==undefined)node.textContent=value;return node;
}
const practiceAssignmentTitles={basic:'기본과제',mission:'미션과제',creative:'창의과제'};
function renderPracticeSeal(result=null){
 const seal=$('practice-seal'),complete=result?.complete===true;
 const label=complete?(practiceAssignmentTitles[result.assignment]||'실습')+' 성공':result?result.passed+' / 4 완료':'확인 필요';
 seal.replaceChildren();seal.setAttribute('aria-label',label+' · 세부 작업 보기');
 if(!complete){seal.textContent=label;return;}
 const top=proofNode('span','practice-seal-meta','OML · VERIFIED'),mark=proofNode('span','practice-seal-mark','✓'),caption=proofNode('span','practice-seal-caption','전 단계 검증 완료');
 for(const node of [top,mark,caption])node.setAttribute('aria-hidden','true');
 seal.append(top,mark,proofNode('strong','practice-seal-label',label),caption);
}
function clearPracticeEvidence(message='현재 상태를 다시 확인하세요.'){
 ++practiceEvidenceVersion;practiceEvidenceResult=null;closePracticeDetail(false);const root=$('practice-proof');if(!root)return;
 $('practice-seal').disabled=true;$('practice-detail-groups')?.replaceChildren();text('practice-detail-summary','');
 text('practice-proof-topic','현재 과제의 기능 실행 결과를 확인합니다.');
 root.dataset.state='pending';renderPracticeSeal();text('practice-proof-status',message);
 text('practice-proof-student',person?person.name+' · '+person.student_id:'로그인 후 확인');
 text('practice-proof-owner',person?.db_user||'—');text('practice-proof-time','확인 전');
 $('practice-capture-guide').hidden=true;
 const row=proofNode('tr'),cell=proofNode('td','',message);cell.colSpan=3;row.append(cell);$('practice-proof-steps').replaceChildren(row);
 $('practice-verify').disabled=!person||practiceEvidenceBusy;
}
function renderPracticeEvidence(result){
 const root=$('practice-proof');if(!root||!person||!result)return;
 if(result.student?.student_id!==person.student_id||result.student?.db_user!==person.db_user)return;
 ++practiceEvidenceVersion;closePracticeDetail(false);practiceEvidenceResult=result;root.dataset.state=result.complete?'success':'pending';
 $('practice-seal').disabled=false;
 text('practice-proof-topic',result.title+(result.mission_title?' · '+result.mission_title:''));
 text('practice-proof-student',result.student.name+' · '+result.student.student_id);text('practice-proof-owner',result.student.db_user);
 text('practice-proof-time',new Date(result.checked_at).toLocaleString('ko-KR'));
 renderPracticeSeal(result);
 const checks=result.steps.flatMap(step=>step.checks||[]),completed=checks.filter(check=>check.success).length;
 text('practice-proof-status',result.complete?'모든 단계 검증 완료':result.passed+'/4 단계 완료'+(checks.length?' · 세부 작업 '+completed+'/'+checks.length+' 완료 · '+(checks.length-completed)+'개 남음':' · 단계를 선택해 남은 작업을 확인하세요.'));
 const rows=$('practice-proof-steps');rows.replaceChildren();
 for(const [index,step] of result.steps.entries()){
  const row=proofNode('tr'),heading=proofNode('th'),link=proofNode('a','',String(index+1).padStart(2,'0')+' '+step.label);
  heading.scope='row';link.href=result.assignment==='basic'?'/basic#'+step.id:'#';link.dataset[result.assignment==='basic'?'basicTab':'assignmentTab']=step.id;
  heading.append(link);const detail=proofNode('td','practice-proof-detail'),status=proofNode('td'),checks=step.checks||[],remaining=checks.filter(check=>!check.success);
  if(!step.success&&checks.length){
   detail.append(proofNode('strong','','남은 작업 '+remaining.length+'개'),proofNode('span','',remaining.slice(0,2).map(check=>check.label).join(' · ')+(remaining.length>2?' 외 '+(remaining.length-2)+'개':'')));
  }else detail.textContent=step.detail;
  const badge=step.success?(practiceSuccessBadges[step.id]||step.badge):checks.length?step.completed+'/'+step.total+' 완료':step.badge;
  const button=proofNode('button','practice-step-stamp',(step.success?'✓ ':'○ ')+badge);button.type='button';button.dataset.proofStep=step.id;
  button.setAttribute('aria-haspopup','dialog');button.setAttribute('aria-controls','practice-detail-dialog');button.setAttribute('aria-label',step.label+' · '+badge+' · 세부 작업 보기');
  row.dataset.state=step.success?'success':'pending';status.append(button);
  if(checks.length&&!step.success)status.append(proofNode('small','practice-work-count',step.remaining+'개 남음 · 클릭해 상세 확인'));
  row.append(heading,detail,status);rows.append(row);
 }
 $('practice-capture-guide').hidden=!result.complete;$('practice-verify').disabled=practiceEvidenceBusy;
}
async function verifyPracticeEvidence(){
 if(!person||practiceEvidenceBusy)return;
 if(basicWorkspace?basicMutationBusy()||refreshing:typeof assignmentBusy!=='undefined'&&(assignmentBusy||assignmentPhase==='loading'))return;
 practiceEvidenceBusy=true;clearPracticeEvidence('현재 DB 상태와 성공 결과를 확인하고 있습니다.');
 const version=practiceEvidenceVersion,generation=sessionGeneration,key=basicWorkspace?'basic':document.querySelector('.assignment-workspace')?.dataset.assignment;
 try{
  const result=await api('/api/practice/'+key+'/evidence');
  if(version!==practiceEvidenceVersion||generation!==sessionGeneration||!person)return;
  renderPracticeEvidence(result);
 }catch(error){
  if(generation!==sessionGeneration)return;
  clearPracticeEvidence('최종 확인 실패 · 다시 확인하세요.');operationNotice(error);
 }finally{practiceEvidenceBusy=false;if($('practice-verify'))$('practice-verify').disabled=!person;}
}
on('practice-verify','click',verifyPracticeEvidence);

function closePracticeDetail(restore=true){
 const opener=practiceDetailOpener;practiceDetailOpener=null;
 const dialog=$('practice-detail-dialog');if(dialog?.open)HelpWindow.close(dialog);
 if(restore&&person&&opener?.isConnected)opener.focus({preventScroll:true});
}
function openPracticeDetail(id=''){
 const result=practiceEvidenceResult;
 if(!result||!person||result.student.student_id!==person.student_id||result.student.db_user!==person.db_user)return;
 const steps=id?result.steps.filter(step=>step.id===id):result.steps;if(!steps.length)return;
 const checks=steps.flatMap(step=>step.checks||[]),completed=checks.filter(check=>check.success).length;
 text('practice-detail-title',id?steps[0].label+' · 세부 작업':'전체 실습 · 세부 작업');
 text('practice-detail-summary',checks.length?completed+'/'+checks.length+' 완료 · '+(checks.length-completed)+'개 남음':'현재 확인 결과');
 const groups=$('practice-detail-groups');groups.replaceChildren();
 for(const step of steps){
  const section=proofNode('section','practice-check-group');
  if(!id)section.append(proofNode('h3','',step.label));
  const list=proofNode('ul','practice-check-list');
  for(const check of step.checks||[]){
   const item=proofNode('li'),state=proofNode('span','practice-check-state',check.success?'✓ 완료':'○ 남음'),body=proofNode('div');
   item.dataset.state=check.success?'success':'pending';body.append(proofNode('strong','',check.label));
   if(check.detail)body.append(proofNode('p','',check.detail));
   item.append(state,body);list.append(item);
  }
  section.append(list);if(!step.checks?.length)section.append(proofNode('p','',step.detail));groups.append(section);
 }
 const go=$('practice-detail-go');go.hidden=!id;delete go.dataset.basicTab;delete go.dataset.assignmentTab;
 if(id){go.href=result.assignment==='basic'?'/basic#'+id:'#';go.dataset[result.assignment==='basic'?'basicTab':'assignmentTab']=id;}
 practiceDetailOpener=document.activeElement;HelpWindow.open($('practice-detail-dialog'),{reset:true});$('close-practice-detail').focus({preventScroll:true});
}
on('practice-seal','click',()=>openPracticeDetail());
on('practice-proof-steps','click',event=>{const button=event.target.closest('[data-proof-step]');if(button)openPracticeDetail(button.dataset.proofStep);});
on('close-practice-detail','click',()=>closePracticeDetail());
on('practice-detail-go','click',event=>{
 const id=event.currentTarget.dataset.basicTab||event.currentTarget.dataset.assignmentTab,assignment=practiceEvidenceResult?.assignment;
 closePracticeDetail(false);
 requestAnimationFrame(()=>document.querySelector(assignment==='basic'?'#basic-workflow [data-basic-tab="'+id+'"]':'.assignment-tabs [data-assignment-tab="'+id+'"]')?.focus({preventScroll:true}));
});
on('practice-detail-dialog','close',()=>{const opener=practiceDetailOpener;practiceDetailOpener=null;if(person&&opener?.isConnected)opener.focus({preventScroll:true});});

document.addEventListener('click',event=>{if(event.target.closest('[data-basic-tab],[data-assignment-tab],[data-step-next]')&&$('practice-detail-dialog')?.open)closePracticeDetail(false);});
