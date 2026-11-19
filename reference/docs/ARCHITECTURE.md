# 현재 구조

실행 UI → app.py → backend/service.py → sql/queries/*.sql 또는 OML_BASIC_RUN → Oracle입니다.
DB는 원본 OML_BASIC_DATA(TRAIN/TEST), 예측 원본 OML_BASIC_PREDICT, 모델 입력 OML_BASIC_PREPARED, OML_BASIC_RUN과 RAW/CLEAN 두 모델입니다.
PREPARE의 INSERT SELECT가 정제 결과와 FIT_YN을 저장합니다. CREATE_MODEL2는 PREPARED에서 선택 PREP_MODE·TRAIN·FIT_YN=Y만 단순 SELECT합니다. 예측도 같은 방식의 입력을 PREPARED에 저장한 뒤 실행합니다.
추가 패키지·뷰·함수·상태 테이블은 만들지 않습니다. 모델 선택과 최신 여부 해시는 runtime에 계정별로 저장하며 원본·DB 소스·선택 방식의 준비값·모델 생성시각을 검증합니다.
코딩도움말은 현재 선택 코드와 Python·PL/SQL 수정 위치의 두 탭을 제공합니다. 실제 실행 SQL 로그 탭은 제공하지 않으며, 로그아웃 시 도움말 코드 영역을 비웁니다.
미션·창의는 기본과제의 테이블/프로시저 복제본을 수정하고 고정 객체 이름 4개로 연결합니다. 특성·정답 컬럼 변경은 DB SQL에 반영하며 웹 코드를 바꾸지 않습니다. 현재 계정의 OML_ 객체만 허용하고 SQL 문장을 입력받지 않습니다.


CSV/DB 자원 변경(2026-11-20): 현재 배포 동작은 루트 README의 “CSV 파일 적재와 자원 관리”를 따른다. backend/db.py의 단일 계정 min=0/max=1 풀, scripts/load_mission_csv.py의 헤더 기반 로컬 파일 검사·500행 바인드 적재를 사용한다. 과거 행별 INSERT 생성 예시는 적용하지 않는다.
