"""강사용: 제공 CSV 변환 함수를 호출해 빈 셀·문자 오류가 보존되는지 관찰합니다."""
from pathlib import Path
import sys
import json

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.assignment_templates import csv_payload


def main():
    # 원리를 설명하는 2행입니다. 미션 데이터나 모델 결과를 대신하지 않습니다.
    csv_text = 'case_id,team_score,label\n1,,A\n2,unknown,B\n'
    payload, count = csv_payload(csv_text.encode('utf-8-sig'))
    print('입력 행 수:', count)
    print(payload)
    values = json.loads(payload)
    print('빈 셀 보존:', values[0]['team_score'] == '')
    print('오류 문자열 보존:', values[1]['team_score'] == 'unknown')
    print('숫자 모양도 문자열:', isinstance(values[0]['case_id'], str))


if __name__ == '__main__':
    main()
