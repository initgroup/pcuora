"""DB 중심 실습의 웹 계약·자유 출력·최신 모델 차단을 검증합니다."""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app import create_app
from backend import assignment_templates as tasks, service


class OmlLabTests(unittest.TestCase):
    def assignment_readiness(self,key,*,absent=(),invalid=(),bad_arguments=False,missing_columns=(),errors=()):
        """메타데이터 응답만 만듭니다. 실제 DB 객체는 생성·수정하지 않습니다."""
        cfg=tasks.assignment(key)
        objects=[{'object_name':cfg[field],'object_type':kind,'status':'INVALID' if field in invalid else 'VALID','object_id':index+1}
                 for index,(field,kind) in enumerate([('training_table','TABLE'),('prediction_table','TABLE'),('prepared_table','TABLE'),('procedure_name','PROCEDURE')]) if field not in absent]
        columns=[{'column_name':name} for name in ('PREP_MODE','SOURCE_KIND','CASE_ID','USE_YN','FIT_YN','EXCLUDE_REASON','PREPARED_AT') if name not in missing_columns]
        args=[{'argument_name':name,'data_type':dtype,'in_out':direction,'position':index+1}
              for index,(name,dtype,direction) in enumerate([('P_ACTION','VARCHAR2','IN'),('P_MODE','VARCHAR2','IN'),('P_RESULT','REF CURSOR','OUT'),('P_SQL','CLOB','OUT')])]
        if 'procedure_name' in absent:args=[]
        if bad_arguments:args[0]['argument_name']='WRONG_ACTION'
        values={'objects.sql':objects,'columns.sql':columns,'procedure_arguments.sql':args,'procedure_errors.sql':list(errors)}
        with patch.object(tasks,'query',side_effect=lambda _conn,path,**_binds:values[path]):
            return tasks.readiness(MagicMock(username='QA'),key)

    def test_absent_objects_are_connected_without_duplicate_creation_examples(self):
        for key in ('mission','creative'):
            with self.subTest(assignment=key):
                state=self.assignment_readiness(key,absent=('training_table','prediction_table','prepared_table','procedure_name'))
                self.assertTrue(state['connected']);self.assertFalse(state['ready'])
                self.assertEqual({item['kind'] for item in state['issues']},{'missing'})
                cfg=tasks.assignment(key)
                self.assertEqual({item['object_name'] for item in state['issues']},{cfg[field] for field in ('training_table','prediction_table','prepared_table','procedure_name')})
                diagnostic=tasks.diagnostic(key,'status',state)
                self.assertEqual(diagnostic['category'],'objects');self.assertTrue(diagnostic['db_connected'])
                self.assertEqual(diagnostic['examples'],[])
                self.assertEqual(diagnostic['sources'],[])
                self.assertNotRegex(str(diagnostic),r'CREATE TABLE|CREATE OR REPLACE PROCEDURE|DBMS_DATA_MINING')

    def test_partial_setup_reports_only_the_missing_object_without_stock_sql(self):
        state=self.assignment_readiness('mission',absent=('prediction_table',))
        diagnostic=tasks.diagnostic('mission','status',state)
        self.assertEqual(diagnostic['examples'],[])
        self.assertEqual(diagnostic['sources'],[])
        self.assertEqual([item['object_name'] for item in state['issues']],['OML_MISSION_PREDICT'])
        self.assertIn('OML_MISSION_PREDICT',str(diagnostic))
        self.assertNotIn('CREATE TABLE',str(diagnostic))

    def test_invalid_arguments_and_missing_columns_have_distinct_repair_guidance(self):
        cases=[({'invalid':('procedure_name',),'errors':({'line':7,'text':'PLS-00103: test compile error'},)},'invalid','OML_CREATIVE_RUN'),
               ({'bad_arguments':True},'arguments','OML_CREATIVE_RUN'),
               ({'missing_columns':('FIT_YN',)},'columns','OML_CREATIVE_PREPARED')]
        for options,kind,name in cases:
            with self.subTest(kind=kind):
                state=self.assignment_readiness('creative',**options)
                self.assertTrue(state['connected']);self.assertFalse(state['ready'])
                self.assertTrue(any(item['kind']==kind and item['object_name']==name for item in state['issues']))
                diagnostic=tasks.diagnostic('creative','status',state)
                self.assertEqual(diagnostic['category'],'objects');self.assertTrue(diagnostic['db_connected'])
                self.assertFalse(diagnostic.get('examples'),'Existing objects get repair guidance, never blind CREATE')
                if kind=='invalid':
                    self.assertEqual(diagnostic['locations'][0]['object_line'],7)
                    self.assertIn('PLS-00103',diagnostic['locations'][0]['code'])

    def test_row_mutation_and_append_csv_endpoints_are_removed(self):
        paths={route.path for route in create_app().routes}
        self.assertTrue({'/api/data/row','/api/data/delete','/api/models/append'}.isdisjoint(paths))

    def test_fixed_objects_do_not_depend_on_user_runtime_configuration(self):
        for task in ('mission','creative'):
            expected=tasks.assignment(task)
            self.assertEqual(tasks.configuration('USER_A',task),expected)
            self.assertEqual(tasks.configuration('USER_B',task),expected)
            with self.assertRaises(ValueError):
                tasks.save_config('USER_A',task,{**expected,'procedure_name':'OML_ANOTHER_RUN'})

    def test_stale_custom_model_is_blocked_before_oracle_call(self):
        cfg=tasks.assignment('creative');conn=MagicMock()
        with patch.object(tasks,'readiness',return_value={'ready':True,'config':cfg}), patch.object(tasks,'model_state',return_value=[{'variant':'RAW','is_current':False}]), patch.object(service,'run_model') as run:
            for action in ('evaluate','predict'):
                with self.assertRaises(ValueError):tasks.run(conn,'creative',action,mode='RAW')
            run.assert_not_called()

    @patch('backend.practice_evidence.begin')
    @patch('backend.practice_evidence.record')
    def test_prediction_accepts_free_labels_and_additional_output_columns(self, record, begin):
        cfg=tasks.assignment('creative');conn=MagicMock()
        rows=[{'case_id':7,'predicted':'등급3','probability':0.72,'student_reason':'직접 구현'}]
        with patch.object(tasks,'readiness',return_value={'ready':True,'config':cfg}), patch.object(tasks,'model_state',return_value=[{'variant':'RAW','is_current':True}]), patch.object(tasks,'execute',return_value=[{'case_id':7,'my_feature':'x'}]), patch.object(service,'run_model',return_value=rows):
            result=tasks.run(conn,'creative','predict',mode='RAW')
            self.assertEqual(result['rows'],rows)
            self.assertEqual(len(result['input_fingerprint']),64)
        with patch.object(tasks,'readiness',return_value={'ready':True,'config':cfg}), patch.object(tasks,'model_state',return_value=[{'variant':'RAW','is_current':True}]), patch.object(service,'run_model',return_value=[{'case_id':7,'predicted':'등급3'}]):
            with self.assertRaisesRegex(ValueError,'OUT'):tasks.run(conn,'creative','predict',mode='RAW')

    def test_training_without_current_preparation_does_not_mutate_a_model(self):
        conn=MagicMock()
        with patch.object(service,'query',return_value=[]),patch.object(service,'preparation_status',return_value={'RAW':{'ready':False}}),patch.object(service,'run_model') as run,patch.object(service,'write_state') as save:
            with self.assertRaisesRegex(ValueError,'전처리'):service.train_model(conn,'RAW','INIT')
            run.assert_not_called();save.assert_not_called()
        cfg=tasks.assignment('creative')
        with patch.object(tasks,'readiness',return_value={'ready':True,'config':cfg}),patch.object(tasks,'preparation_status',return_value={'CLEAN':{'ready':False}}),patch.object(service,'run_model') as run:
            with self.assertRaisesRegex(ValueError,'전처리'):tasks.run(conn,'creative','initial-train',mode='CLEAN')
            run.assert_not_called()

    def test_failed_preparation_is_never_marked_ready(self):
        conn=MagicMock()
        with patch.object(service,'fingerprint',return_value='original'),patch.object(service,'run_model',side_effect=RuntimeError('insert failed')),patch.object(service,'write_state') as save:
            with self.assertRaises(RuntimeError):service.prepare_model_data(conn,'RAW')
            save.assert_not_called()

    def test_prepare_race_cannot_reuse_a_stamp_when_source_returns_to_an_old_value(self):
        conn=MagicMock();saved={'preparations':{'RAW':{'source':'keep'},'CLEAN':{'source':'A'}}}
        # 예전 A 준비 기록이 있는 상태에서 B를 준비하는 동안 원본이 다시 A가 됩니다.
        with patch.object(service,'fingerprint',side_effect=['B','A']),patch.object(service,'read_state',return_value=saved),patch.object(service,'run_model',return_value=[]),patch.object(service,'write_state') as save:
            with self.assertRaisesRegex(ValueError,'변경'):service.prepare_model_data(conn,'CLEAN')
            save.assert_called_once_with(conn,saved)
        self.assertEqual(saved['preparations'],{'RAW':{'source':'keep'}})
        counts=[{'prep_mode':'CLEAN','rows_count':720,'fit_rows':330,'test_rows':360}]
        with patch.object(service,'fingerprint',return_value='A'),patch.object(service,'read_state',return_value=saved),patch.object(service,'execute',return_value=counts):
            self.assertFalse(service.preparation_status(conn)['CLEAN']['ready'])

    def test_procedure_call_uses_the_validated_issued_schema(self):
        conn=MagicMock(username='STUDENT23')
        cursor=conn.cursor.return_value.__enter__.return_value
        cursor.description=[]
        cursor.var.return_value.getvalue.return_value='SELECT 1 FROM DUAL'
        with patch.object(service,'query',return_value=[{'text':'procedure source'}]):
            self.assertEqual(service.run_model(conn,'VALIDATE','RAW',procedure='OML_QA_LAB_B_RUN'),[])
        statement=cursor.execute.call_args.args[0]
        self.assertIn('STUDENT23.OML_QA_LAB_B_RUN',statement)
        for owner in ('OTHER.SCHEMA',"' BAD","123"):
            conn=MagicMock(username=owner)
            with self.subTest(owner=owner),patch.object(service,'query') as query:
                with self.assertRaises(ValueError):service.run_model(conn,'VALIDATE','RAW')
                conn.cursor.assert_not_called();query.assert_not_called()

    def test_actual_schema_preserves_oracle_types_and_column_metadata(self):
        conn=MagicMock(username='STUDENT23')
        defaults={'data_length':22,'char_length':0,'char_used':None,'data_precision':None,'data_scale':None,
                  'nullable':'Y','comments':None,'data_default':None}
        specifications=[
            {'column_name':'CASE_ID','data_type':'NUMBER','nullable':'N','comments':'사례 식별자'},
            {'column_name':'SCORE','data_type':'NUMBER','data_precision':10,'data_scale':2},
            {'column_name':'TITLE','data_type':'VARCHAR2','data_length':120,'char_length':40,'char_used':'C'},
            {'column_name':'CODE','data_type':'VARCHAR2','data_length':10,'char_length':10,'char_used':'B'},
            {'column_name':'NOTE','data_type':'NVARCHAR2','data_length':100,'char_length':50,'char_used':'C'},
            {'column_name':'FLAG','data_type':'NCHAR','data_length':2,'char_length':1,'char_used':'C'},
            {'column_name':'CREATED_AT','data_type':'TIMESTAMP(6)','data_default':'SYSTIMESTAMP'}]
        columns=[{**defaults,**item} for item in specifications]
        with patch.object(tasks,'query',return_value=columns) as query:
            result=tasks.table_schema(conn,'creative','prepared')
            self.assertEqual(result['name'],'STUDENT23.OML_CREATIVE_PREPARED')
            self.assertEqual([column['type'] for column in result['columns']],
                             ['NUMBER','NUMBER(10,2)','VARCHAR2(40 CHAR)','VARCHAR2(10 BYTE)','NVARCHAR2(50)','NCHAR(1)','TIMESTAMP(6)'])
            self.assertEqual(result['columns'][0]['description'],'사례 식별자')
            self.assertEqual(result['columns'][0]['nullable'],'필수')
            self.assertEqual(result['columns'][-1]['rules'],'SYSTIMESTAMP')
            self.assertNotIn('sql',result)
            query.assert_called_once_with(conn,'schema_columns.sql',table_name='OML_CREATIVE_PREPARED')
            conn.commit.assert_not_called();conn.rollback.assert_not_called()
        with patch.object(tasks,'query',return_value=[]):
            with self.assertRaisesRegex(ValueError,'먼저 생성'):tasks.table_schema(conn,'creative')
        with patch.object(tasks,'query') as query:
            with self.assertRaises(ValueError):tasks.table_schema(conn,'creative','invalid')
            query.assert_not_called()

    def test_custom_mutation_is_rejected_before_readiness_or_model_calls(self):
        conn=MagicMock(username='STUDENT23')
        with patch.object(tasks,'readiness') as readiness,patch.object(service,'run_model') as run,patch.object(service,'write_state') as save:
            for key in ('mission','creative'):
                for action in ('prepare','import','prediction-import','train','initial-train','retrain','append-train','delete-model'):
                    with self.subTest(assignment=key,action=action),self.assertRaisesRegex(ValueError,'SQL Developer'):
                        tasks.run(conn,key,action)
            readiness.assert_not_called();run.assert_not_called();save.assert_not_called()

    def test_external_model_link_tracks_source_prepared_values_and_creation(self):
        conn=MagicMock(username='STUDENT23');cfg=tasks.assignment('mission')
        saved={'unrelated':{'keep':True},'assignments':{'creative':{'RAW':{'fingerprint':'preserve'}}}}
        original=[{'case_id':1,'score':'45'}];source=[{'line':1,'text':'procedure source'}]
        prepared={mode:[{'case_id':1,'score':45,'fit_yn':'Y'}] for mode in ('RAW','CLEAN')}
        counts=[{'prep_mode':mode,'rows_count':1500,'fit_rows':1200,'test_rows':300} for mode in ('RAW','CLEAN')]
        models=[{'model_name':'OML_MISSION_'+mode+'_MODEL','creation_date':'created-'+mode} for mode in ('RAW','CLEAN')]
        def query(_conn,path,**_binds):
            return models if path=='assignment_models.sql' else source if path=='procedure_source.sql' else []
        def execute(_conn,path,*_args,**_kwargs):
            return counts if path=='queries/prepared_count.sql' else original if path=='queries/custom_fingerprint_rows.sql' else []
        with patch.object(tasks,'readiness',return_value={'ready':True,'config':cfg}),patch.object(tasks,'query',side_effect=query),patch.object(tasks,'execute',side_effect=execute),patch.object(service,'prepared_values',side_effect=lambda _conn,_table,mode:prepared[mode]),patch.object(service,'read_state',return_value=saved),patch.object(service,'write_state') as write:
            result=tasks.link_external(conn,'mission')
            self.assertTrue(all(model['is_current'] for model in result['models']))
            self.assertTrue(all(value['ready'] for value in result['preparation'].values()))
            self.assertEqual(saved['assignments']['mission']['RAW']['origin'],'external')
            self.assertEqual(saved['assignment_preparations']['mission']['CLEAN']['origin'],'external')
            self.assertEqual(saved['assignments']['creative']['RAW']['fingerprint'],'preserve')
            self.assertEqual(saved['unrelated'],{'keep':True})
            write.assert_called_once_with(conn,saved)

            # Learning input edits invalidate only the changed mode; raw/procedure edits invalidate both.
            prepared['RAW'][0]['score']=60
            self.assertEqual([model['is_current'] for model in tasks.model_state(conn,'mission')],[False,True])
            prepared['RAW'][0]['score']=45
            models[0]['creation_date']='recreated'
            self.assertEqual([model['is_current'] for model in tasks.model_state(conn,'mission')],[False,True])
            models[0]['creation_date']='created-RAW'
            original[0]['score']='46'
            self.assertFalse(any(model['is_current'] for model in tasks.model_state(conn,'mission')))
            self.assertFalse(any(value['ready'] for value in tasks.preparation_status(conn,'mission').values()))
            original[0]['score']='45'
            source[0]['text']='changed procedure'
            self.assertFalse(any(model['is_current'] for model in tasks.model_state(conn,'mission')))
            source[0]['text']='procedure source'

            # Linking no longer usable objects must remove previously saved readiness.
            counts[1]['rows_count']=0;counts[1]['fit_rows']=0
            models.pop()
            result=tasks.link_external(conn,'mission')
            self.assertNotIn('CLEAN',saved['assignments']['mission'])
            self.assertNotIn('CLEAN',saved['assignment_preparations']['mission'])
            self.assertTrue(result['models'][0]['is_current'])
            self.assertFalse(result['models'][1]['is_current'])

    def test_preparation_records_only_the_selected_source_and_keeps_models(self):
        conn=MagicMock();saved={'models':{'RAW':{'fingerprint':'trained'}},'confirmed':'RAW','preparations':{'RAW':{'source':'old'}}}
        with patch.object(service,'fingerprint',return_value='source'),patch.object(service,'read_state',return_value=saved),patch.object(service,'run_model',return_value=[{'fit_yn':'Y'}]) as run,patch.object(service,'write_state') as save:
            self.assertEqual(service.prepare_model_data(conn,'CLEAN'),[{'fit_yn':'Y'}])
            run.assert_called_once_with(conn,'PREPARE','CLEAN');save.assert_called_once_with(conn,saved)
        self.assertEqual(saved['preparations'],{'RAW':{'source':'old'},'CLEAN':{'source':'source'}})
        self.assertEqual(saved['models'],{'RAW':{'fingerprint':'trained'}});self.assertEqual(saved['confirmed'],'RAW')

    def test_preparation_readiness_requires_source_match_and_saved_rows(self):
        conn=MagicMock();saved={'preparations':{'RAW':{'source':'old'},'CLEAN':{'source':'current'}}}
        counts=[{'prep_mode':mode,'rows_count':720,'fit_rows':330,'test_rows':360} for mode in ('RAW','CLEAN')]
        with patch.object(service,'fingerprint',return_value='current'),patch.object(service,'read_state',return_value=saved),patch.object(service,'execute',return_value=counts):
            status=service.preparation_status(conn)
            self.assertFalse(status['RAW']['ready']);self.assertTrue(status['CLEAN']['ready'])
            self.assertEqual(status['CLEAN']['fit_rows'],330)
        with patch.object(service,'fingerprint',return_value='current'),patch.object(service,'read_state',return_value=saved),patch.object(service,'execute',return_value=[]):
            self.assertFalse(service.preparation_status(conn)['CLEAN']['ready'])

    def test_prepared_fingerprint_tracks_learning_values_but_not_storage_time(self):
        conn=MagicMock();row={'prep_mode':'RAW','source_kind':'TRAIN','case_id':1,'fit_yn':'Y','feature':42,'prepared_at':'time-a'}
        with patch.object(service,'query',return_value=[{'source':'unchanged'}]),patch.object(service,'execute',return_value=[row]) as execute:
            first=service.fingerprint(conn,'RAW')
            row['prepared_at']='time-b';self.assertEqual(service.fingerprint(conn,'RAW'),first)
            row['fit_yn']='N';self.assertNotEqual(service.fingerprint(conn,'RAW'),first)
            self.assertEqual(execute.call_args.args[1],'queries/prepared_fingerprint_rows.sql')
            self.assertEqual(execute.call_args.args[2],{'variant':'RAW'})


if __name__ == '__main__':unittest.main()
