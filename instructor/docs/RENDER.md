# Render 강사 시연 운영

학생과 동일한 FastAPI 분류 사이트를 단일 강사 DB 계정으로 실행한다. 학생별 실습·제출 시스템이 아니다.
이 개편에서는 실제 Render 배포나 Git push를 실행하지 않았다.

Build: bash instructor/scripts/render-build.sh
Start: bash instructor/scripts/render-start.sh
플랫폼 PORT를 사용하고 OML_BIND_HOST와 실행 --host/--port를 지원한다. 웹 프로세스는 하나만 실행한다.

필수 환경변수:
- SECRET_KEY: 32자 이상 임의 값
- OML_ACCESS_USER / OML_ACCESS_PASSWORD: 별도 웹 인증, 비밀번호 24자 이상
- DB_USER / DB_PASSWORD / DB_DSN: 강사 DB 계정
- WALLET_DIR=/etc/secrets 또는 배치한 Wallet 디렉터리
- WALLET_PASSWORD: Wallet 다운로드 당시 비밀번호
- ORACLE_CLIENT_LIB: Thin에서는 빈 값
- OML_ROSTER_FILE=/etc/secrets/students.json
- RENDER_EXTERNAL_HOSTNAME: 플랫폼 지정 또는 OML_ALLOWED_HOSTS에 정확한 호스트명 등록

Secret Files로 tnsnames.ora, ewallet.pem과 강사 식별정보 한 행의 students.json을 제공한다.
실제 비밀번호·개인 명단·Wallet을 Git에 넣지 않는다.
사이트 접근은 별도 Basic 인증 후 학번·이름·DB 비밀번호로 실제 DB 로그인을 거친다. 학생 배포 ZIP을 웹에서 제공하지 않는다.
학습데이터 화면에서 CSV 적재 시 고정 테이블 2개와 독립 OML_BASIC_RUN 프로시저 1개를 준비한다. 실제 연결·학습 결과만 표시한다.

브라우저 기본 인증 창은 Render 자체 계정이 아니라 OML_ACCESS_USER / OML_ACCESS_PASSWORD에 지정한 값이다. 학생 로컬 ZIP은 이 강사용 인증 계층을 포함하지 않는다. 학생 웹은 학번·이름·DB 비밀번호 로그인만 사용한다.
