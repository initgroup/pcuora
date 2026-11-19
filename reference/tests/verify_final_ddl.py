"""최종 배포 정의와 현재 DB 원문을 읽기 전용으로 대조합니다. DDL·학습은 실행하지 않습니다."""
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from backend.db import connection, safe_error
from backend.sql_files import definition_files, query, read_sql
from source_files import inventory


def procedure(source):
    return source[source.index('CREATE OR REPLACE PROCEDURE'):].rstrip().rstrip('/').strip()


def verify():
    # 배포 목록의 실제 바이트를 검사하므로 .local 복구 자료가 없어도 성립해야 합니다.
    files = inventory(audience='student')
    expected = ['sql/' + n for n in (*definition_files(), 'table_comments.sql', 'session.sql')]
    expected += ['scripts/db-init.ps1']
    expected += [f'sql/custom/{task}/{name}' for task in ('mission', 'creative')
                 for name in ('01_tables.sql', '02_procedure.sql')]
    expected += ['sql/custom/mission/guide_procedure.sql']
    assert all(n in files for n in expected), '배포 정의 파일 누락'
    assert not any(n.startswith('.local/') for n in files)
    assert not any(re.search(r'OML_CLS_|OML_CLASSIFIER', p.read_text(encoding='utf-8'))
                   for p in (ROOT / 'sql').rglob('*.sql')), '구형 객체명 참조'
    basic = procedure(read_sql('classifier.sql'))
    for task in ('mission', 'creative'):
        for filename in ('01_tables.sql', '02_procedure.sql'):
            custom = read_sql(f'custom/{task}/{filename}')
            active = re.sub(r'--[^\n]*', '', custom).strip()
            assert not active, f'{task}/{filename}: stock executable SQL must not be provided'
    mission_template = read_sql('custom/mission/guide_procedure.sql')
    assert 'CREATE OR REPLACE PROCEDURE OML_MISSION_RUN' in mission_template
    assert '{{' in mission_template, 'Mission template must be resolved using the selected catalog entry'
    report = {'definition_files_in_student_package': expected, 'no_local_dependency': True,
              'no_legacy_names': True, 'assignment_guidance_separated': True,
              'custom_stubs_do_not_supply_basic_stock_sql': True}
    archive = ROOT / 'downloads/COM22417_학번_20261120.zip'
    if archive.is_file():
        with zipfile.ZipFile(archive) as package:
            for name in expected:
                assert package.read(name) == files[name], '기존 배포 ZIP 불일치: ' + name
        report['existing_student_zip_definitions_match'] = True
    with connection() as conn:
        objects = query(conn, 'objects.sql', training_table='OML_BASIC_DATA',
                        prediction_table='OML_BASIC_PREDICT', prepared_table='OML_BASIC_PREPARED',
                        procedure_name='OML_BASIC_RUN')
        assert len(objects) == 4 and all(o['status'] == 'VALID' for o in objects), '기본 객체 누락 또는 INVALID'
        assert not query(conn, 'procedure_errors.sql', procedure_name='OML_BASIC_RUN'), '프로시저 컴파일 오류'
        source = ''.join(r['text'] for r in query(conn, 'procedure_source.sql',
                                               procedure_name='OML_BASIC_RUN'))
        disk = re.sub(r'^CREATE OR REPLACE\s+', '', basic, flags=re.I)
        assert source.replace('\r\n', '\n').strip() == disk.replace('\r\n', '\n').strip(), 'DB 원문 불일치'
        report['basic_db_procedure_matches_final_source'] = True
        report['basic_objects_valid'] = True
        report['tables'] = {}
        for table, filename in [('OML_BASIC_DATA', 'schema.sql'),
                                ('OML_BASIC_PREDICT', 'prediction_table.sql'),
                                ('OML_BASIC_PREPARED', 'prepared_table.sql')]:
            columns = query(conn, 'columns.sql', table_name=table)
            expected_cols = re.findall(
                r'^\s*[, (]?\s*([A-Z][A-Z0-9_]*)\s+(NUMBER|VARCHAR2|CHAR|TIMESTAMP)\b',
                read_sql(filename), re.M)
            actual = [(c['column_name'], re.sub(r'^TIMESTAMP\(6\)$', 'TIMESTAMP', c['data_type']))
                      for c in columns]
            # 과거 ALTER 이력에 따른 물리 열 순서는 달라도 명시한 열 이름으로 조회·적재합니다.
            assert dict(actual) == dict(expected_cols), table
            report['tables'][table] = {'column_names_and_types_match': True,
                                      'physical_order_matches': actual == expected_cols,
                                      'column_count': len(columns)}
    report['scope'] = 'Read-only metadata/source comparison; no fresh-schema execution or model recreation.'
    target = ROOT / 'runtime/final-ddl-verification.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        verify()
    except Exception as error:
        print(str(error) if isinstance(error, AssertionError) else safe_error(error), file=sys.stderr)
        sys.exit(1)
