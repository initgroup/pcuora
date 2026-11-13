# OML Classroom 학생 실습 안내

Python 웹과 Oracle PL/SQL로 분류모델의 원리·학습·평가·예측을 배우는 수업 소스입니다. 이론과 환경설정, 전처리, 실습과 개인 과제는 웹 교재에서 진행합니다.

## 설치와 실행

Windows x64 / Python 3.12가 기준입니다. 제공 ZIP을 `본인PC작업폴더\COM22417\본인학번\`에 풉니다. 설치 원본·출처는 reference/installers, 고정 패키지는 reference/requirements.lock과 reference/wheels에 있습니다. Python 3.12 x64와 Microsoft VC++ x64 Runtime을 준비하세요.

```powershell
python --version
Get-Command python -All
py -0p
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

VS Code에서 학번 폴더를 열고 Python: Select Interpreter로 `.venv/Scripts/python.exe`를 선택합니다. 기존 터미널을 종료하고 새 OML (.venv) 터미널을 만들면 가상환경을 자동 활성화합니다. 폰트는 VS Code 기존 설정을 따릅니다. 확인 명령은 `python -c "import sys; print(sys.executable); print(sys.prefix != sys.base_prefix)"`입니다.

setup이 만든 `security/student.env`에서 STUDENT01을 본인에게 배정된 STUDENT01~STUDENT20 중 자기 계정으로 바꾸고 비밀번호를 입력하세요. 제공 예제의 비밀번호는 비어 있습니다. 동봉된 Windows Client와 cwallet.sso를 사용하는 기본 Thick 연결에는 Wallet 암호가 필요하지 않습니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\db-init.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

http://127.0.0.1:8000 에서 교재를 엽니다. 실습실에서 DB 확인 → 데이터 확인 → 학습 → 새 입력 예측 순서로 실행합니다. 기존 BOOK/CUSTOMER/ORDERS는 변경하지 않고 자기 계정의 OML_ 객체만 사용합니다. 웹 글자는 기본 22px이며 우측 상단에서 조절합니다.

## 서비스와 소스 보관

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\restart.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\check-environment.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\backup.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\compress.ps1
```

모든 스크립트는 자신의 경로에서 루트를 계산합니다. 백업과 소스 ZIP은 backups/에 생성하며 개인 설정·Wallet·가상환경·로그·설치파일을 제외합니다. 다른 PC로 옮길 때 .venv를 복사하지 말고 새 위치에서 setup을 다시 실행하세요. 자세한 절차는 웹 `/lesson/setup`과 reference/docs/OPERATIONS.md에 있습니다.

## 개인 과제 제출

웹 `/lesson/assignment`의 미션·평가기준·주제 설명·시연 질문을 읽습니다. 본인 수행·이해도가 가장 중요한 평가 항목입니다. AI 도움은 허용하며 직접 실행·이해·검증한 과정을 설명해야 합니다. 타인의 과제를 복제해 이름만 바꾸어 제출하면 복제 제출용 제공자와 이용자 모두 감점·최하위 평가 대상입니다.

submission/의 REPORT.md, DATA_DICTIONARY.md, PROCESS_LOG.md, AI_USE.md를 작성하고 증거는 evidence/에 넣습니다. `[[작성]]`을 실제 내용으로 바꾼 뒤 본인 학번으로 포장합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\submit.ps1 -StudentId 20260001
```

결과 downloads/COM22417_2026H2_본인학번.zip을 직접 확인합니다. 소스와 보고서가 포함되며 개인 .env·비밀번호·Wallet은 제출하지 않습니다. 마감은 **2026년 12월 18일(금) 18:00 KST**입니다. 제출처는 수업 공지에서 별도 안내합니다. 포장 스크립트와 웹의 읽음 표시는 제출 완료가 아닙니다.

## 폴더

- deploy/: Python 웹 · SQL · 소량 샘플 CSV
- scripts/: 설치 · 터미널 · 서비스 · DB · 백업 · 제출 도구
- reference/: 설치자료 · 잠금 목록 · 문서 · 검증 코드
- security/: 제공 Wallet · 본인 계정 설정
- submission/: 작성할 보고서와 과정 기록
- runtime/: 실행 중 생성되는 파일 · 로그
- downloads/: 생성한 제출 ZIP

구현 샘플은 분류·상관분석·연관규칙 각각 한 가지입니다. 과제 주제는 설명만 제공하며 완성 소스나 정답 데이터는 제공하지 않습니다. 실제 DB 결과와 설명용 예시를 구분하세요.
