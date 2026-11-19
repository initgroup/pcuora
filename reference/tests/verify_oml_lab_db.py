"""배포 DDL을 격리 이름으로 신규 생성하고 실제 Oracle의 모델 수명주기를 검증합니다."""
import json
import re
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend import assignment_templates as tasks, service, sql_trace, sql_files
from backend.validation import parse_csv
from backend.db import connection, safe_error
from backend.sql_files import query, read_sql
from reference.tests.verify_mission_guide_db import production_snapshot


def verify():
    cleanup = re.split(r'^/\s*$', (ROOT / 'reference/tests/sql/oml_lab_check.sql').read_text(encoding='utf-8'), flags=re.M)
    reports = []
    with connection() as conn, tempfile.TemporaryDirectory(dir=ROOT / 'runtime') as temporary:
        def check(index, cfg, **binds):
            if 'mode' in binds:binds['selected_mode']=binds.pop('mode')
            names = {'procedure':cfg['procedure_name'], 'prediction':cfg['prediction_table'],
                     'prepared':cfg['prepared_table'], 'training':cfg['training_table'],
                     'trigger':cfg['prepared_table'].removesuffix('_PREPARED') + '_PREP_FAIL'}
            assert all(re.fullmatch(r'OML_QA_LAB_[BMC]_[A-Z_]+', value) for value in names.values())
            statement = cleanup[index].strip()
            for key, value in names.items():
                statement = statement.replace('{{' + key + '}}', value)
            plain = re.sub(r'--[^\n]*', '', statement).strip()
            if not plain.upper().startswith(('BEGIN', 'CREATE OR REPLACE TRIGGER')):
                statement = statement.rstrip(';')
            with conn.cursor() as cursor:
                cursor.execute(statement, binds)
                if cursor.description:
                    columns = [c[0].lower() for c in cursor.description]
                    return [dict(zip(columns, row)) for row in cursor]
                return []
        with conn.cursor() as cursor:
            cursor.execute(cleanup[0].strip().rstrip(';'))
            assert not cursor.fetchall(), 'QA objects already exist; inspect before rerunning'
        production_before = production_snapshot(conn)
        before = service.get_data(conn)
        before_models = query(conn, 'models.sql')
        for task in ('basic', 'mission', 'creative'):
            prefix = 'OML_QA_LAB_' + task[0].upper()
            original = 'OML_BASIC'
            cfg = {'title': task, 'route': '/' + task, 'training_table': prefix + '_DATA',
                   'prediction_table': prefix + '_PREDICT', 'prepared_table': prefix + '_PREPARED',
                   'procedure_name': prefix + '_RUN'}
            # 창의는 특성·타깃 이름을 실제로 바꿔 Python에 고정 컬럼 의존이 없는지 확인합니다.
            rename = {'RETURN_PCT':'FEATURE_ONE','STOCK':'CATEGORY','SIGNAL':'OUTCOME'} if task == 'creative' else {}
            def transform(source):
                source = source.replace(original + '_', prefix + '_')
                for old, new in rename.items():
                    source = re.sub(r'\b' + old + r'\b', new, source)
                if task == 'creative':source=source.replace("'BUY'", "'CLASS_A'").replace("'SELL'", "'CLASS_B'")
                return source
            try:
                # The stock source below is a private contract fixture for all three runtime adapters.
                # Mission learner SQL is generated from the selected catalog entry and verified separately.
                # Creative learner SQL is intentionally not supplied by this fixture.
                files = ['schema.sql', 'prediction_table.sql', 'prepared_table.sql', 'classifier.sql', 'table_comments.sql']
                for name in files:
                    source = transform(read_sql(name))
                    separator = r'^/\s*$'
                    for block in re.split(separator, source, flags=re.M):
                        block = block.strip()
                        plain = re.sub(r'--[^\n]*', '', block).strip().upper()
                        if not plain: continue
                        with conn.cursor() as cursor:
                            cursor.execute(block if plain.startswith('CREATE OR REPLACE PROCEDURE') else block.rstrip(';'))
                assert not query(conn, 'procedure_errors.sql', procedure_name=cfg['procedure_name'])
                with patch.object(tasks, 'configuration', return_value=cfg), patch.object(service, 'state_path', return_value=Path(temporary) / (task + '.json')):
                    def payload(filename):
                        raw = (ROOT / 'data' / filename).read_text(encoding='utf-8-sig')
                        header, rest = raw.split('\n', 1)
                        header = ','.join(rename.get(n.upper(), n.upper()) for n in header.split(','))
                        payload=tasks.csv_payload((header + '\n' + rest).encode())[0]
                        if task=='creative':
                            values=json.loads(payload)
                            for row in values:
                                if row.get('OUTCOME') in ('BUY','SELL'):row['OUTCOME']={'BUY':'CLASS_A','SELL':'CLASS_B'}[row['OUTCOME']]
                            payload=json.dumps(values)
                        return payload
                    def run_lab(action, payload=None, *, mode='RAW', source_kind='ALL'):
                        # Mutations represent SQL Developer work, not the restricted web adapter.
                        # The exact QA configuration and cleanup allowlist above remain in force.
                        assert re.fullmatch(r'OML_QA_LAB_[BMC]_RUN', cfg['procedure_name'])
                        if action in ('import','prediction-import'):
                            tasks.load_custom(conn,cfg,payload,prediction=action=='prediction-import')
                            result={'rows':[]}
                        elif action in ('prepare','initial-train','retrain','append-train','delete-model'):
                            direct={'prepare':'PREPARE','initial-train':'INIT','retrain':'RETRAIN',
                                    'append-train':'ADD_TRAIN','delete-model':'DELETE'}[action]
                            result={'rows':service.run_model(conn,direct,mode,procedure=cfg['procedure_name'])}
                        else:
                            return tasks.run(conn,task,action,mode=mode,source_kind=source_kind)
                        # The learner explicitly connects externally completed objects/models.
                        tasks.link_external(conn,task)
                        return result

                    train = payload('classification.csv')
                    run_lab('import', train)
                    assert tasks.readiness(conn, task)['ready']
                    schemas={}
                    for kind,field in (('training','training_table'),('prepared','prepared_table'),('prediction','prediction_table')):
                        metadata=tasks.table_schema(conn,task,kind)
                        assert metadata['name']==conn.username.upper()+'.'+cfg[field]
                        assert 'sql' not in metadata
                        schemas[kind]={column['name']:column for column in metadata['columns']}
                        assert schemas[kind]['CASE_ID']['type']=='NUMBER'
                        assert schemas[kind]['CASE_ID']['description'], 'Oracle column comment was not returned'
                    feature=rename.get('RETURN_PCT','RETURN_PCT')
                    assert schemas['training'][feature]['type'].startswith('VARCHAR2(100 ')
                    assert schemas['prepared'][feature]['type']=='NUMBER'
                    assert schemas['prediction'][feature]['type'].startswith('VARCHAR2(100 ')
                    assert schemas['prepared']['FIT_YN']['nullable']=='필수'
                    assert 'SYSTIMESTAMP' in schemas['prepared']['PREPARED_AT']['rules'].upper()
                    assert schemas['prepared']['PREPARED_AT']['type'].startswith('TIMESTAMP')
                    def expect_failure(action, mode='RAW'):
                        try: run_lab(action, mode=mode)
                        except Exception: return
                        raise AssertionError(action + ' unexpectedly succeeded for ' + mode)
                    object_args = {f:cfg[f] for f in ('training_table','prediction_table','prepared_table','procedure_name')}
                    objects = query(conn, 'objects.sql', **object_args)
                    table_ids = {r['object_name']:r['object_id'] for r in objects if r['object_type'] == 'TABLE'}
                    assert len(table_ids) == 3
                    original_rows = run_lab('data')['rows']
                    expect_failure('initial-train')
                    run_lab('prepare', mode='RAW')
                    raw_prepared = check(7, cfg, mode='RAW')
                    assert len(raw_prepared) == 720
                    assert sum(r['fit_yn'] == 'Y' for r in raw_prepared) == 330
                    assert all(r['fit_yn'] == 'N' for r in raw_prepared if r['source_kind'] == 'TEST')
                    assert run_lab('data')['rows'] == original_rows, 'PREPARE changed source rows'
                    # 원본 TRAIN이 남아 있어도 FIT_YN=N인 준비행은 학습에 쓸 수 없습니다.
                    check(6, cfg);conn.commit()
                    expect_failure('initial-train')
                    for mode in ('RAW','CLEAN'):
                        run_lab('prepare', mode=mode)
                        if mode == 'CLEAN':
                            assert next(m for m in tasks.model_state(conn, task) if m['variant']=='RAW')['is_current']
                            clean_rows = {(r['source_kind'],r['case_id']):r for r in check(7, cfg, mode='CLEAN')}
                            feature = rename.get('RETURN_PCT','RETURN_PCT').lower()
                            outliers = [r for r in raw_prepared if r[feature] == 999999]
                            assert outliers and all(clean_rows[(r['source_kind'],r['case_id'])][feature] is None for r in outliers), 'CLEAN outlier correction was not materialized'
                        sql_trace.begin()
                        run_lab('initial-train', mode=mode)
                        train_sql = next(r['runtime_sql'] for r in reversed(sql_trace.records()) if r.get('action') == 'INIT')
                        assert cfg['prepared_table'] in train_sql and "FIT_YN = 'Y'" in train_sql
                        assert 'TO_NUMBER' not in train_sql and not re.search(r'\bCASE\b',train_sql), 'Training query contains preprocessing business logic'
                        try: run_lab('initial-train', mode=mode)
                        except Exception as error: assert 'ORA-20020' in str(error)
                        else: raise AssertionError('INIT overwrote a model')
                        score = run_lab('evaluate', mode=mode)['rows']
                        assert sum(r['n'] for r in score) == 360
                    run_lab('prepare', mode='RAW')
                    assert all(m['is_current'] for m in tasks.model_state(conn, task)), 'Identical prepared values invalidated models'
                    run_lab('prediction-import', payload('prediction.csv'))
                    first = run_lab('predict', mode='RAW')
                    second = run_lab('predict', mode='CLEAN')
                    assert len(first['rows']) == len(second['rows']) == 30
                    assert first['input_fingerprint'] == second['input_fingerprint']
                    assert all({'case_id','predicted','probability'}.issubset(r) for r in first['rows'])
                    assert all(m['is_current'] for m in tasks.model_state(conn, task)), 'Prediction preparation changed training freshness'
                    snapshots = {mode:check(7, cfg, mode=mode) for mode in ('RAW','CLEAN')}
                    check(8, cfg)
                    try:
                        try: run_lab('prepare', mode='RAW')
                        except Exception as error: assert 'ORA-20991' in str(error), 'Injected PREPARE failure was not reached'
                        else: raise AssertionError('Injected PREPARE failure succeeded')
                    finally: check(9, cfg)
                    assert snapshots == {mode:check(7, cfg, mode=mode) for mode in ('RAW','CLEAN')}, 'Failed PREPARE did not restore prior rows'
                    assert run_lab('data')['rows'] == original_rows
                    # SQL Developer와 같은 INSERT·VALIDATE·COMMIT 후 별도 학습 호출.
                    addition = dict(json.loads(train)[0]);addition['CASE_ID'] = '99990001'
                    tasks.load_custom(conn, cfg, json.dumps([addition]), append=True, mode='RAW')
                    assert not any(m['is_current'] for m in tasks.model_state(conn, task)), 'External data change was not detected'
                    try: run_lab('predict', mode='RAW')
                    except ValueError: pass
                    else: raise AssertionError('Stale prediction allowed')
                    assert not tasks.preparation_status(conn,task)['RAW']['ready'], 'Changed source reused a preparation stamp'
                    run_lab('prepare', mode='RAW')
                    run_lab('append-train', mode='RAW')
                    run_lab('prepare', mode='CLEAN')
                    run_lab('retrain', mode='CLEAN')
                    assert sum(r['n'] for r in run_lab('evaluate', mode='RAW')['rows']) == 360
                    run_lab('delete-model', mode='RAW')
                    assert run_lab('predict', mode='CLEAN')['rows'], 'Other model affected'
                    run_lab('initial-train', mode='RAW')
                    after_objects = query(conn, 'objects.sql', **object_args)
                    assert table_ids == {r['object_name']:r['object_id'] for r in after_objects if r['object_type']=='TABLE'}
                    assert len(run_lab('data')['rows']) == 721
                    if task=='basic':
                        # 원본을 DROP한 뒤에도 메모리에 확보한 CSV로 실제 적재되는지 확인합니다.
                        # 배포 SQL은 QA 이름으로만 치환하며 QA DROP에는 PURGE를 붙여 잔여 휴지통도 남기지 않습니다.
                        values=parse_csv((ROOT/'data/classification.csv').read_bytes())
                        original_read=sql_files.read_sql;original_query=sql_files.query
                        def imported_sql(name):
                            source=transform(original_read(name))
                            if name=='recreate_training.sql':source=source.replace('DROP TABLE '+cfg['training_table'],'DROP TABLE '+cfg['training_table']+' PURGE')
                            return source
                        def imported_query(connection,name,**binds):
                            return original_query(connection,name,**{k:transform(v) if isinstance(v,str) else v for k,v in binds.items()})
                        basic_names={field:cfg[field] for field in ('training_table','prepared_table','prediction_table','procedure_name')}
                        with patch.object(sql_files,'read_sql',side_effect=imported_sql),patch.object(sql_files,'query',side_effect=imported_query),patch.object(service,'BASIC',basic_names),patch.object(service,'state_path',return_value=Path(temporary)/'csv-import.json'):
                            source_id=next(r['object_id'] for r in after_objects if r['object_name']==cfg['training_table'])
                            prediction_before=query(conn,'prediction_rows.sql')
                            prepared_before={mode:check(7,cfg,mode=mode) for mode in ('RAW','CLEAN')}
                            service.write_state(conn,{'preparations':{'RAW':{'source':'before'}},'models':{'RAW':{'fingerprint':'before'}},'confirmed':'RAW'})
                            sql_files.execute_file(conn,'recreate_training.sql')
                            service.invalidate_training_state(conn)
                            sql_files.initialize(conn)
                            assert service.get_data(conn)==[], 'New source table was not empty before CSV reload'
                            service.load_csv(conn,values)
                            actual=service.get_data(conn)
                            assert len(actual)==len(values)==720
                            assert all((row[k] if row[k] is not None else '')==value[k] for row,value in zip(actual,values) for k in value), 'Reloaded rows differ from uploaded CSV'
                            recreated=query(conn,'objects.sql',**basic_names)
                            new_id=next(r['object_id'] for r in recreated if r['object_name']==cfg['training_table'])
                            assert new_id!=source_id
                            assert all(r['object_id']==table_ids[r['object_name']] for r in recreated if r['object_type']=='TABLE' and r['object_name']!=cfg['training_table'])
                            assert query(conn,'prediction_rows.sql')==prediction_before
                            assert all(check(7,cfg,mode=mode)==prepared_before[mode] for mode in ('RAW','CLEAN'))
                            saved=service.read_state(conn)
                            assert not saved.get('preparations') and not saved['models'] and saved['confirmed'] is None
                            # 일반 교체 INSERT 실패는 이전 720행을 복원합니다.
                            try:service.load_csv(conn,[values[0],values[0]])
                            except Exception:pass
                            else:raise AssertionError('Duplicate CSV keys unexpectedly inserted')
                            assert service.get_data(conn)==actual
                            # 재생성 INSERT 실패는 새 빈 테이블로 롤백되며 DROP 전 행은 돌아오지 않습니다.
                            sql_files.execute_file(conn,'recreate_training.sql');service.invalidate_training_state(conn);sql_files.initialize(conn)
                            try:service.load_csv(conn,[values[0],values[0]])
                            except Exception:pass
                            else:raise AssertionError('Duplicate keys unexpectedly inserted after recreate')
                            assert service.get_data(conn)==[]
                            recovery_id=next(r['object_id'] for r in query(conn,'objects.sql',**basic_names) if r['object_name']==cfg['training_table'])
                            service.load_csv(conn,values)
                            assert service.get_data(conn)==actual
                            assert next(r['object_id'] for r in query(conn,'objects.sql',**basic_names) if r['object_name']==cfg['training_table'])==recovery_id
                            assert query(conn,'prediction_rows.sql')==prediction_before
                            assert all(check(7,cfg,mode=mode)==prepared_before[mode] for mode in ('RAW','CLEAN'))
                    reports.append({'task':task,'fresh_ddl':True,'initial_rejects_overwrite':True,'test_rows':360,
                                    'prediction_rows':30,'free_columns':rename,'stale_prediction_blocked':True,
                                    'add_retrain_delete':True,'direct_sql_mutations_and_external_link':True,'actual_schema_metadata':True,'table_ids_preserved':True,'three_tables':True,
                                    'prepare_required':True,'fit_yn_exclusion_enforced':True,'prepare_failure_rollback':True,
                                    'source_rows_preserved':True,'materialized_clean_values':True,
                                    'model_query_has_no_preprocessing_logic':True,'mode_preparation_and_prediction_isolation':True})
            finally:
                with conn.cursor() as cursor:
                    for mode in ('RAW','CLEAN'):
                        try: cursor.execute(cleanup[4].strip(), model_name=prefix+'_'+mode+'_MODEL')
                        except Exception as error:
                            if not any(code in str(error) for code in ('ORA-40284','ORA-40102')): raise
                    for index in (9,1,2,5,3):
                        try: check(index, cfg)
                        except Exception as error:
                            if not any(code in str(error) for code in ('ORA-00942','ORA-04043','ORA-04080')): raise
        assert service.get_data(conn) == before
        assert query(conn, 'models.sql') == before_models
        assert production_snapshot(conn) == production_before, 'Production schema objects, models or task rows changed'
        with conn.cursor() as cursor:
            cursor.execute(cleanup[0].strip().rstrip(';'))
            assert not cursor.fetchall(), 'QA cleanup failed'
    result = {'ok':True,'actual_models_and_rows_preserved':True,'qa_objects_removed':True,'checks':reports}
    (ROOT / 'runtime/oml-lab-db-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    try: verify()
    except Exception as error:
        print(str(error) if isinstance(error, AssertionError) else safe_error(error), file=sys.stderr)
        raise SystemExit(1)
