"""교육용 로그의 값 보존, 임의 객체/소스 차단, 모델 무효화·롤백을 검증합니다."""
import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from backend import sql_trace,sql_files,service,assignment_templates as tasks,coding_help

class SimpleTests(unittest.TestCase):
    def test_bind_display_preserves_sql_literals_comments_and_original(self):
        sql="SELECT :text, :number, :empty, ':text', q'[:text]', \"a:text\" -- :text\n/* :number */ FROM dual"
        shown=sql_trace.rendered(sql,{'text':"O'Brien :number",'number':-1.5,'empty':None})
        self.assertIn("'O''Brien :number', -1.5, NULL",shown)
        self.assertIn("':text', q'[:text]', \"a:text\" -- :text\n/* :number */",shown)
        self.assertTrue(sql.startswith('SELECT :text'))

    def test_request_logs_and_batch_failure_keep_bounded_metadata(self):
        sql_trace.begin();sql_trace.add('SELECT :v',{'v':'first'})
        sql_trace.begin();self.assertEqual(sql_trace.records(),[])
        conn=MagicMock();conn.cursor.return_value.__enter__.return_value.executemany.side_effect=RuntimeError('failed')
        values=[{'case_id':1},{'case_id':1}]
        with self.assertRaises(RuntimeError):sql_files.execute(conn,'queries/insert_training.sql',many=values)
        self.assertNotIn('batch_binds',sql_trace.records()[0])
        self.assertEqual(sql_trace.records()[0]['batch_count'],len(values))
        self.assertEqual(sql_trace.records()[0]['batches'],1)
        self.assertEqual(sql_trace.records()[0]['status'],'error')

    def test_object_and_help_allowlists(self):
        for name in ('OTHER','OML_X;DROP TABLE A','OTHER.OML_X','"OML_X"'):
            with self.assertRaises(ValueError):sql_files.identifier(name)
        for field in ('operation','assignment','variant','split','use_yn'):
            kwargs={'operation':'data',field:'../../security/student.env'}
            with self.assertRaises(ValueError):coding_help.describe(**kwargs)
        with self.assertRaises(ValueError):sql_files.read_sql('../security/student.env')
        for data in ({'training_table':'OML_BASIC_DATA','prediction_table':'OML_OTHER','procedure_name':'OML_RUN'},
                     {'training_table':'OML_DUP','prediction_table':'OML_DUP','procedure_name':'OML_RUN'}):
            with self.assertRaises(ValueError):tasks.save_config('QA','mission',data)

    def test_csv_schema_validation_precedes_delete(self):
        conn=MagicMock();cfg=tasks.assignment('mission')
        with patch.object(tasks,'query',return_value=[{'column_name':'CASE_ID','nullable':'N','data_default':None}]),patch.object(tasks,'execute') as execute:
            with self.assertRaises(ValueError):tasks.load_custom(conn,cfg,'[{"CASE_ID":1,"UNKNOWN_COLUMN":3}]')
            execute.assert_not_called()
        for raw in (b'case_id,CASE_ID\n1,2',b'case_id,x\n1',b'case_id,x\n1,2,3'):
            with self.assertRaises(ValueError):tasks.csv_payload(raw)

    def test_basic_import_failure_rolls_back_and_does_not_confirm(self):
        conn=MagicMock();sql_trace.begin()
        with patch.object(service,'execute',side_effect=[720,RuntimeError('insert failed')]),patch.object(service,'write_state') as save:
            with self.assertRaises(RuntimeError):service.load_csv(conn,[{'case_id':1}])
            conn.rollback.assert_called_once();conn.commit.assert_not_called();save.assert_not_called()
        self.assertEqual(sql_trace.records()[-1]['sql'],'ROLLBACK')

    def test_models_require_matching_data_procedure_and_creation(self):
        conn=MagicMock()
        saved={'models':{'RAW':{'fingerprint':'current','created':'date1'}},'confirmed':'RAW'}
        with patch.object(service,'read_state',return_value=saved),patch.object(service,'query',return_value=[{'model_name':'OML_BASIC_RAW_MODEL','creation_date':'date1'}]),patch.object(service,'fingerprint',return_value='current') as fingerprint:
            self.assertEqual(service.model_rows(conn)[0]['is_confirmed'],1)
            fingerprint.return_value='changed'
            self.assertEqual(service.model_rows(conn)[0]['is_current'],0)
        with patch.object(service,'model_rows',return_value=[{'is_confirmed':0,'is_current':1}]):
            with self.assertRaises(ValueError):service.predictions(conn)

    def test_same_csv_reload_clears_basic_preparation_and_model_stamps(self):
        saved={'preparations':{'RAW':{'source':'same'},'CLEAN':{'source':'same'}},
               'models':{'RAW':{'fingerprint':'same'},'CLEAN':{'fingerprint':'same'}},'confirmed':'RAW',
               'assignment_preparations':{'mission':{'RAW':{'source':'keep'}}}}
        conn=MagicMock()
        with patch.object(service,'execute'),patch.object(service,'read_state',return_value=saved),patch.object(service,'write_state') as save:
            service.load_csv(conn,[{'case_id':1}])
        conn.commit.assert_called_once();conn.rollback.assert_not_called()
        self.assertNotIn('preparations',saved);self.assertEqual(saved['models'],{});self.assertIsNone(saved['confirmed'])
        self.assertEqual(saved['assignment_preparations']['mission']['RAW']['source'],'keep')
        save.assert_called_once_with(conn,saved)

    def test_prediction_csv_does_not_clear_training_stamps(self):
        with patch.object(service,'execute'),patch.object(service,'invalidate_training_state') as invalidate:
            service.load_csv(MagicMock(),[{'case_id':1}],prediction=True)
        invalidate.assert_not_called()

if __name__=='__main__':unittest.main()
