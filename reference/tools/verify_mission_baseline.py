"""검증 전용 객체만 생성하고 정리합니다. 기준 정확도를 실제 Oracle에서 측정합니다."""
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.db import connection
from reference.tools.make_mission_samples import sample

TABLE = 'OML_MSN_VFY_DATA'
MODELS = ['OML_MSN_VFY_RAW', 'OML_MSN_VFY_CLEAN', 'OML_MSN_VFY_CONTROL']


def verify():
    catalog = json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
    report = []
    with connection() as conn, conn.cursor() as cursor:
        # 검증 전용 이름만 사용합니다. 공통 학습 테이블·모델은 건드리지 않습니다.
        def cleanup():
            for model in MODELS:
                cursor.execute('SELECT COUNT(*) FROM USER_MINING_MODELS WHERE MODEL_NAME = :name', name=model)
                if cursor.fetchone()[0]: cursor.callproc('DBMS_DATA_MINING.DROP_MODEL', [model])
        cursor.execute('SELECT COUNT(*) FROM USER_TABLES WHERE TABLE_NAME = :name', name=TABLE)
        if cursor.fetchone()[0]:
            raise RuntimeError('Verification table already exists; inspect it before retrying.')
        cursor.execute('CREATE TABLE OML_MSN_VFY_DATA (CASE_ID NUMBER PRIMARY KEY, X1 NUMBER, X2 NUMBER, X3 NUMBER, LABEL VARCHAR2(20), SPLIT VARCHAR2(10), VALID_ROW NUMBER, ORIGINAL_X1 NUMBER, ORIGINAL_X2 NUMBER, ORIGINAL_X3 NUMBER)')
        try:
            for index,item in enumerate(catalog):
                cleanup()
                cursor.execute('DELETE FROM OML_MSN_VFY_DATA')
                raw = (ROOT/'data/examples'/item['filename']).read_bytes()
                records = list(csv.DictReader(raw.decode('utf-8').splitlines()))
                pristine,_ = sample(index,corrupt=False)
                pristine={int(row['case_id']):row for row in pristine}
                fields = item['columns'][1:4]
                def number(value):
                    try: return float(value)
                    except ValueError: return None
                values = []
                for row in records:
                    x = [number(row[key]) for key in fields]
                    valid = int(all(v is not None and 0 <= v <= 100 for v in x))
                    original=pristine[int(row['case_id'])]
                    assert original['label']==row['label'] and original['split']==row['split']
                    if row['split']=='TEST': assert all(original[key]==row[key] for key in fields)
                    values.append((int(row['case_id']), *x, row['label'], row['split'], valid,*[number(original[key]) for key in fields]))
                cursor.executemany('INSERT INTO OML_MSN_VFY_DATA VALUES (:1,:2,:3,:4,:5,:6,:7,:8,:9,:10)', values)
                conn.commit()
                result = {'key': item['key'], 'sha256': hashlib.sha256(raw).hexdigest(), 'test_rows': 300,
                          'algorithm': 'ALGO_DECISION_TREE', 'prep_auto': 'ON', 'max_depth': 6,
                          'test_unchanged': True}
                result['min_percent_node']=10
                result['raw_train_rows'] = sum(row[5] == 'TRAIN' for row in values)
                result['clean_train_rows'] = sum(row[5] == 'TRAIN' and row[6] == 1 for row in values)
                result['classes'] = 5
                result['numeric_conversion'] = '숫자로 변환 불가능한 값과 빈 셀은 NULL, 범위 밖 숫자는 RAW에 유지'
                for variant, model in zip(['raw', 'clean', 'control'], MODELS):
                    query = "SELECT CASE_ID, X1, X2, X3, LABEL FROM OML_MSN_VFY_DATA WHERE SPLIT = 'TRAIN'"
                    if variant == 'clean': query += ' AND VALID_ROW = 1'
                    if variant == 'control':
                        query = "SELECT CASE_ID, ORIGINAL_X1 X1, ORIGINAL_X2 X2, ORIGINAL_X3 X3, LABEL FROM OML_MSN_VFY_DATA WHERE SPLIT = 'TRAIN'"
                    script = (ROOT/'reference/tests/sql/mission_baseline.sql').read_text(encoding='utf-8').rsplit('/', 1)[0]
                    cursor.execute(script, model_name=model, data_query=query)
                    cursor.execute(f"SELECT COUNT(*), SUM(CASE WHEN PREDICTION({model} USING X1, X2, X3) = LABEL THEN 1 ELSE 0 END) FROM OML_MSN_VFY_DATA WHERE SPLIT = 'TEST'")
                    total, correct = cursor.fetchone()
                    assert total == 300
                    result[variant+'_correct'] = correct
                    result[variant+'_accuracy'] = round(100*correct/total, 4)
                report.append(result)
                print(json.dumps(result))
        finally:
            cleanup()
            cursor.execute('DROP TABLE OML_MSN_VFY_DATA PURGE')
    (ROOT/'runtime/mission-baseline-verification.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    assert all(item['raw_accuracy'] < 50 for item in report), 'Raw baseline threshold not met'
    assert all(item['clean_accuracy'] > item['raw_accuracy'] and item['control_accuracy'] > item['raw_accuracy'] for item in report), 'Garbage-input effect not demonstrated'
    for item, result in zip(catalog, report): item['baseline'] = result
    (ROOT/'data/catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__': verify()
