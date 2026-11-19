"""운영은 메인 로그인만 사용하며 API·강사 권한·CSRF·Secure 쿠키는 유지합니다."""
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.hosting import create_hosted_app
from reference.tests import test_classifier as fixtures

ENVIRONMENT = {'SECRET_KEY': 'hosted-auth-test-secret-' * 3,
               'RENDER_EXTERNAL_HOSTNAME': 'classroom.example.invalid'}


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
                login = fixture.login(client, people[0])
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
                self.assertEqual(fixture.login(client, people[1]).status_code, 200)
                self.assertEqual(client.get('/instructor/python-web-lecture.html').status_code, 403)

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
            files=inventory(project,audience='student-git')
            for name in ('backend/hosting.py','scripts/render-build.sh','scripts/render-start.sh',STUDENT_GUIDE):
                self.assertIn(name,files)
            self.assertNotIn('reference/distribution/public-files.json',files)
            self.assertFalse(any(name.startswith('instructor/') or name.endswith('student.env')
                                 or name.endswith('students.json') or 'Wallet_' in name for name in files))
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
