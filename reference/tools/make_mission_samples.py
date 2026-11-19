"""강사용 합성 미션 CSV 생성. 고정 TEST·라벨과 독립인 TRAIN 오류를 만듭니다.

학생 배포 제외. 점수로 TEST를 고르거나 정답을 바꾸지 않습니다.
"""
import csv
import hashlib
import io
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED = 20261120
TARGET_NAMES = {'esports':'경기력등급', 'festival':'혼잡등급', 'ott':'예상별점',
                'resale':'판매속도등급', 'space':'탐사후보등급',
                'wifi':'Wi-Fi 품질등급', 'bike':'이용수요등급', 'maker':'작품완성도',
                'package':'재활용적합도', 'greenhouse':'환경적합등급', 'delivery':'배송소요등급', 'appux':'사용성등급'}
SPECS = [
    ('esports', 'e스포츠 팀 경기력 등급', '전투·오브젝트 지표로 팀 경기력 5등급을 분류하는 가상 리그',
     [('team_score', '팀 전투 점수', 100), ('objective_score', '오브젝트 점수', 100), ('teamwork_score', '협동 점수', 100)], ['D', 'C', 'B', 'A', 'S']),
    ('festival', '캠퍼스 축제 혼잡도', '사전 반응·참여 의향으로 혼잡 5등급을 분류하는 가상 축제',
     [('interest_score', '관심 점수', 100), ('reservation_score', '사전 예약 점수', 100), ('promotion_score', '홍보 반응 점수', 100)], ['QUIET', 'LIGHT', 'NORMAL', 'BUSY', 'FULL']),
    ('ott', 'OTT 콘텐츠 예상 별점', '예고편·장르·리뷰 반응으로 예상 별점 1~5를 분류하는 가상 콘텐츠',
     [('trailer_score', '예고편 반응 점수', 100), ('genre_score', '장르 선호 점수', 100), ('review_score', '리뷰 반응 점수', 100)], ['STAR1', 'STAR2', 'STAR3', 'STAR4', 'STAR5']),
    ('resale', '중고거래 판매 속도', '가격 매력·상품 상태·관심으로 판매 속도 5등급을 분류하는 가상 거래',
     [('price_score', '가격 매력 점수', 100), ('condition_score', '상품 상태 점수', 100), ('demand_score', '관심 점수', 100)], ['VERY_SLOW', 'SLOW', 'NORMAL', 'FAST', 'VERY_FAST']),
    ('space', '우주 탐사 후보 등급', '세 가지 가상 탐사 지표로 탐사 후보 5등급을 분류하는 교육 시뮬레이션',
     [('spectrum_score', '스펙트럼 지표', 100), ('density_score', '밀도 지표', 100), ('orbit_score', '궤도 지표', 100)], ['GRADE1', 'GRADE2', 'GRADE3', 'GRADE4', 'GRADE5']),
    ('wifi', '캠퍼스 Wi-Fi 품질 등급', '신호·여유 용량·연결 안정 점수로 Wi-Fi 품질 5등급을 분류하는 가상 네트워크',
     [('signal_score', '신호 점수', 100), ('capacity_score', '여유 용량 점수', 100), ('stability_score', '연결 안정 점수', 100)], ['VERY_POOR', 'POOR', 'FAIR', 'GOOD', 'EXCELLENT']),
    ('bike', '공유 자전거 이용 수요', '날씨 쾌적도·접근성·주변 활동 점수로 이용 수요 5등급을 분류하는 가상 대여소',
     [('weather_score', '날씨 쾌적 점수', 100), ('accessibility_score', '접근성 점수', 100), ('activity_score', '주변 활동 점수', 100)], ['VERY_LOW', 'LOW', 'NORMAL', 'HIGH', 'VERY_HIGH']),
    ('maker', '메이커 작품 완성도', '설계·기능·마감 점수로 작품 완성도 5단계를 분류하는 가상 제작 실습',
     [('design_score', '설계 점수', 100), ('function_score', '기능 점수', 100), ('finish_score', '마감 점수', 100)], ['CONCEPT', 'INITIAL', 'BASIC', 'ADVANCED', 'COMPLETE']),
    ('package', '재활용 포장 적합도', '재활용성·분리 용이성·청결 점수로 포장 적합도 5등급을 분류하는 가상 분류 실습',
     [('recyclability_score', '재활용성 점수', 100), ('separation_score', '분리 용이성 점수', 100), ('cleanliness_score', '청결 점수', 100)], ['VERY_LOW', 'LOW', 'NORMAL', 'HIGH', 'VERY_HIGH']),
    ('greenhouse', '스마트 온실 환경 등급', '온도·수분·광량 적합 점수로 환경 5등급을 분류하는 가상 온실',
     [('temperature_score', '온도 적합 점수', 100), ('moisture_score', '수분 적합 점수', 100), ('light_score', '광량 적합 점수', 100)], ['VERY_POOR', 'POOR', 'FAIR', 'GOOD', 'EXCELLENT']),
    ('delivery', '온라인 주문 배송 소요 등급', '거리·교통 혼잡·처리 부하 점수로 배송 소요 5등급을 분류하는 가상 주문',
     [('distance_score', '배송 거리 부담 점수', 100), ('congestion_score', '교통 혼잡 점수', 100), ('load_score', '처리 부하 점수', 100)], ['VERY_FAST', 'FAST', 'NORMAL', 'SLOW', 'VERY_SLOW']),
    ('appux', '모바일 앱 사용성 등급', '탐색 편의·응답 체감·접근성 점수로 사용성 5등급을 분류하는 가상 앱',
     [('navigation_score', '탐색 편의 점수', 100), ('response_score', '응답 체감 점수', 100), ('accessibility_score', '접근성 점수', 100)], ['VERY_POOR', 'POOR', 'FAIR', 'GOOD', 'EXCELLENT']),
]



# Purpose, use case, target interpretation, then feature meaning/low/high in SPECS order.
# This teaching metadata is emitted to catalog.json; the generator itself is not distributed.
LESSONS = {
    'esports': (
        '팀의 세 가지 경기 지표로 새 경기의 경기력 등급을 분류하는 연습입니다.',
        '가상 리그에서 경기 리뷰 대상을 고르고 팀별 약점을 설명하는 상황에 활용합니다.',
        'D → C → B → A → S 순으로 높은 경기력입니다. 실제 승률이나 선수 능력의 측정값은 아닙니다.',
        [('교전 수행을 0~100으로 표현한 교육용 점수입니다. 킬 수 자체가 아닙니다.','교전 수행이 약함','교전 수행이 강함'),
         ('거점·중립 오브젝트 확보를 점수화한 지표입니다. 획득 개수 자체가 아닙니다.','목표 확보가 적음','목표 확보가 활발함'),
         ('합류·역할 분담 등 팀 협동을 점수화한 지표입니다.','협동이 부족함','협동이 원활함')]),
    'festival': (
        '행사 시작 전에 수집한 반응으로 축제의 예상 혼잡 등급을 분류합니다.',
        '가상 캠퍼스 축제의 안내 인력·대기 공간을 어느 행사에 우선 배치할지 검토하는 연습입니다.',
        'QUIET → LIGHT → NORMAL → BUSY → FULL은 한산함에서 매우 혼잡함까지의 5등급입니다. 실제 인원수는 아닙니다.',
        [('행사에 관심을 보인 반응의 강도를 점수화했습니다. 방문 인원수가 아닙니다.','관심이 낮음','관심이 높음'),
         ('사전 참여 예약·신청 수준을 점수화했습니다. 예약 건수 자체가 아닙니다.','예약 반응이 적음','예약 반응이 많음'),
         ('홍보 노출 뒤 클릭·공유 등 반응을 점수화했습니다. 광고비가 아닙니다.','홍보 반응이 약함','홍보 반응이 강함')]),
    'ott': (
        '공개 전 콘텐츠 반응을 설명변수로 사용해 예상 별점 등급을 분류합니다.',
        '가상 OTT 서비스에서 콘텐츠 반응을 비교하고 소개 순서를 검토하는 연습입니다.',
        'STAR1~STAR5는 예상 별점 1~5 등급입니다. 실제 이용자가 남긴 별점 평균을 그대로 담은 값은 아닙니다.',
        [('예고편을 본 사람들의 관심·호응을 점수화한 지표입니다. 조회수 자체가 아닙니다.','예고편 호응이 낮음','예고편 호응이 높음'),
         ('콘텐츠 장르와 가상 이용자 취향이 맞는 정도입니다. 장르 번호가 아닙니다.','취향과 덜 맞음','취향과 잘 맞음'),
         ('초기 소개·리뷰에 대한 긍정 반응을 점수화했습니다. 리뷰 개수 자체가 아닙니다.','리뷰 반응이 부정적','리뷰 반응이 긍정적')]),
    'resale': (
        '중고 상품의 세 가지 특성으로 판매 속도 등급을 분류합니다.',
        '가상 중고거래 목록에서 오래 남을 상품을 찾고 가격·상품 설명을 점검하는 연습입니다.',
        'VERY_SLOW → SLOW → NORMAL → FAST → VERY_FAST는 느린 판매에서 빠른 판매 순서입니다. 실제 판매 일수는 아닙니다.',
        [('유사 상품 대비 가격의 매력도를 점수화했습니다. 판매 가격이나 할인율 자체가 아닙니다.','가격 매력이 낮음','가격 매력이 높음'),
         ('외관·작동 상태의 양호함을 점수화했습니다.','상품 상태가 나쁨','상품 상태가 좋음'),
         ('가상 구매자의 관심·문의 수준을 점수화했습니다. 문의 건수 자체가 아닙니다.','구매 관심이 적음','구매 관심이 많음')]),
    'space': (
        '가상 관측 지표를 사용해 탐사 후보의 우선순위 등급을 분류합니다.',
        '교육 시뮬레이션에서 탐사 후보를 비교하고 선택 이유를 설명하는 연습입니다.',
        'GRADE1~GRADE5는 낮은 우선순위에서 높은 우선순위입니다. 실제 천체의 생명 가능성 판정이 아닙니다.',
        [('가상의 목표 스펙트럼과 맞는 정도입니다. 실제 파장이나 분광 측정값이 아닙니다.','가상 목표와 덜 유사함','가상 목표와 더 유사함'),
         ('가상 탐사 조건에 맞는 밀도 특성의 적합도입니다. 실제 질량밀도 값이 아닙니다.','설정한 조건과 덜 맞음','설정한 조건과 잘 맞음'),
         ('관측·접근에 유리한 궤도 조건의 가상 적합도입니다. 실제 궤도 반지름이 아닙니다.','접근 조건이 불리함','접근 조건이 유리함')]),
    'wifi': (
        '네트워크의 세 가지 상태 점수로 Wi-Fi 품질 등급을 분류합니다.',
        '가상 캠퍼스에서 품질 점검이 필요한 구역의 우선순위를 정하는 연습입니다.',
        'VERY_POOR → POOR → FAIR → GOOD → EXCELLENT는 매우 낮은 품질에서 높은 품질 순서입니다.',
        [('수신 신호의 양호함을 0~100으로 변환한 지수입니다. 음수 dBm 측정값을 직접 넣는 칼럼이 아닙니다.','수신이 약함','수신이 양호함'),
         ('추가 사용자를 수용할 여유를 점수화했습니다. 사용 중인 비율이 아니므로 높을수록 여유롭습니다.','남은 용량이 적음','남은 용량이 많음'),
         ('연결 끊김이 적고 유지가 잘되는 정도입니다. 끊김 횟수 자체가 아닙니다.','연결이 불안정함','연결이 안정적임')]),
    'bike': (
        '대여소 주변 조건으로 공유 자전거 이용 수요 등급을 분류합니다.',
        '가상 대여소의 자전거 재배치 우선순위를 비교하는 연습입니다.',
        'VERY_LOW → LOW → NORMAL → HIGH → VERY_HIGH는 낮은 수요에서 높은 수요 순서입니다. 실제 대여 건수는 아닙니다.',
        [('자전거를 타기 쾌적한 날씨의 정도입니다. 섭씨 온도나 강수량 자체가 아닙니다.','이용에 덜 쾌적함','이용에 더 쾌적함'),
         ('대여소에 쉽게 접근할 수 있는 정도입니다. 실제 거리(m)가 아닙니다.','접근하기 어려움','접근하기 쉬움'),
         ('주변 통학·상업·여가 활동의 활발함입니다. 통행 인원수 자체가 아닙니다.','주변 활동이 적음','주변 활동이 많음')]),
    'maker': (
        '제작물의 설계·기능·마감 상태로 완성도 단계를 분류합니다.',
        '가상 메이커 실습에서 작품의 보완 항목과 다음 점검 순서를 설명하는 연습입니다.',
        'CONCEPT → INITIAL → BASIC → ADVANCED → COMPLETE는 구상에서 높은 완성도까지의 단계입니다. 실제 과제 점수는 아닙니다.',
        [('목표·구조·도면이 정리된 정도를 점수화했습니다.','설계가 덜 구체적임','설계가 구체적임'),
         ('목표 기능이 구현되고 작동하는 정도입니다. 기능 개수 자체가 아닙니다.','작동 구현이 부족함','작동 구현이 충분함'),
         ('조립·외관·마무리 상태의 양호함입니다.','마감 보완이 많음','마감이 양호함')]),
    'package': (
        '포장 상태의 세 가지 점수로 재활용 적합도 등급을 분류합니다.',
        '가상 포장 검수에서 세척·재질 분리 등 보완이 필요한 사례를 설명하는 연습입니다.',
        'VERY_LOW → LOW → NORMAL → HIGH → VERY_HIGH는 낮은 적합도에서 높은 적합도입니다. 실제 분리배출 규정의 판정값은 아닙니다.',
        [('포장 재질 구성의 재활용 적합성을 점수화했습니다. 재질의 고유 코드가 아닙니다.','재활용에 불리한 구성','재활용에 유리한 구성'),
         ('여러 재질·부속을 쉽게 분리할 수 있는 정도입니다.','분리하기 어려움','분리하기 쉬움'),
         ('내용물·오염이 적은 청결 상태를 점수화했습니다. 오염률 자체가 아닙니다.','오염이 많음','오염이 적음')]),
    'greenhouse': (
        '온실 환경의 적합 점수로 재배 환경 등급을 분류합니다.',
        '가상 온실에서 점검할 환경 요소를 고르고 조정 전후 조건을 비교하는 연습입니다.',
        'VERY_POOR → POOR → FAIR → GOOD → EXCELLENT는 낮은 적합도에서 높은 적합도 순서입니다.',
        [('목표 온도 범위에 맞는 정도입니다. 실제 온도(℃)가 아니며 100은 매우 더운 상태를 뜻하지 않습니다.','목표 범위에서 벗어남','목표 범위에 잘 맞음'),
         ('목표 수분 조건에 맞는 정도입니다. 실제 습도(%)나 토양 수분량이 아닙니다.','목표 수분과 덜 맞음','목표 수분과 잘 맞음'),
         ('목표 광량에 맞는 정도입니다. 실제 조도(lux)를 직접 넣는 칼럼이 아닙니다.','목표 광량과 덜 맞음','목표 광량과 잘 맞음')]),
    'delivery': (
        '주문 처리 조건으로 배송 소요 등급을 분류하는 연습입니다.',
        '가상 쇼핑몰에서 배송 안내 범주를 정하고 지연 점검 대상 주문을 찾는 상황에 활용합니다.',
        'VERY_FAST → FAST → NORMAL → SLOW → VERY_SLOW는 짧은 소요에서 긴 소요 순서입니다. 실제 분·시간 값은 아닙니다.',
        [('배송 거리로 인한 부담을 점수화했습니다. 실제 거리(km)가 아닙니다.','거리 부담이 적음','거리 부담이 큼'),
         ('배송 구간의 교통 혼잡 수준입니다. 평균 속도(km/h)가 아니며 높을수록 혼잡합니다.','교통이 원활함','교통이 혼잡함'),
         ('분류·포장·출고 작업의 처리 부담입니다. 처리 완료율이 아니며 높을수록 일이 몰린 상태입니다.','처리 부하가 적음','처리 부하가 큼')]),
    'appux': (
        '화면 사용 경험의 세 가지 점수로 앱 사용성 등급을 분류합니다.',
        '가상 앱의 화면·버전별 사용 경험을 비교하고 개선할 항목을 설명하는 연습입니다.',
        'VERY_POOR → POOR → FAIR → GOOD → EXCELLENT는 낮은 사용성에서 높은 사용성 순서입니다. 실제 이용자 만족도 조사 결과는 아닙니다.',
        [('메뉴·화면에서 원하는 기능을 찾기 쉬운 정도입니다. 클릭 횟수 자체가 아닙니다.','기능을 찾기 어려움','기능을 찾기 쉬움'),
         ('반응을 빠르고 원활하게 느끼는 정도입니다. 지연시간(ms)이 아니며 높을수록 좋습니다.','응답 체감이 답답함','응답 체감이 원활함'),
         ('글자·대비·조작 방식이 이용을 돕는 정도입니다. 실제 접근성 인증 여부가 아닙니다.','사용 지원이 부족함','사용 지원이 충분함')]),
}

def sample(index, corrupt=True):
    # 데이터·분할은 오류 RNG보다 먼저 정합니다. TEST는 전후 평가에서 변경하지 않습니다.
    rng = random.Random(SEED + index)
    errors = random.Random(SEED + 1000 + index)
    key, title, description, features, classes = SPECS[index]
    rows = []
    for case_id in range(1, 1531):
        x = [rng.uniform(0, 100) for _ in range(3)]
        # 가상 현상의 생성식. 정답 생성기를 학생 소스에 넣지 않습니다.
        score = sum(x) / 3
        label = classes[sum(score >= boundary for boundary in (36, 46, 54, 64))]
        split = 'TRAIN' if case_id <= 1200 else 'TEST' if case_id <= 1500 else 'PREDICT'
        values = [f'{value:.3f}' for value in x]
        # 기록 전체의 센서/수집 장애를 가정합니다. 장애 여부는 라벨·TEST와 독립입니다.
        # 정상 TRAIN도 충분히 남겨 N 처리의 효과와 학습량을 함께 비교합니다.
        if split == 'TRAIN' and corrupt and errors.random() < 0.8:
            values = [errors.choice(['', 'unknown', '999999']) for _ in range(3)]
        rows.append(dict(zip(['case_id', *[f[0] for f in features], 'label', 'split', 'use_yn'],
                             [case_id, *values, label, split, 'Y'])))
    columns = list(rows[0])
    layout = [{'name': 'case_id', 'korean_name': '사례번호', 'role': '사례 식별 키', 'valid': '중복 없는 양의 정수'}]
    layout += [{'name': name, 'korean_name': meaning, 'role': '모델 설명변수', 'valid': f'숫자 0~{maximum}, 단위 없음'} for name, meaning, maximum in features]
    layout += [{'name': 'label', 'korean_name': TARGET_NAMES[key], 'role': '분류 타겟', 'valid': ' / '.join(classes)},
               {'name': 'split', 'korean_name': '데이터구분', 'role': '미리 고정한 학습·평가 구분', 'valid': 'TRAIN 1200 / TEST 300'},
               {'name': 'use_yn', 'korean_name': '사용여부', 'role': '학습 사용 여부', 'valid': 'Y / N · TEST는 원본 유지'}]
    purpose,use_case,target_meaning,interpretations=LESSONS[key]
    layout[0]['meaning']='각 사례를 구분하는 키입니다. 모델 설명변수에서 제외합니다.'
    for field,(meaning,low,high) in zip(layout[1:4],interpretations):
        field.update(meaning=meaning,low_meaning=low,high_meaning=high)
    layout[4]['meaning']=target_meaning
    layout[5]['meaning']='미리 고정한 TRAIN은 학습, TEST는 평가에 사용하며 TEST 원본은 바꾸지 않습니다.'
    layout[6]['meaning']='원본의 학습 사용 여부입니다. 실제 전처리 후 학습 제공 여부는 PREPARED의 FIT_YN으로 확인합니다.'
    return rows, {'key': key, 'title': f'{index+1}. {title}', 'description': description + '. 합성 데이터이며 실제 인과관계·성능을 보장하지 않습니다.',
                  'filename': key + '.csv', 'prediction_filename': key + '_prediction.csv', 'columns': columns,
                  'learning':{'purpose':purpose,'use_case':use_case},
                  'rows': 1500, 'issues': ['결측값', '숫자 대신 문자열', '범위 밖 수치'], 'layout': layout,
                  'task': '새 테이블·적재·조회·전처리·모델·평가·예측 프로시저를 만들고 Python에서 호출하세요. TEST 300행은 변경하지 않습니다.'}


def encode(rows, columns):
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction='ignore', lineterminator='\n')
    writer.writeheader(); writer.writerows(rows)
    return buffer.getvalue()


if __name__ == '__main__':
    # 기존 CSV·검증 결과는 재생성으로 덮어쓰지 않습니다. 먼저 전체 일치 여부를 확인합니다.
    target = ROOT/'data/catalog.json'
    previous = {item['key']:item for item in json.loads(target.read_text(encoding='utf-8'))} if target.exists() else {}
    catalog, pending = [], []
    assert len({spec[0] for spec in SPECS}) == len(SPECS)
    for i in range(len(SPECS)):
        rows, item = sample(i)
        sources = [(item['filename'], encode(rows[:1500], item['columns'])),
                   (item['prediction_filename'], encode(rows[1500:], item['columns'][:4]))]
        for name, text in sources:
            path = ROOT/'data/examples'/name
            # 동일한 설치 CSV를 모든 OS에서 재현합니다.
            raw = text.replace('\n', '\r\n').encode('utf-8')
            if path.exists():
                if path.read_bytes() != raw:
                    raise RuntimeError('Existing CSV differs; inspect before replacement: '+name)
            else:
                pending.append((path, raw))
        old = previous.get(item['key'])
        if old:
            # Only teaching explanations may be enriched; identifiers, ranges, tasks and CSV stay fixed.
            core={key:value for key,value in item.items() if key not in ('learning','layout')}
            same_layout=len(old['layout'])==len(item['layout']) and all(
                all(before.get(key)==after[key] for key in ('name','korean_name','role','valid'))
                for before,after in zip(old['layout'],item['layout']))
            if any(old.get(key)!=value for key,value in core.items()) or not same_layout:
                raise RuntimeError('Existing mission core metadata differs: '+item['key'])
            if old.get('baseline') and old['baseline']['sha256'] != hashlib.sha256(sources[0][1].replace('\n','\r\n').encode('utf-8')).hexdigest():
                raise RuntimeError('Baseline checksum differs: '+item['key'])
            item = {**old, **item}
        else:
            item['csv_sha256'] = hashlib.sha256(sources[0][1].replace('\n','\r\n').encode('utf-8')).hexdigest()
        catalog.append(item)
    for path, raw in pending:
        path.write_bytes(raw)
    target.write_bytes((json.dumps(catalog, ensure_ascii=False, indent=2)+'\n').replace('\n','\r\n').encode('utf-8'))
    print(f'Available {len(catalog)} datasets: TRAIN 1200 / TEST 300 / PREDICT 30. Existing CSV/baselines preserved. New Oracle baselines not run.')
