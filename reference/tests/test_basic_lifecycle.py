"""기본과제 고정 범위 초기화·권한·롤백 검사. 실제 DB에는 접속하지 않습니다."""
import re
import unittest
from unittest.mock import MagicMock, patch
from backend import basic_lifecycle as life, service
from reference.tests.test_assignment_guides import AssignmentGuideTests

OBJECTS=[{'object_name':name,'object_type':'TABLE','status':'VALID'} for name in
         ('OML_BASIC_DATA','OML_BASIC_PREPARED','OML_BASIC_PREDICT')]

class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.conn=MagicMock();self.conn.username='STUDENT23'

    def test_unknown_scope_owner_and_variant_fail_before_any_sql(self):
        with patch.object(life,'execute') as execute:
            for action,owner,mode in [('other','STUDENT23','RAW'),('drop-objects','WRONG','RAW'),
                                       ('clear-training','STUDENT23','ALL')]:
                with self.assertRaises(ValueError):life.apply(self.conn,action,owner,mode)
            execute.assert_not_called()

    def test_create_tables_does_not_register_or_drop_anything(self):
        with patch.object(life,'execute') as execute,patch.object(life,'execute_file') as file:
            life.apply(self.conn,'create-tables','STUDENT23')
            self.assertEqual([c.args[1] for c in file.call_args_list],
                ['schema.sql','prepared_table.sql','prediction_table.sql','table_comments.sql'])
            self.assertEqual(execute.call_args.args[1],'queries/csv_owner.sql')

    def test_register_requires_tables_and_applies_only_procedure(self):
        with patch.object(life,'execute'),patch.object(life,'execute_file') as file,patch.object(life,'query',return_value=[]):
            with self.assertRaises(ValueError):life.apply(self.conn,'register-procedure','STUDENT23')
            file.assert_not_called()
        def query(conn,path,**values):return OBJECTS if path=='objects.sql' else []
        with patch.object(life,'execute'),patch.object(life,'execute_file') as file,patch.object(life,'query',side_effect=query),patch.object(service,'invalidate_training_state') as invalid:
            life.apply(self.conn,'register-procedure','STUDENT23')
            file.assert_called_once_with(self.conn,'classifier.sql');invalid.assert_called_once()

    def test_first_registration_and_reregistration_enforce_their_own_state(self):
        existing=OBJECTS+[{'object_name':'OML_BASIC_RUN','object_type':'PROCEDURE','status':'VALID'}]
        for action,rows in (('register-procedure',existing),('reregister-procedure',OBJECTS)):
            with patch.object(life,'execute'),patch.object(life,'execute_file') as file,patch.object(life,'query',return_value=rows):
                with self.assertRaises(ValueError):life.apply(self.conn,action,'STUDENT23')
                file.assert_not_called()

    def test_initial_csv_does_not_delete_existing_rows(self):
        with patch.object(service,'execute') as execute,patch.object(service,'invalidate_training_state'):
            service.load_csv(self.conn,[{'case_id':1}],initial=True)
            self.assertEqual([c.args[1] for c in execute.call_args_list],['queries/insert_training.sql'])
            self.conn.commit.assert_called_once()

    def test_dml_failure_rolls_back_and_preserves_local_freshness(self):
        def execute(conn,path,*args,**kwargs):
            if path=='queries/clear_prepared.sql':raise RuntimeError('fixture failure')
        with patch.object(life,'execute',side_effect=execute),patch.object(life,'query',return_value=OBJECTS),patch.object(service,'invalidate_training_state') as invalid:
            with self.assertRaises(RuntimeError):life.apply(self.conn,'clear-training','STUDENT23')
            self.conn.rollback.assert_called_once();self.conn.commit.assert_not_called();invalid.assert_not_called()

    def test_prepared_reset_only_changes_selected_mode(self):
        state={'preparations':{'RAW':1,'CLEAN':2},'models':{'RAW':1,'CLEAN':2},'confirmed':'CLEAN'}
        with patch.object(life,'execute') as execute,patch.object(life,'query',return_value=OBJECTS),patch.object(service,'read_state',return_value=state),patch.object(service,'write_state') as write:
            life.apply(self.conn,'clear-prepared','STUDENT23','RAW')
            self.assertEqual(execute.call_args.args[2],{'variant':'RAW','source_kind':'ALL'})
            self.assertEqual(state,{'preparations':{'CLEAN':2},'models':{'CLEAN':2},'confirmed':'CLEAN'})
            self.conn.commit.assert_called_once()

    def test_unconfirm_keeps_models_and_preparations(self):
        state={'models':{'RAW':1},'preparations':{'RAW':2},'confirmed':'RAW'}
        with patch.object(life,'execute') as execute,patch.object(service,'read_state',return_value=state),patch.object(service,'write_state'):
            life.apply(self.conn,'unconfirm','STUDENT23')
            self.assertEqual(execute.call_count,1)
            self.assertEqual(state,{'models':{'RAW':1},'preparations':{'RAW':2},'confirmed':None})

    def test_drop_is_exact_allowlist_and_partial_failure_invalidates_web_state(self):
        from backend.sql_files import read_sql
        sql=read_sql('reset_basic_objects.sql')
        self.assertNotIn('CASCADE',sql);self.assertNotIn('PURGE',sql)
        self.assertNotRegex(sql,r'DROP (?:TABLE|PROCEDURE) DM')
        self.assertEqual(set(re.findall(r'DROP (?:TABLE|PROCEDURE) (OML_[A-Z_]+)',sql)),
                         {'OML_BASIC_DATA','OML_BASIC_PREPARED','OML_BASIC_PREDICT','OML_BASIC_RUN'})
        def execute(conn,path,*args):
            if path=='reset_basic_objects.sql':raise RuntimeError('partial DDL')
        saved={'models':{},'assignments':{'mission':{'RAW':{'fingerprint':'keep'}}},'practice_evidence':{'basic':{},'mission':{'predict':{'total':30}}}}
        with patch.object(life,'execute',side_effect=execute),patch.object(service,'read_state',return_value=saved),patch.object(service,'write_state') as write:
            with self.assertRaises(RuntimeError):life.apply(self.conn,'drop-objects','STUDENT23')
            write.assert_called_once_with(self.conn,{'models':{},'assignments':{'mission':{'RAW':{'fingerprint':'keep'}}},'practice_evidence':{'mission':{'predict':{'total':30}}}})

class LifecycleApiTests(unittest.TestCase):
    def test_login_csrf_and_owner_precede_mutation(self):
        fixture=AssignmentGuideTests()
        with fixture.client(authenticated=False) as (client,headers,connect),patch.object(life,'apply') as apply:
            response=client.post('/api/basic/lifecycle',json={'action':'drop-objects'})
            self.assertIn(response.status_code,(401,403));apply.assert_not_called();connect.assert_not_called()
        with fixture.client() as (client,headers,connect),patch.object(life,'apply',return_value='done') as apply,patch.object(service,'status',return_value={}):
            self.assertEqual(client.post('/api/basic/lifecycle',json={'action':'drop-objects'}).status_code,403)
            apply.assert_not_called()
            response=client.post('/api/basic/lifecycle',headers=headers,json={'action':'clear-prepared','variant':'CLEAN'})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(apply.call_args.args[1:],
                ('clear-prepared',connect.return_value.__enter__.return_value.username,'CLEAN'))

    def test_new_help_uses_real_files_without_database_calls(self):
        fixture=AssignmentGuideTests()
        with fixture.client() as (client,headers,connect):
            for action in life.ACTIONS:
                response=client.get('/api/coding-help',params={'operation':action,'assignment':'basic','variant':'CLEAN','page':'models' if action=='unconfirm' else ''})
                self.assertEqual(response.status_code,200,response.text)
                flow=response.json()['flow']
                self.assertEqual(len(flow['stages']),6)
                self.assertIn('backend/basic_lifecycle.py',[f['path'] for f in flow['files'].values()])
            connect.assert_not_called()

    def test_mission_reset_guides_are_scoped_and_creative_has_no_answers(self):
        fixture=AssignmentGuideTests()
        with fixture.client() as (client,headers,connect):
            fixture.select(client,headers,'festival')
            for op in ('clear-training','clear-prediction','clear-prepared','drop-objects'):
                response=client.get('/api/coding-help',params={'operation':op,'assignment':'mission','variant':'CLEAN'})
                self.assertEqual(response.status_code,200,response.text)
                result=response.json()
                sql='\n'.join(f['content'] for f in result['flow']['files'].values() if f['origin']=='generated')
                self.assertIn('OML_MISSION_',sql);self.assertNotIn('OML_BASIC_',sql)
                self.assertEqual(result['flow']['mode'],'manual-guide')
                creative=client.get('/api/coding-help',params={'operation':op,'assignment':'creative'})
                self.assertEqual(creative.status_code,200,creative.text)
                generated='\n'.join(f['content'] for f in creative.json()['flow']['files'].values() if f['origin']=='generated')
                self.assertNotIn('CREATE_MODEL2',generated)
            connect.return_value.__enter__.return_value.cursor.assert_not_called()

if __name__=='__main__':unittest.main()
