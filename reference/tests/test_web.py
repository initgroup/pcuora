import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'deploy'))
from oml.app import create_app
from oml.lessons import LESSONS
from oml.source_guide import SOURCE_CATALOG

class WebBoundaries(unittest.TestCase):
    def setUp(self):
        self.app=create_app({'TESTING':True})
        self.client=self.app.test_client();self.client.get('/')
        with self.client.session_transaction() as session:self.csrf=session['csrf']
    def test_all_lessons_and_assets(self):
        for path in ['/','/lab','/sources','/static/app.js','/static/style.css','/static/teaching.css','/static/reading.js','/download/sample.csv']+['/lesson/'+s for s in LESSONS]:
            with self.subTest(path=path):
                response=self.client.get(path);self.assertEqual(response.status_code,200);response.close()
    def test_csrf_blocks_training(self):
        with patch('oml.app.connection') as connect:
            self.assertEqual(self.client.post('/api/train').status_code,403);connect.assert_not_called()
    def test_validated_upload_without_database(self):
        raw=(ROOT/'deploy/data/classification.csv').read_bytes()
        res=self.client.post('/api/upload/validate',data={'file':(io.BytesIO(raw),'sample.csv')},headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(res.status_code,200);self.assertEqual(res.json['rows'],120)
    def test_credentials_and_paths_not_exposed(self):
        for path in ['/security/teacher.env','/runtime/server.err.log','/api/source/teacher','/api/source/../../security/teacher.env']:
            self.assertEqual(self.client.get(path).status_code,404)
    def test_public_source_viewer_is_read_only_and_allowlisted(self):
        with patch('oml.app.connection') as connect:
            for key,item in SOURCE_CATALOG.items():
                with self.subTest(source=key):
                    response=self.client.get('/api/source/'+key)
                    self.assertEqual(response.status_code,200)
                    self.assertEqual(response.mimetype,'application/json')
                    self.assertEqual(response.json['path'],item['path'])
                    self.assertTrue(response.json['source'])
            for name in ('student.env','teacher.env','env','../security/student.env'):
                self.assertEqual(self.client.get('/api/source/'+name).status_code,404)
            connect.assert_not_called()
    def test_missing_connection_is_not_a_demo(self):
        with patch('oml.app.connection',side_effect=ValueError('Missing settings')):
            res=self.client.get('/api/status');self.assertEqual(res.status_code,400)
            self.assertIn('error',res.json);self.assertNotIn('models',res.json)
    def test_upload_limit(self):
        res=self.client.post('/api/upload/validate',data=b'x'*(3*1024*1024),content_type='application/octet-stream',headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(res.status_code,413)
    def test_host_check(self):
        app=create_app({'TESTING':False})
        self.assertEqual(app.test_client().get('/',headers={'Host':'attacker.invalid'}).status_code,400)

if __name__=='__main__':unittest.main()
