"""Public classroom file map. No connection settings or private files are exposed."""
SOURCE_CATALOG = {
    'schema': dict(path='deploy/sql/01_schema.sql', title='테이블·뷰', purpose='OML_ 테이블, 컬럼·제약조건, 원본 주문에서 특성·라벨을 만드는 뷰, 학습용 뷰와 장바구니 뷰.'),
    'procedures': dict(path='deploy/sql/02_package.sql', title='PL/SQL 패키지', purpose='OML_LAB 명세와 본문. 샘플 특성 생성, 학습, 예측, 평가, 모델 상세·설정, 상관·연관규칙 처리.'),
    'python': dict(path='deploy/oml/app.py', title='웹 요청·DB 호출', purpose='API 경로, 업로드 적재 SQL, 조회 SQL, PL/SQL 호출과 JSON 응답. 화면과 DB를 연결하는 위치.'),
    'connection': dict(path='deploy/oml/db.py', title='DB 연결·결과 변환', purpose='본인 계정 설정 읽기, Wallet 연결, 커서 결과 변환, SYS_REFCURSOR를 받는 공통 result_set 함수.'),
    'validation': dict(path='deploy/oml/validation.py', title='입력·CSV 검증·지표', purpose='COLUMNS, LIMITS, validate_csv, numeric, metrics. 컬럼·범위·라벨·분리 조건과 이진분류 평가 수식.'),
    'initialize': dict(path='deploy/manage.py', title='초기화·샘플 적재', purpose='01/02 SQL 실행, 최초 원본 CSV 적재, 패키지 오류 확인, 서버 실행. initialize 함수가 실제 처리 순서를 결정.'),
    'lab-markup': dict(path='deploy/oml/templates/lab.html', title='실습 입력·결과 화면', purpose='실습 탭, 파일 업로드, 예측 입력 폼의 name/min/max와 결과 영역. 입력 특성 변경 시 함께 확인.'),
    'browser': dict(path='deploy/oml/static/app.js', title='브라우저 동작', purpose='버튼 이벤트, API 요청, dataColumns, 클래스 표시 이름 names, 모델·지표·확률 순위·산점도 출력.'),
    'sample-data': dict(path='deploy/data/classification.csv', title='분류 CSV 샘플', purpose='현재 샘플의 헤더·입력 특성·라벨·TRAIN/TEST 예시. 파일 수정만으로 DB가 바뀌지는 않음.'),
    'page-style': dict(path='deploy/oml/static/teaching.css', title='교육 화면 스타일', purpose='큰 글자·읽기 간격·표·입력창과 반응형 화면 설정. 모델의 계산과는 별개.'),
}

PROCEDURES = [
    ('REFRESH_SAMPLE', 'OML_DERIVED_FEATURES에서 특성·라벨을 복사하고 TRAIN/TEST를 나눔.', '관측 기간·라벨은 01_schema.sql의 뷰, 복사·분리는 이 프로시저. 현재 OML_FEATURES를 교체함.'),
    ('TRAIN_CLASSIFIER', '학습 데이터 조건을 확인하고 OML_REBUY_DT를 생성·갱신.', 'cfg 설정, data_query, case_id_column_name, target_column_name. 학습 입력은 OML_TRAIN_V.'),
    ('PREDICT_RANK', '네 입력을 받아 PREDICTION_SET의 클래스별 확률을 순위로 반환.', '인자·값 검증·특성 별칭·바인드 순서. Python 인자와 화면 name도 함께 변경.'),
    ('EVALUATE_MODEL', 'TEST 데이터의 실제 라벨·예측 라벨별 건수를 반환.', '평가 SELECT와 TEST 조건. Python metrics의 양성 클래스·지표도 함께 확인.'),
    ('MODEL_DETAILS / MODEL_SETTINGS', '학습된 모델의 분기·노드와 설정을 조회.', '모델명·상세 뷰·설정 조회 조건. 다른 알고리즘은 상세 조회 구조가 다를 수 있음.'),
    ('CORRELATION', 'TRAIN의 주문 횟수와 총액에 SQL CORR를 계산.', '집계 SELECT. 산점도의 점 데이터 조회는 app.py의 correlation에도 있음.'),
    ('TRAIN_RULES / RULES', 'OML_BASKET_AR를 학습하고 발견한 규칙을 조회.', '학습 설정·규칙 SELECT. 거래·품목 구성은 01_schema.sql의 OML_BASKET_V.'),
]
