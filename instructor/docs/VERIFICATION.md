# 2026-11-17 단순화 검증

기본과제는 OML_BASIC_DATA·OML_BASIC_PREDICT와 OML_BASIC_RUN 하나다. 전환 전 소스는 backups/oml-source-20261117-085258-280311.zip, 구형 DB 원문·DDL·원본 행은 배포 제외 .local/simple-before-20261117/에 보관했다. 학습 720행과 예측 30행, 일반 마당서점 객체는 보존했다.

실제 Oracle에서 두 모델을 생성하고 동일 TEST 360행을 평가했다. RAW 46.9444%, CLEAN 57.7778%다. 이 결과는 현재 기본 주식 샘플의 결과이며 성능 향상을 보장하지 않는다. CLEAN 확정 후 실제 예측 30행을 확인했다.

미션·창의 복제본을 격리된 OML_QA_SIMPLE_* 이름으로 실행해 각 학습 720행·TEST 360행·예측 30행을 확인했다. 중복 키 적재 실패 시 이전 행 복원, 프로시저 컴파일 오류·인자 불일치 진단, 실제 SQL/DB 원문 반환을 검증한 뒤 검증 객체를 모두 제거했다. 기본 데이터는 유지했다.

브라우저에서 실제 로그인·조회 필터·SQL 로그·예측·드래그/키보드/ESC·소스 위치와 기본/미션/창의 반응형을 검증한다. 자동 검증은 reference/tests/verify_simple_browser.cjs, 결과는 runtime/simple-browser-verification.json이다. 로그인·CSRF·계정 전환·소스 허용 목록·학생 ZIP 개인정보 보호·제출 파일 검증은 test_*.py에 있다.

교재는 instructor/build_lecture.py로 실제 소스 20개를 재생성하고 instructor/verify_lecture.py로 줄·내용·해시·학생 배포 제외를 대조한다. 학생 가이드 경로·SQL 객체·도움말은 reference/tools/audit_student_content.py, 배포 ZIP은 reference/tools/verify_release.py로 현재 소스와 대조한다. 실제 Render 배포와 Git push는 수행하지 않았다.
