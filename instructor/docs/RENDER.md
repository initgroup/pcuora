# Render 운영
학생과 강사는 같은 backend/hosting.py·scripts/render-build.sh·scripts/render-start.sh를 사용한다. 학생 ZIP에 공통 실행 파일을 포함한다. 서비스 하나당 본인의 DB 계정 하나·프로세스 하나를 사용한다. 통합 안내 downloads/COM22417_과제설명및평가.html의 ‘04 Git·Render 배포’가 화면별 상세 절차다.

| 항목 | 설정 |
| --- | --- |
| Source | 본인 Git Provider → GitHub 저장소 |
| Branch | main |
| Language | Python 3 |
| Root Directory | 비움 (app.py가 있는 저장소 루트) |
| Build Command | bash scripts/render-build.sh |
| Start Command | bash scripts/render-start.sh |
| Health Check Path | /healthz |
| Auto-Deploy | On Commit |

기존 강사 instructor/scripts/render-build.sh·render-start.sh와 instructor/server.py도 공통 구현에 위임한다. Git 반영과 Render 배포 성공은 구분하고 Live의 커밋을 확인한다.

필수 환경변수:
- PYTHON_VERSION=3.12.10 / PYTHONUNBUFFERED=1
- SECRET_KEY: 서비스마다 생성한 32자 이상 난수 (실제 값은 Render에만 입력)
- DB_USER / DB_PASSWORD / DB_DSN: 본인 DB 계정·비밀번호·Wallet의 DSN 별칭 (예: pcuora_high)
- WALLET_DIR=/etc/secrets / WALLET_PASSWORD: Wallet 다운로드 당시 암호
- ORACLE_CLIENT_LIB: Thin에서는 빈 값

PORT·RENDER_EXTERNAL_HOSTNAME은 Render가 제공한다. 사용자 도메인은 OML_ALLOWED_HOSTS에 정확한 호스트명을 추가한다. OML_SITE_MODE=lab은 현재 소스에서 읽지 않는다. OML_ACCESS_USER·OML_ACCESS_PASSWORD도 사용하지 않으며 브라우저 Basic 인증 팝업은 없다.

학생 본인 Git에는 한 행의 security/students.json을 포함한다. 강사 전체 명단·비밀번호·환경파일·Wallet은 포함하지 않는다. Wallet의 tnsnames.ora·ewallet.pem만 Secret Files에 등록한다. Render 메인에서 학번·이름이 일치하면 JSON의 db_user를 사용하고 서버 환경변수 DB_PASSWORD로 Oracle에 연결한다. 클라이언트 DB 계정·비밀번호와 기존 로컬 환경파일은 운영 인증에 사용하지 않는다. DB_USER는 선택 기본값이며 JSON 매핑을 우선한다. Git 명단이 있으면 OML_ROSTER_FILE·Secret Files 명단보다 우선한다. 강사 운영처럼 Git 명단이 없을 때만 OML_ROSTER_FILE을 대체 경로로 사용한다.

Save, rebuild, and deploy 후 /healthz의 {"status":"ok"}와 메인 연결 테스트를 각각 확인한다. healthz는 DB를 조회하지 않는다. 로그인 전 업무 API 차단·CSRF·Secure 쿠키·강사 교재 권한을 유지한다. 검사는 reference/tests/test_hosted_auth.py와 학생 ZIP·Git 관련 검사에서 격리 실행하며 실제 학생 DB를 변경하지 않는다.

공식 참고: https://render.com/docs/web-services · https://render.com/docs/configure-environment-variables · https://render.com/docs/python-version · https://render.com/docs/deploys · https://render.com/docs/health-checks
