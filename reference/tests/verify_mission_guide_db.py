"""선택 미션 10종의 제공 SQL을 실제 Oracle의 전용 QA 객체에서만 검증합니다."""
import argparse
import csv
import hashlib
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import oracledb
from backend import mission_guide
from backend.db import connection, safe_error, student_settings
from reference.tests.verify_sql_provision_db import statements

PREFIX = 'OML_QA_LAB_G_'
TABLES = tuple(PREFIX + suffix for suffix in ('DATA', 'PREPARED', 'PREDICT'))
PROCEDURE = PREFIX + 'RUN'
MODELS = tuple(PREFIX + mode + '_MODEL' for mode in ('RAW', 'CLEAN'))
ALLOWED = frozenset((*TABLES, PROCEDURE, *MODELS))
SCHEMA = ''
LIMIT = None
REPORT = {'ok': False, 'checks': [], 'started_at': datetime.now(timezone.utc).isoformat()}


def read(conn, sql, **binds):
    with conn.cursor() as cursor:
        cursor.execute(sql, binds)
        return cursor.fetchall()


def transform(source):
    source = source.replace('OML_MISSION_', PREFIX)
    source = re.sub(r'^\s*WHENEVER\s+SQLERROR[^\n]*\n', '', source, flags=re.M | re.I)
    identifiers = set(re.findall(r'\bOML_[A-Z0-9_]+', source))
    assert identifiers <= ALLOWED, 'SQL references non-allowlisted names'
    # Test tables must not leave recycle-bin objects; production scripts do not add PURGE.
    for table in TABLES:
        source = re.sub(r"'DROP TABLE ((?:[A-Z][A-Z0-9_$#]*\.)?" + table + r")'",
                        lambda match: "'DROP TABLE " + match.group(1) + " PURGE'", source)
    return source


def execute_script(conn, source):
    source = transform(source)
    for statement in statements(source):
        plain = re.sub(r'--[^\n]*', '', statement).strip().upper()
        assert plain.startswith(('ALTER SESSION', 'DECLARE', 'CREATE TABLE',
                                 'CREATE OR REPLACE PROCEDURE', 'COMMENT ON', 'BEGIN', 'SELECT'))
        with conn.cursor() as cursor:
            cursor.execute(statement)
            if cursor.description:
                cursor.fetchall()


def production_snapshot(conn):
    objects = read(conn, "SELECT OBJECT_NAME, OBJECT_TYPE, OBJECT_ID, STATUS FROM USER_OBJECTS WHERE OBJECT_TYPE IN ('TABLE','PROCEDURE','MINING MODEL') ORDER BY OBJECT_NAME, OBJECT_TYPE")
    objects = [row for row in objects if not row[0].startswith(PREFIX)]
    hashes = {}
    for task in ('BASIC', 'MISSION', 'CREATIVE'):
        for suffix in ('DATA', 'PREPARED', 'PREDICT'):
            table = 'OML_' + task + '_' + suffix
            if not read(conn, 'SELECT TABLE_NAME FROM USER_TABLES WHERE TABLE_NAME=:name', name=table):
                continue
            columns = read(conn, 'SELECT COLUMN_NAME FROM USER_TAB_COLUMNS WHERE TABLE_NAME=:name ORDER BY COLUMN_ID', name=table)
            order = 'PREP_MODE, SOURCE_KIND, CASE_ID' if suffix == 'PREPARED' else 'CASE_ID'
            rows = read(conn, 'SELECT * FROM ' + table + ' ORDER BY ' + order)
            hashes[table] = {'rows': len(rows), 'sha256': hashlib.sha256(repr((columns, rows)).encode('utf-8')).hexdigest()}
    return {'objects': objects, 'tables': hashes, 'models': read(conn, 'SELECT MODEL_NAME, MINING_FUNCTION, ALGORITHM FROM USER_MINING_MODELS ORDER BY MODEL_NAME')}


def qa_objects(conn):
    return [row for row in read(conn, 'SELECT OBJECT_NAME, OBJECT_TYPE FROM USER_OBJECTS') if row[0].startswith(PREFIX)]


def cleanup(conn):
    # Every destructive target is an exact, fixed allowlisted QA identifier.
    with conn.cursor() as cursor:
        for model in MODELS:
            assert model in ALLOWED and model.startswith(PREFIX)
            if read(conn, 'SELECT MODEL_NAME FROM USER_MINING_MODELS WHERE MODEL_NAME=:name', name=model):
                cursor.execute("BEGIN DBMS_DATA_MINING.DROP_MODEL('" + model + "'); END;")
        if read(conn, "SELECT OBJECT_NAME FROM USER_OBJECTS WHERE OBJECT_NAME=:name AND OBJECT_TYPE='PROCEDURE'", name=PROCEDURE):
            cursor.execute('DROP PROCEDURE ' + PROCEDURE)
        for table in TABLES:
            assert table in ALLOWED and table.startswith(PREFIX)
            if read(conn, 'SELECT TABLE_NAME FROM USER_TABLES WHERE TABLE_NAME=:name', name=table):
                cursor.execute('DROP TABLE ' + table + ' PURGE')


def run(conn, action, mode):
    with conn.cursor() as cursor:
        result = cursor.var(oracledb.DB_TYPE_CURSOR)
        sql = cursor.var(oracledb.DB_TYPE_CLOB)
        cursor.execute('BEGIN ' + (SCHEMA + '.' if SCHEMA else '') + PROCEDURE + '(:action,:mode,:result,:sql); END;',
                       action=action, mode=mode, result=result, sql=sql)
        returned = result.getvalue()
        try:
            rows = returned.fetchall() if returned else []
            names = [field[0] for field in returned.description] if returned and returned.description else []
        finally:
            if returned:
                returned.close()
        clob = sql.getvalue()
        return names, rows, clob.read() if hasattr(clob, 'read') else clob


def expected_error(conn, action, mode, code):
    try:
        run(conn, action, mode)
    except oracledb.DatabaseError as error:
        assert 'ORA-' + code in str(error), safe_error(error)
        return
    raise AssertionError(action + ' unexpectedly succeeded')


def raw_rows(conn, table, fields):
    assert table in TABLES
    return read(conn, 'SELECT ' + ', '.join(name.upper() for name in fields) + ' FROM ' + table + ' ORDER BY CASE_ID')


def verify_csv(conn, item, prediction=False):
    filename = item['prediction_filename' if prediction else 'filename']
    with (ROOT / 'data/examples' / filename).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        expected = [tuple(int(row[name]) if name == 'case_id' else row[name] or None for name in fields) for row in reader]
    actual = raw_rows(conn, PREFIX + ('PREDICT' if prediction else 'DATA'), fields)
    assert actual == sorted(expected), 'CSV literal insertion changed original values'
    return actual


def verify():
    global SCHEMA
    catalog = json.loads((ROOT / 'data/catalog.json').read_text(encoding='utf-8'))
    if LIMIT is not None:
        assert LIMIT > 0
        catalog = catalog[:LIMIT]
    with connection(student_settings()) as conn:
        if SCHEMA:
            SCHEMA = read(conn, "SELECT USER FROM DUAL")[0][0]
            assert re.fullmatch(r'[A-Z][A-Z0-9_$#]{0,29}', SCHEMA)
        REPORT['qualified_schema'] = SCHEMA
        assert not qa_objects(conn), 'QA namespace already contains objects; inspect before running'
        before = production_snapshot(conn)
        try:
            if SCHEMA:
                # The invalid-account script must fail in its first PL/SQL block before CREATE.
                try:
                    execute_script(conn, mission_guide.table_sql(catalog[0], schema='QA_WRONG_USER')['sql'])
                except oracledb.DatabaseError as error:
                    assert 'ORA-20030' in str(error), safe_error(error)
                else:
                    raise AssertionError('Wrong-account guard unexpectedly accepted the connection')
                assert not qa_objects(conn)
                REPORT['wrong_account_script_rejected'] = True
            for item in catalog:
                assert not qa_objects(conn)
                check = {'mission': item['key'], 'modes': {}}
                try:
                    for kind in mission_guide.KINDS:
                        execute_script(conn, mission_guide.table_sql(item, kind, schema=SCHEMA)['sql'])
                    execute_script(conn, mission_guide.procedure_sql(item, schema=SCHEMA))
                    errors = read(conn, 'SELECT LINE, POSITION, TEXT FROM USER_ERRORS WHERE NAME=:name ORDER BY SEQUENCE', name=PROCEDURE)
                    assert not errors, 'Procedure compilation errors: ' + repr(errors)
                    if SCHEMA:
                        # A compiled invoker-rights procedure must also reject a different CURRENT_SCHEMA.
                        with conn.cursor() as cursor:
                            cursor.execute('ALTER SESSION SET CURRENT_SCHEMA = SYS')
                        try:
                            expected_error(conn, 'VALIDATE', 'RAW', '20030')
                        finally:
                            with conn.cursor() as cursor:
                                cursor.execute('ALTER SESSION SET CURRENT_SCHEMA = ' + SCHEMA)
                        check['wrong_current_schema_call_rejected'] = True
                    check['three_tables_created'] = True
                    check['procedure_valid'] = True
                    for prediction in (False, True):
                        execute_script(conn, mission_guide.csv_load_sql(item, prediction, schema=SCHEMA))
                    original = verify_csv(conn, item)
                    prediction_original = verify_csv(conn, item, True)
                    check['raw_csv_rows'] = len(original)
                    check['prediction_csv_rows'] = len(prediction_original)
                    run(conn, 'VALIDATE', 'RAW')
                    for mode in ('RAW', 'CLEAN'):
                        names, prepared, _ = run(conn, 'PREPARE', mode)
                        assert len(prepared) == 1500
                        rows = [dict(zip(names, row)) for row in prepared]
                        assert sum(row['SOURCE_KIND'] == 'TEST' for row in rows) == 300
                        assert all(row['FIT_YN'] == 'N' for row in rows if row['SOURCE_KIND'] == 'TEST')
                        fit = sum(row['FIT_YN'] == 'Y' for row in rows)
                        assert fit == 1200 if mode == 'RAW' else 0 < fit < 1200
                        if mode == 'CLEAN':
                            feature_names = [field['name'].upper() for field in item['layout'] if '설명변수' in field['role']]
                            assert all(all(row[name] is None or 0 <= row[name] <= 100 for name in feature_names) for row in rows)
                            assert all(all(row[name] is not None for name in feature_names) for row in rows if row['FIT_YN'] == 'Y')
                        _, _, train_sql = run(conn, 'INIT', mode)
                        assert PREFIX + 'PREPARED' in train_sql and "FIT_YN = 'Y'" in train_sql
                        assert 'TO_NUMBER' not in train_sql
                        expected_error(conn, 'INIT', mode, '20020')
                        score_names, scores, _ = run(conn, 'EVALUATE', mode)
                        assert score_names == ['VARIANT', 'ACTUAL', 'PREDICTED', 'N']
                        assert sum(row[3] for row in scores) == 300
                        pred_names, predictions, _ = run(conn, 'PREDICT', mode)
                        assert pred_names == ['CASE_ID', 'PREDICTED', 'PROBABILITY']
                        assert len(predictions) == 30
                        assert all(row[1] is not None and row[2] is not None for row in predictions)
                        run(conn, 'RETRAIN', mode)
                        run(conn, 'ADD_TRAIN', mode)
                        _, second_scores, _ = run(conn, 'EVALUATE', mode)
                        assert sum(row[3] for row in second_scores) == 300
                        # Deleting one model must preserve the other, all raw rows, and all tables.
                        run(conn, 'DELETE', mode)
                        expected_error(conn, 'PREDICT', mode, '20021')
                        assert raw_rows(conn, PREFIX + 'DATA', item['columns']) == original
                        assert verify_csv(conn, item, True) == prediction_original
                        check['modes'][mode] = {'prepared_rows': len(prepared), 'fit_rows': fit,
                                               'test_rows': 300, 'prediction_rows': len(predictions),
                                               'initial_overwrite_rejected': True, 'retrain': True,
                                               'add_train': True, 'delete': True, 'raw_rows_preserved': True}
                    REPORT['checks'].append(check)
                    print('Mission guide checked: ' + item['key'], flush=True)
                finally:
                    cleanup(conn)
                assert not qa_objects(conn), 'QA objects remained after mission'
        finally:
            cleanup(conn)
            REPORT['production_objects_and_rows_preserved'] = production_snapshot(conn) == before
            REPORT['qa_objects_removed'] = not qa_objects(conn)
            assert REPORT['production_objects_and_rows_preserved'], 'Production objects or rows changed'
            assert REPORT['qa_objects_removed'], 'QA cleanup failed'
    REPORT['ok'] = True
    REPORT['source_hashes'] = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
                               ('backend/mission_guide.py', 'sql/custom/mission/guide_procedure.sql')}
    REPORT['finished_at'] = datetime.now(timezone.utc).isoformat()
    (ROOT / 'runtime/mission-guide-verification.json').write_text(json.dumps(REPORT, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 'missions': len(REPORT['checks']), 'workflows': sum(len(check['modes']) for check in REPORT['checks']),
                      'production_preserved': True, 'qa_objects_removed': True}), flush=True)


if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--qualified', action='store_true', help='Use the actual issued schema for all generated SQL references.')
        parser.add_argument('--limit', type=int, help='Verify only this many catalog missions; default verifies all 10.')
        args = parser.parse_args()
        SCHEMA = 'ISSUED_SCHEMA' if args.qualified else ''
        LIMIT = args.limit
        verify()
    except Exception as error:
        REPORT['error'] = safe_error(error) if isinstance(error, oracledb.DatabaseError) else str(error)
        (ROOT / 'runtime/mission-guide-verification.json').write_text(json.dumps(REPORT, ensure_ascii=False, indent=2), encoding='utf-8')
        print(REPORT['error'], file=sys.stderr)
        raise
