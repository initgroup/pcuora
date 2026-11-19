"""배포 CSV 원본 조회·다운로드가 DB 없이 동작하고 값·범위를 보존하는지 검사합니다."""
import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from app import create_app
from fastapi.testclient import TestClient

class DatasetPreviewTests(unittest.TestCase):
    def setUp(self):
        self.db=patch('app.connection',side_effect=AssertionError('CSV lookup must not connect to DB'))
        self.db.start();self.addCleanup(self.db.stop)
        self.client=TestClient(create_app({'SECRET_KEY':'dataset-preview-test-key'}))
        self.addCleanup(self.client.close)
        self.catalog=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))

    def test_all_missions_preview_and_download_preserve_csv(self):
        for item in self.catalog:
            for kind,name in [('training',item['filename']),('prediction',item['prediction_filename'])]:
                with self.subTest(key=item['key'],kind=kind):
                    raw=(ROOT/'data/examples'/name).read_bytes()
                    expected=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
                    url=f"/api/datasets/{item['key']}/preview?kind={kind}"
                    first=self.client.get(url).json()
                    self.assertEqual(first['rows'],expected[:50]);self.assertEqual(first['total'],len(expected))
                    self.assertEqual(first['columns'],list(expected[0]));self.assertEqual(first['filename'],name)
                    last=self.client.get(url+f"&page={first['pages']}").json()
                    self.assertEqual(last['rows'],expected[(first['pages']-1)*50:])
                    downloaded=self.client.get(f"/download/datasets/{item['key']}?kind={kind}")
                    self.assertEqual(downloaded.status_code,200);self.assertEqual(downloaded.content,raw)
                    if kind=='prediction':self.assertNotIn('label',first['columns'])
            for split,total in [('TRAIN',1200),('TEST',300)]:
                data=self.client.get(f"/api/datasets/{item['key']}/preview?split={split}").json()
                self.assertEqual(data['total'],total);self.assertTrue(all(row['split']==split for row in data['rows']))

    def test_invalid_keys_kinds_and_ranges(self):
        for suffix in ['unknown/preview','festival/preview?kind=other','festival/preview?kind=../../security/student.env']:
            self.assertEqual(self.client.get('/api/datasets/'+suffix).status_code,404)
        for suffix in ['split=other','page=0','page=31','kind=prediction&split=TEST']:
            self.assertEqual(self.client.get('/api/datasets/festival/preview?'+suffix).status_code,400)
        self.assertEqual(self.client.get('/api/datasets/festival/preview?page=abc').status_code,422)
        self.assertEqual(self.client.get('/download/datasets/unknown').status_code,404)

    def test_raw_text_whitespace_newline_empty_and_html_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);(base/'data/examples').mkdir(parents=True)
            (base/'data/catalog.json').write_text(json.dumps([{'key':'fixture','filename':'text.csv','prediction_filename':'text.csv'}]),encoding='utf-8')
            source='case_id,value,empty\n001,"  <script>alert(1)</script>\nnext line  ",\n'
            (base/'data/examples/text.csv').write_text(source,encoding='utf-8',newline='')
            with patch('app.ROOT',base):
                result=self.client.get('/api/datasets/fixture/preview').json()
            self.assertEqual(result['rows'],[{'case_id':'001','value':'  <script>alert(1)</script>\nnext line  ','empty':''}])

    def test_ui_and_deployment_catalog(self):
        html=self.client.get('/mission').text
        self.assertEqual(len(self.catalog),12)
        self.assertEqual(html.count('data-mission-preview='),len(self.catalog))
        self.assertEqual(html.count('data-mission-schema='),len(self.catalog))
        from scripts.source_files import APP_FILES
        for item in self.catalog:
            for name in [item['filename'],item['prediction_filename']]:self.assertIn('data/examples/'+name,APP_FILES)
        self.assertIn('id="mission-csv-dialog"',html)
        self.assertIn('식별자 키',html);self.assertIn('설명변수',html);self.assertIn('타깃변수',html)
        self.assertNotIn('id="mission-csv-dialog"',self.client.get('/creative').text)

if __name__=='__main__':unittest.main()
