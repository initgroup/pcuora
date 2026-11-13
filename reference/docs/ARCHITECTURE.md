# 교육용 구조와 실습 규약

브라우저 → Flask API → python-oracledb → 현재 계정의 OML_LAB → DBMS_DATA_MINING / SQL 분석 순서입니다. 별도 로컬 머신러닝 라이브러리나 가짜 모델을 사용하지 않습니다. 정적 교재는 DB 연결 없이 읽을 수 있습니다.

| 웹 작업 | DB 구현 |
|---|---|
| 초기 테이블·샘플 | manage.py init, 01_schema.sql, books/customers/orders.csv |
| 원본 특성 생성 | OML_DERIVED_FEATURES, OML_LAB.REFRESH_SAMPLE |
| CSV 교체 | Python 전체 파일 검증 → 바인드 INSERT → 데이터 버전 증가 → 커밋 |
| 분류 학습 | OML_LAB.TRAIN_CLASSIFIER → CREATE_MODEL2 |
| 새 입력 예측 | OML_LAB.PREDICT_RANK → PREDICTION_SET → SYS_REFCURSOR |
| 평가 | OML_LAB.EVALUATE_MODEL → TEST의 PREDICTION 집계 |
| 모델 노드 | OML_LAB.MODEL_DETAILS → DM$VOOML_REBUY_DT |
| 상관 | OML_LAB.CORRELATION → CORR |
| 규칙 | OML_LAB.TRAIN_RULES, RULES → DM$VAOML_BASKET_AR |

현재 분류는 4개 수치 특성의 이진분류이며, 임의 열·알고리즘·사용자 SQL 실행기는 제공하지 않습니다. 다른 분류 과제에서는 스키마·검증기·PL/SQL·입력 폼·지표를 목적에 맞게 수정해야 합니다.

CSV: UTF-8, BOM 허용, 헤더 순서 고정, 30~1000행, 2MB 이하. 고객 ID 고유, 숫자 유한성 검사, 누락·추가 열 거부. TRAIN/TEST 각 라벨 최소 3개. 숫자 범위는 validation.py 및 DB CHECK 제약으로 일치시킵니다. 식별자·SPLIT·미래 정답은 예측 특성에 포함하지 않습니다.

모델 관리: 업로드 후 MODEL_REV=NULL, 학습 완료 후 MODEL_REV=DATA_REV. 모델 생성 실패 시 이전 모델을 계속 유효한 것으로 표시하지 않습니다. CREATE_MODEL2가 DDL을 실행하므로 기존 모델 교체 전체는 트랜잭션 롤백 대상이 아닙니다. 데이터가 보존되므로 실패 원인을 해결한 뒤 재학습합니다.

동시성: 학생별 노트북 1개 프로세스·스키마 1개를 가정합니다. 프로세스 내 DB 작업 mutex로 학습 중 업로드·예측을 막습니다. 다른 SQL Developer 세션이나 중복 실행에서 같은 스키마의 OML_ 객체를 수정하는 것은 학생이 피해야 합니다. 중앙 멀티사용자 서비스는 별도 인증·동시성 설계가 필요합니다.

접속: 기본은 상대경로 Instant Client + Wallet 자동 로그인(Thick), 선택은 암호화 PEM + Wallet 암호(Thin). Wallet ZIP 원본을 바꾸지 않고 runtime에 필요한 파일만 추출합니다. tnsnames의 재시도 횟수를 0, 접속 시간을 제한하고 sqlnet Wallet 경로를 현재 위치로 작성합니다. TLS 이름 검증은 유지합니다.

HTTP: loopback 바인딩, Host 허용 목록, 세션 CSRF 토큰, SameSite/HttpOnly 쿠키, 업로드 제한, 비밀정보를 포함하지 않는 오류 메시지, 고정 소스 파일 허용 목록. runtime/security는 정적 파일 경로가 아니며 ZIP의 Wallet만 의도적으로 내려받습니다.
