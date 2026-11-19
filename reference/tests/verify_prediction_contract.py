"""현재 CLEAN 모델에 대한 컬럼 대응 실험. 읽기 전용 트랜잭션이며 DDL/DML은 없습니다."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.db import connection, rows
from backend import service
from backend.sql_files import query


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def read_sections():
    content = (ROOT / 'reference/tests/sql/prediction_contract.sql').read_text(encoding='utf-8')
    parts = re.split(r'^-- @section (\w+)\s*$', content, flags=re.M)
    return {parts[i]: parts[i + 1].strip().rstrip(';') for i in range(1, len(parts), 2)}


def fetch(conn, sql):
    with conn.cursor() as cursor:
        cursor.execute(sql)
        return rows(cursor)


def snapshot(conn, sections):
    return {
        'training': digest(query(conn, 'training_rows.sql', use_yn='ALL', split='ALL')),
        'prediction': digest(query(conn, 'prediction_rows.sql')),
        'model': fetch(conn, sections['model']),
        'procedure': digest(query(conn, 'procedure_source.sql', procedure_name='OML_BASIC_RUN')),
        'prepared': digest([service.get_prepared_data(conn,mode) for mode in ('RAW','CLEAN')]),
    }


def prepared_select(runtime_sql):
    """DB에 저장된 예측 SELECT의 준비행 조회를 그대로 사용합니다."""
    match = re.search(r'\bFROM\s*\((.*)\)\s+d\s+ORDER\s+BY\s+d\.CASE_ID\s*;?\s*$',
                      runtime_sql, re.S | re.I)
    if not match:
        raise AssertionError('현재 예측 SQL의 정제 SELECT 경계를 확인하여 검증기를 갱신하세요.')
    return match.group(1).strip()


def compare(expected, actual):
    assert len(expected) == len(actual)
    labels = probabilities = 0
    for first, second in zip(expected, actual):
        assert first['row_no'] == second['row_no']
        labels += first['predicted'] != second['predicted']
        probabilities += any(abs(float(first[key]) - float(second[key])) > 1e-12
                             for key in ('buy_probability', 'sell_probability'))
    return {'changed_predictions': labels, 'changed_probabilities': probabilities,
            'identical': labels == 0 and probabilities == 0}


def verify():
    sections = read_sections()
    cases = [
        ('baseline', 'baseline', 'using_all', 'same'),
        ('explicit_columns', 'baseline', 'using_explicit', 'same'),
        ('unqualified_star', 'baseline', 'using_unqualified', 'same'),
        ('reversed_columns', 'reversed_columns', 'using_all', 'same'),
        ('target_buy', 'target_buy', 'using_all', 'same'),
        ('target_sell', 'target_sell', 'using_all', 'same'),
        ('target_null', 'target_null', 'using_all', 'same'),
        ('case_id_changed', 'case_id_changed', 'using_all', 'same'),
        ('case_id_absent', 'case_id_absent', 'using_all', 'same'),
        ('extra_columns', 'extra_columns', 'using_all', 'same'),
        ('name_typo', 'name_typo', 'using_all', 'success'),
        ('alias_restored', 'name_typo', 'using_alias', 'same'),
        ('missing_return', 'missing_return', 'using_all', 'success'),
        ('stock_only', 'stock_only', 'using_all', 'success'),
        ('numeric_strings', 'numeric_strings', 'using_all', 'same'),
        ('invalid_numeric_string', 'invalid_numeric_string', 'using_all', 'error'),
        ('numeric_date', 'numeric_date', 'using_all', 'error'),
        ('numeric_binary', 'numeric_binary', 'using_all', 'error'),
        ('stock_number', 'stock_number', 'using_all', 'success'),
        ('stock_unknown', 'stock_unknown', 'using_all', 'success'),
    ]
    report = {'verified_at': datetime.now(timezone.utc).isoformat(), 'read_only': True,
              'model': 'OML_BASIC_CLEAN_MODEL', 'cases': [], 'ok': False}
    output_path = ROOT / 'runtime/prediction-contract-verification.json'
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sections['read_only'])
        before = snapshot(conn, sections)
        report['model_metadata'] = before['model']
        report['attributes'] = fetch(conn, sections['attributes'])
        # PREDICT 프로시저는 이제 INSERT SELECT를 포함합니다. 읽기 전용 검증에서는
        # 호출하지 않고 저장된 프로시저의 최종 CLEAN SELECT만 직접 실행합니다.
        source=''.join(row['text'] for row in query(conn,'procedure_source.sql',procedure_name='OML_BASIC_RUN'))
        selects=re.findall(r"p_sql\s*:=\s*q'~(.*?)~'",source,re.S|re.I)
        assert len(selects)==6, '현재 프로시저의 학습·평가·예측 SELECT 경계를 확인하세요.'
        prediction_sql=selects[-1].strip()
        actual=fetch(conn,prediction_sql)
        assert actual, '먼저 CLEAN 예측을 1회 실행하여 PREPARED의 PREDICT 행을 저장하세요.'
        normalized = prepared_select(prediction_sql)
        report['runtime_sql'] = prediction_sql
        report['procedure_called'] = False
        report['prepared_prediction_rows_required'] = True
        report['normalized_sql'] = normalized
        baseline = None
        for name, projection, using, expected in cases:
            sql = sections['score'].replace('{{normalized}}', normalized).replace(
                '{{projection}}', sections[projection]).replace('{{using}}', sections[using])
            item = {'case': name, 'expected': expected, 'sql': sql}
            try:
                values = fetch(conn, sql)
                if baseline is None:
                    baseline = values
                    assert len(values) == len(actual)
                    for row, original in zip(values, actual):
                        assert row['row_no'] == original['case_id']
                        assert row['predicted'] == original['predicted']
                        assert abs(row['buy_probability'] - original['buy_probability']) < 1e-12
                item.update(status='success', rows=len(values), **compare(baseline, values))
                item['passed'] = expected != 'error' and (expected != 'same' or item['identical'])
            except Exception as error:
                code = re.search(r'(ORA-\d{5}|DPY-\d{4})', str(error))
                item.update(status='error', error_code=code.group(0) if code else type(error).__name__)
                expected_errors = {'invalid_numeric_string': 'ORA-01722',
                                   'numeric_date': 'ORA-00932', 'numeric_binary': 'ORA-00932'}
                item['passed'] = expected == 'error' and item['error_code'] == expected_errors.get(name)
            report['cases'].append(item)
        after = snapshot(conn, sections)
        report['data_model_procedure_preserved'] = before == after
        report['prediction_rows'] = len(baseline or [])
        report['before_hashes'] = before
        report['ok'] = report['data_model_procedure_preserved'] and all(item['passed'] for item in report['cases'])
        conn.rollback()
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items()
                      if key in ('ok', 'read_only', 'prediction_rows', 'data_model_procedure_preserved')}, ensure_ascii=False))
    for item in report['cases']:
        print(json.dumps({key: value for key, value in item.items() if key != 'sql'}, ensure_ascii=False))
    if not report['ok']:
        raise AssertionError('예측 입력 실험에서 예상과 다른 결과가 있습니다. runtime의 실제 결과를 확인하세요.')


if __name__ == '__main__':
    verify()
