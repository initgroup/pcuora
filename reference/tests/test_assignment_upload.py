"""Multipart CSV authorization, bounded loading and rollback. Never connects to student Oracle."""
import io
import json
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch, MagicMock
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from app import create_app
from backend import assignment_templates as tasks, service, sql_files
from reference.tests import test_classifier as fixtures
from reference.tests.test_csv_resources import FakeConnection
CATALOG=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
ITEM=next(item for item in CATALOG if item['key']=='ott')

def columns(names):
    return [dict(column_name=name.upper(),nullable='N' if name in ('case_id','split') else 'Y',data_default=None) for name in names]

class AssignmentUploadTests(unittest.TestCase):
    @contextmanager
    def client(self):
        fixture=fixtures.ClassifierTests()
        with fixture.login_project() as (_,env,people),patch('app.connection') as connect,patch.object(tasks,'ROOT',env.parent.parent):
            connect.return_value.__enter__.return_value.username=people[0]['db_user']
            with TestClient(create_app({'SECRET_KEY':'assignment-upload-test-key'})) as client:
                login=fixture.login(client,people[0])
                headers={'X-CSRF-Token':login.json()['csrf']}
                client.post('/api/assignments/mission/selection',json={'key':'ott'},headers=headers)
                connect.reset_mock()
                yield client,headers,connect

    def test_multipart_only_auth_csrf_and_action_allowlist_before_db(self):
        anonymous=TestClient(create_app({'SECRET_KEY':'upload-anonymous'}))
        self.assertEqual(anonymous.post('/api/assignments/mission/import/csv',files={'file':('x.csv',b'x','text/csv')}).status_code,403)
        with self.client() as (client,headers,connect):
            self.assertEqual(client.post('/api/assignments/mission/import/csv',files={'file':('x.csv',b'x','text/csv')}).status_code,403)
            self.assertEqual(client.post('/api/assignments/mission/train/csv',files={'file':('x.csv',b'x','text/csv')},headers=headers).status_code,403)
            self.assertEqual(client.post('/api/assignments/mission/import',json={},headers=headers).status_code,403)
            connect.assert_not_called()

    def test_selected_mission_training_and_prediction_upload_without_other_objects(self):
        with self.client() as (client,headers,connect),patch.object(tasks,'import_csv') as loader,patch.object(tasks,'readiness') as readiness:
            for prediction in (False,True):
                name=ITEM['prediction_filename' if prediction else 'filename']
                raw=(ROOT/'data/examples'/name).read_bytes()
                count=30 if prediction else 1500
                loader.return_value={'loaded_rows':count,'table':'STUDENT23.OML_MISSION_DATA','message':'적재 완료'}
                route='/api/assignments/mission/'+('prediction-import' if prediction else 'import')+'/csv'
                response=client.post(route,files={'file':(name,raw,'text/csv')},data={'mission':'ott'},headers=headers)
                self.assertEqual(response.status_code,200,response.text)
                values=loader.call_args.args[2]
                self.assertEqual(len(values),count)
                self.assertEqual(loader.call_args.args[3],'STUDENT23')
                self.assertEqual(loader.call_args.kwargs['prediction'],prediction)
                self.assertIsInstance(values,list)
            readiness.assert_not_called()

    def test_api_reaches_real_bound_loader_and_returns_bounded_trace(self):
        with self.client() as (client,headers,connect),patch.object(tasks,'query',return_value=columns(ITEM['columns'])),patch.object(service,'read_state',return_value={}),patch.object(service,'write_state'):
            conn=FakeConnection();connect.return_value.__enter__.return_value=conn
            response=client.post('/api/assignments/mission/import/csv',files={'file':('ott.csv',(ROOT/'data/examples/ott.csv').read_bytes(),'text/csv')},data={'mission':'ott','owner':'STUDENT99'},headers=headers)
            self.assertEqual(response.status_code,200,response.text)
            result=response.json()
            self.assertEqual(result['loaded_rows'],1500)
            self.assertEqual(result['table'],'STUDENT23.OML_MISSION_DATA')
            self.assertEqual([size for _,size in conn.batches],[500,500,500])
            self.assertEqual(conn.commits,1)
            self.assertLess(len(json.dumps(result)),7000)
            self.assertNotIn('batch_binds',json.dumps(result))

    def test_invalid_or_mismatched_files_fail_before_connection_and_delete(self):
        with self.client() as (client,headers,connect),patch.object(tasks,'import_csv') as loader:
            valid=(ROOT/'data/examples/ott.csv').read_bytes()
            for raw,mission in [(b'case_id,wrong\n1,2\n','ott'),(b'\xff','ott'),(b'x'*(2*1024*1024+1),'ott'),(valid,'festival'),(valid+valid.splitlines()[1]+b'\n','ott')]:
                response=client.post('/api/assignments/mission/import/csv',files={'file':('x.csv',raw,'text/csv')},data={'mission':mission},headers=headers)
                self.assertEqual(response.status_code,400,response.text)
            connect.assert_not_called();loader.assert_not_called()

    def test_actual_loader_uses_three_batches_one_commit_and_qualified_target(self):
        values,_=tasks.csv_payload((ROOT/'data/examples/ott.csv').read_bytes(),encoded=False)
        conn=FakeConnection()
        saved={'assignments':{'mission':{'RAW':{'old':True}},'creative':{'keep':True}},'assignment_preparations':{'mission':{'old':True}},'practice_evidence':{'mission':{'predict':{'old':True}},'basic':{'keep':True}}}
        with patch.object(tasks,'query',return_value=columns(ITEM['columns'])),patch.object(service,'read_state',return_value=saved),patch.object(service,'write_state') as save:
            result=tasks.import_csv(conn,'mission',values,'STUDENT23')
        self.assertEqual(result['loaded_rows'],1500)
        self.assertEqual([size for _,size in conn.batches],[500,500,500])
        self.assertEqual((conn.commits,conn.rollbacks),(1,0))
        self.assertTrue(all('STUDENT23.OML_MISSION_DATA' in sql for sql,_ in conn.batches))
        self.assertEqual(saved['assignments'],{'creative':{'keep':True}})
        self.assertNotIn('mission',saved['practice_evidence']);save.assert_called_once()

    def test_late_batch_failure_rolls_back_and_keeps_state(self):
        values,_=tasks.csv_payload((ROOT/'data/examples/ott.csv').read_bytes(),encoded=False)
        conn=FakeConnection(fail_batch=2)
        with patch.object(tasks,'query',return_value=columns(ITEM['columns'])),patch.object(service,'write_state') as save:
            with self.assertRaisesRegex(RuntimeError,'batch failure'):tasks.import_csv(conn,'mission',values,'STUDENT23')
            save.assert_not_called()
        self.assertEqual(conn.data,[{'case_id':9000}])
        self.assertEqual((conn.commits,conn.rollbacks),(0,1))

    def test_missing_target_foreign_owner_and_creative_cap_are_non_destructive(self):
        values=[{'case_id':'1','feature':'2'}]
        conn=FakeConnection()
        with patch.object(tasks,'query',return_value=[]):
            with self.assertRaisesRegex(ValueError,'먼저 생성'):tasks.import_csv(conn,'mission',values,'STUDENT23')
        self.assertEqual(conn.data,[{'case_id':9000}]);self.assertEqual(conn.batches,[])
        with patch.object(tasks,'execute') as execute:
            with self.assertRaisesRegex(ValueError,'발급'):tasks.import_csv(conn,'mission',values,'STUDENT24')
            execute.assert_not_called()
        with patch.object(tasks,'query',return_value=columns(['case_id','feature'])),patch.object(tasks,'execute',side_effect=[None,[{'rows_count':10000}]]):
            with self.assertRaisesRegex(ValueError,'10,000'):tasks.import_csv(conn,'creative',values,'STUDENT23')
        self.assertEqual(conn.data,[{'case_id':9000}])

    def test_creative_upload_has_free_headers_and_does_not_need_procedure(self):
        with self.client() as (client,headers,connect),patch.object(tasks,'import_csv',return_value={'loaded_rows':1,'message':'적재 완료'}) as loader:
            response=client.post('/api/assignments/creative/import/csv',files={'file':('creative.csv',b'CASE_ID,MY_FEATURE,LABEL,SPLIT,USE_YN\n1,unknown,A,TRAIN,Y\n','text/csv')},headers=headers)
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(loader.call_args.args[2][0]['MY_FEATURE'],'unknown')

    def test_table_only_reads_work_without_run_or_other_tables(self):
        conn=MagicMock(username='STUDENT23')
        for action,target in [('data','DATA'),('prediction-data','PREDICT')]:
            with patch.object(tasks,'query',return_value=columns(['case_id'])),patch.object(tasks,'execute',return_value=[{'case_id':1}]) as execute,patch.object(tasks,'readiness') as readiness:
                self.assertEqual(tasks.run(conn,'mission',action)['rows'],[{'case_id':1}])
                self.assertEqual(execute.call_args.kwargs['replacements']['table'],'STUDENT23.OML_MISSION_'+target)
                readiness.assert_not_called()

if __name__=='__main__':unittest.main()
