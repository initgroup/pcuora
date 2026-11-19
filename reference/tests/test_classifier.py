"""입력·계정 매핑·CSRF·실제 배포 ZIP의 유출 방지를 검증합니다."""
import ast
import base64
from contextlib import contextmanager
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT),str(ROOT/'scripts')]
from fastapi.testclient import TestClient
from backend import identity, db, sql_files, assignment_templates, service
from app import create_app, SESSION_COOKIE_NAME
from backend.validation import parse_csv,quality
from backend.connection_help import explain
from source_files import inventory
from package_student import build,GUIDE_NAME
from package_submission import build as build_submission


class ClassifierTests(unittest.TestCase):
    def test_recreate_validates_before_drop_and_reloads_from_uploaded_csv(self):
        raw=(ROOT/'data/classification.csv').read_bytes()
        for failure in (None,'csv','drop','initialize','insert'):
            with self.subTest(failure=failure),self.login_project() as (_,env,people):
                events=[];conn=MagicMock(username=people[0]['db_user']);state_file=env.parent/'qa-model-state.json'
                saved={'preparations':{'RAW':{'source':'old'}},'models':{'RAW':{'fingerprint':'old'}},'confirmed':'RAW'}
                state_file.write_text(json.dumps(saved),encoding='utf-8')
                def parse(content):
                    events.append('parse');return parse_csv(content)
                def drop(_conn,path):
                    events.append('drop');self.assertEqual(path,'recreate_training.sql')
                    if failure=='drop':raise RuntimeError('ORA-00054: locked')
                def initialize(_conn):
                    events.append('initialize')
                    if failure=='initialize':raise ValueError('sql/classifier.sql 컴파일 오류: DB 7행')
                def execute(_conn,path,*args,**kwargs):
                    if path.endswith('delete_training.sql'):events.append('delete')
                    if path.endswith('insert_training.sql'):
                        events.append('insert');bindings=list(kwargs['many']);self.assertEqual(len(bindings),720)
                        self.assertEqual(bindings[0]['case_id'],parse_csv(raw)[0]['case_id'])
                        if failure=='insert':raise RuntimeError('ORA-12899: too long')
                conn.commit.side_effect=lambda:events.append('commit')
                conn.rollback.side_effect=lambda:events.append('rollback')
                with patch('app.connection') as connection,patch('app.query',return_value=[{'object_name':'OML_BASIC_DATA'}]),patch('app.parse_csv',side_effect=parse),patch('app.execute_file',side_effect=drop),patch('app.initialize',side_effect=initialize),patch.object(service,'execute',side_effect=execute),patch.object(service,'state_path',return_value=state_file),patch.object(service,'status',return_value={}):
                    connection.return_value.__enter__.return_value=conn
                    with TestClient(create_app({'SECRET_KEY':'recreate-test-key'*3})) as client:
                        login=self.login(client,people[0]);self.assertEqual(login.status_code,200)
                        response=client.post('/api/data/import',files={'file':('sample.csv',b'invalid\n1' if failure=='csv' else raw,'text/csv')},data={'mode':'recreate'},headers={'X-CSRF-Token':login.json()['csrf']})
                after=json.loads(state_file.read_text(encoding='utf-8'))
                if failure is None:
                    self.assertEqual(response.status_code,200,response.text)
                    self.assertEqual(events,['parse','drop','initialize','delete','insert','commit'])
                    self.assertEqual(response.json()['loaded_rows'],720)
                    self.assertEqual(response.json()['operation'],'recreated')
                elif failure=='csv':
                    self.assertEqual(response.status_code,400);self.assertEqual(events,['parse']);self.assertEqual(after,saved)
                elif failure=='drop':
                    self.assertEqual(events,['parse','drop']);self.assertEqual(after,saved)
                    self.assertIn('완료하지 못했습니다',response.json()['diagnostic']['message'])
                else:
                    self.assertIn(response.status_code,(400,503));diagnostic=response.json()['diagnostic']
                    self.assertIn('원본 삭제 완료',diagnostic['message'])
                    self.assertIn('일반 교체 적재',' '.join(diagnostic['steps']))
                    if failure=='initialize':self.assertEqual(events,['parse','drop','initialize'])
                    if failure=='insert':self.assertEqual(events,['parse','drop','initialize','delete','insert','rollback'])
                if failure in (None,'initialize','insert'):
                    self.assertNotIn('preparations',after);self.assertEqual(after['models'],{});self.assertIsNone(after['confirmed'])

    @contextmanager
    def login_project(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'runtime') as temporary:
            root=Path(temporary);(root/'security').mkdir()
            path=root/'security/students.json';env=root/'security/student.env'
            people=[{'student_id':'V01041','name':'테스트','department':'학과','grade':4,'db_user':'STUDENT23'},
                    {'student_id':'ID3','name':'두번째 학생','db_user':'STUDENT02'}]
            path.write_text(json.dumps(people),encoding='utf-8')
            env.write_text('DB_USER=PREVIOUS\nDB_PASSWORD=PreviousPassword\nDB_DSN=keep_dsn\nWALLET_PASSWORD=KeepWalletValue\n',encoding='utf-8')
            with patch.object(identity,'ROSTER',path),patch.object(db,'ROOT',root),patch.dict('os.environ',{'OML_ENV_FILE':str(env)}):
                yield path,env,people

    def login(self,client,person,password='StudentPassword_22417'):
        token=client.get('/api/session').json()['csrf']
        return client.post('/api/identity',json={**person,'db_password':password},headers={'X-CSRF-Token':token})

    def test_session_deadline_readonly_status_and_manual_extension(self):
        now=[10000.0]
        with self.login_project() as (_,env,people),patch('app.connection') as connect,patch('app.service.status',return_value={}):
            connect.return_value.__enter__.return_value.username=people[0]['db_user']
            app=create_app({'SECRET_KEY':'session-test','SESSION_CLOCK':lambda:now[0]})
            client=TestClient(app)
            result=self.login(client,people[0])
            token=result.json()['csrf'];headers={'X-CSRF-Token':token}
            self.assertEqual(result.json()['session']['expires_at'],11800)
            now[0]+=100
            self.assertEqual(client.get('/api/session').json()['session']['expires_at'],11800)
            self.assertEqual(client.post('/api/session/extend',json={}).status_code,403)
            result=client.post('/api/session/extend',json={},headers=headers)
            self.assertEqual(result.json()['session']['expires_at'],11900)
            now[0]+=100
            result=client.get('/api/status')
            self.assertEqual(float(result.headers['X-Session-Expires-At']),12000)
            self.assertEqual(client.get('/api/session').json()['session']['expires_at'],12000)
            now[0]=12000
            result=client.post('/api/session/extend',json={},headers=headers)
            self.assertEqual(result.status_code,401)
            self.assertEqual(result.json()['code'],'SESSION_TIMEOUT')
            self.assertIsNone(client.get('/api/session').json()['identity'])

    def test_session_expiry_is_shared_and_replayed_cookie_cannot_revive(self):
        now=[10000.0]
        with self.login_project() as (_,env,people),patch('app.connection'):
            app=create_app({'SECRET_KEY':'session-test','SESSION_CLOCK':lambda:now[0]})
            first=TestClient(app);second=TestClient(app)
            result=self.login(first,people[0]);token=result.json()['csrf']
            saved=first.cookies.get(SESSION_COOKIE_NAME);second.cookies.set(SESSION_COOKIE_NAME,saved)
            now[0]+=1700
            self.assertEqual(first.post('/api/session/extend',json={},headers={'X-CSRF-Token':token}).status_code,200)
            self.assertEqual(second.get('/api/session').json()['session']['expires_at'],13500)
            now[0]=13500
            result=second.get('/api/session').json()
            self.assertTrue(result['session']['expired']);self.assertIsNone(result['identity'])
            first.cookies.clear();first.cookies.set(SESSION_COOKIE_NAME,saved)
            self.assertEqual(first.post('/api/session/extend',json={},headers={'X-CSRF-Token':token}).status_code,401)
            self.assertEqual(TestClient(app).post('/api/session/extend',json={}).status_code,403)

    def test_mission_selection_survives_login_and_restart_and_is_account_scoped(self):
        with self.login_project() as (_,env,people),patch('app.connection') as connect,patch.object(assignment_templates,'ROOT',env.parent.parent):
            application=create_app({'SECRET_KEY':'selection-test'})
            client=TestClient(application)
            self.assertEqual(client.get('/api/assignments/mission/selection').status_code,401)
            response=self.login(client,people[0]);token=response.json()['csrf']
            connect.reset_mock()
            path='/api/assignments/mission/selection';headers={'X-CSRF-Token':token}
            self.assertEqual(client.get(path).json()['key'],'')
            self.assertEqual(client.post(path,json={'key':'festival'}).status_code,403)
            self.assertEqual(client.post(path,json={'key':'festival'},headers=headers).json()['key'],'festival')
            for value in ('../../other',None,{},42):
                self.assertEqual(client.post(path,json={'key':value},headers=headers).status_code,400)
            self.assertEqual(client.get(path).json()['key'],'festival')
            connect.assert_not_called()
            client.post('/api/logout',json={},headers=headers)
            self.assertEqual(client.get(path).status_code,401)
            self.login(client,people[0])
            self.assertEqual(client.get(path).json()['key'],'festival')
            self.login(client,people[1])
            self.assertEqual(client.get(path).json()['key'],'')
            client=TestClient(create_app({'SECRET_KEY':'selection-test'}))
            self.login(client,people[0])
            self.assertEqual(client.get(path).json()['key'],'festival')
            files=list((env.parent.parent/'runtime').glob('mission-selection-*.json'))
            self.assertEqual(len(files),1)
            self.assertEqual(json.loads(files[0].read_text(encoding='utf-8')),{'key':'festival'})

    def test_roster_account_password_and_env_save(self):
        with self.login_project() as (path,env,people),patch('app.connection') as connect,patch('app.service.status',return_value={'test':'connected'}):
            connect.return_value.__enter__.return_value.username=people[0]['db_user']
            client=TestClient(create_app({'SECRET_KEY':'test-session-key'*3}))
            self.assertIsNone(client.get('/api/session').json()['identity'])
            token=client.get('/api/session').json()['csrf'];before=env.read_bytes()
            lookup=client.post('/api/identity/lookup',json=people[0],headers={'X-CSRF-Token':token})
            self.assertEqual(lookup.json()['identity']['db_user'],'STUDENT23')
            self.assertEqual(env.read_bytes(),before);connect.assert_not_called()
            password=" leading_${DB_PASSWORD}_'value trailing "
            response=self.login(client,{**people[0],'db_user':'FORGED_ACCOUNT'},password)
            self.assertEqual(response.status_code,200)
            self.assertEqual(connect.call_args.args[0]['DB_USER'],'STUDENT23')
            self.assertEqual(connect.call_args.args[0]['DB_PASSWORD'],password)
            cfg=db.settings()
            self.assertEqual(cfg['DB_USER'],'STUDENT23');self.assertEqual(cfg['DB_PASSWORD'],password)
            self.assertEqual(cfg['DB_DSN'],'keep_dsn');self.assertEqual(cfg['WALLET_PASSWORD'],'KeepWalletValue')
            cookie=json.loads(base64.b64decode(client.cookies.get(SESSION_COOKIE_NAME).split('.')[0]))
            self.assertNotIn(password,json.dumps(cookie)+response.text)
            self.assertNotIn('db_password',json.dumps(cookie)+response.text)
            self.assertEqual(client.get('/api/status').status_code,200)
            people[0]['db_user']='STUDENT99';path.write_text(json.dumps(people),encoding='utf-8')
            self.assertEqual(client.get('/api/status').status_code,401)

    def test_failed_login_preserves_file_and_does_not_authorize(self):
        with self.login_project() as (path,env,people),patch('app.connection',side_effect=RuntimeError('ORA-01017: invalid login')) as connect:
            client=TestClient(create_app({'SECRET_KEY':'test-session-key'*3}));before=env.read_bytes()
            for payload in ({**people[0],'name':people[1]['name']},{**people[0],'db_password':''}):
                response=self.login(client,payload,payload.get('db_password','test-password'))
                self.assertEqual(response.status_code,400)
            connect.assert_not_called()
            response=self.login(client,people[0],'wrong-password')
            self.assertEqual(response.status_code,503);self.assertEqual(response.json()['diagnostic']['code'],'ORA-01017')
            self.assertEqual(env.read_bytes(),before)
            self.assertEqual(client.get('/api/status').status_code,401)

    def test_assignment_guide_menu_and_access_for_every_student(self):
        from html.parser import HTMLParser
        import hashlib, re
        class Links(HTMLParser):
            def __init__(self, html):
                super().__init__(); self.links={}; self.feed(html)
            def handle_starttag(self, tag, attrs):
                data=dict(attrs)
                if tag=='a' and data.get('id'): self.links[data['id']]=data
        route='/download/assignment-guide.html'
        source=ROOT/'downloads/COM22417_과제설명및평가.html'
        before=source.read_bytes(); before_mtime=source.stat().st_mtime_ns
        with self.login_project() as (_,env,people),patch('app.connection') as connect:
            client=TestClient(create_app({'SECRET_KEY':'guide-access-test-key'*3}))
            self.assertEqual(client.get(route).status_code,401)
            page=client.get('/').text
            links=Links(page).links
            for key,teacher in (('assignment-guide-link','instructor-lecture-link'),
                                ('mobile-assignment-guide-link','mobile-instructor-lecture-link')):
                self.assertEqual(links[key]['href'],route)
                self.assertEqual(links[key]['target'],'_blank')
                self.assertIn('noopener',links[key]['rel'])
                self.assertNotIn('hidden',links[key])
                self.assertNotIn('data-instructor-lecture',links[key])
                self.assertIn('hidden',links[teacher])
                self.assertIn('data-instructor-lecture',links[teacher])
                self.assertLess(page.index('id="'+teacher+'"'),page.index('id="'+key+'"'))
            for person in reversed(people):
                with self.subTest(student=person['student_id']):
                    self.assertEqual(self.login(client,person).status_code,200)
                    connect.reset_mock()
                    response=client.get(route)
                    self.assertEqual(response.status_code,200)
                    self.assertEqual(response.content,before)
                    self.assertTrue(response.headers['content-type'].startswith('text/html'))
                    self.assertNotIn('attachment',response.headers.get('content-disposition',''))
                    self.assertEqual(response.headers['cache-control'],'no-store')
                    hashes=re.findall(r"'sha256-([^']+)'",response.headers['content-security-policy'])
                    for script in re.findall(r'<script>(.*?)</script>',before.decode('utf-8').replace('\r\n','\n').replace('\r','\n'),re.S):
                        self.assertIn(base64.b64encode(hashlib.sha256(script.encode('utf-8')).digest()).decode('ascii'),hashes)
                    connect.assert_not_called()
            with tempfile.TemporaryDirectory(prefix='assignment-guide-path-') as directory:
                temp=Path(directory)
                with patch('app.ROOT',temp):
                    self.assertEqual(client.get(route).status_code,404)
                    (temp/source.name).write_bytes(before)
                    self.assertEqual(client.get(route).content,before)
                    (temp/'downloads').mkdir()
                    (temp/'downloads'/source.name).write_text('<h1>canonical downloads first</h1>',encoding='utf-8')
                    self.assertEqual(client.get(route).text,'<h1>canonical downloads first</h1>')
            token=client.get('/api/session').json()['csrf']
            client.post('/api/logout',json={},headers={'X-CSRF-Token':token})
            self.assertEqual(client.get(route).status_code,401)
        self.assertEqual(source.read_bytes(),before)
        self.assertEqual(source.stat().st_mtime_ns,before_mtime)

    def test_instructor_lecture_requires_authenticated_teacher_and_existing_file(self):
        route='/instructor/python-web-lecture.html'
        with self.login_project() as (roster,env,people),patch('app.connection') as connect:
            # 같은 DB 계정을 사용하더라도 student_id가 다르면 강사 권한이 없습니다.
            people[1]['db_user']='STUDENT23';roster.write_text(json.dumps(people),encoding='utf-8')
            app=create_app({'SECRET_KEY':'test-session-key'*3});client=TestClient(app)
            self.assertIsNone(client.get('/api/session').json()['instructor_lecture_url'])
            self.assertEqual(client.get(route).status_code,401)
            self.assertEqual(client.get('/instructor/lecture-source/call').status_code,401)
            forged={**people[1],'is_instructor':True,'instructor_lecture_url':route}
            response=self.login(client,forged)
            self.assertEqual(response.status_code,200)
            self.assertIsNone(response.json()['instructor_lecture_url'])
            self.assertIsNone(client.get('/api/session').json()['instructor_lecture_url'])
            self.assertEqual(client.get(route).status_code,403)
            self.assertEqual(client.get('/instructor/lecture-source/call').status_code,403)
            self.assertNotIn('source-manifest',client.get(route).text)
            response=self.login(client,people[0]);self.assertEqual(response.json()['instructor_lecture_url'],route)
            connect.reset_mock()
            page=client.get(route)
            self.assertEqual(page.status_code,200);self.assertIn('source-manifest',page.text)
            self.assertEqual(page.headers['cache-control'],'no-store')
            policy=page.headers['content-security-policy']
            self.assertIn("script-src 'sha256-",policy);self.assertNotIn("script-src 'unsafe-inline'",policy)
            self.assertEqual(client.get('/api/session').json()['instructor_lecture_url'],route)
            source=client.get('/instructor/lecture-source/call')
            self.assertEqual(source.status_code,200);self.assertIn('def run_model(',source.text)
            self.assertEqual(source.headers['cache-control'],'no-store')
            self.assertEqual(client.get('/instructor/lecture-source/student.env').status_code,404)
            self.assertEqual(client.get('/instructor/samples/http_basics.py').status_code,404)
            connect.assert_not_called()
            original=Path.is_file
            def absent(path):
                return False if path==ROOT/'instructor/python-web-lecture.html' else original(path)
            with patch.object(Path,'is_file',absent):
                self.assertIsNone(client.get('/api/session').json()['instructor_lecture_url'])
                self.assertEqual(client.get(route).status_code,404)
            token=client.get('/api/session').json()['csrf']
            client.post('/api/logout',json={},headers={'X-CSRF-Token':token})
            self.assertEqual(client.get(route).status_code,401)
            self.assertIsNone(client.get('/api/session').json()['instructor_lecture_url'])

    def test_connection_test_pings_without_login_or_saving(self):
        with self.login_project() as (path,env,people),patch('app.connection') as connect,patch('backend.connection_profile.query',side_effect=[
                [{'session_user':'STUDENT23','current_schema':'STUDENT23','database_name':'QA_DB','service_name':'QA_SERVICE','server_host':'QA_HOST','instance_name':'QA_INSTANCE'}],
                [{'privilege':'CREATE TABLE'}]]):
            client=TestClient(create_app({'SECRET_KEY':'test-session-key'*3}));before=env.read_bytes()
            token=client.get('/api/session').json()['csrf']
            payload={**people[0],'db_password':'TypedPassword_ForTest'}
            self.assertEqual(client.post('/api/identity/test',json=payload).status_code,403)
            connect.assert_not_called()
            response=client.post('/api/identity/test',json=payload,headers={'X-CSRF-Token':token})
            self.assertEqual(response.status_code,200)
            self.assertTrue(response.json()['success']);self.assertEqual(response.json()['db_user'],'STUDENT23')
            self.assertEqual(connect.call_args.args[0]['DB_USER'],'STUDENT23')
            self.assertEqual(connect.call_args.args[0]['DB_PASSWORD'],payload['db_password'])
            connect.return_value.__enter__.return_value.ping.assert_called_once()
            self.assertEqual(env.read_bytes(),before)
            self.assertIsNone(client.get('/api/session').json()['identity'])
            self.assertEqual(client.get('/api/status').status_code,401)
            connect.side_effect=RuntimeError('DPY-6005: failed ORA-01017 TypedPassword_ForTest private-host')
            response=client.post('/api/identity/test',json=payload,headers={'X-CSRF-Token':token})
            self.assertEqual(response.status_code,503)
            self.assertEqual(response.json()['diagnostic']['code'],'ORA-01017')
            self.assertGreaterEqual(len(response.json()['diagnostic']['steps']),2)
            for private in ('TypedPassword_ForTest','private-host','PreviousPassword'):
                self.assertNotIn(private,response.text)
            self.assertEqual(env.read_bytes(),before)

    def test_connection_failure_guidance(self):
        cases=[(RuntimeError('ORA-28000'), 'ORA-28000', '잠겨'),
               (RuntimeError('DPI-1047'),'DPI-1047','Oracle Client'),
               (RuntimeError('ORA-12154'),'ORA-12154','서비스'),
               (RuntimeError('ORA-29024'),'ORA-29024','인증서'),
               (RuntimeError('DPY-6005'),'DPY-6005','연결'),
               (ValueError('Thin 연결에는 WALLET_PASSWORD가 필요합니다.'),'WALLET-PASSWORD','Wallet')]
        for error,code,title in cases:
            with self.subTest(code=code):
                result=explain(error)
                self.assertEqual(result['code'],code);self.assertIn(title,result['title'])
                self.assertGreaterEqual(len(result['steps']),2)

    def test_assignment_setup_and_connection_failures_are_different_http_results(self):
        with self.login_project() as (_path,_env,people),patch('app.connection') as connect:
            connect.return_value.__enter__.return_value.username=people[0]['db_user']
            client=TestClient(create_app({'SECRET_KEY':'test-session-key'*3}))
            self.assertEqual(self.login(client,people[0]).status_code,200)
            token=client.get('/api/session').json()['csrf'];headers={'X-CSRF-Token':token}
            with patch.object(assignment_templates,'query',return_value=[]),patch.object(assignment_templates,'model_state',return_value=[]):
                for key in ('mission','creative'):
                    with self.subTest(assignment=key):
                        response=client.get('/api/assignments/'+key+'/status')
                        self.assertEqual(response.status_code,200)
                        state=response.json();self.assertTrue(state['connected']);self.assertFalse(state['ready'])
                        self.assertEqual(state['diagnostic']['category'],'objects')
                        self.assertTrue(state['diagnostic']['db_connected'])
                        self.assertEqual(state['diagnostic']['examples'],[])
                        self.assertEqual(state['diagnostic']['sources'],[])
                        response=client.post('/api/assignments/'+key+'/initial-train',json={'variant':'RAW'},headers=headers)
                        self.assertEqual(response.status_code,403)
                        self.assertIn('SQL Developer',response.json()['error'])
            # 인증은 유지하되, DB 연결 시작 실패와 연결 뒤 조회 실패만 따로 재현합니다.
            connect.return_value.__enter__.side_effect=RuntimeError('DPY-6005: private-host SecretPassword_ForTest')
            response=client.get('/api/assignments/mission/status')
            self.assertEqual(response.status_code,503)
            self.assertEqual(response.json()['diagnostic']['category'],'connection')
            self.assertFalse(response.json()['diagnostic']['db_connected'])
            for private in ('private-host','SecretPassword_ForTest'):self.assertNotIn(private,response.text)
            connect.return_value.__enter__.side_effect=None
            for error,category in [(RuntimeError('ORA-00942: private-table SecretPassword_ForTest'),'query'),
                                   (RuntimeError('DPY-4011: connection closed SecretPassword_ForTest'),'connection'),
                                   (AttributeError('private-code SecretPassword_ForTest'),'query')]:
                with self.subTest(category=category,error=type(error).__name__),patch.object(assignment_templates,'readiness',side_effect=error):
                    response=client.get('/api/assignments/creative/status')
                    self.assertEqual(response.status_code,503)
                    self.assertEqual(response.json()['diagnostic']['category'],category)
                    self.assertEqual(response.json()['diagnostic']['db_connected'],category!='connection')
                    for private in ('private-table','private-code','SecretPassword_ForTest'):self.assertNotIn(private,response.text)

    def test_account_switch_and_logout_revoke_existing_sessions(self):
        with self.login_project() as (path,env,people),patch('app.connection') as connect,patch('app.service.status',return_value={'test':'connected'}):
            app=create_app({'SECRET_KEY':'test-session-key'*3});first=TestClient(app);second=TestClient(app)
            self.assertEqual(self.login(first,people[0]).status_code,200)
            self.assertEqual(self.login(second,people[1]).status_code,200)
            self.assertEqual(db.settings()['DB_USER'],'STUDENT02')
            self.assertEqual(first.get('/api/status').status_code,401)
            connect.return_value.__enter__.return_value.username=people[1]['db_user']
            self.assertEqual(second.get('/api/status').status_code,200)
            copied=TestClient(app);copied.cookies.update(second.cookies)
            token=second.get('/api/session').json()['csrf']
            response=second.post('/api/logout',json={},headers={'X-CSRF-Token':token})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['message'],'로그아웃되었습니다.')
            self.assertEqual(second.get('/api/status').status_code,401)
            self.assertEqual(copied.get('/api/status').status_code,401)
            self.assertIsNone(second.get('/api/session').json()['identity'])

    def test_connected_database_account_must_match_the_issued_account(self):
        with self.login_project() as (_,env,people),patch('app.connection') as connect,patch('app.service.status') as status:
            connect.return_value.__enter__.return_value.username='WRONG_ACCOUNT'
            client=TestClient(create_app({'SECRET_KEY':'account-guard-test'*3}))
            self.assertEqual(self.login(client,people[0]).status_code,200)
            response=client.get('/api/status')
            self.assertEqual(response.status_code,400,response.text)
            self.assertIn('발급 계정',response.json()['error'])
            status.assert_not_called()

    def test_env_file_values_are_preserved(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'runtime') as temporary:
            path=Path(temporary)/'student.env'
            path.write_text('DB_USER=LOCAL_USER\nDB_PASSWORD=literal_${DB_PASSWORD}_keep\nWALLET_PASSWORD=LocalWalletValue\n',encoding='utf-8')
            with patch.dict('os.environ',{'OML_ENV_FILE':str(path),'DB_USER':'OTHER_USER',
                                         'DB_PASSWORD':'OtherPassword','WALLET_PASSWORD':'OtherWallet'}):
                cfg=db.settings()
                self.assertEqual(cfg['DB_USER'],'LOCAL_USER')
                self.assertEqual(cfg['DB_PASSWORD'],'literal_${DB_PASSWORD}_keep')
                self.assertEqual(cfg['WALLET_PASSWORD'],'LocalWalletValue')

    def test_dirty_sample_preserved(self):
        data=parse_csv((ROOT/'data/classification.csv').read_bytes())
        stats=quality(data)
        self.assertEqual(len(data),720)
        for key in ('missing','invalid','outliers'):
            self.assertGreater(stats[key],0)
        self.assertTrue(any(row['return_pct']=='unknown' for row in data))
        broken=b'case_id,return_pct,range_pct,volume_change_pct,close_price,stock,signal,week_ending,split\n1,20,1,50,0,MSFT,BUY,2011-01-07,TRAIN\n1,20,1,50,0,MSFT,BUY,2011-04-01,TEST\n'
        with self.assertRaisesRegex(ValueError,'중복'): parse_csv(broken)


    def test_identity_and_csrf(self):
        with self.login_project() as (path,env,people),patch('app.connection'):
            person=people[0]
            client=TestClient(create_app({'SECRET_KEY':'test-session-key'*3}))
            self.assertEqual(client.get('/api/status').status_code,401)
            csrf=client.get('/api/session').json()['csrf']
            self.assertEqual(client.post('/api/identity',json=person).status_code,403)
            self.assertEqual(client.post('/api/identity',json={'student_id':person['student_id'],'name':'다른이름'},headers={'X-CSRF-Token':csrf}).status_code,400)
            self.assertEqual(self.login(client,person).status_code,200)
            client.cookies.clear()
            self.assertEqual(client.post('/api/identity',json=person,headers={'X-CSRF-Token':csrf}).status_code,403)
            csrf=client.get('/api/session').json()['csrf']
            self.assertEqual(client.post('/api/identity',json={**person,'db_password':'StudentPassword_22417'},headers={'X-CSRF-Token':csrf}).status_code,200)
            for path in ('/','/data','/models','/predictions'):
                self.assertEqual(client.get(path).status_code,200)
            self.assertEqual(client.get('/lesson/classification').status_code,404)
            self.assertEqual(client.get('/security/students.json').status_code,404)

    def test_no_embedded_backend_sql(self):
        for name in ('app.py','db.py','identity.py','service.py','validation.py','sql_files.py','connection_help.py','operation_help.py','source_help.py'):
            path=ROOT/'app.py' if name=='app.py' else ROOT/'backend'/name
            tree=ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node,ast.Constant) and isinstance(node.value,str):
                    import re
                    self.assertFalse(re.search(r'^\s*(SELECT\s+.+\s+FROM|INSERT\s+INTO\s+[A-Z_][A-Z0-9_]*\s*\(|DELETE\s+FROM\s+[A-Z_][A-Z0-9_]*\b|UPDATE\s+[A-Z_][A-Z0-9_]*\s+SET|CREATE\s+TABLE\s+[A-Z_][A-Z0-9_]*\s*\()',node.value,re.I|re.S),name)













    def test_shared_wallet_exception_keeps_private_credentials_blocked(self):
        from distribution_guard import validate_files
        with tempfile.TemporaryDirectory(dir=ROOT/'runtime') as temporary:
            root=Path(temporary);(root/'security').mkdir()
            personal=root/'security/student.env'
            personal.write_text('DB_PASSWORD=PrivateDBPassword_22417\nWALLET_PASSWORD=Pcuora2026\nSECRET_KEY=PrivateSecretKey_22417\n',encoding='utf-8')
            shared=b'DB_USER=\nDB_PASSWORD=\nWALLET_PASSWORD=Pcuora2026\n'
            files={'security/student.env.example':shared,'security/student.env':shared,
                   'guide.html':b'WALLET_PASSWORD=Pcuora2026'}
            validate_files(files,root,allow_student_env=True)
            for field,value in (('DB_USER','STUDENT23'),('DB_PASSWORD','PrivateDBPassword_22417'),
                                ('WALLET_PASSWORD','OtherWalletPassword_22417'),('SECRET_KEY','PrivateSecretKey_22417'),
                                ('API_TOKEN','Pcuora2026')):
                with self.subTest(field=field):
                    bad=shared+(field+'='+value+'\n').encode()
                    with self.assertRaises(ValueError):
                        validate_files({**files,'security/student.env.example':bad,'security/student.env':bad},root,allow_student_env=True)
            for value in (b'PrivateDBPassword_22417',b'PrivateSecretKey_22417'):
                with self.assertRaisesRegex(ValueError,'Configured secret'):
                    validate_files({**files,'leak.html':value},root,allow_student_env=True)
            with self.assertRaisesRegex(ValueError,'match the public example'):
                validate_files({**files,'security/student.env':shared+b'# different bytes\n'},root,allow_student_env=True)
            # The same text used as a private DB password is still a private secret.
            personal.write_text('DB_PASSWORD=Pcuora2026\nWALLET_PASSWORD=Pcuora2026\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Configured secret'):
                validate_files({'guide.html':b'Pcuora2026'},root)

    def test_student_zip_is_light_and_private(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'runtime') as temporary:
            root=Path(temporary)
            for name,raw in inventory().items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            secret='PrivateTestSecret_22417'
            (root/'security/teacher.env').write_text('DB_PASSWORD='+secret,encoding='utf-8')
            local_env=root/'security/student.env'
            original_env="DB_USER=LOCAL_PRIVATE_USER\nDB_PASSWORD='PrivateDBPassword_22417'\nDB_DSN=pcuora_low\nWALLET_PASSWORD='WalletPassword_22417'\nORACLE_CLIENT_LIB=\n"
            local_env.write_text(original_env,encoding='utf-8')
            roster=[{'student_id':'20260001','name':'학생1','department':'학과','grade':3,'db_user':'STUDENT01'},
                    {'student_id':'20260002','name':'학생2','department':'학과','grade':3,'db_user':'STUDENT02'},
                    {'student_id':'V01041','name':'테스트','department':'학과','grade':4,'db_user':'STUDENT23'}]
            (root/'security/students.json').write_text(json.dumps(roster),encoding='utf-8')
            with zipfile.ZipFile(root/'security/Wallet_PCUORA.zip','w') as wallet: wallet.writestr('tnsnames.ora','test-wallet')
            canonical=root/'downloads'/GUIDE_NAME
            canonical_bytes=canonical.read_bytes();canonical_mtime=canonical.stat().st_mtime_ns
            legacy=root/'reference/student/environment-setup.html'
            legacy.parent.mkdir(parents=True,exist_ok=True)
            legacy.write_text('<html>obsolete guide must not be used</html>',encoding='utf-8')
            self.assertEqual(GUIDE_NAME,'COM22417_과제설명및평가.html')
            archive=build(root,student_id='20260001')
            self.assertEqual(canonical.read_bytes(),canonical_bytes)
            self.assertEqual(canonical.stat().st_mtime_ns,canonical_mtime)
            self.assertFalse((root/'downloads/COM22417_개발환경설정.html').exists())
            with zipfile.ZipFile(archive) as zipped:
                names=zipped.namelist(); prefix=''
                self.assertIn('app.py',names)
                self.assertIn('templates/index.html',names)
                self.assertIn(GUIDE_NAME,names)
                self.assertNotIn('COM22417_개발환경설정.html',names)
                self.assertFalse(any(name.startswith(archive.stem+'/') for name in names))
                extracted=root/'20260001'
                extracted.mkdir()
                zipped.extractall(extracted)
                self.assertTrue((extracted/'app.py').is_file())
                self.assertTrue((extracted/'scripts/start.ps1').is_file())
                self.assertFalse((extracted/archive.stem).exists())
                expected=[roster[0]]
                self.assertEqual(json.loads(zipped.read(prefix+'security/students.json')),expected)
                self.assertEqual(zipped.read(prefix+'security/Wallet_PCUORA.zip'),(root/'security/Wallet_PCUORA.zip').read_bytes())
                self.assertFalse(any(n.lower().endswith(('.md','.markdown','.env','.whl','.exe')) for n in names if n!='security/student.env'))
                from dotenv import dotenv_values
                import io
                cfg=dotenv_values(stream=io.StringIO(zipped.read('security/student.env').decode('utf-8')),interpolate=False)
                self.assertEqual(cfg['DB_USER'],'');self.assertEqual(cfg['DB_PASSWORD'],'')
                self.assertEqual(cfg['WALLET_PASSWORD'],'Pcuora2026')
                self.assertEqual(cfg['DB_DSN'],'pcuora_low')
                self.assertEqual(local_env.read_text(encoding='utf-8'),original_env)
                for name in names:
                    self.assertNotIn(b'PrivateDBPassword_22417',zipped.read(name))
                    self.assertNotIn(b'LOCAL_PRIVATE_USER',zipped.read(name))
                from distribution_guard import validate_files
                with self.assertRaisesRegex(ValueError,'Private configuration'):
                    validate_files({'security/student.env':zipped.read('security/student.env')},root)
                with self.assertRaisesRegex(ValueError,'blank DB_USER'):
                    validate_files({'security/student.env':original_env.encode()},root,allow_student_env=True)
                with self.assertRaisesRegex(ValueError,'Configured secret'):
                    validate_files({'static/leak.txt':b'WalletPassword_22417'},root,allow_student_env=True)
                self.assertFalse(any('/instructor/' in n or 'environment-setup.html' in n or '/.local/' in n for n in names))
                campus=zipped.getinfo('static/images/paichai-campus-night.jpg')
                self.assertLess(campus.file_size,500000)
                topics=json.loads(zipped.read('data/catalog.json'))
                pairs=[sum(zipped.getinfo('data/examples/'+topic[field]).compress_size for field in ('filename','prediction_filename')) for topic in topics]
                self.assertTrue(all(value<15000 for value in pairs))
                self.assertLess(archive.stat().st_size-campus.compress_size-sum(pairs),400000)
                self.assertLess(archive.stat().st_size,1000000)
                self.assertIn('templates/login-gate.html',names)
                self.assertIn('static/css/intro.css',names)
                self.assertIn(prefix+'static/css/studio.css',names)
                self.assertIn('method-flow',zipped.read(prefix+'templates/pages/home.html').decode('utf-8'))
                self.assertEqual(zipped.read(prefix+GUIDE_NAME),(root/'downloads'/GUIDE_NAME).read_bytes())
                self.assertNotIn(b'Pcuora2026',zipped.read(prefix+GUIDE_NAME))
                self.assertIn('WALLET_PASSWORD="본인의_Wallet_다운로드_암호"'.encode('utf-8'),zipped.read(prefix+GUIDE_NAME))
                guide_text=zipped.read(prefix+GUIDE_NAME).decode('utf-8')
                self.assertNotRegex(guide_text,r'(?i)ppt|powerpoint|보고서|submit\.ps1|submission/')
                self.assertIn('제출 — Render 사이트 주소를 LMS 과제에 등록',guide_text)
                self.assertIn('https://your-service.onrender.com',guide_text)
            with self.assertRaises(FileExistsError): build(root,student_id='20260001')
            updated=root/'templates/index.html'
            updated.write_bytes(updated.read_bytes()+b'\n<!-- latest source -->\n')
            rebuilt=build(root,student_id='20260001',replace=True)
            self.assertEqual(rebuilt,archive)
            with zipfile.ZipFile(rebuilt) as zipped:
                self.assertEqual(zipped.read(prefix+'templates/index.html'),updated.read_bytes())
                self.assertEqual(zipped.read(prefix+GUIDE_NAME),(root/'downloads'/GUIDE_NAME).read_bytes())
            alternate=build(root,student_id='20260001',output=root/'alternate')
            with zipfile.ZipFile(alternate) as zipped:
                self.assertEqual(zipped.read(GUIDE_NAME),canonical_bytes)
            self.assertEqual((alternate.parent/GUIDE_NAME).read_bytes(),canonical_bytes)
            self.assertEqual(canonical.stat().st_mtime_ns,canonical_mtime)
            saved_zip=rebuilt.read_bytes()
            guide=root/'downloads'/GUIDE_NAME
            guide_raw=guide.read_bytes();guide.unlink()
            with self.assertRaisesRegex(ValueError,'HTML'): build(root,student_id='20260001',replace=True)
            self.assertEqual(rebuilt.read_bytes(),saved_zip)
            guide.write_bytes(guide_raw)
            self.assertFalse(list((root/'downloads').glob('release-*')))
            self.assertFalse(list((root/'downloads').glob('*.tmp')))
            with zipfile.ZipFile(build(root,student_id='V01041')) as zipped:
                self.assertEqual(json.loads(zipped.read('security/students.json')),[roster[2]])
            with zipfile.ZipFile(build(root)) as zipped:
                examples=json.loads((root/'security/students.example.json').read_text(encoding='utf-8'))
                self.assertEqual(json.loads(zipped.read('security/students.json')),examples)
                self.assertEqual(zipped.read('security/student.env'),zipped.read('security/student.env.example'))
                for name in zipped.namelist():
                    if name!='security/Wallet_PCUORA.zip':
                        self.assertNotIn(b'WalletPassword_22417',zipped.read(name))
            (root/'static/js/main.js').write_text(secret,encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'secret'): build(root,output=root/'rejected')

    def test_submission_includes_source_and_ppt(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'runtime') as temporary:
            root=Path(temporary)
            for name,raw in inventory(audience='student').items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            (root/'submission').mkdir()
            (root/'submission/report.txt').write_text('학번: 20260001\n직접 실행한 검증 기록',encoding='utf-8')
            (root/'backend/mission.py').write_text('# Student extension\n',encoding='utf-8')
            (root/'sql/03_mission.sql').write_text('-- Student DDL and procedure\n',encoding='utf-8')
            (root/'templates/mission.html').write_text('<main>Student screen</main>',encoding='utf-8')
            (root/'static/js/mission.js').write_text('// Student browser code\n',encoding='utf-8')
            (root/'security/student.env').write_text('DB_PASSWORD=PrivateTestSecret_22417',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'one PPT'): build_submission(root,'20260001')
            presentation=root/'submission/presentation.pptx'
            presentation.write_bytes(b'not a PowerPoint file')
            with self.assertRaisesRegex(ValueError,'PowerPoint archive'): build_submission(root,'20260001')

            def write_deck(text):
                # ZIP 수집·누락·비밀값 검사용 최소 파일이며 제출용 발표자료가 아닙니다.
                with zipfile.ZipFile(presentation,'w',zipfile.ZIP_DEFLATED) as deck:
                    deck.writestr('[Content_Types].xml','<Types/>')
                    deck.writestr('ppt/presentation.xml','<presentation/>')
                    deck.writestr('ppt/slides/slide1.xml','<slide>'+text+'</slide>')

            write_deck('Test slide')
            archive=build_submission(root,'20260001')
            with zipfile.ZipFile(archive) as zipped:
                prefix='COM22417_2026H2_20260001/'
                for name in ('source/app.py','source/backend/mission.py',
                             'source/sql/schema.sql','source/sql/classifier.sql',
                             'source/sql/03_mission.sql','source/templates/mission.html','source/static/js/mission.js',
                             'report/presentation.pptx','report/report.txt'):
                    self.assertIn(prefix+name,zipped.namelist())
                self.assertEqual(zipped.read(prefix+'report/presentation.pptx'),presentation.read_bytes())
                self.assertFalse(any(n.lower().endswith(('.env','.md','.whl','.exe')) or 'wallet' in n.lower()
                                     for n in zipped.namelist()))
                self.assertIsNone(zipped.testzip())
            write_deck('PrivateTestSecret_22417')
            with self.assertRaisesRegex(ValueError,'Configured secret'): build_submission(root,'20260001')
            write_deck('Test slide')
            (root/'sql/schema.sql').unlink()
            with self.assertRaisesRegex(ValueError,'Required Python/DDL/procedure'): build_submission(root,'20260001')


if __name__=='__main__': unittest.main()
