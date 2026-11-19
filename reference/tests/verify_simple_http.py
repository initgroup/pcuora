"""실제 로그인/DB 조회/SQL 로그/읽기 전용 코딩도움말 HTTP 검증. 비밀값 출력 금지."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from backend.db import student_settings
from backend import identity
from app import create_app
from unittest.mock import patch
from backend import service

def verify():
    cfg=student_settings();person=next(p for p in identity.roster() if p['db_user']==cfg['DB_USER'] and identity.is_instructor(p))
    result={}
    with TestClient(create_app()) as client:
        assert client.get('/api/data').status_code==401
        session=client.get('/api/session').json()
        login=client.post('/api/identity',json={'student_id':person['student_id'],'name':person['name'],'db_password':cfg['DB_PASSWORD']},headers={'X-CSRF-Token':session['csrf']})
        assert login.status_code==200,login.status_code
        token=login.json()['csrf'];headers={'X-CSRF-Token':token}
        for path in ('/basic','/mission','/creative','/api/status','/api/data?use_yn=Y&split=TRAIN','/api/data/prepared?variant=RAW&source_kind=TRAIN','/api/models','/api/models/dictionary?variant=RAW','/api/models/dictionary?variant=CLEAN','/api/predictions/data','/api/assignments/mission/status','/api/assignments/creative/status'):
            response=client.get(path)
            assert response.status_code==200,(path,response.status_code,response.text[:120])
            if path.startswith('/api/'):
                data=response.json();assert data.get('trace'),path
                for key in ('DB_PASSWORD','WALLET_PASSWORD'):
                    if cfg.get(key):assert cfg[key] not in response.text
                result[path]={'status':response.status_code,'trace_count':len(data['trace'])}
        response=client.get('/api/data?use_yn=N&split=TRAIN').json()
        last=next(r for r in response['trace'] if r['path']=='sql/queries/training_rows.sql')
        assert "'N'" in last['rendered_sql'] and "'TRAIN'" in last['rendered_sql']
        for operation in ('status','data','import','prepare','prepared-data','initialize','train','evaluate','confirm','prediction-import','prediction-data','predict','columns','connection'):
            for assignment in ('basic','mission','creative'):
                response=client.get('/api/coding-help',params={'operation':operation,'assignment':assignment,'variant':'RAW'})
                assert response.status_code==200,(operation,assignment,response.status_code)
                assert response.json()['sources']
        # 라우팅만 검증합니다. 실제 기본 모델을 만들거나 삭제하지 않습니다.
        with patch.object(service,'prepare_model_data',return_value=[]) as prepare:
            assert client.post('/api/data/prepare',json={'variant':'CLEAN'},headers=headers).status_code==200
            assert prepare.call_args.args[1:] == ('CLEAN',)
            assert client.post('/api/data/prepare',json={'variant':'RAW'}).status_code==403
        with patch.object(service,'train_model',return_value=[]) as train:
            for action in ('INIT','RETRAIN','ADD_TRAIN'):
                assert client.post('/api/models/train',json={'variant':'RAW','action':action},headers=headers).status_code==200
                assert train.call_args.args[1:]==('RAW',action)
        with patch.object(service,'delete_model',return_value=[]) as delete:
            assert client.post('/api/models/delete',json={'variant':'CLEAN'},headers=headers).status_code==200
            assert delete.call_args.args[1:] == ('CLEAN',)
        for path in ('/api/models/append','/api/data/row','/api/data/delete'):
            assert client.post(path,json={},headers=headers).status_code==404
        assert client.post('/api/models/delete',json={'variant':'RAW'}).status_code==403
        current=client.get('/api/status').json()['state'].get('confirmed_current')==1
        if current:
            # PREDICT는 준비행 INSERT SELECT를 포함하므로 실제 실행은 격리 DB 검증에서만 합니다.
            with patch.object(service,'predictions',return_value=[]) as predict:
                response=client.post('/api/predictions/run',json={'experiment':'baseline'},headers=headers)
                assert response.status_code==200,response.text[:200]
                predict.assert_called_once()
        else:
            response=client.post('/api/predictions/run',json={'experiment':'baseline'},headers=headers)
            assert response.status_code==400,response.status_code
        missing=client.post('/api/assignments/mission/train',json={'variant':'RAW'},headers=headers)
        assert missing.status_code==409,missing.status_code
        assert '02_procedure.sql' in missing.text
        assert client.post('/api/data/delete',json={'case_id':1},headers=headers).status_code==404
        assert client.get('/api/sources/student.env').status_code==404
        assert client.get('/instructor/python-web-lecture.html').status_code==200
        client.post('/api/logout',json={},headers=headers)
        assert client.get('/api/status').status_code==401
        assert client.get('/instructor/python-web-lecture.html').status_code==401
    (ROOT/'runtime/simple-http-verification.json').write_text(json.dumps({'ok':True,'checks':result},indent=2),encoding='utf-8')
    print(json.dumps({'ok':True,'routes':len(result),'coding_help_cases':42,'prediction_rows':0,'unconfirmed_prediction_blocked':not current,'all_mutations_mocked_or_blocked':True,'auth_csrf_secrets_checked':True}))

if __name__=='__main__':verify()
