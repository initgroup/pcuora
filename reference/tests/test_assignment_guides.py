"""Assignment-specific teaching contracts without a real Oracle connection."""
from contextlib import contextmanager
import csv
import json
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient
from app import create_app
from backend import assignment_templates as tasks
from reference.tests import test_classifier as fixtures


class AssignmentGuideTests(unittest.TestCase):
    @contextmanager
    def client(self, authenticated=True):
        fixture = fixtures.ClassifierTests()
        with fixture.login_project() as (_, env, people), patch('app.connection') as connect, patch.object(tasks, 'ROOT', env.parent.parent):
            with TestClient(create_app({'SECRET_KEY': 'assignment-guide-test-key' * 3})) as client:
                connect.return_value.__enter__.return_value.username=people[0]['db_user']
                csrf = None
                if authenticated:
                    response = fixture.login(client, people[0])
                    self.assertEqual(response.status_code, 200, response.text)
                    csrf = response.json()['csrf']
                    connect.reset_mock()
                yield client, {'X-CSRF-Token': csrf} if csrf else {}, connect

    def select(self, client, headers, key):
        response = client.post('/api/assignments/mission/selection', json={'key': key}, headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['key'], key)

    def test_generated_mission_help_requires_login_and_a_valid_selection(self):
        with self.client(authenticated=False) as (client, _, connect):
            for path in ('/api/assignments/mission/guide?operation=prepare',
                         '/api/assignments/mission/guide/download?file=procedure',
                         '/api/assignments/mission/schema',
                         '/api/coding-help?assignment=mission&operation=prepare'):
                self.assertEqual(client.get(path).status_code, 401, path)
            connect.assert_not_called()
        with self.client() as (client, headers, connect):
            for path in ('/api/assignments/mission/guide?operation=prepare',
                         '/api/assignments/mission/guide/download?file=procedure',
                         '/api/assignments/mission/schema',
                         '/api/coding-help?assignment=mission&operation=prepare'):
                self.assertEqual(client.get(path).status_code, 400, path)
            # A card preview can resolve its own catalog key without changing the account selection.
            response = client.get('/api/assignments/mission/guide?operation=prepare&mission=festival')
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn('INTEREST_SCORE', str(response.json()))
            self.assertFalse(client.get('/api/assignments/mission/selection').json()['key'])
            for query in ('operation=prepare&mission=not-a-mission',
                          'operation=not-an-operation&mission=festival',
                          'operation=prepare&mission=festival&variant=BROKEN',
                          'operation=prepared-data&mission=festival&source_kind=BROKEN'):
                response = client.get('/api/assignments/mission/guide?' + query)
                self.assertIn(response.status_code, (400, 404), response.text)
            connect.assert_not_called()

    def test_mission_switch_changes_guides_downloads_and_legacy_help_together(self):
        with self.client() as (client, headers, connect):
            owner=connect.return_value.__enter__.return_value.username
            previous = None
            for key, feature, absent in (('esports', 'TEAM_SCORE', 'INTEREST_SCORE'),
                                         ('festival', 'INTEREST_SCORE', 'TEAM_SCORE')):
                self.select(client, headers, key)
                response = client.get('/api/coding-help?assignment=mission&operation=prepare&variant=CLEAN')
                self.assertEqual(response.status_code, 200, response.text)
                guide = response.json()
                self.assertEqual(guide['assignment'], 'mission')
                self.assertEqual(guide['schema'],owner)
                generated='\n'.join(file['content'] for file in guide['flow']['files'].values() if file['origin']=='generated')
                self.assertIn(owner+'.OML_MISSION_RUN',generated)
                self.assertIn(feature,generated)
                self.assertNotIn(absent,generated)
                self.assertNotIn('source_groups',guide)
                self.assertNotIn('sources',guide)
                for file, filename in (('tables', '01_tables.sql'), ('procedure', '02_procedure.sql')):
                    response = client.get('/api/assignments/mission/guide/download?file=' + file)
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertIn(filename, response.headers.get('content-disposition', ''))
                    sql = response.content.decode('utf-8-sig')
                    self.assertIn(feature, sql)
                    self.assertNotIn(absent, sql)
                    self.assertNotIn('RETURN_PCT', sql)
                    self.assertNotIn('{{', sql)
                    self.assertIn("IF USER <> '"+owner+"'",sql)
                    self.assertIn('WHENEVER SQLERROR EXIT',sql)
                    if file == 'tables':
                        order = re.findall(r'CREATE TABLE\s+('+re.escape(owner)+r'\.OML_MISSION_[A-Z]+)', sql)
                        self.assertEqual(order, [owner+'.'+name for name in ('OML_MISSION_DATA','OML_MISSION_PREPARED','OML_MISSION_PREDICT')])
                    else:
                        self.assertIn('CREATE OR REPLACE PROCEDURE '+owner+'.OML_MISSION_RUN', sql)
                        self.assertIn("model_name => '"+owner+".OML_MISSION_RAW_MODEL'",sql)
                        if previous is not None:
                            self.assertNotEqual(sql, previous)
                        previous = sql
                response = client.post('/api/assignments/mission/script/prepare', headers=headers)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIn(feature, str(response.json()))
                self.assertNotIn(absent, str(response.json()))
            connect.assert_not_called()

    def test_creative_has_no_query_help_and_requires_manual_mutation(self):
        with self.client() as (client, headers, connect):
            for operation in ('data', 'evaluate', 'predict'):
                response = client.get('/api/coding-help?assignment=creative&operation=' + operation)
                self.assertEqual(response.status_code, 404, response.text)
                response = client.post('/api/assignments/creative/script/' + operation, headers=headers)
                self.assertEqual(response.status_code, 404, response.text)
            page = client.get('/creative')
            self.assertEqual(page.status_code, 200, page.text)
            self.assertIn('data-code="initial-train"',page.text)
            self.assertNotIn('data-code="evaluate"',page.text)
            self.assertNotIn('data-execution=', page.text)
            connect.assert_not_called()

    def test_creative_manual_help_is_guarded_and_never_executes_or_generates_answers(self):
        with self.client() as (client,headers,connect):
            owner=connect.return_value.__enter__.return_value.username
            for operation,action in (('prepare','PREPARE'),('initial-train','INIT'),('retrain','RETRAIN'),('delete-model','DELETE')):
                for mode in ('RAW','CLEAN'):
                    response=client.get('/api/coding-help',params={'assignment':'creative','operation':operation,'variant':mode})
                    self.assertEqual(response.status_code,200,response.text)
                    flow=response.json()['flow']
                    self.assertEqual([stage['id'] for stage in flow['stages']],['ui','event','api','service','database','sql'])
                    first=flow['stages'][-1]['items'][0]
                    script=flow['files'][first['file_id']]['content']
                    self.assertIn(owner+'.OML_CREATIVE_RUN',script)
                    self.assertIn("('"+action+"', '"+mode+"'",script)
                    self.assertIn("CURRENT_SCHEMA",script)
                    self.assertIn('VARIABLE result REFCURSOR',script)
                    self.assertIn('PRINT executed_sql',script)
                    self.assertNotIn('CREATE OR REPLACE PROCEDURE',script)
                    self.assertNotIn('CREATE_MODEL2',script)
                    self.assertFalse(flow['stages'][4]['items'])
                    self.assertEqual(client.post('/api/assignments/creative/'+operation,json={'variant':mode},headers=headers).status_code,403)
            for operation in ('clear-training','clear-prepared','clear-prediction','drop-objects'):
                response=client.get('/api/coding-help',params={'assignment':'creative','operation':operation})
                self.assertEqual(response.status_code,200,response.text)
                flow=response.json()['flow'];first=flow['stages'][-1]['items'][0]
                script=flow['files'][first['file_id']]['content']
                self.assertIn('OML_CREATIVE_',script)
                self.assertNotIn('OML_MISSION_',script)
                self.assertNotIn('OML_BASIC_',script)
            connect.assert_not_called()

    def test_input_counts_use_only_existing_tables_and_no_row_download(self):
        state={'config':tasks.assignment('mission'),'objects':[{'object_name':'OML_MISSION_DATA','object_type':'TABLE','status':'VALID'}]}
        with patch.object(tasks,'execute',return_value=[{'rows_count':17}]) as execute:
            result=tasks.input_state(None,state)
            self.assertEqual(result,{'state':{'total_rows':17},'prediction_storage':{'rows':0}})
            execute.assert_called_once_with(None,'queries/custom_count.sql',replacements={'table':'OML_MISSION_DATA'},fetch=True)

    def test_manual_mutations_are_forbidden_before_any_database_work(self):
        with self.client() as (client, headers, connect),patch.object(tasks,'run') as run,patch.object(tasks,'load_custom') as load:
            for key in ('mission','creative'):
                for action in ('prepare','train','initial-train','retrain','delete-model','import','prediction-import'):
                    with self.subTest(assignment=key,action=action):
                        response=client.post('/api/assignments/'+key+'/'+action,json={'variant':'RAW'},headers=headers)
                        self.assertEqual(response.status_code,403,response.text)
                        self.assertIn('SQL Developer',response.json()['error'])
                response=client.post('/api/assignments/'+key+'/train/csv',
                                     files={'file':('test.csv',b'x','text/csv')},headers=headers)
                self.assertEqual(response.status_code,403,response.text)
            connect.assert_not_called();run.assert_not_called();load.assert_not_called()

    def test_selected_mission_schema_is_qualified_and_never_executes(self):
        with self.client() as (client,headers,connect):
            owner=connect.return_value.__enter__.return_value.username
            self.select(client,headers,'festival')
            for kind,name in (('training','DATA'),('prepared','PREPARED'),('prediction','PREDICT')):
                response=client.get('/api/assignments/mission/schema?kind='+kind)
                self.assertEqual(response.status_code,200,response.text)
                schema=response.json();qualified=owner+'.OML_MISSION_'+name
                self.assertEqual(schema['name'],qualified)
                self.assertIn('CREATE TABLE '+qualified,schema['sql'])
                self.assertIn("IF USER <> '"+owner+"'",schema['sql'])
                self.assertIn('INTEREST_SCORE',schema['sql'])
                self.assertNotIn('TEAM_SCORE',schema['sql'])
                self.assertNotIn('{{',schema['sql'])
            response=client.get('/api/assignments/mission/schema?mission=esports&kind=training')
            self.assertEqual(response.status_code,200,response.text)
            self.assertIn('TEAM_SCORE',response.json()['sql'])
            self.assertEqual(client.get('/api/assignments/mission/selection').json()['key'],'festival')
            self.assertEqual(client.get('/api/assignments/mission/schema?kind=invalid').status_code,400)
            self.assertEqual(client.get('/api/assignments/mission/schema?mission=absent').status_code,400)
            connect.assert_not_called()

    def test_actual_creative_schema_requires_login_and_the_issued_account(self):
        with self.client(authenticated=False) as (client,_,connect):
            self.assertEqual(client.get('/api/assignments/creative/schema').status_code,401)
            connect.assert_not_called()
        with self.client() as (client,_,connect),patch.object(tasks,'query',return_value=[{
            'column_name':'CASE_ID','data_type':'NUMBER','data_length':22,'char_length':0,'char_used':None,
            'data_precision':None,'data_scale':None,'nullable':'N','comments':'사례 식별자','data_default':None}]) as query:
            owner=connect.return_value.__enter__.return_value.username
            for kind,suffix in (('training','DATA'),('prepared','PREPARED'),('prediction','PREDICT')):
                response=client.get('/api/assignments/creative/schema?kind='+kind)
                self.assertEqual(response.status_code,200,response.text)
                schema=response.json()
                self.assertEqual(schema['name'],owner+'.OML_CREATIVE_'+suffix)
                self.assertEqual(schema['columns'][0]['type'],'NUMBER')
                self.assertNotIn('sql',schema)
                self.assertNotRegex(str(schema),r'CREATE TABLE|CREATE OR REPLACE|DBMS_DATA_MINING')
                self.assertEqual(query.call_args.kwargs,{'table_name':'OML_CREATIVE_'+suffix})
            connect.return_value.__enter__.return_value.username='WRONG_ACCOUNT';query.reset_mock()
            self.assertEqual(client.get('/api/assignments/creative/schema').status_code,400)
            query.assert_not_called()

    def test_schema_tabs_follow_table_creation_order(self):
        with self.client() as (client, _, connect):
            page = client.get('/mission')
            self.assertEqual(page.status_code, 200, page.text)
            kinds = re.findall(r'data-mission-schema-kind="([^"]+)"', page.text)
            self.assertEqual(kinds, ['training', 'prepared', 'prediction', 'procedure'])
            connect.assert_not_called()

    def test_schema_run_tab_uses_exact_selected_mission_procedure_without_database(self):
        from backend.mission_guide import procedure_sql
        catalog=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
        with self.client(authenticated=False) as (client,headers,connect):
            self.assertEqual(client.get('/api/assignments/mission/schema?kind=procedure&mission=esports').status_code,401)
            connect.assert_not_called()
        with self.client() as (client,headers,connect):
            owner=connect.return_value.__enter__.return_value.username
            for item in catalog:
                self.select(client,headers,item['key'])
                response=client.get('/api/assignments/mission/schema?kind=procedure')
                self.assertEqual(response.status_code,200,response.text)
                result=response.json()
                self.assertEqual(result['sql'],procedure_sql(item,schema=owner))
                self.assertEqual(result['object_type'],'PROCEDURE')
                self.assertEqual(result['name'],owner+'.OML_MISSION_RUN')
                self.assertEqual(result['columns'],[])
                self.assertIn('CREATE OR REPLACE PROCEDURE '+owner+'.OML_MISSION_RUN',result['sql'])
                self.assertIn("p_action = 'PREDICT'",result['sql'])
                self.assertNotIn('{{',result['sql'])
                self.assertNotIn('RETURN_PCT',result['sql'])
                download=client.get('/api/assignments/mission/guide/download?file=procedure')
                self.assertEqual(download.text,result['sql'])
            self.assertEqual(client.get('/api/assignments/mission/schema?kind=other').status_code,400)
            connect.assert_not_called()

    def test_csv_guides_preserve_raw_values_without_expanding_sql(self):
        from backend import mission_guide
        from backend.csv_import import mission_rows
        catalog = json.loads((ROOT / 'data/catalog.json').read_text(encoding='utf-8'))
        for item in catalog:
            for prediction, operation, table in ((False, 'import', 'OML_MISSION_DATA'),
                                                  (True, 'prediction-import', 'OML_MISSION_PREDICT')):
                with self.subTest(mission=item['key'], operation=operation):
                    filename = item['prediction_filename' if prediction else 'filename']
                    path = ROOT / 'data/examples' / filename
                    with path.open(encoding='utf-8-sig', newline='') as stream:
                        expected = [{key:int(value) if key=='case_id' else value or None for key,value in row.items()}
                                    for row in csv.DictReader(stream)]
                    with path.open(encoding='utf-8-sig', newline='') as stream:
                        self.assertEqual(list(mission_rows(stream,item,prediction)),expected)
                    result = mission_guide.generate(item,operation,schema='STUDENT23')
                    script = result['script']
                    self.assertEqual(len(re.findall(r'(?m)^INSERT INTO ', script)),1)
                    self.assertIn('STUDENT23.'+table,script)
                    self.assertIn(':case_id',script)
                    self.assertLess(len(script),1500)
                    self.assertIn('load_mission_csv.py',result['load_command'])
                    self.assertIn(filename,result['load_command'])
                    self.assertNotIn('--replace',result['load_command'])
                    self.assertEqual(result['procedure_sql'],'')
                    self.assertNotIn('999999',script)

    def test_basic_schema_includes_only_its_own_complete_comments(self):
        from backend.basic_dataset import table_schema
        for kind in ('training', 'prepared', 'prediction'):
            with self.subTest(kind=kind):
                result = table_schema(kind, owner='STUDENT23')
                sql, name = result['sql'], result['name']
                self.assertEqual(sql.count('COMMENT ON TABLE ' + name + ' IS '), 1)
                comments = dict(re.findall(
                    r"COMMENT ON COLUMN " + re.escape(name) + r"\.([A-Z_]+) IS '((?:''|[^'])*)';", sql))
                self.assertEqual(set(comments), {column['name'] for column in result['columns']})
                for column in result['columns']:
                    self.assertEqual(comments[column['name']].replace("''", "'"), column['description'])
                    expected = ('identifier' if column['name'] == 'CASE_ID' else
                                'feature' if column['name'] in ('RETURN_PCT','RANGE_PCT','VOLUME_CHANGE_PCT','CLOSE_PRICE','STOCK') else
                                'target' if column['name'] == 'SIGNAL' else 'metadata')
                    self.assertEqual(column['role'], expected)
                self.assertEqual(set(re.findall(r'STUDENT23\.OML_BASIC_[A-Z]+', sql)), {name})
                self.assertLess(sql.index('CREATE TABLE '), sql.index('COMMENT ON TABLE '))
                self.assertIn("'SESSION_USER') <> 'STUDENT23'", sql)
                self.assertIn('sql/table_comments.sql', result['source_paths'])

    def test_all_ten_missions_supply_matching_runnable_definitions(self):
        from backend import mission_guide
        catalog = json.loads((ROOT / 'data/catalog.json').read_text(encoding='utf-8'))
        self.assertEqual(len(catalog), 12)
        for item in catalog:
            with self.subTest(mission=item['key']):
                features = [name.upper() for name in item['columns'][1:4]]
                for kind, name in (('training', 'OML_MISSION_DATA'),
                                   ('prepared', 'OML_MISSION_PREPARED'),
                                   ('prediction', 'OML_MISSION_PREDICT')):
                    schema = mission_guide.table_sql(item, kind)
                    self.assertEqual(schema['name'], name)
                    self.assertEqual(schema['sql'].count('COMMENT ON TABLE ' + name + ' IS '), 1)
                    commented = re.findall(r'COMMENT ON COLUMN ' + name + r'\.([A-Z_]+) IS ', schema['sql'])
                    self.assertEqual(commented, [c['name'] for c in schema['columns']])
                    for column in schema['columns']:
                        expected = ('identifier' if column['name']=='CASE_ID' else 'feature' if column['name'] in features
                                    else 'target' if column['name']=='LABEL' else 'metadata')
                        self.assertEqual(column['role'], expected)
                    self.assertEqual(len([c for c in schema['columns'] if c['name'] in features]), 3)
                    self.assertIn('USER_TABLES', schema['sql'])
                    self.assertRegex(schema['sql'], r'DROP TABLE\s+' + name + r'\b')
                    self.assertRegex(schema['sql'], r'CREATE TABLE\s+' + name + r'\b')
                    self.assertLess(schema['sql'].index('DROP TABLE'), schema['sql'].index('CREATE TABLE'))
                    mentioned = set(re.findall(r'\bOML_MISSION_(?:DATA|PREPARED|PREDICT)\b', schema['sql']))
                    self.assertEqual(mentioned, {name}, 'Each reset block only drops its CREATE target')
                    self.assertNotIn('{{', schema['sql'])
                procedure = mission_guide.procedure_sql(item)
                self.assertIn('CREATE OR REPLACE PROCEDURE OML_MISSION_RUN', procedure)
                for feature in features:
                    self.assertIn(feature, procedure)
                self.assertIn("DEFAULT NULL ON CONVERSION ERROR", procedure)
                self.assertIn("SOURCE_KIND = 'TRAIN'", procedure)
                self.assertIn("FIT_YN = 'Y'", procedure)
                self.assertIn('DBMS_DATA_MINING.CREATE_MODEL2', procedure)
                self.assertNotRegex(procedure, r'\bRETURN_PCT\b|\bRANGE_PCT\b|\bSTOCK_NAME\b|\bWEEK_ENDING\b')
                self.assertNotIn("'BUY'", procedure)
                self.assertNotIn("'SELL'", procedure)
                self.assertNotIn('{{', procedure)
                for mode in ('RAW', 'CLEAN'):
                    for operation, action in (('prepare', 'PREPARE'), ('initial-train', 'INIT'),
                                              ('retrain', 'RETRAIN'),
                                              ('delete-model', 'DELETE'), ('evaluate', 'EVALUATE'),
                                              ('predict', 'PREDICT')):
                        guide = mission_guide.generate(item, operation, mode)
                        self.assertEqual(guide['assignment'], 'mission')
                        self.assertEqual(guide['procedure_sql'], procedure)
                        self.assertRegex(guide['script'], r"OML_MISSION_RUN\(\s*'" + action + r"'\s*,\s*'" + mode + r"'")
                        self.assertNotIn('{{', guide['script'])


if __name__ == '__main__':
    unittest.main()
