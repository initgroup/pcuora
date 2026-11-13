# OML Classroom — Oracle 26ai 교육·실습 웹

마당서점의 도서·고객·주문을 바탕으로 OML의 원리와 실습을 함께 학습하는 한국어 웹 교재입니다. Python Flask가 PL/SQL 프로시저를 호출하고, 실제 모델은 Oracle Cloud의 각 사용자 스키마에서 실행합니다.

## 빠른 시작

학생 ZIP을 `본인PC작업폴더\COM22417\본인학번\`에 풉니다. Python 3.12 x64가 필요합니다. Python 설치파일과 Oracle Instant Client는 `reference/installers/`에 있습니다. 기본 Windows Thick 연결에 필요한 VC++ x64 Runtime은 이미 호환 버전이 설치되어 있으면 추가 설치하지 않습니다. Client 로드 실패 시에만 아래 환경 가이드와 같은 폴더의 설치 안내를 확인하세요.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
# security/student.env에서 DB_USER와 DB_PASSWORD를 본인 계정으로 수정
powershell -ExecutionPolicy Bypass -File .\scripts\db-init.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

브라우저에서 **http://127.0.0.1:22417**을 엽니다. 로컬 기본 포트는 과목 코드에 맞춘 22417입니다. 이미 사용 중이면 start.ps1의 -Port 옵션으로 다른 포트를 지정하세요. DB 인증 전에도 이론·환경설정 교재는 읽을 수 있습니다. 모든 스크립트는 자신의 위치를 기준으로 경로를 계산합니다. 폴더를 옮겼다면 `.venv`는 복사하지 말고 새 위치에서 setup을 실행합니다.

**수업 화면:** 기본 본문 22px, 우측 상단 A−/A+로 18~30px 조절, ‘기본’으로 22px 복원. 선택은 브라우저에 저장되며 표·코드·실습 입력창에도 적용됩니다.

**VS Code 자동 가상환경:** 학번 폴더를 열고 setup 완료 후 `Python: Select Interpreter`에서 `.venv/Scripts/python.exe`를 선택합니다. 기존 터미널은 휴지통 버튼으로 종료하고 새 **OML (.venv)** 터미널을 만드세요. 제공된 시작 스크립트가 프로젝트 루트로 이동하고 가상환경을 활성화합니다. 복원된 옛 터미널은 새로 만들어야 합니다. 전역 PATH와 PowerShell 프로필은 변경하지 않습니다.

```powershell
python --version
python -c "import sys; print(sys.executable); print(sys.prefix != sys.base_prefix)"
code --list-extensions --show-versions
powershell -ExecutionPolicy Bypass -File .\scripts\check-environment.ps1
```

기대 결과는 Python 3.12.x, 프로젝트 `.venv` 경로, `True`입니다. Python Launcher 목록(`py -0p`)에 등록되지 않은 설치도 있을 수 있습니다. 자세한 버전 확인·확장 설치·터미널 설정·운영 절차는 웹의 **02. VS Code 실습환경 준비**와 [설치·운영 안내](reference/docs/OPERATIONS.md)에 있습니다.

기본 학생 연결은 동봉된 Instant Client + `cwallet.sso`(Thick)입니다. Wallet 암호를 별도로 입력할 필요가 없고 **자기 DB 계정의 비밀번호는 반드시 필요**합니다. Thin을 원하면 `.env`의 `ORACLE_CLIENT_LIB`를 비우고 `WALLET_PASSWORD`를 입력합니다. `.env`는 재시작 후 다시 적용됩니다.

```powershell
# 종료 / 재시작 / 포트 변경
powershell -ExecutionPolicy Bypass -File .\scripts\stop.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\restart.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1 -Port 22418

# 강사 PC: 개인 설정 security/teacher.env 사용
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1 -Profile teacher
```

## 제공 내용

- **7개 교재 장:** OML 개요, VS Code 환경, 전처리·라벨, 분류, 상관, 연관규칙, 개인 과제.
- **분류 1개:** 다음 달 재구매 이진분류, Decision Tree, `OML_REBUY_DT`.
- **상관분석 1개:** 학습용 고객의 주문 횟수와 총 결제액, SQL `CORR`. 학습모델과 구분합니다.
- **연관규칙 1개:** 같은 주문의 도서 분야 조합, Apriori, `OML_BASKET_AR`.
- CSV 검증·적용, 원본 주문에서 특성 재생성, 실제 모델 구조·설정 조회, TEST 혼동행렬·정밀도·재현율·F1, 새 입력의 클래스별 확률 순위, 상관 산점도, 규칙 조회, 평가 JSON 다운로드.
- 모델의 원리와 누수·과적합·확률 해석의 한계까지 설명하며, 과제용 별도 정답 구현은 제공하지 않습니다.
- **개인 과제:** 본인 수행·이해도 40점을 중심으로 한 100점 평가, 구현 코드 없는 주제 설명 12개, AI 활용·복제 기준, 시연 질문과 보고서 작성 항목을 웹에서 제공합니다. 마감은 **2026년 12월 18일(금) 18:00 KST**, 제출처는 별도 수업 공지입니다. 웹 자체의 과제 접수 기능은 없습니다.

## 데이터와 객체

도서 8종, 가상 고객 120명, 주문 상세 1,017행입니다. 실제 개인정보가 아닙니다. 2026-07-01 이상 10-01 미만의 주문을 특성으로, 10-01 이상 11-01 미만 주문의 존재 여부를 라벨로 사용합니다. 고정 분리 결과 TRAIN 97명, TEST 23명입니다.

`OML_BOOK`, `OML_CUSTOMER`, `OML_ORDERS`, `OML_FEATURES`, `OML_LAB_STATE`, 3개 뷰, `OML_LAB` 패키지를 사용합니다. 기존 BOOK/CUSTOMER/ORDERS 테이블과 다른 학생 스키마는 변경하지 않습니다. 초기화 재실행은 데이터를 보존하며, 샘플 복원·CSV 적용은 해당 사용자의 `OML_FEATURES`만 교체합니다. 재학습은 이름이 고정된 해당 실습 모델만 갱신합니다.

학습은 DDL을 포함하므로 업로드 커밋과 분리합니다. 데이터 버전과 모델 버전이 다르면 예측·평가를 차단합니다. 로컬 웹의 DB 작업은 한 번에 하나로 제한합니다. 여러 웹 프로세스로 동일 스키마를 동시에 변경하는 운영 환경은 지원 범위가 아닙니다.

## 디렉터리

| 경로 | 목적 |
|---|---|
| `deploy/` | 배포할 Python 웹, HTML/CSS/JS, SQL, CSV |
| `reference/docs/` | 설치·설계·권한·검증 문서 |
| `reference/requirements.lock` | 전이 의존성을 포함한 고정 버전 |
| `reference/wheels/` | Windows x64 / CPython 3.12용 오프라인 wheel |
| `reference/installers/` | Python, Oracle Client 설치 원본과 출처 |
| `reference/tests/` | 데이터 검증·HTTP·실제 DB 통합 검사 |
| `reference/tools/` | 강사용 샘플 생성 및 로컬 도구. 학생 ZIP에서 제외 |
| `scripts/` | 설치·터미널 활성화·점검·서비스·DB·백업·압축·GitHub 배포 |
| `security/` | Wallet과 개인 .env. Wallet ZIP만 명시적으로 학생 배포에 포함 |
| `runtime/` | 추출 Wallet, Oracle Client, PID, 로그, 검증 결과. 배포 제외 |
| `downloads/` | 생성한 학생 실습 ZIP. Git 제외 |
| `backups/` | 시간별 소스 백업 폴더·ZIP. Git 및 학생 ZIP 제외 |
| `instructor/` | 강사용 배포 스크립트·서버 진입점·운영 문서·검사. 학생 ZIP 제외 |
| `submission/` | 학생이 작성할 보고서·데이터 명세·과정 기록·AI 활용 기록·실행 증거 |

## 학생 배포

학생 웹 교재와 학생 ZIP에는 배포·호스팅 안내를 포함하지 않습니다. 학생 ZIP에서는 README·AGENTS·보고서 양식을 포함한 모든 Markdown 파일을 제외합니다. 시작 안내는 start-here.html로 제공하고 상세 교육·제출 안내는 웹에서 읽습니다. instructor/ 및 강사용 검사·포장 도구도 제외합니다. VS Code 글자 크기를 강제하지 않습니다.


```powershell
# (.venv) PowerShell, 프로젝트 루트에서 학생 제공용 ZIP 생성
& .\scripts\package.ps1

# 실행 정책이 제한된 다른 터미널에서 실행할 때
powershell -ExecutionPolicy Bypass -File .\scripts\package.ps1
```

생성 스크립트는 `scripts/package.ps1`이며 내부에서 `scripts/package_student.py`를 실행합니다. 파일명은 **`downloads/oml-student-kit-YYYYMMDD-NNN.zip`**입니다. 한국시간의 날짜와 당일 순번을 사용합니다. 예: `oml-student-kit-20261113-001.zip`, 같은 날 다시 생성하면 `oml-student-kit-20261113-002.zip`. 이전 ZIP은 덮어쓰지 않으며 날짜가 바뀌면 001부터 시작합니다. 실패한 생성 작업이나 사용 중인 예약 번호가 있으면 순번이 건너뛸 수 있습니다.

웹의 **소스·수정 위치**에 있는 ZIP 다운로드는 완료된 버전 중 최신 파일을 내려줍니다. 다운로드 주소 `/download/student.zip`은 그대로 사용하며 실제 저장 파일명은 날짜-순번입니다. 명시적 허용 목록으로 묶으며 강사·학생 `.env`, DB 비밀번호, `.venv`, 로그, 개인 도구는 포함하지 않습니다. 사용자의 요청에 따라 `security/Wallet_PCUORA.zip`은 포함합니다. 수업 참여자에게만 배포하세요. 파일별 SHA256은 ZIP 내부 `MANIFEST.sha256.json`에 기록됩니다.

서비스 실행·중지·재시작·소스 백업·학생 ZIP 생성·Git 배포의 주석이 붙은 명령 모음은 이 PC의 **`.local/operations-commands.txt`**에 있습니다. 가상환경 PowerShell에서 필요한 명령만 선택해 실행합니다. 이 파일은 Git 무시 규칙과 배포 허용 목록으로 Git·소스 백업·학생 ZIP·과제 제출 ZIP에서 제외합니다. 복제한 저장소에는 이 로컬 파일이 없으며 이 PC에서만 보관합니다.

학생 과제 제출에는 Wallet과 `.env`를 제외합니다. ZIP에 든 환경 예제의 `STUDENT01`은 학생이 자기 번호로 바꿔야 합니다. 프로그램이 20개 학생 계정을 생성하거나 비밀번호를 변경하지 않습니다.

학생 ZIP 생성은 공개 소스 목록에 설치 원본·wheel·원본 Wallet만 더합니다. **teacher.env·tearher.env·student.env 등 모든 개인 .env를 제외**하고, student.env.example이 STUDENT01·빈 비밀번호인지 검사합니다. setup이 이 예제로 학생 개인 설정을 만듭니다. 배포에 실패하면 기존 ZIP을 보존합니다. security에 설정된 비밀번호·토큰이 소스에 복사된 경우도 포장을 중단합니다. 이미지·임의 인코딩으로 숨긴 비밀까지 판별하는 도구는 아니므로 자료를 직접 확인하세요.

## 개인 과제 제출

웹 `/lesson/assignment`의 미션·100점 평가표·주제 설명·시연 질문을 읽습니다. 직접 코딩을 권장하고 AI는 보조적으로 활용합니다. 학생이 submission 폴더를 만들고 report.pdf, report.html, report.txt 중 하나로 보고서를 직접 작성하며 문제·데이터 명세·수행 과정·AI 사용/미사용을 포함합니다. 증거는 submission/evidence/에 넣습니다. 배포용 보고서 양식은 제공하지 않습니다. AI 사용 자체는 감점하지 않으며 본인의 실행·이해·검증을 평가합니다. 다른 학생의 과제를 복제하여 이름만 바꾸어 제출하면 복제 제출용으로 제공한 사람과 이용한 사람 모두 감점·최하위 평가 대상입니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\submit.ps1 -StudentId 20260001
```

실제 학번을 사용하세요. 결과는 `downloads/COM22417_2026H2_학번.zip`이며 내부를 source/와 report/로 구분합니다. 보고서 유무·허용 형식·텍스트/HTML의 학번 일치·금지 파일·등록된 비밀값을 검사합니다. PDF의 학번과 내용은 직접 확인해야 합니다. 스크립트는 포장만 합니다. ZIP을 직접 확인한 후 **2026-12-18 18:00 KST**까지 공지한 제출처에 올립니다.

## Render 설정은 별도 안내

[강사용 Render 설정](instructor/docs/RENDER.md)에 서비스 항목·환경변수·Secret Files·Oracle 연결 확인을 정리했습니다. Start Command는 `bash instructor/scripts/render-start.sh`, 기본은 실제 학습·조회·예측을 제공하는 `OML_SITE_MODE=lab`입니다. 강사 예제를 온라인에서 시연하며 별도 웹 인증과 DB 환경변수를 설정합니다. 학생 PC에서는 기존 start.ps1과 STUDENT 설정을 사용합니다.

현재 GitHub push와 Render 배포는 수행하지 않았습니다. Render는 Linux Thin 연결을 사용하므로 Wallet 암호와 Secret Files 설정이 필요합니다. 실제 비밀번호는 안내 문서에 포함하지 않습니다.

## 소스 백업·압축과 GitHub 배포

```powershell
# 시간별 폴더 / 시간별 ZIP (backups/)
powershell -ExecutionPolicy Bypass -File .\scripts\backup.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\compress.ps1

# 기본 대상 https://github.com/initgroup/pcuora.git, 브랜치 main
# 기본 실행: 파일 목록만 표시, 원격 변경 없음
powershell -ExecutionPolicy Bypass -File .\instructor\scripts\deploy-github.ps1

# 로컬 commit 준비 / 실제 push
powershell -ExecutionPolicy Bypass -File .\instructor\scripts\deploy-github.ps1 -Prepare
powershell -ExecutionPolicy Bypass -File .\instructor\scripts\deploy-github.ps1 -Push
```

Git for Windows와 저장소 쓰기 권한이 필요합니다. Git 작성자 정보가 없으면 `-AuthorName "본인 이름" -AuthorEmail "본인 GitHub 이메일"`을 지정하세요. Git Credential Manager로 인증하며 토큰을 URL에 넣지 않습니다. `-Repository`와 `-Branch`로 본인 저장소를 지정할 수 있습니다.

백업·압축·Git은 `scripts/source_files.py`의 허용 목록을 공유합니다. 소스·SQL·샘플 CSV·문서·잠금 목록만 포함하고, **Wallet·개인 .env·설치파일·wheel·로그·.venv는 제외**합니다. DB 데이터나 모델 백업이 아닙니다. 소스에 비밀번호를 직접 쓰지 마세요. 새 파일 형식이나 디렉터리를 추가했다면 허용 목록도 검토합니다.

Git은 `runtime/github-…`의 별도 checkout에서 커밋하며 기존 작업 폴더의 Git 상태를 변경하지 않습니다. 강제 push하지 않고, 이전 배포 manifest에 기록된 파일만 갱신·삭제합니다. 관리되지 않은 기존 저장소나 예상 외 파일은 자동 덮어쓰지 않고 중단합니다. GitHub 코드는 웹 서버 호스팅과 별개입니다. Git clone으로 설치할 경우 학생 패키지의 설치자료·Wallet을 별도로 준비하세요. 복원 절차와 스크립트별 범위는 [설치·운영 안내](reference/docs/OPERATIONS.md)에 있습니다.

## 검증

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s reference/tests -p "test_*.py" -v
# 선택: Node.js가 설치된 개발 PC에서 글자 크기 동작 검사
node --test .\reference\tests\test_reading.js
.\.venv\Scripts\python.exe -m unittest discover -s instructor/tests -p "test_*.py" -v
powershell -ExecutionPolicy Bypass -File .\scripts\verify-db.ps1 -Profile teacher
# API 통합 검사는 현재 실습 데이터 교체와 재학습을 수행하므로 샘플 실습 계정에서만 실행
$env:OML_ENV_FILE='security/teacher.env'
.\.venv\Scripts\python.exe .\reference\tests\integration_db.py
```

실제 TEACHER01 계정·Oracle `23.26.4.1.0`에서 테이블·패키지 생성, 두 모델 학습, 예측 순위, 평가, 모델 상세, 상관, 규칙을 검증했습니다. Oracle 26ai는 23.26 계열 버전 문자열을 사용합니다. 실제 검증 근거와 제약은 `instructor/docs/VERIFICATION.md`에 기록합니다. 브라우저 시각 검증은 도구가 현재 URL을 확신하지 못해 중단되어 미완료입니다.

공식 참고: [DBMS_DATA_MINING](https://docs.oracle.com/en/database/oracle/oracle-database/26/arpls/DBMS_DATA_MINING.html), [CORR](https://docs.oracle.com/en/database/oracle/oracle-database/26/sqlrf/CORR.html), [python-oracledb](https://python-oracledb.readthedocs.io/en/v3.4.1/user_guide/connection_handling.html), [26ai Client 버전 안내](https://www.oracle.com/database/technologies/instant-client/winx64-64-downloads.html).

## 웹 소스·수정 안내

웹 `/sources`에서 파일 경로·목적, OML_LAB 프로시저별 역할, SQL 쿼리 위치, 변경 목표에 따른 연관 파일, DB 반영·컴파일 진단을 제공합니다. 같은 공통 샘플을 설명하며 과제용 추가 구현은 제공하지 않습니다. 특히 기존 테이블은 db-init만으로 컬럼 구조가 바뀌지 않으며 별도 변경문을 직접 반영해야 함을 안내합니다. 개인 환경파일은 소스 뷰어의 허용 목록에 넣지 않습니다.
