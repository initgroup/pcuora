import base64
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT/'deploy'), str(ROOT/'scripts')]
from oml.app import create_app
from instructor.hosting import create_hosted_app
from oml.assignment import RUBRIC, IDEAS
from oml.db import wallet_directory, settings
from source_files import FILES, inventory
from package_student import build as student_kit, INSTALLERS
from package_submission import build as submission_kit
from datetime import datetime, timezone


class DistributionPolicy(unittest.TestCase):
    def setUp(self):
        parent=ROOT/'runtime'/'policy-tests';parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent)
        self.root=Path(self.temp.name).resolve()
        self.assertTrue(self.root.is_relative_to(parent.resolve()))
        self.addCleanup(self.temp.cleanup)
        for name in FILES: self.write(name, (ROOT/name).read_bytes())
        self.write('reference/student/start-here.html',(ROOT/'reference/student/start-here.html').read_bytes())
        self.write('deploy/example.py',b'print("example")')
        self.password='fake-secret-for-packaging-tests-123'
        self.write('.local/operations-commands.txt',b'PRIVATE_OPERATIONS_TEST_MARKER')
        for name in ('teacher.env','tearher.env','student.env'):
            self.write('security/'+name,('DB_USER=TEACHER01\nDB_PASSWORD='+self.password+'\n').encode())
        for name in INSTALLERS: self.write('reference/installers/'+name,b'fake installer')
        self.write('reference/wheels/fake.whl',b'fake offline wheel')
        self.write('security/Wallet_PCUORA.zip',b'fake provided wallet')

    def write(self,name,data):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)

    def test_student_archive_has_only_blank_student_example(self):
        self.write('instructor/scripts/private-tool.py',b'not for students')
        for name in ('README.md','AGENTS.md','reference/installers/README.md','submission/nested/notes.MD'):
            self.write(name,b'Markdown should not be distributed')
        with contextlib.redirect_stdout(io.StringIO()): output=student_kit(self.root)
        with zipfile.ZipFile(output) as archive:
            self.assertIn('security/Wallet_PCUORA.zip',archive.namelist())
            self.assertFalse(any(name.endswith('.env') for name in archive.namelist()))
            self.assertIn(b'DB_USER=STUDENT01',archive.read('security/student.env.example'))
            self.assertFalse(any(self.password.encode() in archive.read(name) for name in archive.namelist()))
            self.assertFalse(any(name.startswith('instructor/') for name in archive.namelist()))
            self.assertFalse(any(name.lower().endswith(('.md','.markdown')) for name in archive.namelist()))
            self.assertIn('start-here.html',archive.namelist())
            self.assertFalse(any(b'PRIVATE_OPERATIONS_TEST_MARKER' in archive.read(name) for name in archive.namelist()))

    def test_copied_secret_rejected_and_old_zip_retained(self):
        with contextlib.redirect_stdout(io.StringIO()): output=student_kit(self.root)
        old=output.read_bytes()
        self.write('deploy/leaked.py',self.password.encode())
        with self.assertRaisesRegex(ValueError,'Configured secret'): student_kit(self.root)
        self.assertEqual(output.read_bytes(),old)

    def test_student_documents_must_exist(self):
        (self.root/'reference/student/start-here.html').unlink()
        with self.assertRaisesRegex(ValueError,'Student start page'): student_kit(self.root)

    def test_build_versions_preserve_previous_packages(self):
        now=datetime(2026,11,13,1,tzinfo=timezone.utc)
        with contextlib.redirect_stdout(io.StringIO()):
            first=student_kit(self.root,now=now); raw=first.read_bytes()
            second=student_kit(self.root,now=now)
        self.assertEqual(first.name,'oml-student-kit-20261113-001.zip')
        self.assertEqual(second.name,'oml-student-kit-20261113-002.zip')
        self.assertEqual(first.read_bytes(),raw)

    def test_failed_build_does_not_publish_partial_zip(self):
        with contextlib.redirect_stdout(io.StringIO()): previous=student_kit(self.root)
        with patch('package_student.zipfile.ZipFile',side_effect=RuntimeError('Simulated archive failure')):
            with self.assertRaisesRegex(RuntimeError,'Simulated'): student_kit(self.root)
        self.assertEqual(list((self.root/'downloads').glob('*.zip')),[previous])
        self.assertFalse(list((self.root/'downloads').glob('*.reserve')))

    def test_teacher_example_or_misspelled_config_rejected(self):
        self.write('security/student.env.example',b'DB_USER=TEACHER01\nDB_PASSWORD=\n')
        with self.assertRaisesRegex(ValueError,'STUDENT01'): inventory(self.root)
        self.write('security/student.env.example',(ROOT/'security/student.env.example').read_bytes())
        self.write('submission/tearher-settings.txt',b'private config')
        with self.assertRaisesRegex(ValueError,'Private configuration'): inventory(self.root)

    def test_submission_requires_completed_report_and_matching_id(self):
        with self.assertRaisesRegex(ValueError,'Complete'): submission_kit(self.root,'20260001')
        self.write('submission/report.txt','학번: 20260001\n직접 수행한 작업 설명\n'.encode('utf-8'))
        with self.assertRaisesRegex(ValueError,'Student ID'): submission_kit(self.root,'20260002')
        output=submission_kit(self.root,'20260001')
        with zipfile.ZipFile(output) as archive:
            self.assertIn('COM22417_2026H2_20260001/report/report.txt',archive.namelist())
            self.assertIn('COM22417_2026H2_20260001/source/deploy/example.py',archive.namelist())
            self.assertFalse(any('Wallet' in name or name.endswith('.env') for name in archive.namelist()))
            self.assertFalse(any(name.lower().endswith(('.md','.markdown')) for name in archive.namelist()))

    def test_html_report_and_ambiguous_formats(self):
        self.write('submission/report.html','<!doctype html><p>학번: <b>20260001</b></p><p>직접 작성한 보고서</p>'.encode('utf-8'))
        output=submission_kit(self.root,'20260001')
        self.assertTrue(output.is_file())
        self.write('submission/report.txt','학번: 20260001'.encode('utf-8'))
        with self.assertRaisesRegex(ValueError,'one report'): submission_kit(self.root,'20260001')

    def test_invalid_pdf_and_unfinished_text_rejected(self):
        self.write('submission/report.pdf',b'not a PDF')
        with self.assertRaisesRegex(ValueError,'PDF header'): submission_kit(self.root,'20260001')
        (self.root/'submission/report.pdf').unlink()
        self.write('submission/report.txt','학번: 20260001\n[[작성]]'.encode('utf-8'))
        with self.assertRaisesRegex(ValueError,'own content'): submission_kit(self.root,'20260001')


class RenderPolicy(unittest.TestCase):
    def test_online_example_is_default(self):
        env={'SECRET_KEY':'x'*64,'OML_ACCESS_PASSWORD':'y'*32}
        app=create_hosted_app(env)
        self.assertTrue(app.config['ENABLE_LAB'])
        token=base64.b64encode(('instructor:'+'y'*32).encode()).decode()
        client=app.test_client()
        response=client.get('/lab',headers={'Authorization':'Basic '+token})
        self.assertIn('id="train-model"',response.get_data(as_text=True))
        self.assertFalse(app.config['ALLOW_STUDENT_KIT'])

    def app(self, mode='guide'):
        env={'OML_DEPLOYMENT':'render','OML_SITE_MODE':mode,'SECRET_KEY':'x'*64,
             'RENDER_EXTERNAL_HOSTNAME':'classroom.onrender.com','OML_ACCESS_PASSWORD':'y'*32}
        return create_hosted_app(env)

    def test_public_guide_cannot_connect_to_database_or_download_wallet(self):
        app=self.app();client=app.test_client()
        with patch('oml.app.connection') as connect:
            self.assertEqual(client.get('/lesson/assignment').status_code,200)
            self.assertEqual(client.get('/healthz').status_code,200)
            self.assertEqual(client.get('/lab').status_code,200)
            for path in ('/api/status','/api/model','/download/student.zip'):
                self.assertEqual(client.get(path).status_code,403)
            self.assertEqual(client.post('/api/train').status_code,403)
            connect.assert_not_called()
        self.assertNotIn('href="/download/student.zip"',client.get('/sources').get_data(as_text=True))

    def test_hosted_lab_requires_auth_and_keeps_wallet_private(self):
        app=self.app('lab');client=app.test_client()
        self.assertEqual(client.get('/api/status').status_code,401)
        token=base64.b64encode(('instructor:'+ 'y'*32).encode()).decode()
        headers={'Authorization':'Basic '+token}
        self.assertEqual(client.get('/lesson/assignment',headers=headers).status_code,200)
        self.assertEqual(client.get('/download/student.zip',headers=headers).status_code,403)
        with patch('oml.app.connection') as connect:
            self.assertEqual(client.post('/api/train',headers=headers).status_code,403)
            connect.assert_not_called()

    def test_host_and_required_secrets(self):
        client=self.app().test_client()
        self.assertEqual(client.get('/',headers={'Host':'classroom.onrender.com'}).status_code,200)
        self.assertEqual(client.get('/',headers={'Host':'evil.invalid'}).status_code,400)
        with patch.dict(os.environ,{'OML_DEPLOYMENT':'render','SECRET_KEY':'','OML_SITE_MODE':'guide'}):
            with self.assertRaisesRegex(ValueError,'SECRET_KEY'): create_hosted_app()
        with patch.dict(os.environ,{'OML_DEPLOYMENT':'render','SECRET_KEY':'x'*64,'OML_SITE_MODE':'lab','OML_ACCESS_PASSWORD':''}):
            with self.assertRaisesRegex(ValueError,'OML_ACCESS_PASSWORD'): create_hosted_app()

    def test_secret_files_directory_without_wallet_zip(self):
        parent=ROOT/'runtime'/'policy-tests';parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            path=Path(directory)
            (path/'tnsnames.ora').write_text('test alias')
            (path/'ewallet.pem').write_text('test PEM, not a real key')
            self.assertEqual(wallet_directory({'WALLET_DIR':directory}),path)
            with self.assertRaisesRegex(ValueError,'Thin'): wallet_directory({'WALLET_DIR':directory,'ORACLE_CLIENT_LIB':'windows-client'})
        with patch.dict(os.environ,{'OML_ENV_FILE':'runtime/does-not-exist.env','WALLET_DIR':'/etc/secrets','DB_USER':'STUDENT07','DB_PASSWORD':'test-only-value'}):
            cfg=settings();self.assertEqual(cfg['WALLET_DIR'],'/etc/secrets');self.assertEqual(cfg['DB_USER'],'STUDENT07')

    def test_rubric_and_deadline(self):
        self.assertEqual(sum(row['points'] for row in RUBRIC),100)
        self.assertEqual(RUBRIC[0]['points'],40)
        self.assertEqual(len(IDEAS),12)
        page=create_app({'TESTING':True}).test_client().get('/lesson/assignment').get_data(as_text=True)
        self.assertIn('2026년 12월 18일(금) 오후 6시',page)
        self.assertIn('제공한 학생과 이용한 학생 모두 감점',page)


if __name__=='__main__': unittest.main()
