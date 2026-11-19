"""운영은 메인 로그인만 사용하며 API·강사 권한·CSRF·Secure 쿠키는 유지합니다."""
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.hosting import create_hosted_app
from reference.tests import test_classifier as fixtures

ENVIRONMENT = {'SECRET_KEY': 'hosted-auth-test-secret-' * 3,
               'RENDER_EXTERNAL_HOSTNAME': 'classroom.example.invalid',
               'DB_PASSWORD': 'RenderEnvironmentPassword_Test', 'DB_DSN': 'render_test'}


class HostedAuthTests(unittest.TestCase):
    def test_intro_never_requires_basic_credentials(self):
        for legacy in ({}, {'OML_ACCESS_USER': '', 'OML_ACCESS_PASSWORD': 'short'}):
            with self.subTest(legacy=bool(legacy)), TestClient(
                    create_hosted_app({**ENVIRONMENT, **legacy}),
                    base_url='https://classroom.example.invalid') as client:
                for path in ('/', '/?login=1', '/healthz', '/static/css/style.css'):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 200, path)
                    self.assertNotIn('www-authenticate', response.headers)
                response = client.get('/', headers={'Authorization': 'Basic invalid-old-browser-value'})
                self.assertEqual(response.status_code, 200)

    def test_main_login_logout_and_api_guards(self):
        fixture = fixtures.ClassifierTests()
        with (fixture.login_project() as (_, env, people),
              patch('app.connection') as connect,
              patch('app.service.status', return_value={})):
            connect.return_value.__enter__.return_value.username = people[0]['db_user']
            with TestClient(create_hosted_app(ENVIRONMENT),
                            base_url='https://classroom.example.invalid') as client:
                for path in ('/api/status', '/api/assignments/mission/selection',
                             '/download/assignment-guide.html', '/instructor/python-web-lecture.html'):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 401, path)
                    self.assertNotIn('www-authenticate', response.headers)
                self.assertEqual(client.post('/api/initialize', json={}).status_code, 403)
                connect.assert_not_called()
                login = fixture.login(client, people[0], ENVIRONMENT['DB_PASSWORD'])
                self.assertEqual(login.status_code, 200, login.text)
                cookie = login.headers['set-cookie'].lower()
                for flag in ('secure', 'httponly', 'samesite=strict'):
                    self.assertIn(flag, cookie)
                self.assertEqual(client.get('/api/session').json()['identity']['student_id'],
                                 people[0]['student_id'])
                self.assertEqual(client.get('/api/status').status_code, 200)
                self.assertEqual(client.get('/instructor/python-web-lecture.html').status_code, 200)
                response = client.post('/api/logout', json={},
                                       headers={'X-CSRF-Token': login.json()['csrf']})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(client.get('/api/status').status_code, 401)

    def test_student_cannot_open_instructor_lecture(self):
        fixture = fixtures.ClassifierTests()
        with fixture.login_project() as (_, env, people), patch('app.connection'):
            with TestClient(create_hosted_app(ENVIRONMENT),
                            base_url='https://classroom.example.invalid') as client:
                self.assertEqual(fixture.login(client, people[1], ENVIRONMENT['DB_PASSWORD']).status_code, 200)
                self.assertEqual(client.get('/instructor/python-web-lecture.html').status_code, 403)

    def test_hosted_login_maps_json_user_and_uses_only_environment_password(self):
        fixture=fixtures.ClassifierTests()
        with fixture.login_project() as (_, env, people), patch('app.connection') as connect, patch('app.save_credentials') as save:
            original=env.read_bytes()
            with TestClient(create_hosted_app({**ENVIRONMENT,'DB_USER':'IGNORED_DEFAULT'}),
                            base_url='https://classroom.example.invalid') as client:
                page=client.get('/?login=1').text
                self.assertIn('id="login-password" type="password" required',page)
                self.assertIn('data-remember-password="false"',page)
                self.assertNotIn(ENVIRONMENT['DB_PASSWORD'],page)
                token=client.get('/api/session').json()['csrf']
                headers={'X-CSRF-Token':token}
                who={'student_id':people[0]['student_id'],'name':people[0]['name']}
                self.assertEqual(client.post('/api/identity/lookup',json=who,headers=headers).json()['identity']['db_user'],people[0]['db_user'])
                result=client.post('/api/identity',json={**who,'db_user':'OTHER','db_password':ENVIRONMENT['DB_PASSWORD']},headers=headers)
                self.assertEqual(result.status_code,200,result.text)
                cfg=connect.call_args.args[0]
                self.assertEqual(cfg['DB_USER'],people[0]['db_user'])
                self.assertEqual(cfg['DB_PASSWORD'],ENVIRONMENT['DB_PASSWORD'])
                self.assertNotIn(ENVIRONMENT['DB_PASSWORD'],result.text)
                self.assertEqual(client.get('/api/session').json()['identity']['db_user'],people[0]['db_user'])
                self.assertEqual(env.read_bytes(),original)
                save.assert_not_called()

    def test_hosted_password_is_required_and_checked_before_any_db_access(self):
        fixture=fixtures.ClassifierTests()
        with fixture.login_project() as (_, env, people), patch('app.connection') as connect, patch('app.save_credentials') as save:
            original=env.read_bytes()
            with TestClient(create_hosted_app(ENVIRONMENT),
                            base_url='https://classroom.example.invalid') as client:
                token=client.get('/api/session').json()['csrf']
                headers={'X-CSRF-Token':token}
                who={'student_id':people[0]['student_id'],'name':people[0]['name']}
                for endpoint in ('/api/identity','/api/identity/test'):
                    for password in (None,'',123,[],{},'wrong','비밀번호',
                                     ENVIRONMENT['DB_PASSWORD'].lower(),
                                     ' '+ENVIRONMENT['DB_PASSWORD'],ENVIRONMENT['DB_PASSWORD']+' '):
                        with self.subTest(endpoint=endpoint,password_type=type(password).__name__):
                            payload=dict(who)
                            if password is not None:payload['db_password']=password
                            result=client.post(endpoint,json=payload,headers=headers)
                            self.assertEqual(result.status_code,400,result.text)
                            self.assertNotIn(ENVIRONMENT['DB_PASSWORD'],result.text)
                            self.assertIsNone(client.get('/api/session').json()['identity'])
                    self.assertEqual(client.post(endpoint,json={**who,'db_password':ENVIRONMENT['DB_PASSWORD']}).status_code,403)
                connect.assert_not_called()
                save.assert_not_called()
                self.assertEqual(env.read_bytes(),original)

    def test_hosted_connection_test_and_login_both_require_matching_password(self):
        fixture=fixtures.ClassifierTests()
        with fixture.login_project() as (_, env, people), patch('app.connection') as connect, patch('app.save_credentials') as save, patch('app.connection_profile.inspect_connection',return_value={}):
            with TestClient(create_hosted_app(ENVIRONMENT),
                            base_url='https://classroom.example.invalid') as client:
                token=client.get('/api/session').json()['csrf']
                payload={**people[0],'db_password':ENVIRONMENT['DB_PASSWORD']}
                result=client.post('/api/identity/test',json=payload,headers={'X-CSRF-Token':token})
                self.assertEqual(result.status_code,200,result.text)
                self.assertIsNone(client.get('/api/session').json()['identity'])
                self.assertEqual(connect.call_args.args[0]['DB_PASSWORD'],ENVIRONMENT['DB_PASSWORD'])
                connect.return_value.__enter__.return_value.ping.side_effect=RuntimeError('ORA-01017')
                self.assertEqual(fixture.login(client,people[0],ENVIRONMENT['DB_PASSWORD']).status_code,503)
                self.assertIsNone(client.get('/api/session').json()['identity'])
                connect.return_value.__enter__.return_value.ping.side_effect=None
                login=fixture.login(client,people[0],ENVIRONMENT['DB_PASSWORD'])
                self.assertEqual(login.status_code,200,login.text)
                connect.reset_mock()
                failure=fixture.login(client,people[1],'wrong')
                self.assertEqual(failure.status_code,400)
                self.assertEqual(client.get('/api/session').json()['identity']['student_id'],people[0]['student_id'])
                connect.assert_not_called()
                save.assert_not_called()

    def test_missing_environment_password_cannot_fall_back_to_browser_password(self):
        fixture=fixtures.ClassifierTests()
        with fixture.login_project() as (_, env, people), patch('app.connection') as connect:
            with TestClient(create_hosted_app({**ENVIRONMENT,'DB_PASSWORD':''}),
                            base_url='https://classroom.example.invalid') as client:
                response=fixture.login(client,people[0])
                self.assertEqual(response.status_code,400)
                self.assertIn('DB_PASSWORD',response.json()['error'])
                connect.assert_not_called()

    def test_secret_and_hostname_restrictions_remain(self):
        for secret in ('', 'short'):
            with self.subTest(secret_length=len(secret)), self.assertRaises(ValueError):
                create_hosted_app({**ENVIRONMENT, 'SECRET_KEY': secret})
        with self.assertRaises(ValueError):
            create_hosted_app({**ENVIRONMENT, 'OML_ALLOWED_HOSTS': '*.example.invalid'})
        with TestClient(create_hosted_app(ENVIRONMENT),
                        base_url='https://untrusted.example.invalid') as client:
            self.assertEqual(client.get('/').status_code, 400)

class StudentRenderPackageTests(unittest.TestCase):
    def test_student_zip_runs_render_launcher_and_git_includes_runtime_and_guide(self):
        import json
        import os
        import shutil
        import socket
        import subprocess
        import sys
        import tempfile
        import time
        import urllib.error
        import urllib.request
        import zipfile
        from source_files import inventory, STUDENT_GUIDE
        from pathlib import Path
        root=Path(__file__).resolve().parents[2]
        shell=Path('C:/Program Files/Git/bin/bash.exe') if os.name=='nt' else Path(shutil.which('bash') or '')
        if not shell.is_file():self.skipTest('Bash is unavailable')
        archive=root/'runtime/final-student-release/COM22417_학번_20261120.zip'
        with tempfile.TemporaryDirectory(prefix='student render ',dir=root/'runtime') as directory:
            temporary=Path(directory);project=temporary/'student source';project.mkdir()
            with zipfile.ZipFile(archive) as bundle:
                self.assertTrue(all((project/name).resolve().is_relative_to(project.resolve()) for name in bundle.namelist()))
                bundle.extractall(project)
            (project/'security/students.json').write_text(json.dumps([{'student_id':'20260001','name':'Example','db_user':'STUDENT01'}]),encoding='utf-8')
            files=inventory(project,audience='student-git')
            self.assertIn('security/students.json',files)
            for name in ('backend/hosting.py','scripts/render-build.sh','scripts/render-start.sh',STUDENT_GUIDE):
                self.assertIn(name,files)
            self.assertNotIn('reference/distribution/public-files.json',files)
            self.assertFalse(any(name.startswith('instructor/') or name.endswith('student.env')
                                 or 'Wallet_' in name for name in files))
            for name in ('render-build.sh','render-start.sh'):
                result=subprocess.run([str(shell),'-n',str(project/'scripts'/name)],capture_output=True,timeout=20)
                self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            env=os.environ.copy()
            env.update(SECRET_KEY='student-render-test-'*3,PORT=str(port),OML_PYTHON=Path(sys.executable).as_posix())
            log=temporary/'server.log'
            with log.open('wb') as stream:
                process=subprocess.Popen([str(shell),str(project/'scripts/render-start.sh'),'--host','127.0.0.1'],
                    cwd=temporary,env=env,stdout=stream,stderr=stream,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                try:
                    base='http://127.0.0.1:'+str(port)
                    ready=False
                    for _ in range(200):
                        if process.poll() is not None:break
                        try:
                            with urllib.request.urlopen(base+'/healthz',timeout=1) as response:
                                self.assertEqual(json.load(response),{'status':'ok'});ready=True;break
                        except (OSError,urllib.error.URLError):
                            time.sleep(.05)
                    self.assertTrue(ready,log.read_text(encoding='utf-8',errors='replace'))
                    with urllib.request.urlopen(base+'/',timeout=3) as response:
                        self.assertEqual(response.status,200)
                        self.assertNotIn('WWW-Authenticate',response.headers)
                    with self.assertRaises(urllib.error.HTTPError) as denied:
                        urllib.request.urlopen(base+'/api/status',timeout=3)
                    self.assertEqual(denied.exception.code,401)
                finally:
                    if os.name=='nt':
                        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=15)
                    else:
                        process.kill()
                    process.wait(timeout=15)
