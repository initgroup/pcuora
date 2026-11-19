"""Coding-help flow traces actual source ranges without executing student code."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend import coding_help, mission_guide, service, sql_files
from reference.tests import test_assignment_guides as guide_fixtures
from scripts.source_files import APP_FILES, STUDENT_SCRIPTS, CONFIG

STUDENT_SOURCE_PATHS = frozenset((*APP_FILES, *('scripts/' + name for name in STUDENT_SCRIPTS), *CONFIG))

STAGES = ('ui', 'event', 'api', 'service', 'database', 'sql')
MISSION_WEB = {'connection', 'status', 'data', 'prepared-data', 'prediction-data', 'evaluate', 'predict', 'import', 'prediction-import'}
MISSION_OPERATIONS = ('setup', 'initialize', 'connection', 'status', 'data', 'preview',
                      'import', 'prepare', 'prepared-data', 'initial-train', 'train',
                      'retrain', 'delete-model', 'validate', 'evaluate',
                      'prediction-preview', 'prediction-import', 'prediction-data',
                      'columns', 'predict')


class CodingFlowTests(unittest.TestCase):
    def assert_flow(self, help_data, operation, assignment):
        flow = help_data['flow']
        self.assertEqual(flow['version'], 2)
        originals = [file for file in flow['files'].values() if file['origin']=='source']
        self.assertEqual(len(originals),len({file['path'] for file in originals}))
        for file in originals:
            self.assertIn(file['path'],STUDENT_SOURCE_PATHS)
            self.assertEqual(file['content'],(ROOT/file['path']).read_text(encoding='utf-8-sig'))
        self.assertEqual(flow['operation'], operation)
        self.assertEqual(flow['assignment'], assignment)
        self.assertEqual(tuple(stage['id'] for stage in flow['stages']), STAGES)
        self.assertIn(flow['mode'], ('web-execution', 'local-preview', 'manual-guide'))
        ids = []
        for stage in flow['stages']:
            for field in ('label', 'technology', 'summary'):
                self.assertTrue(stage[field], (operation, stage['id'], field))
            for item in stage['items']:
                ids.append(item['id'])
                self.assertNotIn('content',item,'Source content is sent once per file, never once per navigation item')
                file=flow['files'][item['file_id']]
                self.assertEqual(file['path'],item['path'])
                self.assertEqual(file['origin'],item['origin'])
                # Hydrate only this test copy for the existing exact-range checks below.
                item['content']='\n'.join(file['content'].splitlines()[item['line']-1:item['end_line']]) if item['origin']=='source' else file['content']
                for field in ('id', 'title', 'path', 'content', 'role', 'kind'):
                    self.assertTrue(item[field], (operation, stage['id'], field))
                self.assertIn(item['origin'], ('source', 'generated'))
                if item['origin'] == 'source':
                    self.assertIn(item['path'], STUDENT_SOURCE_PATHS,
                                  'Flow original must belong to the student distribution; no temporary/local sources')
                    path = (ROOT / item['path']).resolve()
                    self.assertTrue(path.is_relative_to(ROOT.resolve()), item['path'])
                    self.assertTrue(path.is_file(), item['path'])
                    self.assertFalse(path.is_symlink())
                    lines = path.read_text(encoding='utf-8-sig').splitlines()
                    self.assertIsInstance(item['line'], int)
                    self.assertIsInstance(item['end_line'], int)
                    self.assertGreaterEqual(item['line'], 1)
                    self.assertGreaterEqual(item['end_line'], item['line'])
                    self.assertLessEqual(item['end_line'], len(lines))
                    expected = '\n'.join(lines[item['line'] - 1:item['end_line']])
                    if 'focus_text' in item:
                        self.assertEqual(item['content'][item['focus_start']:item['focus_end']],item['focus_text'])
                        self.assertTrue(item['focus_text'])
                    self.assertEqual(item['content'], expected,
                                     (assignment, operation, item['path'], item['line']))
                else:
                    # Generated execution SQL is not an on-disk source excerpt.
                    self.assertIsNone(item['line'])
                    self.assertIsNone(item['end_line'])
        self.assertTrue(ids)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn(flow['initial_item'], ids)
        return {stage['id']: stage for stage in flow['stages']}

    def test_every_basic_operation_has_exact_ordered_sources_without_database_work(self):
        fixture = guide_fixtures.AssignmentGuideTests()
        with fixture.client() as (client, _, connect), \
                patch.object(service, 'run_model', side_effect=AssertionError('Help must not execute')), \
                patch.object(service, 'write_state', side_effect=AssertionError('Help must not save')), \
                patch.object(sql_files, 'initialize', side_effect=AssertionError('Help must not compile')):
            for operation in coding_help.OPERATIONS:
                for variant in ('RAW', 'CLEAN'):
                    with self.subTest(operation=operation, variant=variant):
                        response = client.get('/api/coding-help', params={
                            'operation': operation, 'assignment': 'basic', 'variant': variant,
                            'use_yn': 'Y', 'split': 'TRAIN', 'source_kind': 'TRAIN'})
                        self.assertEqual(response.status_code, 200, response.text)
                        stages = self.assert_flow(response.json(), operation, 'basic')
                        if operation in ('preview', 'prediction-preview'):
                            self.assertEqual(response.json()['flow']['mode'], 'local-preview')
                            self.assertEqual(stages['database']['items'], [])
                            self.assertEqual(stages['sql']['items'], [])
                        else:
                            self.assertEqual(response.json()['flow']['mode'], 'web-execution')
            connect.assert_not_called()

    def test_mission_paths_distinguish_guides_from_web_operations_and_preserve_selected_columns(self):
        catalog = json.loads((ROOT / 'data/catalog.json').read_text(encoding='utf-8'))
        fixture = guide_fixtures.AssignmentGuideTests()
        with fixture.client() as (client, headers, connect):
            # Every operation, both modes; all ten topics additionally exercise generated model SQL.
            for topic_index, topic in enumerate(catalog):
                fixture.select(client, headers, topic['key'])
                operations = MISSION_OPERATIONS if topic_index == 0 else ('prepare', 'initial-train', 'predict')
                for operation in operations:
                    for variant in ('RAW', 'CLEAN'):
                        with self.subTest(topic=topic['key'], operation=operation, variant=variant):
                            response = client.get('/api/coding-help', params={
                                'operation': operation, 'assignment': 'mission',
                                'variant': variant, 'source_kind': 'TRAIN'})
                            self.assertEqual(response.status_code, 200, response.text)
                            result = response.json()
                            stages = self.assert_flow(result, operation, 'mission')
                            if operation in ('preview', 'prediction-preview'):
                                self.assertEqual(stages['database']['items'], [])
                                self.assertEqual(stages['sql']['items'], [])
                            elif operation in MISSION_WEB:
                                self.assertEqual(result['flow']['mode'], 'web-execution')
                                api = '\n'.join(item['content'] for item in stages['api']['items'])
                                self.assertIn('/api/assignments/', api)
                            else:
                                self.assertEqual(result['flow']['mode'], 'manual-guide')
                                api = '\n'.join(item['content'] for item in stages['api']['items'])
                                self.assertIn('/api/coding-help', api)
                            if operation in ('prepare', 'initial-train', 'predict'):
                                generated = [item for stage in stages.values() for item in stage['items']
                                             if item['origin'] == 'generated']
                                self.assertTrue(generated)
                                sql = '\n'.join(item['content'] for item in generated)
                                for feature in topic['columns'][1:4]:
                                    self.assertIn(feature.upper(), sql)
                                self.assertIn(result['schema'] + '.OML_MISSION_', sql)
            connect.assert_not_called()

    def test_model_flow_preserves_real_declaration_and_call_ranges(self):
        for variant in ('RAW', 'CLEAN'):
            for operation in ('initial-train', 'retrain', 'delete-model',
                              'prepare', 'evaluate', 'predict'):
                with self.subTest(operation=operation, variant=variant):
                    result = coding_help.describe(operation, variant=variant, user='STUDENT_QA')
                    stages = self.assert_flow(result, operation, 'basic')
                    sql = '\n'.join(item['content'] for item in stages['sql']['items'])
                    if operation != 'prepare':
                        self.assertIn('OML_BASIC_' + variant + '_MODEL', sql)
                    if operation in ('initial-train', 'retrain'):
                        self.assertIn('DBMS_DATA_MINING.CREATE_MODEL2', sql)
                        self.assertIn('data_query => p_sql', sql)
                    if operation in ('retrain', 'delete-model'):
                        self.assertIn('DBMS_DATA_MINING.DROP_MODEL', sql)
                    if operation in ('evaluate', 'predict'):
                        self.assertIn('PREDICTION(', sql)

    def test_clicked_button_source_focus_and_model_card_event(self):
        value=coding_help.describe('evaluate',variant='BOTH',user='STUDENT_QA',trigger_id='query-models',trigger_label='TEST 평가·새로고침',page='models')
        focus=value['flow']['stages'][0]['items'][0]['focus_text']
        self.assertIn('id="query-models"',focus);self.assertIn('TEST 평가·새로고침',focus)
        value=coding_help.describe('confirm',variant='RAW',user='STUDENT_QA',page='models',trigger_label='이 모델 확정')
        self.assert_flow(value,'confirm','basic')
        self.assertIn('data-confirm',value['flow']['stages'][0]['items'][0]['content'])
        self.assertIn("document.querySelectorAll('[data-confirm]')",value['flow']['stages'][1]['items'][0]['content'])
        for page in ('', 'models', 'predictions'):
            value=coding_help.describe('confirm',variant='CLEAN',user='STUDENT_QA',page=page)
            self.assert_flow(value,'confirm','basic')
            self.assertEqual(value['flow']['stages'][0]['items'][0]['path'],'templates/pages/models.html')
            self.assertIn("document.querySelectorAll('[data-confirm]')",value['flow']['stages'][1]['items'][0]['content'])
        from backend.basic_lifecycle import describe as lifecycle_help
        value=lifecycle_help('unconfirm','STUDENT_QA')
        self.assertEqual(value['flow']['stages'][0]['items'][0]['path'],'templates/pages/models.html')

    def test_mission_header_refresh_does_not_claim_link_save(self):
        topic=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))[0]
        result=mission_guide.generate(topic,'connection',schema='STUDENT_QA',trigger_id='refresh',trigger_label='새로고침',page='mission')
        stages=self.assert_flow(result,'connection','mission')
        self.assertEqual(stages['ui']['items'][0]['path'],'templates/index.html')
        self.assertIn('id="refresh"',stages['ui']['items'][0]['focus_text'])
        api=' '.join(item['content'] for item in stages['api']['items'])
        self.assertIn('assignment_status',api);self.assertNotIn('link_assignment',api)
        self.assertFalse(any('write_state' in item['title'] for item in stages['service']['items']))

    def test_file_reads_are_deduplicated_within_one_flow_and_generated_sources_stay_separate(self):
        from backend.coding_flow import basic_flow
        from backend import sql_trace
        result=coding_help.describe('retrain',variant='RAW',user='STUDENT_QA')
        with patch.object(sql_trace,'source',wraps=sql_trace.source) as read:
            flow=basic_flow(result)
        paths=[call.args[0] for call in read.call_args_list]
        self.assertEqual(len(paths),len(set(paths)))
        items=[item for stage in flow['stages'] for item in stage['items']]
        classifier=[item for item in items if item['path']=='sql/classifier.sql' and item['origin']=='source']
        self.assertGreater(len(classifier),3)
        self.assertEqual(len({item['file_id'] for item in classifier}),1)
        self.assertTrue(all(flow['files'][item['file_id']]['origin']==item['origin'] for item in items))

    def test_help_authorization_and_creative_boundary_stay_intact(self):
        fixture = guide_fixtures.AssignmentGuideTests()
        with fixture.client(authenticated=False) as (client, _, connect):
            self.assertEqual(client.get('/api/coding-help?operation=data').status_code, 401)
            connect.assert_not_called()
        with fixture.client() as (client, _, connect):
            for operation in ('data', 'predict'):
                response = client.get('/api/coding-help', params={'operation': operation, 'assignment': 'creative'})
                self.assertEqual(response.status_code, 404)
            for query in ({'operation': '../../security/student.env'},
                          {'assignment': '../../security/student.env'},
                          {'variant': '../../security/student.env'}):
                response = client.get('/api/coding-help', params={'operation': 'data', **query})
                self.assertIn(response.status_code, (400, 404, 422))
            connect.assert_not_called()


if __name__ == '__main__':
    unittest.main()
