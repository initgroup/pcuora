# 강사용 Render 설정 안내

이 문서는 학생의 Windows 실습 설정과 별도입니다. 실제 비밀번호·Wallet 내용은 포함하지 않습니다. 현재 GitHub push와 Render 서비스 생성은 실행하지 않았습니다. 아래는 이번 소스에 추가한 `instructor/server.py` 기준 설정입니다.

## 1. 서비스 생성 화면

먼저 `instructor/scripts/deploy-github.ps1 -Push`로 검토한 최신 소스를 GitHub에 올립니다. Render에서 **New → Web Service → Git Provider**로 연결합니다. Static Site가 아닙니다.

| Render 항목 | 입력 |
|---|---|
| Repository | https://github.com/initgroup/pcuora.git |
| Branch | main |
| Name | pcuora-oml-classroom 등 사용 가능한 이름 |
| Language / Runtime | Python 3 |
| Root Directory | 비워 둠(저장소 루트) |
| Build Command | `bash instructor/scripts/render-build.sh` |
| Start Command | `bash instructor/scripts/render-start.sh` |
| Health Check Path | `/healthz` |
| Region | Oracle DB 위치와 접속 지연을 고려해 선택 |
| Instance count | 1. DB 작업 잠금은 한 프로세스 안에서만 적용됨 |

Windows용 setup.ps1·start.ps1과 동봉 Windows wheel/Oracle Client를 Render에서 실행하지 않습니다. Render는 Linux 패키지를 잠금 목록에서 설치합니다. 제공 진입점은 `0.0.0.0:$PORT`에 바인딩하며 PORT 기본값은 10000입니다. [Render Web Services](https://render.com/docs/web-services)

## 2. 실제 예제 온라인 시연: 기본 lab 설정

이번 서비스는 현재 만든 예제의 데이터 조회·학습·모델 상세·새 입력 예측·상관·연관규칙을 온라인에서 시연하기 위한 것입니다. 기본 모드는 lab입니다. 교재만 보여 주는 guide 모드는 선택 사항입니다.

Environment → Environment Variables에 아래 값을 직접 등록합니다. Value에는 .env 문법의 따옴표를 덧붙이지 않습니다.

| Key | Value | 설명 |
|---|---|---|
| PYTHON_VERSION | `3.12.10` | 명시적 수업 버전 |
| OML_SITE_MODE | `lab` | 기본값. 실제 예제 기능 활성화 |
| SECRET_KEY | 새 무작위 값 32자 이상 | 세션 서명. DB 비밀번호와 다른 값 |
| OML_ACCESS_USER | `instructor` | 온라인 시연 웹 로그인 계정 |
| OML_ACCESS_PASSWORD | 새 무작위 값 24자 이상 | 웹 로그인 비밀번호. DB 비밀번호와 별개 |
| DB_USER | `TEACHER01` 또는 별도 시연 계정 | PCUORA_TEACHER01은 표시 이름 |
| DB_PASSWORD | 해당 계정의 실제 비밀번호 | 로컬 teacher.env 값을 확인해 직접 입력. 파일을 배포하지 않음 |
| DB_DSN | `pcuora_low` | 서비스 별칭 |
| WALLET_DIR | `/etc/secrets` | 아래 Secret Files 경로 |
| WALLET_PASSWORD | Wallet 다운로드 당시의 암호 | DB 비밀번호와 별개. 이 작업에서는 미확보 |
| ORACLE_CLIENT_LIB | 비워 두거나 미등록 | Linux Thin 연결 사용 |
| PYTHONUNBUFFERED | `1` | 로그 즉시 출력 |

SECRET_KEY와 웹 로그인 암호는 각각 `python -c "import secrets; print(secrets.token_hex(32))"`로 새로 생성할 수 있습니다. 실제 값을 문서·소스·학생 ZIP에 저장하지 않습니다. Render의 HTTPS URL에 접속하고 웹 인증 후 실습실을 엽니다. 이 서비스는 강사 시연용 단일 DB 계정이며 학생들은 각자의 PC에서 STUDENT 계정으로 실습합니다.

RENDER_EXTERNAL_HOSTNAME은 자동 허용합니다. 별도 도메인은 OML_ALLOWED_HOSTS에 정확한 호스트명만 쉼표로 입력합니다. https://, 경로, *는 넣지 않습니다. OML_ENV_FILE과 WALLET_ZIP은 등록하지 않습니다. [환경변수와 Secret Files](https://render.com/docs/configure-environment-variables), [Python 버전](https://render.com/docs/python-version)

## 3. Build/Start 스크립트 조정

두 스크립트는 자신의 경로로 프로젝트 루트를 계산하므로 실행 작업 폴더에 의존하지 않습니다. Build는 Linux 패키지 설치·의존성 확인·구문 검사를 수행하고, Start는 같은 예제 앱을 실행합니다. DB 초기화·재학습은 자동으로 실행하지 않습니다.

| 조정 항목 | 기본값 | 설정 방법 |
|---|---|---|
| Python 실행파일 | python | OML_PYTHON 환경변수. 필요할 때만 지정 |
| 잠금 목록 | reference/requirements.lock | OML_REQUIREMENTS_FILE. 루트 기준 상대경로 또는 절대경로 |
| 바인딩 주소 | 0.0.0.0 | OML_BIND_HOST. Render에서는 기본값 사용 |
| 포트 | Render PORT 또는 10000 | PORT 환경변수 |
| 스레드 | 4 | OML_THREADS 환경변수 |
| 추가 pip 옵션 | 없음 | Build Command 뒤에 옵션 추가 |
| 추가 서버 옵션 | 없음 | Start Command 뒤에 --host/--port/--threads 추가 |

예: Build Command를 `bash instructor/scripts/render-build.sh --no-cache-dir`, Start Command를 `bash instructor/scripts/render-start.sh --threads 6`으로 조절할 수 있습니다. 기본 사용은 표의 두 명령만 입력하면 됩니다. 스크립트 수정은 instructor/에서 관리하며 학생 배포 ZIP에는 포함하지 않습니다.

## 4. Render Secret Files: Wallet 중 필요한 두 파일

로컬의 `security/Wallet_PCUORA.zip`을 안전한 임시 폴더에 열어 아래 두 파일을 확인하고 **Environment → Secret Files → Add Secret File**에 각각 등록합니다. ZIP 바이너리를 Contents에 붙여넣지 않습니다.

| Filename | Contents |
|---|---|
| `tnsnames.ora` | 동명 파일의 전체 원문 |
| `ewallet.pem` | 동명 파일의 전체 원문. BEGIN/END 줄과 줄바꿈 보존 |

Render의 Secret Files는 런타임에 `/etc/secrets/파일명`으로 제공됩니다. `ewallet.pem`은 암호화되어 있어도 비밀 파일로 취급하고 공개 저장소에 올리지 않습니다. python-oracledb Thin 모드는 두 파일과 Wallet 암호로 mTLS 연결합니다. 로컬 Windows Thick 모드에서 Wallet 암호 없이 접속되었다고 Thin에서도 암호를 생략할 수 있는 것은 아닙니다. [Render Secret Files](https://render.com/docs/configure-environment-variables), [python-oracledb 3.4.1 Autonomous DB 연결](https://python-oracledb.readthedocs.io/en/v3.4.1/user_guide/connection_handling.html)

Wallet 암호를 모르면 관리자에게 확인하거나 Oracle Cloud에서 적절한 Wallet을 다시 내려받고 새 암호를 기록해야 합니다. 이 작업에서는 기존 Wallet 암호를 추출하거나 Oracle Wallet을 교체하지 않았습니다.

## 5. DB 초기화·접속 확인

1. 대상 계정의 CREATE TABLE/VIEW/PROCEDURE/MINING MODEL 권한과 할당량을 확인합니다.
2. 그 계정으로 로컬 `db-init.ps1`을 실행해 OML_ 객체를 준비합니다. 현재 TEACHER01은 이미 초기화·실습 검증된 상태입니다. 다른 서비스 계정을 택하면 그 계정에 초기화를 해야 합니다. Build/Start Command에 매번 초기화·재학습을 붙이지 않습니다.
3. Oracle에서 IP 접근 제어를 사용한다면 Render 서비스의 **Connect → Outbound**에 표시된 범위를 확인해 해당 DB 접근 규칙에 반영합니다. 전체 네트워크를 무작정 개방하지 않습니다. 사설 전용 DB는 추가 네트워크 연결이 필요합니다. [Render Outbound IP](https://render.com/docs/outbound-ip-addresses)
4. Save and deploy 후 `/healthz`가 200인지 확인합니다. 이 경로는 웹 기동만 확인하며 DB 상태를 검사하지 않습니다.
5. lab 모드에서 인증 후 `/lab`의 ‘DB 연결 확인’을 누릅니다. 실제 접속 계정이 예상 계정인지 확인합니다. 오류 코드는 로그와 가이드로 확인하고 비밀번호를 로그에 출력하지 않습니다.
6. 실제 학습·예측은 해당 계정의 OML_ 데이터와 모델을 변경합니다. 로컬 강사 웹과 Render를 동시에 사용하여 같은 스키마를 수정하지 않습니다.

## 6. 한계와 운영 구분

- 기본 lab은 실제 DB 시연용입니다. 선택적으로 OML_SITE_MODE=guide를 쓰면 DB 기능을 비활성화하고 교재만 제공할 수 있습니다.
- Render 배포 및 Render에서 Oracle Thin 실제 연결은 아직 검증하지 않았습니다. 로컬에서 Render 모드의 호스트 검사·인증·DB 차단·Secret Files 경로 처리를 별도로 검사합니다.
- 무료 서비스는 유휴 시 중지될 수 있고 재시작·재배포 시 로컬 파일이 사라집니다. DB 모델은 Oracle에 저장되지만 runtime 파일이나 업로드 파일을 영구 저장소로 생각하지 마세요. 무료 요금제에는 Shell 제약도 있어 DB 초기화는 로컬에서 준비하는 흐름을 안내했습니다. [Render Free 제한](https://render.com/docs/free)
- 학생 ZIP에는 강사 환경파일이 없고, `student.env.example`은 STUDENT01·빈 비밀번호입니다. setup이 학생 개인 student.env를 만들고 학생이 본인 번호와 비밀번호를 입력합니다.
- Render 시연용 웹 인증은 학생별 평가·제출·권한 관리 시스템이 아닙니다. 학생 제출은 2026-12-18 18:00 KST까지 별도 공지한 제출처를 사용합니다.

Git·Render 관련 안내와 실행 도구는 instructor/에만 보관하며 학생 웹 교재·학생 ZIP·학생 제출 ZIP에 포함하지 않습니다. 학생에게 제공하는 웹페이지에는 이 운영 안내 링크를 노출하지 않습니다.
