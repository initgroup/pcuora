"""실제 인증/세션 API + 격리 설정 + Oracle 응답 fixture. 실제 DB/학생 설정은 변경하지 않습니다."""
import json
import socket
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import uvicorn
from fastapi.responses import JSONResponse
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from app import create_app
from backend import db, identity, connection_profile
qa={'offset':0,'failure':False,'checks':0}
people=[{'student_id':'QA2026','name':'홍길동','department':'소프트웨어학','grade':4,'db_user':'STUDENT_QA'},
        {'student_id':'QA2027','name':'김학생','department':'소프트웨어학','grade':3,'db_user':'STUDENT_QB'},
        {'student_id':'V01041','name':'테스트강사','department':'소프트웨어학','grade':4,'db_user':'STUDENT_QT'}]

@contextmanager
def connection(cfg, **options):
    def ping():
        if cfg.get('DB_PASSWORD')!='FixturePassword' or qa['failure']:
            raise RuntimeError('ORA-01017: invalid credentials')
    ping()
    yield SimpleNamespace(username=cfg['DB_USER'],ping=ping)

def query(conn,name,**binds):
    if name=='connection_profile.sql':
        qa['checks']+=1
        return [{'session_user':conn.username,'current_schema':conn.username,'database_name':'LAB_DB',
                 'service_name':'lab_machine_learning_low.adb.oraclecloud.com','server_host':'lab-db-host','instance_name':'lab_instance'}]
    if name=='connection_info.sql':
        return [{'privilege':value} for value in ('CREATE TABLE','CREATE PROCEDURE','CREATE MINING MODEL')]
    raise AssertionError('Unexpected SQL '+name)

app=create_app({'SECRET_KEY':'main-browser-fixture','SESSION_CLOCK':lambda:time.time()+qa['offset']})
@app.middleware('http')
async def fixture(request,next_call):
    if request.url.path=='/qa/state':return JSONResponse(qa)
    if request.url.path=='/qa/fail':qa['failure']=True;return JSONResponse({'ok':True})
    if request.url.path=='/qa/recover':qa['failure']=False;return JSONResponse({'ok':True})
    if request.url.path=='/qa/expire':qa['offset']+=1801;return JSONResponse({'ok':True})
    if request.url.path=='/api/assignments/mission/status':
        from backend.assignment_templates import ASSIGNMENTS
        return JSONResponse({'ready':False,'config':ASSIGNMENTS['mission'],'objects':[],'missing':['fixture missing'],'issues':[{'kind':'missing'}],'models':[],'preparation':{}})
    return await next_call(request)

if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='main-login-qa-') as directory:
        tmp=Path(directory);(tmp/'security').mkdir()
        roster=tmp/'security/students.json';roster.write_text(json.dumps(people),encoding='utf-8')
        env=tmp/'security/student.env';env.write_text('DB_DSN=lab_low\nWALLET_PASSWORD=UnusedFixtureWallet\n',encoding='utf-8')
        with patch.object(identity,'ROSTER',roster),patch.object(db,'ROOT',tmp),patch.dict('os.environ',{'OML_ENV_FILE':str(env)}),patch('app.connection',side_effect=connection),patch.object(connection_profile,'query',side_effect=query):
            with socket.socket() as listener:
                listener.bind(('127.0.0.1',0));listener.listen(128)
                print('MAIN_QA_URL=http://127.0.0.1:'+str(listener.getsockname()[1]),flush=True)
                uvicorn.Server(uvicorn.Config(app,log_level='error')).run(sockets=[listener])
