# Render 강사 시연 운영

학생과 동일한 FastAPI 분류 사이트를 단일 강사 DB 계정으로 실행한다. 학생별 실습·제출 시스템이 아니다.
Git main 반영 후 Render의 새 배포에서 적용한다. 실제 Render 배포 성공 여부는 배포 로그와 운영 화면으로 별도 확인한다.

Build: bash instructor/scripts/render-build.sh
Start: bash instructor/scripts/render-start.sh
플랫폼 PORT를 사용하고 OML_BIND_HOST와 실행 --host/--port를 지원한다. 웹 프로세스는 하나만 실행한다.

필수 환경변수:
- SECRET_KEY: 32자 이상 임의 값
- DB_USER / DB_PASSWORD / DB_DSN: 강사 DB 계정
- WALLET_DIR=/etc/secrets 또는 배치한 Wallet 디렉터리
- WALLET_PASSWORD: Wallet 다운로드 당시 비밀번호
- ORACLE_CLIENT_LIB: Thin에서는 빈 값
- OML_ROSTER_FILE=/etc/secrets/students.json
- RENDER_EXTERNAL_HOSTNAME: 플랫폼 지정 또는 OML_ALLOWED_HOSTS에 정확한 호스트명 등록

Secret Files로 tnsnames.ora, ewallet.pem과 강사 식별정보 한 행의 students.json을 제공한다.
실제 비밀번호·개인 명단·Wallet을 Git에 넣지 않는다.
사이트는 메인 인트로를 바로 표시하고, 메인 로그인에서 학번·이름·DB 비밀번호로 실제 DB 인증을 거친다. 로그인 전 업무 API와 강사 교재의 접근 검사는 유지한다. 학생 배포 ZIP을 웹에서 제공하지 않는다.
기본과제의 테이블 생성·프로시저 최초 등록 버튼으로 고정 테이블 3개(DATA·PREPARED·PREDICT)와 OML_BASIC_RUN 프로시저를 준비하고 CSV를 적재한다. 실제 연결·학습 결과만 표시한다.

OML_ACCESS_USER / OML_ACCESS_PASSWORD는 더 이상 읽거나 검사하지 않는다. Render Environment에 기존 키가 남아 있어도 무시되며 삭제해도 된다. 브라우저 기본 인증 팝업은 제공하지 않는다. SECRET_KEY·DB·Wallet·명단 설정은 계속 필요하다.

운영 인증 회귀 검사는 reference/tests/test_hosted_auth.py에서 기본 인증 없이 인트로 접근, 메인 로그인·로그아웃, 미로그인 API 차단·CSRF·강사 권한·Secure 쿠키·호스트 제한을 실제 Oracle 대신 격리된 연결 대역으로 확인한다.
