"""버튼별 현재 코드 원본과 관련 쿼리를 실제 파일·API 연결과 대조합니다."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend import assignment_templates, coding_help


CUSTOM_SKIP = {'preview', 'prediction-preview', 'save', 'delete', 'initialize',
               'recreate', 'confirm', 'status', 'columns','model-dictionary'}


class CodingHelpTests(unittest.TestCase):
    def describe(self, operation, assignment='basic', **options):
        # 개인 runtime 연결 설정과 독립된 공개 예제만 사용합니다.
        with patch.object(assignment_templates, 'configuration',
                          side_effect=lambda user, key: assignment_templates.assignment(key)):
            return coding_help.describe(operation, assignment=assignment,
                                        user='CODING_HELP_TEST', **options)

    def primary_paths(self, operation, assignment='basic'):
        return [s['path'] for s in self.describe(operation, assignment)['source_groups']['primary']]

    def test_visible_button_sources_have_real_keywords_lines_and_distinct_groups(self):
        checked = 0
        for assignment in ('basic',):
            for operation in coding_help.OPERATIONS:
                if assignment != 'basic' and operation in CUSTOM_SKIP:
                    continue
                with self.subTest(assignment=assignment, operation=operation):
                    item = self.describe(operation, assignment, use_yn='Y', split='TRAIN')
                    groups = item['source_groups']
                    self.assertEqual(set(groups), {'primary', 'related_sql', 'support'})
                    self.assertTrue(groups['primary'])
                    self.assertEqual(item['sources'], sum((groups[k] for k in
                                     ('primary', 'related_sql', 'support')), []))
                    identities = [(s['path'], s['keyword']) for s in item['sources']]
                    self.assertEqual(len(identities), len(set(identities)))
                    self.assertTrue(all(s['path'].endswith('.sql') for s in groups['related_sql']))
                    self.assertTrue(all(not s['path'].endswith('.sql') for s in groups['support']))
                    for source in item['sources']:
                        path = ROOT / source['path']
                        self.assertTrue(path.resolve().is_relative_to(ROOT.resolve()))
                        self.assertTrue(path.is_file(), source['path'])
                        self.assertFalse(path.is_symlink())
                        content = path.read_text(encoding='utf-8-sig')
                        self.assertEqual(source['content'], content)
                        self.assertTrue(source['role'])
                        if source['keyword']:
                            self.assertIn(source['keyword'], content)
                            self.assertIn(source['keyword'], content.splitlines()[source['line'] - 1])
                    checked += 1
        self.assertEqual(checked, len(coding_help.OPERATIONS))

    def test_current_code_primary_sources_match_compound_database_work(self):
        expected = {
            'status': ['sql/queries/objects.sql'],
            'data': ['sql/queries/training_rows.sql'],
            'preview': ['backend/validation.py'],
            'prediction-preview': ['backend/validation.py'],
            'import': ['sql/queries/delete_training.sql', 'sql/queries/insert_training.sql'],
            'initialize': ['sql/schema.sql', 'sql/prediction_table.sql', 'sql/prepared_table.sql', 'sql/classifier.sql', 'sql/table_comments.sql'],
            'recreate': ['sql/recreate_training.sql', 'sql/schema.sql', 'sql/queries/delete_training.sql',
                         'sql/queries/insert_training.sql'],
            'train': ['sql/classifier.sql'],
            'evaluate': ['sql/classifier.sql'],
            'confirm': ['backend/service.py'],
            'prediction-import': ['sql/queries/delete_prediction.sql', 'sql/queries/insert_prediction.sql'],
            'prediction-data': ['sql/queries/prediction_rows.sql'],
            'predict': ['sql/classifier.sql'],
            'columns': ['sql/queries/columns.sql'],
            'connection': ['sql/queries/objects.sql'],
            'initial-train':['sql/classifier.sql'],
            'retrain':['sql/classifier.sql'],
                        'delete-model':['sql/classifier.sql'],
            'prepare':['sql/classifier.sql'],
            'prepared-data':['sql/queries/prepared_rows.sql'],
            'model-dictionary':['sql/queries/dictionary_'+key+'.sql' for key in ('model','attributes','settings','views','xforms','object','generated_objects','generated_columns')],
        }
        for operation, paths in expected.items():
            with self.subTest(operation=operation):
                self.assertEqual(self.primary_paths(operation), paths)
        self.assertEqual(len(expected), len(coding_help.OPERATIONS))

    def test_confirmation_shows_real_python_save_without_confirming_any_model(self):
        import inspect
        from backend import service
        for mode in ('RAW','CLEAN'):
            with patch.object(service,'confirm_model',side_effect=AssertionError('Help must not confirm')), patch.object(service,'write_state',side_effect=AssertionError('Help must not write')):
                item=self.describe('confirm',variant=mode,use_yn='N',split='TEST')
            self.assertIn(f"service.confirm_model(conn, '{mode}')",item['script'])
            self.assertEqual(item['script_path'],'backend/service.py')
            self.assertIn('Python',item['code_title'])
            self.assertNotIn('자동 커밋',item['notice'])
            self.assertIn("saved['confirmed']=mode;write_state(conn,saved)",item['script'])
            self.assertIn("os.replace(temp,path)",item['script'])
            for name in ('confirm_model','model_rows','fingerprint','read_state','write_state','state_path'):
                self.assertIn(inspect.getsource(getattr(service,name)).strip(),item['script'])
            self.assertEqual([source['path'] for source in item['source_groups']['related_sql']],
                             ['sql/queries/training_rows.sql','sql/queries/prepared_fingerprint_rows.sql','sql/queries/procedure_source.sql','sql/queries/models.sql'])
        with self.assertRaises(ValueError):self.describe('confirm',variant='BOTH')

    def test_recreate_shows_drop_create_csv_values_and_separate_preparation(self):
        item=self.describe('recreate')
        code=item['script']
        table=item['owner']+'.OML_BASIC_DATA'
        self.assertLess(code.index('DROP TABLE '+table),code.index('CREATE TABLE '+table))
        self.assertLess(code.index('CREATE TABLE '+table),code.index('INSERT INTO '+table))
        self.assertIn("SESSION_USER') <> '"+item['owner']+"'",code)
        self.assertIn('WHENEVER SQLERROR EXIT',code)
        self.assertIn('VALUES',code);self.assertIn(':case_id',code);self.assertIn('COMMIT;',code)
        self.assertNotRegex(re.sub(r'--[^\n]*','',code),r'(?i)\bSELECT\b')
        self.assertNotIn('CREATE TABLE OML_BASIC_PREDICT',code)
        self.assertNotIn('CREATE TABLE OML_BASIC_PREPARED',code)
        self.assertNotIn('CREATE OR REPLACE PROCEDURE',code)
        self.assertIn('def import_data(',item['python_script'])
        self.assertIn('def load_csv(',item['python_script'])
        explanation = ' '.join(note['text'] for note in item['application']['details'])
        self.assertIn('메모리',explanation)
        self.assertIn('INSERT SELECT',explanation)
        self.assertIn('되돌릴',item['application']['caution'])
        self.assertEqual(len(item['application']['steps']),3)
        self.assertNotIn(':training_table',item['application']['verification'])
        self.assertIn('단독',explanation)

    def test_model_help_prioritizes_oracle_commands_and_direct_calls(self):
        for assignment in ('basic',):
            prefix='OML_'+assignment.upper()
            for mode in ('RAW','CLEAN'):
                for operation,action in coding_help.MODEL_ACTIONS.items():
                    item=self.describe(operation,assignment,variant=mode)
                    code='\n'.join(section['content'] for section in item['oracle_sections'])
                    self.assertTrue(item['source_groups']['primary'][0]['path'].endswith('.sql'))
                    self.assertIn(f"{prefix}_RUN('{action}', '{mode}', :result, :executed_sql)",item['direct_script'])
                    if operation=='prepare':
                        self.assertIn('INSERT INTO '+prefix+'_PREPARED',code)
                    else:self.assertIn(prefix+'_'+mode+'_MODEL',code)
                    if operation in ('train','initial-train','retrain'):
                        self.assertIn('DBMS_DATA_MINING.CREATE_MODEL2',code)
                        self.assertIn("data_query => p_sql",code)
                        self.assertNotIn('service.append_training',code)
                    if operation in ('retrain','delete-model'):
                        self.assertIn('DBMS_DATA_MINING.DROP_MODEL',code)
                    if operation in ('evaluate','predict'):
                        self.assertIn('PREDICTION(',code)

    def test_fixed_assignment_names_and_free_columns(self):
        for task in ('mission','creative'):
            cfg=assignment_templates.configuration('TEST',task)
            self.assertEqual(cfg['training_table'],'OML_'+task.upper()+'_DATA')
            with self.assertRaises(ValueError):assignment_templates.save_config('TEST',task,{**cfg,'training_table':'OML_OTHER'})

    def test_basic_prediction_is_separate_from_csv_loading(self):
        for task in ('basic',):
            item=self.describe('predict',task)
            code='\n'.join(section['content'] for section in item['oracle_sections'])
            prefix='OML_'+task.upper()
            self.assertNotIn('DELETE FROM '+prefix+'_PREDICT',code)
            self.assertNotIn('INSERT INTO '+prefix+'_PREDICT',code)
            self.assertIn('INSERT INTO '+prefix+'_PREPARED',code)
            self.assertIn('PROBABILITY',code)
            upload=self.describe('prediction-import',task)
            self.assertIn('DELETE FROM',upload['script'])
            self.assertIn('INSERT INTO',upload['script'])

    def test_preview_explains_python_only_and_has_no_irrelevant_sql(self):
        for operation in ('preview', 'prediction-preview'):
            item = self.describe(operation)
            self.assertEqual(item['source_groups']['related_sql'], [])
            primary = item['source_groups']['primary'][0]
            self.assertEqual(primary['path'], 'backend/validation.py')
            self.assertEqual(primary['keyword'], 'def parse_csv(')
            self.assertIn('DB SQL은 실행하지 않습니다', item['script'])

    def test_help_allowlists_reject_path_traversal_and_untrusted_configuration(self):
        for field in ('operation', 'assignment', 'variant', 'split', 'use_yn'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                coding_help.describe(**{'operation': 'data', field: '../../security/student.env'})
        for operation in ('save','delete'):
            with self.assertRaises(ValueError):coding_help.describe(operation)

    def test_oracle_sections_are_exact_contiguous_source_ranges(self):
        for assignment in ('basic',):
            for mode in ('RAW','CLEAN','BOTH'):
                for operation in coding_help.MODEL_ACTIONS:
                    sections=coding_help.oracle_sections(operation,mode,assignment)
                    self.assertGreater(len(sections),1,(assignment,mode,operation))
                    for section in sections:
                        lines=(ROOT/section['path']).read_text(encoding='utf-8').splitlines(keepends=True)
                        expected=''.join(lines[section['line']-1:section['end_line']])
                        self.assertIn(expected,(section['content'],section['content']+'\n'),(assignment,mode,operation,section['title']))
        item=self.describe('initial-train')
        self.assertEqual(item['script'],item['oracle_sections'][0]['content'])
        self.assertIn('선언부',item['oracle_sections'][0]['role'])
        query=next(s for s in item['oracle_sections'] if s['title'].startswith('실행 3'))
        execution=next(s for s in item['oracle_sections'] if s['title'].startswith('실행 4'))
        self.assertLess(query['line'],execution['line'])
        self.assertIn('FIT_YN',query['content'])
        body=execution['content']
        self.assertLess(body.index('validate_source;'),body.index("IF p_action = 'INIT'"))
        self.assertLess(body.index('validate_prepared;'),body.index('create_raw_model;'))
        self.assertIn('OPEN p_result FOR',body)
        self.assertTrue(body.rstrip().endswith('END IF;'))

    def test_select_excerpts_do_not_depend_on_global_q_string_order(self):
        path='sql/classifier.sql';source=(ROOT/path).read_text(encoding='utf-8')
        modified=source.replace('  -- [MODEL-LIFECYCLE]',"      p_sql := q'~\nSELECT 42 EXTRA FROM DUAL\n~';\n  -- [MODEL-LIFECYCLE]",1)
        with patch.object(coding_help.sql_trace,'source',return_value={'content':modified}):
            for operation in ('initial-train','evaluate','predict'):
                sections=coding_help.oracle_sections(operation,'CLEAN','basic')
                self.assertGreater(len(sections),1)
                query=next(s['content'] for s in sections if s['content'].lstrip().startswith("p_sql := q'~"))
                self.assertNotIn('42 EXTRA',query)
                self.assertIn("PREP_MODE = 'CLEAN'",query)
                if operation!='initial-train':self.assertIn('OML_BASIC_CLEAN_MODEL',query)
        modified=source.replace('-- [/OML-CREATE-RAW]','-- marker changed')
        with patch.object(coding_help.sql_trace,'source',return_value={'content':modified}):
            sections=coding_help.oracle_sections('initial-train','RAW','basic')
        self.assertEqual(len(sections),1)
        self.assertEqual(sections[0]['content'],modified)

    def test_application_guidance_is_short_and_specific_to_the_operation(self):
        from backend.coding_help import OPERATIONS
        for operation in OPERATIONS:
            with self.subTest(operation=operation):
                result=self.describe(operation)
                app=result['application']
                self.assertEqual(len(app['steps']),3)
                self.assertEqual(len(app['step_titles']),3)
                self.assertLessEqual(len(app['summary']),100)
                self.assertLessEqual(sum(map(len,app['steps'])),210)
                self.assertLessEqual(len(app['details']),2)
                if operation in ('preview','prediction-preview','data','status','columns','model-dictionary'):
                    self.assertEqual(app['command'],'')
                    self.assertEqual(app['verification'],'')
                    self.assertNotIn('재학습',' '.join(app['steps']))

    def test_runtime_help_separates_saved_definition_from_real_calls_without_executing(self):
        from backend import service, sql_files
        import inspect
        call_source=inspect.getsource(service.run_model).strip()
        with patch.object(service,'run_model',side_effect=AssertionError('Help must not execute')), patch.object(sql_files,'initialize',side_effect=AssertionError('Help must not compile')):
            for assignment in ('basic',):
                for operation in ('initial-train','retrain','delete-model','evaluate','predict'):
                    item=self.describe(operation,assignment,variant='CLEAN')
                    self.assertIn('DB에 저장된',item['application']['summary'])
                    self.assertIn(call_source,item['python_script'])
                    self.assertNotIn('CREATE OR REPLACE PROCEDURE',item['script'])
                    app=item['application'];instructions=' '.join([*app['steps'],*[note['text'] for note in app['details']]])
                    for word in ('저장해도 로컬','F5','VALID','USER_ERRORS','USER_SOURCE','ALTER PROCEDURE','자동 커밋'):
                        self.assertIn(word,instructions)
                    for view in ('USER_OBJECTS','USER_ERRORS','USER_SOURCE'):self.assertIn(view,app['verification'])
                    self.assertNotIn(':procedure_name',app['verification'])
                    self.assertEqual(app['command'],'.\\scripts\\db-init.ps1' if assignment=='basic' else '')
        confirmed=self.describe('confirm')
        self.assertIn('기본 예측 모델',confirmed['application']['summary'])
        self.assertIn('model-choice-',' '.join(note['text'] for note in confirmed['application']['details']))


if __name__ == '__main__':
    unittest.main()
