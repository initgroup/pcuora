"""강사용: dict/list, 함수 반환값, JSON 직렬화, 예외, with의 처리 순서."""
from contextlib import contextmanager
import json


def summarize(items):
    # items는 dict 한 개가 아니라 dict를 담은 list입니다.
    return {'rows': items, 'count': len(items)}


@contextmanager
def trace_scope():
    print('1. 자원 준비')
    try:
        yield '학습용 자원'
    finally:
        print('3. 자원 정리')


def main():
    record = {'case_id': '1', 'team_score': '', 'use_yn': 'Y'}
    result = summarize([record])
    print(json.dumps(result, ensure_ascii=False))
    print('빈 문자열인가:', record['team_score'] == '')
    print('None인가:', record['team_score'] is None)
    with trace_scope() as resource:
        print('2. 블록 실행:', resource)
    try:
        int('unknown')
    except ValueError:
        print('4. 숫자로 바꿀 수 없는 원본은 별도로 판별해야 함')


if __name__ == '__main__':
    main()
