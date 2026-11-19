"""Runtime SQL is rendered from real templates, without DB work or fabricated CSV data."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from backend import coding_help, mission_guide, runtime_sql, service, sql_files
from reference.tests import test_assignment_guides as guide_fixtures

class RuntimeSqlTests(unittest.TestCase):
    def selected(self,result,path):
        items=[i for i in result['flow']['stages'][-1]['items'] if i.get('runtime_kind')=='selected' and i['source_path']==path]
        return [result['flow']['files'][i['file_id']]['content'] for i in items]

    def test_current_inputs_replace_actual_prepared_template_for_both_assignments(self):
        topic=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))[2]
        path='sql/queries/prepared_rows.sql'
        original=(ROOT/path).read_text(encoding='utf-8')
        for assignment in ('basic','mission'):
            for mode in ('RAW','CLEAN'):
                for kind in ('ALL','TRAIN','TEST','PREDICT'):
                    with self.subTest(assignment=assignment,mode=mode,kind=kind):
                        result=(coding_help.describe('prepared-data',user='STUDENT23',variant=mode,source_kind=kind) if assignment=='basic'
                                else mission_guide.generate(topic,'prepared-data',mode,kind,schema='STUDENT23'))
                        scripts=self.selected(result,path);self.assertEqual(len(scripts),1)
                        sql=scripts[0]
                        self.assertIn('FROM STUDENT23.OML_'+assignment.upper()+'_PREPARED',sql)
                        self.assertIn("PREP_MODE = '"+mode+"'",sql)
                        self.assertIn("('"+kind+"' = 'ALL' OR SOURCE_KIND = '"+kind+"')",sql)
                        self.assertIn('FETCH FIRST 5000 ROWS ONLY',sql)
                        self.assertIn("CURRENT_SCHEMA",sql)
                        self.assertFalse(runtime_sql.bind_names(sql));self.assertNotIn('{{',sql)
                        files=[f for f in result['flow']['files'].values() if f['origin']=='source' and f['path']==path]
                        self.assertEqual(len(files),1);self.assertEqual(files[0]['content'],original)
                        item=next(i for i in result['flow']['stages'][-1]['items'] if i.get('source_path')==path)
                        self.assertIsNone(item['line']);self.assertIsNone(item['end_line'])
                        self.assertEqual(item['origin'],'generated')

    def test_mission_original_data_has_separate_runnable_sql_for_selected_owner(self):
        topic=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))[2]
        result=mission_guide.generate(topic,'data','RAW','ALL',schema='STUDENT23')
        path='sql/queries/custom_rows.sql'
        scripts=self.selected(result,path)
        self.assertEqual(len(scripts),1)
        self.assertIn('FROM STUDENT23.OML_MISSION_DATA',scripts[0])
        self.assertNotIn('{{table}}',scripts[0])
        self.assertFalse(runtime_sql.bind_names(scripts[0]))
        original=[f for f in result['flow']['files'].values() if f['origin']=='source' and f['path']==path]
        self.assertEqual(original[0]['content'],(ROOT/path).read_text(encoding='utf-8'))
        self.assertIn('{{table}}',original[0]['content'])

    def test_basic_filters_and_metadata_literals_are_exact(self):
        result=coding_help.describe('data',user='STUDENT23',use_yn='N',split='TEST')
        sql=self.selected(result,'sql/queries/training_rows.sql')[0]
        self.assertIn("'N'",sql);self.assertIn("'TEST'",sql)
        status=coding_help.describe('status',user='STUDENT23')
        sql=self.selected(status,'sql/queries/objects.sql')[0]
        self.assertIn("'OML_BASIC_DATA'",sql);self.assertNotIn("'STUDENT23.OML_BASIC_DATA'",sql)

    def test_known_out_parameters_are_declared_for_f5_including_mission(self):
        topic=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))[2]
        for assignment in ('basic','mission'):
            result=(coding_help.describe('evaluate',user='STUDENT23',variant='CLEAN') if assignment=='basic'
                    else mission_guide.generate(topic,'evaluate','CLEAN','TRAIN',schema='STUDENT23'))
            script=self.selected(result,'sql/queries/call_classifier.sql')[0]
            self.assertIn('VARIABLE p_result REFCURSOR',script);self.assertIn('VARIABLE p_sql CLOB',script)
            self.assertIn("STUDENT23.OML_"+assignment.upper()+"_RUN('EVALUATE', 'CLEAN', :p_result, :p_sql)",script)
            self.assertIn('PRINT p_result',script);self.assertIn('PRINT p_sql',script)
            self.assertEqual(runtime_sql.bind_names(script),{'p_result','p_sql'})

    def test_unknown_inputs_and_csv_values_are_never_invented(self):
        result=dict(assignment='basic',owner='STUDENT23',operation='data',variant='RAW',binds={})
        for sql in ('SELECT :unknown_value FROM DUAL','SELECT {{view}} FROM DUAL','INSERT INTO {{table}} VALUES (:csv_row)'):
            self.assertIsNone(runtime_sql.selected_sql('sql/queries/custom_rows.sql',sql,result))
        for operation in ('import','prediction-import','recreate','save','delete','clear-training'):
            result['operation']=operation
            self.assertIsNone(runtime_sql.selected_sql('sql/queries/custom_delete.sql','DELETE FROM {{table}}',result))
        for operation in ('import','prediction-import'):
            result=coding_help.describe(operation,user='STUDENT23')
            self.assertFalse(any(i.get('runtime_kind') for i in result['flow']['stages'][-1]['items']))

    def test_literal_escaping_colons_and_original_names_are_preserved(self):
        result=dict(assignment='basic',owner='STUDENT23',operation='data',variant='RAW',binds={'split':"T'EST"})
        sql="-- :not_a_bind\nSELECT ':clock', 'OML_BASIC_DATA', :split FROM OML_BASIC_DATA"
        script=runtime_sql.selected_sql('sql/queries/training_rows.sql',sql,result)
        self.assertIn("'T''EST'",script);self.assertIn("':clock'",script);self.assertIn('-- :not_a_bind',script)
        self.assertIn("'OML_BASIC_DATA'",script);self.assertIn('FROM STUDENT23.OML_BASIC_DATA',script)
        self.assertFalse(runtime_sql.bind_names(script))

    def test_both_mode_has_distinct_runnable_calls(self):
        result=coding_help.describe('evaluate',variant='BOTH',user='STUDENT23')
        scripts=self.selected(result,'sql/queries/call_classifier.sql')
        self.assertEqual(len(scripts),2)
        self.assertIn("'RAW'",scripts[0]);self.assertIn("'CLEAN'",scripts[1])
        self.assertTrue(all("'BOTH'" not in s for s in scripts))

    def test_help_does_not_connect_execute_or_collect_csv_and_creative_stays_private(self):
        fixture=guide_fixtures.AssignmentGuideTests()
        with fixture.client() as (client,headers,connect), patch.object(service,'get_prepared_data',side_effect=AssertionError('Help must not query')), patch.object(sql_files,'execute',side_effect=AssertionError('Help must not execute')):
            fixture.select(client,headers,'ott')
            for assignment in ('basic','mission'):
                response=client.get('/api/coding-help',params=dict(operation='prepared-data',assignment=assignment,variant='CLEAN',source_kind='TEST'))
                self.assertEqual(response.status_code,200,response.text)
                self.assertTrue(self.selected(response.json(),'sql/queries/prepared_rows.sql'))
            self.assertEqual(client.get('/api/coding-help',params=dict(assignment='creative')).status_code,404)
            connect.assert_not_called()

if __name__=='__main__':unittest.main()
