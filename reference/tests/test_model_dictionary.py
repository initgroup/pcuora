"""실제 자동 생성 객체 조회의 읽기 전용·식별자·빈 결과·실패 경계를 검증합니다."""
import sys,unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from backend import model_dictionary,coding_help
from fastapi.testclient import TestClient
from app import create_app

class ModelDictionaryTests(unittest.TestCase):
    def test_fixed_selects_use_selected_model_bind_without_writes(self):
        conn=MagicMock();conn.username='STUDENT_QA'
        with patch.object(model_dictionary,'query',return_value=[]) as query,patch.object(model_dictionary,'execute') as execute:
            value=model_dictionary.read(conn,'CLEAN')
        self.assertFalse(value['exists']);self.assertEqual(len(value['sections']),len(model_dictionary.CATALOG))
        self.assertEqual(query.call_count,len(model_dictionary.CATALOG));execute.assert_not_called()
        for call,entry in zip(query.call_args_list,model_dictionary.CATALOG):
            self.assertEqual(call.args,(conn,'dictionary_'+entry[0]+'.sql'))
            self.assertEqual(call.kwargs,{'model_name':'OML_BASIC_CLEAN_MODEL'})
            self.assertIn(':model_name',(ROOT/'sql/queries'/call.args[1]).read_text(encoding='utf-8'))
        conn.commit.assert_not_called();conn.rollback.assert_not_called()
        with self.assertRaises(ValueError):model_dictionary.read(conn,'RAW; DROP MODEL')

    def test_actual_objects_have_owner_qualified_limited_safe_queries(self):
        conn=MagicMock();conn.username='STUDENT_QA';name='DM$VCOML_BASIC_RAW_MODEL'
        cols=[dict(column_name='COST',data_type='NUMBER'),dict(column_name='VALUE',data_type='XMLTYPE'),dict(column_name='CHUNK',data_type='RAW')]
        with patch.object(model_dictionary,'execute',return_value=[]) as execute:
            detail=model_dictionary.object_detail(conn,'OML_BASIC_RAW_MODEL',dict(object_name=name,object_type='VIEW'),cols,'Scoring Cost Matrix','DECISION_TREE')
        self.assertIn('FROM "STUDENT_QA"."'+name+'"',detail['sql'])
        self.assertIn('FETCH FIRST 20 ROWS ONLY',detail['sql']);self.assertIn('XMLSERIALIZE',detail['sql'])
        self.assertNotIn('"CHUNK"',detail['sql']);self.assertEqual(detail['omitted_columns'],['CHUNK (RAW)'])
        self.assertIn('0행',detail['explanation']);self.assertEqual(detail['error'],'');execute.assert_called_once()
        with patch.object(model_dictionary,'execute') as execute:
            bad=model_dictionary.object_detail(conn,'OML_BASIC_RAW_MODEL',dict(object_name='OTHER;DROP',object_type='TABLE'),cols,'','')
        self.assertEqual(bad['sql'],'');execute.assert_not_called()

    def test_detail_failure_is_not_an_empty_success_and_does_not_leak_connection(self):
        conn=MagicMock();conn.username='STUDENT_QA'
        with patch.object(model_dictionary,'execute',side_effect=RuntimeError('ORA-00942 secret-connection-string')):
            detail=model_dictionary.object_detail(conn,'OML_BASIC_RAW_MODEL',dict(object_name='DM$VCOML_BASIC_RAW_MODEL',object_type='VIEW'),[dict(column_name='COST',data_type='NUMBER')],'','DECISION_TREE')
        self.assertIn('ORA-00942',detail['error']);self.assertNotIn('secret',detail['error'])

    def test_code_meaning_is_algorithm_aware(self):
        self.assertIn('예측',model_dictionary.code_meaning('VC','DECISION_TREE'))
        self.assertIn('학습',model_dictionary.code_meaning('VM','DECISION_TREE'))
        self.assertIn('내부 저장',model_dictionary.code_meaning('P5','DECISION_TREE'))
        self.assertNotIn('비용',model_dictionary.code_meaning('VC','CUR','Attribute Importance'))
        self.assertEqual(model_dictionary.code_meaning('VC','CUR','Attribute Importance'),'Attribute Importance')

    def test_dictionary_failure_is_not_missing_model_or_empty_result(self):
        with patch.object(model_dictionary,'query',side_effect=RuntimeError('ORA-00942 secret-connection-string')):
            with self.assertRaisesRegex(ValueError,'USER_MINING_MODELS 조회 실패.*ORA-00942') as result:model_dictionary.read(MagicMock(),'RAW')
        self.assertNotIn('secret-connection-string',str(result.exception))

    def test_help_is_current_read_only_sources_and_route_requires_login(self):
        with patch.object(model_dictionary,'query',side_effect=AssertionError('Help must not query DB')):
            for mode in ('RAW','CLEAN'):
                help=coding_help.describe('model-dictionary',variant=mode)
                for entry in model_dictionary.CATALOG:self.assertIn('FROM '+entry[1],help['script'])
                self.assertIn("= 'OML_BASIC_"+mode+"_MODEL'",help['script'])
                self.assertNotIn(':model_name',help['script']);self.assertEqual(help['application']['command'],'')
                sql=' '.join(i['path'] for stage in help['flow']['stages'] for i in stage['items'])
                self.assertIn('dictionary_detail_rows.sql',sql)
        with self.assertRaises(ValueError):coding_help.describe('model-dictionary',variant='BOTH')
        with TestClient(create_app()) as client:self.assertEqual(client.get('/api/models/dictionary').status_code,401)

if __name__=='__main__':unittest.main()
