"""강사용: UCI의 실제 2011년 주간 시세를 수업 CSV로 변환합니다.

원본 다운로드는 reference/datasets/dow-jones/uci-dow-jones.zip에 보관합니다.
라벨/기간/결함은 모델 평가를 실행하기 전에 고정합니다. 모델 점수는 읽지 않습니다.
원본의 다음 주 가격은 정답 계산에만 사용하며 학생 CSV 입력에는 포함하지 않습니다.
"""
import csv
from collections import Counter
from datetime import datetime
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import random
import zipfile

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT/'reference/datasets/dow-jones/uci-dow-jones.zip'
COLUMNS = ('case_id','return_pct','range_pct','volume_change_pct','close_price','stock','signal','week_ending','split','use_yn')
SEED = 20261120
ARCHIVE_SHA256 = '08ad8e30915f071b46f6f5bef2b1ccdfe70aacfa31aee116117048ad2adec0bf'
SOURCE_URL = 'https://archive.ics.uci.edu/static/public/312/dow+jones+index.zip'


def decimal_price(value):
    return Decimal(value.removeprefix('$'))


def write_csv(path, rows, columns):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def build():
    if not ARCHIVE.exists():
        raise FileNotFoundError('공식 원본 ZIP을 먼저 보관하세요: '+SOURCE_URL+' -> '+str(ARCHIVE))
    if hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        raise ValueError('검증된 UCI 원본 ZIP과 SHA256이 다릅니다. 새 원본으로 자동 변경하지 않습니다.')
    with zipfile.ZipFile(ARCHIVE) as archive:
        original = archive.read('dow_jones_index.data')
        source = list(csv.DictReader(io.StringIO(original.decode('ascii'))))
        for name in ('dow_jones_index.data','dow_jones_index.names'):
            (ARCHIVE.parent/name).write_bytes(archive.read(name))
    assert len(source) == 750
    for row in source:
        row['iso_date'] = datetime.strptime(row['date'], '%m/%d/%Y').date().isoformat()
    source.sort(key=lambda row: (row['iso_date'], row['stock']))
    rng = random.Random(SEED)
    training, predictions, changes = [], [], []
    for case_id, src in enumerate(source, 1):
        week = src['iso_date']
        future_return = decimal_price(src['next_weeks_close']) - decimal_price(src['next_weeks_open'])
        row = dict(zip(COLUMNS, (
            case_id, src['percent_change_price'],
            format(100*(decimal_price(src['high'])-decimal_price(src['low']))/decimal_price(src['open']), '.6f'),
            src['percent_change_volume_over_last_wk'], src['close'].removeprefix('$'), src['stock'],
            'BUY' if future_return > 0 else 'SELL', week,
            'TRAIN' if week < '2011-04-01' else 'TEST',
            'N' if week == '2011-03-25' else 'Y',
        )))
        # 금요일 장 마감 후 판단 → 다음 주 시가 진입/종가 결과.
        # 마지막 주는 미래 정답 없이 별도 예측에 사용합니다.
        if week == '2011-06-24':
            row['signal'] = ''
            predictions.append(row)
            continue
        # 수업용 결함: 라벨·기간·점수와 무관한 고정 난수로 특성만 변경합니다.
        # 단위는 설명/컬럼 제목에만 표시합니다. 첫 주 거래량 증감률 결측은 보존합니다.
        for key in COLUMNS[1:5]:
            value = row[key]
            dice = rng.random()
            if not value:
                continue
            if dice < .02:
                row[key] = ''
                kind = 'missing'
            elif dice < .03:
                row[key] = 'unknown'
                kind = 'invalid_string'
            elif dice < .04:
                row[key] = '999999'
                kind = 'out_of_range'
            else:
                continue
            changes.append({'case_id':case_id,'column':key,'original':value,'stored':row[key],'kind':kind})
        # 이전 버전과 결측·오류·이상치 위치를 동일하게 유지하는 예약 난수입니다.
        # 단위·종목 접두어를 추가하지 않으며 라벨·모델 점수와 무관합니다.
        rng.random()
        training.append(row)
    assert len(training) == 720 and len(predictions) == 30
    write_csv(ROOT/'data/classification.csv', training, COLUMNS)
    write_csv(ROOT/'data/prediction.csv', predictions, COLUMNS[:8])
    manifest = {
        'title':'다음 주 주식 매수·매도 신호 분류',
        'citation':'Brown, M. (2013). Dow Jones Index [Dataset]. UCI Machine Learning Repository.',
        'source_url':'https://archive.ics.uci.edu/dataset/312/dow+jones+index',
        'doi':'https://doi.org/10.24432/C5788V',
        'license':'CC BY 4.0', 'license_url':'https://creativecommons.org/licenses/by/4.0/',
        'source_sha256':hashlib.sha256(original).hexdigest(),
        'archive_sha256':hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
        'period':'2011-01-07 ~ 2011-06-24', 'source_rows':750, 'stocks':30,
        'classification_rows':720, 'train_rows':330, 'test_rows':360, 'excluded_boundary_rows':30, 'prediction_rows':30,
        'train_period':'2011-01-07 ~ 2011-03-18', 'test_period':'2011-04-01 ~ 2011-06-17',
        'excluded_boundary':'2011-03-25 (TRAIN, N): 다음 주 정답 기간이 TEST 시작과 겹쳐 학습에서 제외',
        'prediction_week':'2011-06-24 (정답 비공개, TEST 평가와 분리)',
        'signal_definition':'다음 주 종가 > 다음 주 시가이면 BUY, 그 외 SELL. SELL은 매도/매수 회피를 뜻하며 공매도 주문이 아니다.',
        'decision_time':'week_ending 장 마감 후 다음 주의 방향을 예측한다. 다음 주 시가·종가·수익률은 입력에서 제외한다.',
        'features':{
            'return_pct':'이번 주 시가 대비 종가 등락률(%) — 원본 percent_change_price',
            'range_pct':'100 × (이번 주 고가 - 저가) / 시가(%) — 소수 6자리',
            'volume_change_pct':'전주 대비 이번 주 거래량 증감률(%) — 원본 percent_change_volume_over_last_wk',
            'close_price':'이번 주 종가(USD) — 원본 close에서 $를 제거한 숫자 문자열',
            'stock':'2011년 당시 종목 코드 — 현재 상장명/종목 구성과 다를 수 있음',
        },
        'metadata':'CASE_ID·WEEK_ENDING·SPLIT·USE_YN은 모델 특성이 아니다. SIGNAL은 학습 정답이며 예측 입력 특성이 아니다.',
        'class_counts': {part:dict(Counter(r['signal'] for r in training if r['split']==part and r['use_yn']=='Y')) for part in ('TRAIN','TEST')},
        'adaptations':'주식 신호 라벨·고저폭을 계산하고 기간을 분리했다. 단위는 값에서 제외하고 컬럼 설명에만 표시한다. 학습·TEST 숫자 특성에만 결측(빈 셀), 유효하지 않은 값(unknown), 매우 큰 이상치(999999)를 고정 시드로 추가했다. 원본 가격 자체와 교육용 결함을 구분한다.',
        'defect_seed':SEED, 'added_defects':dict(Counter(c['kind'] for c in changes)),
        'limitations':'과거 자료의 방향 분류 실습이다. 거래 비용·슬리피지·배당·운용 수익률은 평가하지 않는다. 정확도나 정제 적용이 투자 수익을 보장하지 않는다.',
    }
    (ROOT/'data/stock-source.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (ARCHIVE.parent/'classroom-changes.json').write_text(json.dumps(changes, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({key:manifest[key] for key in ('classification_rows','train_rows','test_rows','prediction_rows','class_counts','added_defects')},ensure_ascii=False))


if __name__ == '__main__':
    build()
