"""UI-only fixtures: synthetic login/results. Every DB connection and mutating API is blocked."""
import csv
import asyncio
import json
import socket
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import uvicorn
from fastapi.responses import JSONResponse
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from app import create_app
from backend.assignment_templates import ASSIGNMENTS
from backend.coding_help import describe
from backend.mission_guide import generate, table_sql, schema_guide
from backend.source_help import read_source
from backend import basic_dataset, model_dictionary, practice_evidence
CATALOG=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
OWNER='STUDENT_QA'
NOW='2026-11-19T09:30:00'
selection={'key':'festival'}
qa={'blocked':[],'reads':[],'mutations':[]}
app=create_app({'SECRET_KEY':'workspace-visual-fixture-only'})
def runtime_trace(assignment,mode,kind):
    if not qa.get('runtime_sql'):return {}
    from backend.sql_trace import rendered
    sql=(ROOT/'sql/queries/prepared_rows.sql').read_text(encoding='utf-8-sig').replace('{{table}}','OML_'+assignment.upper()+'_PREPARED').rstrip().rstrip(';')
    binds={'variant':mode,'source_kind':kind}
    return {'trace':[dict(sql=sql,binds=binds,rendered_sql=rendered(sql,binds),path='sql/queries/prepared_rows.sql',status='success',at='2026-11-19T09:30:00+00:00')]}

def dictionary_fixture(mode='RAW'):
    model='OML_BASIC_'+mode+'_MODEL'
    objects=[dict(object_name='DM$'+code+model,internal_code=code,object_type=typ,status='VALID',statistic_rows=None) for code,typ in [('P5','TABLE'),('VC','VIEW'),('VM','VIEW'),('VO','VIEW')]]
    columns=[dict(object_name=obj['object_name'],column_id=i+1,column_name=col,data_type=typ,data_length=100,data_precision=None,data_scale=None,nullable='Y') for obj in objects for i,(col,typ) in enumerate([('ACTUAL_TARGET_VALUE','VARCHAR2'),('PREDICTED_TARGET_VALUE','VARCHAR2'),('COST','NUMBER')]+([('VALUE','XMLTYPE')] if obj['internal_code']=='VO' else []))]
    def metadata(conn,filename,**binds):
        if filename=='dictionary_model.sql':return [dict(model_name=model,algorithm='DECISION_TREE')]
        if filename=='dictionary_views.sql':return [dict(view_name=obj['object_name'],view_type='Scoring Cost Matrix' if obj['internal_code']=='VC' else 'Decision Tree Build Cost Matrix' if obj['internal_code']=='VM' else 'Decision Tree Nodes') for obj in objects if obj['object_type']=='VIEW']
        if filename=='dictionary_generated_objects.sql':return objects
        if filename=='dictionary_generated_columns.sql':return columns
        return []
    def data(conn,filename,**kwargs):
        return [] if 'DM$VM' in kwargs['replacements']['view'] else [dict(actual_target_value='BUY',predicted_target_value='SELL',cost=1,value='<Element>AA</Element>')]
    conn=MagicMock();conn.username=OWNER
    with patch.object(model_dictionary,'query',side_effect=metadata),patch.object(model_dictionary,'execute',side_effect=data):
        return model_dictionary.read(conn,mode)

def models(key='basic'):
    result=[dict(variant=mode,model_name='OML_'+key.upper()+'_'+mode+'_MODEL',exists=int(mode!='RAW' or qa.get('raw_exists',True)),is_current=int(mode!='RAW' or qa.get('raw_exists',True)),is_confirmed=int(mode==qa.get('confirmed_mode','CLEAN')),trained_at=NOW,trained_rev='UI_FIXTURE',status='VALID') for mode in ('RAW','CLEAN')]
    if key=='basic' and (life:=qa.get('lifecycle')):
        for row in result:
            row.update(exists=int(life['models'][row['variant']]),is_current=int(life['models'][row['variant']]),is_confirmed=int(life['confirmed']==row['variant']))
    return result
def objects(key='basic'):
    cfg=ASSIGNMENTS[key] if key in ASSIGNMENTS else dict(training_table='OML_BASIC_DATA',prepared_table='OML_BASIC_PREPARED',prediction_table='OML_BASIC_PREDICT',procedure_name='OML_BASIC_RUN')
    return [dict(object_name=cfg[field],object_type='PROCEDURE' if field=='procedure_name' else 'TABLE',status='VALID',object_id=100+i,created=NOW) for i,field in enumerate(('training_table','prepared_table','prediction_table','procedure_name'))]
def prep():
    return {mode:dict(ready=True,rows=690,fit_rows=330,test_rows=360) for mode in ('RAW','CLEAN')}
def linked_preparations(key):
    return {mode:dict(ready=qa.get('linked_preparations',{}).get(key,False),rows=1500,
                      fit_rows=1200 if mode=='RAW' else 249,test_rows=300) for mode in ('RAW','CLEAN')}

def source_rows(custom=False):
    if custom:
        return [dict(case_id=i,interest_score=str(48+i),reservation_score=str(60+i),promotion_score=str(70+i),label=['QUIET','NORMAL','BUSY'][i%3],split='TRAIN' if i<6 else 'TEST',use_yn='Y') for i in range(1,9)]
    return [dict(case_id=i,stock=['AA','AXP','BA'][i%3],week_ending='2011-01-07',return_pct='1.25',range_pct='2.90',volume_change_pct='-3.10',close_price='42.50',signal='BUY' if i%2 else 'SELL',split='TRAIN' if i<6 else 'TEST',use_yn='Y') for i in range(1,9)]
def prepared_rows(custom=False,mode='RAW'):
    return [dict(row,prep_mode=mode,source_kind=row['split'],fit_yn='Y',exclude_reason=None,prepared_at=NOW) for row in source_rows(custom)]
def prediction_rows(custom=False):
    return [dict(case_id=100+i,predicted=('BUSY' if custom else 'BUY') if i%2 else ('NORMAL' if custom else 'SELL'),probability=0.826125) for i in range(1,7)]
def metrics(custom=False):
    a,b=('BUSY','NORMAL') if custom else ('BUY','SELL')
    return [dict(variant=mode,actual=x,predicted=y,n=n) for mode in ('RAW','CLEAN') for x,y,n in [(a,a,145),(a,b,25),(b,a,30),(b,b,160)]]
def status():
    objs=objects()
    def storage(i,rows):
        row=objs[i]
        return dict(name=row['object_name'],qualified_name=OWNER+'.'+row['object_name'],exists=True,object_id=row['object_id'],created_at=NOW,loaded_at=NOW,rows=rows)
    result=dict(connected=True,initialized=True,user=OWNER,version='UI fixture',objects=objs,models=models(),state=dict(total_rows=720,used_rows=690,disabled_rows=30,train_rows=330,test_rows=360,data_rev='UI_FIXTURE',confirmed_variant=qa.get('confirmed_mode','CLEAN'),confirmed_current=1),preparation=prep(),storage=storage(0,720),prepared_storage=storage(1,690),prediction_storage=storage(2,30))
    if life:=qa.get('lifecycle'):
        result['initialized']=life['tables'] and life['registered']
        result['objects']=[row for row in objs if life['tables'] and row['object_type']=='TABLE' or life['registered'] and row['object_type']=='PROCEDURE']
        for key,n in (('storage',life['training']),('prediction_storage',life['prediction']),('prepared_storage',sum(life['prepared'].values()))):
            result[key].update(exists=life['tables'],rows=n)
        result['state'].update(total_rows=life['training'],train_rows=life['training'],test_rows=0,confirmed_current=int(bool(life['confirmed'])),confirmed_variant=life['confirmed'])
        result['models']=[dict(m,exists=int(life['models'][m['variant']]),is_current=int(life['models'][m['variant']]),is_confirmed=int(life['confirmed']==m['variant'])) for m in models()]
        result['preparation']={mode:dict(ready=bool(n),rows=n,fit_rows=n,test_rows=0) for mode,n in life['prepared'].items()}
    return result
proof_states={}
def proof_saved(key):
    if key not in proof_states:
        stamps={mode:dict(fingerprint=key+'-'+mode,created=NOW) for mode in ('RAW','CLEAN')}
        proof_states[key]={'models':stamps,'assignments':{key:stamps}}
    return proof_states[key]

def proof_inputs():
    return [dict(case_id=100+i,value=qa.get('input_version',1)) for i in range(1,7)]

def proof_record(key,kind,mode,rows):
    from copy import deepcopy
    saved=proof_saved(key)
    with patch.object(practice_evidence.service,'read_state',side_effect=lambda conn:deepcopy(saved)),patch.object(practice_evidence.service,'write_state',side_effect=lambda conn,value:saved.update(value)):
        practice_evidence.begin(None,key,kind,mode)
        return practice_evidence.record(None,key,kind,mode,rows,inputs=proof_inputs() if kind=='predict' else None,mission_key=selection['key'] if key=='mission' else '')

def proof_result(key):
    state=status() if key=='basic' else dict(ready=True,user=OWNER,objects=objects(key),config=ASSIGNMENTS[key],state={'total_rows':1500},prediction_storage={'rows':30},models=models(key),preparation=prep())
    if key!='basic':
        state['preparation']={mode:dict(ready=True,fit_rows=1200,test_rows=300) for mode in ('RAW','CLEAN')}
    if key!='basic' and qa.get('preparation_linking'):state['preparation']=linked_preparations(key)
    if qa.get('proof_missing_run'):
        state['objects']=[obj for obj in state.get('objects',[]) if obj['object_type']!='PROCEDURE']
        state['initialized']=False;state['ready']=False
    if qa.get('proof_clean_pending'):state['preparation']['CLEAN']['ready']=False
    if qa.get('stale_proof'):
        state['models']=[dict(m,is_current=0) for m in state['models']]
    topic=next(item for item in CATALOG if item['key']==selection['key']) if key=='mission' else None
    result=practice_evidence.summarize(key,state,proof_saved(key),inputs=proof_inputs(),mission=topic)
    return dict(result,title={'basic':'기본과제','mission':'미션과제','creative':'창의과제'}[key],
        student=dict(student_id='QA2026',name='화면 검증',db_user=OWNER),mission_title=topic['title'] if topic else '')

def proof_metrics(key):
    result=metrics(key!='basic')
    if key!='basic':
        result=[dict(r,n=100 if r['n']==160 else r['n']) for r in result]
    return result

@app.middleware('http')
async def fixture(request,next_call):
    path=request.url.path;q=request.query_params
    if path=='/qa/state':return JSONResponse(qa)
    if path=='/qa/feedback':
        qa.update(await request.json());return JSONResponse({'ok':True})
    if qa.get('work_delay_path') and path.startswith(qa['work_delay_path']):
        await asyncio.sleep(qa.get('work_delay',.8))
        if qa.get('work_failure'):return JSONResponse({'error':'격리 적재 오류'},status_code=500)
    if path=='/qa/runtime':qa['runtime_sql']=True;return JSONResponse({'ok':True})
    if path=='/qa/preparation-link':
        qa.update(preparation_linking=True,linked_preparations={},evidence=True)
        return JSONResponse({'ok':True})
    if path=='/qa/evidence':
        qa['evidence']=True
        return JSONResponse({'ok':True})
    if path=='/qa/evidence/change':
        qa[q.get('kind','input_version')]=int(q.get('value','2'))
        return JSONResponse({'ok':True})
    if path.startswith('/api/practice/') and path.endswith('/evidence'):
        if qa.get('evidence_error'):return JSONResponse({'error':'격리 조회 실패'},status_code=500)
        return JSONResponse(proof_result(path.split('/')[3]))

    if path=='/qa/lifecycle':
        qa['lifecycle']={'tables':True,'registered':True,'training':720,'prediction':30,'prepared':{'RAW':690,'CLEAN':690},'models':{'RAW':True,'CLEAN':True},'confirmed':'CLEAN'}
        return JSONResponse(status())
    if path=='/api/basic/lifecycle' and qa.get('lifecycle'):
        body=await request.json();action=body['action'];mode=body.get('variant','RAW');life=qa['lifecycle']
        qa['mutations'].append(dict(body))
        if action=='drop-objects':life.update(tables=False,registered=False,training=0,prediction=0,prepared={'RAW':0,'CLEAN':0},models={'RAW':False,'CLEAN':False},confirmed=None)
        elif action=='create-tables':life['tables']=True
        elif action in ('register-procedure','reregister-procedure'):life['registered']=True
        elif action=='clear-training':life.update(training=0,prepared={'RAW':0,'CLEAN':0},confirmed=None)
        elif action=='clear-prediction':life['prediction']=0
        elif action=='clear-prepared':life['prepared'][mode]=0;life['confirmed']=None if life['confirmed']==mode else life['confirmed']
        elif action=='unconfirm':life['confirmed']=None
        return JSONResponse({'message':'격리 검증 완료',**status()})
    if path=='/api/models/confirm' and qa.get('lifecycle'):
        body=await request.json();mode=body['variant']
        assert mode in ('RAW','CLEAN') and qa['lifecycle']['models'][mode]
        qa['mutations'].append({'action':'confirm-model','variant':mode})
        qa['lifecycle']['confirmed']=mode
        return JSONResponse(status())
    if path=='/api/models/delete' and qa.get('lifecycle'):
        body=await request.json();mode=body['variant'];qa['mutations'].append({'action':'delete-model','variant':mode})
        qa['lifecycle']['models'][mode]=False
        return JSONResponse({'message':'격리 검증 완료',**status()})
    if path in ('/api/data/preview','/api/predictions/preview') and qa.get('lifecycle'):
        from backend.validation import parse_csv, quality
        form=await request.form();values=parse_csv(await form['file'].read(),prediction=path.startswith('/api/predictions'))
        return JSONResponse({'rows':values[:100],'summary':quality(values,prediction=path.startswith('/api/predictions'))})
    if path in ('/api/data/import','/api/predictions/import') and qa.get('lifecycle'):
        body=await request.form();mode=body.get('mode');qa['mutations'].append({'action':path,'mode':mode})
        qa['lifecycle']['training' if path=='/api/data/import' else 'prediction']=8
        return JSONResponse({'message':'격리 검증 완료','operation':'replaced','loaded_rows':8,**status()})

    if path=='/qa/enable-execution':
        qa['simulate_execution']=True
        return JSONResponse({'ok':True})
    if path=='/qa/no-raw-model':
        qa['raw_exists']=False
        return JSONResponse({'ok':True})
    if path=='/api/session':
        qa['session_reads']=qa.get('session_reads',0)+1
        await asyncio.sleep(qa.get('session_delay',0))
        if qa.get('session_failure'):return JSONResponse({'error':'Isolated session lookup failure'},status_code=503)
        person={'student_id':'QA2026','name':'화면 검증','department':'소프트웨어학','grade':4,'db_user':OWNER} if qa.get('authenticated',True) else None
        return JSONResponse({'csrf':'fixture-only','identity':person,'configured':True,'session':{'expires_at':time.time()+1800,'logged_at':time.time(),'server_time':time.time()}})
    if path=='/api/account/connection':
        return JSONResponse({'connection':dict(session_user=OWNER,current_schema=OWNER,checked_at=NOW,elapsed_ms=3,checks=['격리 연결 확인'],privileges=['CREATE TABLE','CREATE PROCEDURE','CREATE MINING MODEL'])})
    if path.startswith('/api/'):
        qa['reads'].append(path)
        if request.method=='POST' and (path=='/api/predictions/run' or path.endswith('/predict') or path.endswith('/selection')):
            qa['mutations'].append(path)
    if path.startswith('/api/sources/'):return JSONResponse(read_source(path.rsplit('/',1)[-1]))
    if path=='/api/coding-help':
        kwargs=dict(variant=q.get('variant','RAW'),source_kind=q.get('source_kind','TRAIN'),
                    trigger_id=q.get('trigger_id',''),trigger_label=q.get('trigger_label',''),page=q.get('page',''))
        if q.get('assignment')=='mission':
            item=next(item for item in CATALOG if item['key']==selection['key'])
            return JSONResponse(generate(item,q.get('operation','setup'),schema=OWNER,**kwargs))
        if q.get('assignment')=='creative':return JSONResponse({'error':'Creative has no SQL guide'},status_code=404)
        return JSONResponse(describe(q.get('operation','data'),user=OWNER,use_yn=q.get('use_yn','ALL'),split=q.get('split','ALL'),**kwargs))
    if path=='/api/status':return JSONResponse(dict(status(),practice=proof_result('basic')) if qa.get('evidence') and q.get('include_evidence') else status())
    if qa.get('simulate_execution') and request.method=='POST' and path in ('/api/initialize','/api/data/prepare','/api/models/train','/api/models/confirm','/api/predictions/import','/api/assignments/mission/link'):
        qa['mutations'].append(path)
        if path=='/api/models/train':qa['raw_exists']=True
        return JSONResponse({'message':'Synthetic fixture completed','loaded_rows':1,**status()})
    if path=='/api/data':return JSONResponse({'rows':source_rows()})
    if path=='/api/data/prepared':return JSONResponse({'rows':prepared_rows(mode=q.get('variant','RAW')),**runtime_trace('basic',q.get('variant','RAW'),q.get('source_kind','ALL'))})
    if path=='/api/models/dictionary':return JSONResponse(dictionary_fixture(q.get('variant','RAW')))
    if path=='/api/models':
        if qa.get('evidence'):
            for mode in ('RAW','CLEAN'):proof_record('basic','evaluate',mode,[r for r in proof_metrics('basic') if r['variant']==mode])
        return JSONResponse({'models':models(),'metrics':metrics(),'details':{mode:[dict(section='SETTING',name='ALGO_NAME',value='ALGO_DECISION_TREE')] for mode in ('RAW','CLEAN')}})
    if path=='/api/predictions/data':return JSONResponse({'rows':[{k:v for k,v in row.items() if k not in ('signal','split')} for row in source_rows()]})
    if path=='/api/predictions/columns':return JSONResponse({'columns':[dict(column_id=i+1,column_name=name,data_type=typ) for i,(name,typ) in enumerate([('RETURN_PCT','NUMBER'),('RANGE_PCT','NUMBER'),('VOLUME_CHANGE_PCT','NUMBER'),('CLOSE_PRICE','NUMBER'),('STOCK','VARCHAR2')])]})
    if path=='/api/predictions/run':
        body=await request.json()
        mode=body.get('variant') or next(m['variant'] for m in models() if m['is_confirmed'])
        qa.setdefault('prediction_variants',[]).append(mode)
        if qa.get('evidence'):proof_record('basic','predict',mode,prediction_rows())
        qa['confirmed_mode']=mode
        if qa.get('lifecycle'):qa['lifecycle']['confirmed']=mode
        return JSONResponse({'rows':prediction_rows(),'input_fingerprint':'UI_FIXTURE','model_name':'OML_BASIC_'+mode+'_MODEL','verified':True})
    if path=='/api/assignments/mission/selection':
        if request.method=='POST':selection['key']=(await request.json())['key']
        return JSONResponse(selection)
    if path=='/api/basic/dataset/preview':return JSONResponse(basic_dataset.preview(q.get('kind','training'),q.get('split','all'),int(q.get('page','1'))))
    if path=='/api/basic/dataset/schema':return JSONResponse(basic_dataset.table_schema(q.get('kind','training'),owner=OWNER))
    if path=='/api/assignments/mission/schema':
        item=next(item for item in CATALOG if item['key']==q.get('mission'))
        return JSONResponse(schema_guide(item,q.get('kind','training'),schema=OWNER))
    if path.startswith('/api/assignments/'):
        pieces=path.strip('/').split('/')
        key=pieces[2];action=pieces[3] if len(pieces)>3 else ''
        if key in ('mission','creative'):
            if action=='link' and qa.get('preparation_linking'):
                qa['mutations'].append(path);qa.setdefault('linked_preparations',{})[key]=True
                return JSONResponse({'message':'Synthetic linkage saved','preparation':linked_preparations(key)})
            if action=='status':
                response={'ready':True,'config':ASSIGNMENTS[key],'objects':objects(key),'missing':[],'issues':[],'models':models(key),'preparation':prep()}
                if qa.get('preparation_linking'):response['preparation']=linked_preparations(key)
                if qa.get('evidence') and q.get('include_evidence'):response['practice']=proof_result(key)
                return JSONResponse(response)
            if action=='data':return JSONResponse({'rows':source_rows(True)})
            if action=='prepared-data':
                body=await request.json()
                return JSONResponse({'rows':prepared_rows(True,body.get('variant','RAW')),**runtime_trace(key,body.get('variant','RAW'),body.get('source_kind','ALL'))})
            if action=='prediction-data':return JSONResponse({'rows':[{k:v for k,v in row.items() if k not in ('label','split')} for row in source_rows(True)]})
            if action=='evaluate':
                result=proof_metrics(key) if qa.get('evidence') else metrics(True)
                mode=(await request.json()).get('variant','RAW')
                result=[r for r in result if r['variant']==mode]
                if qa.get('evidence'):proof_record(key,'evaluate',mode,result)
                return JSONResponse({'rows':result,'input_fingerprint':'UI_FIXTURE'})
            if action=='predict':
                if qa.get('evidence'):proof_record(key,'predict',(await request.json()).get('variant','RAW'),prediction_rows(True))
                return JSONResponse({'rows':prediction_rows(True),'input_fingerprint':'UI_FIXTURE','verified':True})
    if path.startswith('/api/') and not path.startswith('/api/datasets'):
        qa['blocked'].append(path)
        return JSONResponse({'error':'DB and unconfigured actions disabled in visual fixture'},status_code=403)
    return await next_call(request)
if __name__=='__main__':
    with patch('app.connection',side_effect=AssertionError('Actual DB access forbidden in visual fixture')):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));listener.listen(128)
            print('VISUAL_QA_URL=http://127.0.0.1:'+str(listener.getsockname()[1]),flush=True)
            uvicorn.Server(uvicorn.Config(app,log_level='error')).run(sockets=[listener])
