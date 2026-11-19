"""브라우저 전용 격리 fixture: 가상 로그인·객체 미생성 상태, 실제 배포 CSV. DB 접근 금지."""
import socket
import time
import sys
from pathlib import Path
from unittest.mock import patch
import uvicorn
from fastapi.responses import JSONResponse
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from app import create_app
from backend.assignment_templates import ASSIGNMENTS
app=create_app({'SECRET_KEY':'mission-csv-browser-fixture'})
qa={'expires':time.time()+1800,'active':True,'expired':False,'reads':0,'extensions':0}
selection={'key':''}
@app.middleware('http')
async def fixture(request,next_call):
    if request.url.path=='/qa/state':return JSONResponse(qa)
    if request.url.path=='/qa/expire':
        qa.update(active=False,expired=True)
        return JSONResponse({'ok':True})
    if request.url.path=='/qa/reset':
        qa.update(active=True,expired=False,expires=time.time()+1800)
        return JSONResponse({'ok':True})
    if request.url.path=='/api/session/extend':
        if not qa['active']:return JSONResponse({'error':'Session expired','code':'SESSION_TIMEOUT'},status_code=401)
        if request.headers.get('X-CSRF-Token')!='fixture-only':return JSONResponse({'error':'CSRF'},status_code=403)
        qa.update(expires=time.time()+1800,extensions=qa['extensions']+1)
        return JSONResponse({'session':{'expires_at':qa['expires'],'server_time':time.time()}})
    if request.url.path=='/api/assignments/mission/selection':
        if request.method=='POST':selection['key']=(await request.json())['key']
        return JSONResponse(selection)
    if request.url.path=='/api/session':
        qa['reads']+=1
        expired=qa['expired'];qa['expired']=False
        return JSONResponse({'csrf':'fixture-only','identity':{'name':'Session UI QA','student_id':'QA','db_user':'QA'} if qa['active'] else None,'configured':True,'session':{'expires_at':qa['expires'] if qa['active'] else None,'server_time':time.time(),'expired':expired}})
    if request.url.path=='/unused-session':
        return JSONResponse({'csrf':'fixture-only','identity':{'name':'CSV UI QA','student_id':'QA','db_user':'QA'},'configured':True})
    if request.url.path=='/api/assignments/mission/status':
        return JSONResponse({'ready':False,'config':ASSIGNMENTS['mission'],'objects':[],'missing':['fixture objects not created'],'issues':[{'kind':'missing'}],'models':[],'preparation':{}})
    if request.url.path.startswith('/api/') and not request.url.path.startswith('/api/datasets'):
        return JSONResponse({'error':'DB actions disabled in CSV UI fixture'},status_code=403)
    return await next_call(request)
if __name__=='__main__':
    with patch('app.connection',side_effect=AssertionError('No database access in CSV UI fixture')):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));listener.listen(128)
            print('CSV_QA_URL=http://127.0.0.1:'+str(listener.getsockname()[1]),flush=True)
            uvicorn.Server(uvicorn.Config(app,log_level='error')).run(sockets=[listener])
