"""브라우저 전용 격리 fixture: 가상 로그인·객체 미생성 상태, 실제 배포 CSV. DB 접근 금지."""
import socket
import csv
import io
import sys
from pathlib import Path
from unittest.mock import patch
import uvicorn
from fastapi.responses import JSONResponse
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from app import create_app
from backend.assignment_templates import ASSIGNMENTS
from backend.mission_guide import generate, table_sql
import json
CATALOG=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
app=create_app({'SECRET_KEY':'mission-csv-browser-fixture'})
selection={'key':''}
upload_qa={'enabled':False,'posts':[]}
@app.middleware('http')
async def fixture(request,next_call):
    if request.url.path=='/qa/upload':
        if request.method=='POST':upload_qa.update(await request.json())
        return JSONResponse(upload_qa)
    if upload_qa['enabled'] and request.url.path.endswith('/csv') and request.url.path.startswith('/api/assignments/'):
        if request.headers.get('X-CSRF-Token')!='fixture-only':return JSONResponse({'error':'CSRF'},status_code=403)
        form=await request.form();file=form['file'];raw=await file.read()
        values=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
        parts=request.url.path.split('/');key=parts[3];prediction=parts[4]=='prediction-import'
        name='OML_'+key.upper()+('_PREDICT' if prediction else '_DATA')
        upload_qa['posts'].append({'assignment':key,'action':parts[4],'filename':file.filename,'rows':len(values),'mission':form.get('mission','')})
        return JSONResponse({'loaded_rows':len(values),'table':'QA.'+name,'message':'CSV 적재 완료 · '+str(len(values))+'행'})
    if upload_qa['enabled'] and request.method=='POST' and request.url.path.endswith(('/data','/prediction-data')):
        return JSONResponse({'rows':[{'case_id':1,'feature':'42','label':'A'}]})
    if request.url.path=='/api/assignments/mission/selection':
        if request.method=='POST':selection['key']=(await request.json())['key']
        return JSONResponse(selection)
    if request.url.path=='/api/basic/dataset/preview':
        from backend.basic_dataset import preview
        return JSONResponse(preview(request.query_params.get('kind','training'),request.query_params.get('split','all'),int(request.query_params.get('page','1'))))
    if request.url.path=='/api/basic/dataset/schema':
        from backend.basic_dataset import table_schema
        return JSONResponse(table_schema(request.query_params.get('kind','training'),owner='QA'))
    if request.url.path=='/api/assignments/mission/schema':
        item=next(item for item in CATALOG if item['key']==request.query_params.get('mission'))
        return JSONResponse(table_sql(item,request.query_params.get('kind','training'),schema='QA'))
    if request.url.path=='/api/coding-help' and request.query_params.get('assignment')=='mission':
        item=next(item for item in CATALOG if item['key']==(selection['key'] or 'festival'))
        return JSONResponse(generate(item,request.query_params.get('operation','setup'),request.query_params.get('variant','RAW'),request.query_params.get('source_kind','ALL'),schema='QA',trigger_id=request.query_params.get('trigger_id',''),trigger_label=request.query_params.get('trigger_label',''),page=request.query_params.get('page','')))
    if request.url.path=='/api/session':
        return JSONResponse({'csrf':'fixture-only','identity':{'name':'CSV UI QA','student_id':'QA','db_user':'QA'},'configured':True})
    if request.url.path in ('/api/assignments/mission/status','/api/assignments/creative/status','/api/assignments/mission/link','/api/assignments/creative/link'):
        key=request.url.path.split('/')[3]
        objects=[{'object_name':ASSIGNMENTS[key][field],'object_type':'TABLE','status':'VALID','object_id':index+1} for index,field in enumerate(('training_table','prediction_table'))] if upload_qa['enabled'] else []
        return JSONResponse({'ready':False,'config':ASSIGNMENTS[key],'objects':objects,'missing':['fixture objects not created'],'issues':[{'kind':'missing'}],'models':[],'preparation':{}})
    if request.url.path.startswith('/api/') and not request.url.path.startswith('/api/datasets'):
        return JSONResponse({'error':'DB actions disabled in CSV UI fixture'},status_code=403)
    return await next_call(request)
if __name__=='__main__':
    with patch('app.connection',side_effect=AssertionError('No database access in CSV UI fixture')):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));listener.listen(128)
            print('CSV_QA_URL=http://127.0.0.1:'+str(listener.getsockname()[1]),flush=True)
            uvicorn.Server(uvicorn.Config(app,log_level='error')).run(sockets=[listener])
