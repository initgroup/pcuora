# 설치와 운영 안내

전체 따라하기 교재: 웹의 `/lesson/setup`. 웹을 아직 실행할 수 없을 때는 이 안내와 루트 README를 사용합니다. 기준 환경은 Windows x64 / Python 3.12이며 고정 패키지는 `reference/requirements.lock`, 오프라인 wheel은 `reference/wheels`, 설치파일과 공식 출처는 `reference/installers`에 있습니다. Node.js는 웹 실행에 필요하지 않습니다.

## 학생 PC 준비

1. 수업 ZIP을 `본인PC작업폴더\COM22417\본인학번\`에 풀고 VS Code에서 그 폴더를 엽니다.
2. `python --version`, `Get-Command python -All`, `py -0p`로 확인합니다. Launcher는 모든 설치를 표시하지 않을 수 있습니다. `python -c "import sys; print(sys.executable)"`로 실제 실행 경로도 확인합니다.
3. Python 3.12 x64가 없으면 동봉 설치파일을 사용합니다. 기본 Thick 연결용 VC++ x64 Runtime은 이미 호환 버전이 있으면 추가 설치하지 않습니다. Client 로드 실패 시 경로·x64 일치를 먼저 확인하고 Runtime 미설치·버전 부족일 때만 공식 설치파일을 사용합니다.
4. 확장(Ctrl+Shift+X)에서 `@installed`로 확인합니다. `code --list-extensions --show-versions`도 가능합니다. 없는 확장은 아래 명령 중 필요한 것만 실행합니다.

```powershell
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension ms-python.debugpy
code --install-extension oracle.sql-developer
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

5. `Python: Select Interpreter`에서 `.venv\Scripts\python.exe`를 선택합니다. 기존 터미널을 휴지통으로 종료하고 새 OML (.venv) 터미널을 만듭니다.
6. `python --version`은 3.12.x, `sys.executable`은 현재 폴더의 .venv, `sys.prefix != sys.base_prefix`는 True여야 합니다. 전체 확인은 `scripts/check-environment.ps1`입니다.
7. `security/student.env`에 자신의 STUDENT 번호·비밀번호를 넣고 `scripts/db-init.ps1`, `scripts/start.ps1`을 실행합니다.

VS Code 프로젝트 설정은 새 터미널에서 `terminal-init.ps1`을 실행합니다. 이 스크립트는 자신의 경로에서 프로젝트 루트를 계산하고 Activate.ps1을 dot-source합니다. Windows 전체의 사용자 프로필·PATH를 바꾸지 않습니다. 프로필은 `-NoProfile`로 시작하여 다른 수업의 Anaconda 자동 활성화와 분리합니다. VS Code가 복원한 예전 터미널은 닫고 새로 만드세요. 편집기 인터프리터 선택과 터미널 Python 경로는 각각 확인합니다.

설정 변경 전에 열린 터미널에는 적용되지 않습니다. 새 터미널이 다른 프로필이면 ▾ → 기본 프로필 선택 → OML (.venv)를 선택합니다. 가상환경은 상대경로 설정만으로 옮길 수 있는 파일 묶음이 아닙니다. PC나 프로젝트 경로를 옮길 때는 소스만 옮겨 .venv를 새로 생성합니다.

## 스크립트 목록

모든 PowerShell 스크립트는 `powershell -ExecutionPolicy Bypass -File 스크립트경로` 형식으로 실행할 수 있습니다. 다른 작업 폴더에서는 스크립트의 절대경로를 지정합니다. Bypass는 해당 프로세스에만 적용됩니다.

| 스크립트 | 역할 | 주요 옵션 |
|---|---|---|
| setup.ps1 | 가상환경·고정 패키지·Client 설치 | -PythonExe |
| terminal-init.ps1 | 새 터미널을 프로젝트 .venv로 활성화 | VS Code 기본 프로필이 호출 |
| check-environment.ps1 | Python·패키지·확장 확인 | 인증정보 조회 없음 |
| db-init.ps1 | 자기 스키마에 OML 객체와 샘플 준비 | -Profile student/teacher |
| verify-db.ps1 | 실제 DB 모델 학습·조회 검증 | -Profile student/teacher |
| start.ps1 | 숨김 서버 시작, PID·시작시간·로그 관리 | -Profile, -Port |
| stop.ps1 | 기록된 자기 프로젝트 서버만 종료 | DB 데이터는 유지 |
| restart.ps1 | 기존 프로필·포트로 재시작 | -Profile, -Port로 변경 가능 |
| backup.ps1 | 시간별 공개 소스 폴더 백업 | backups/ |
| compress.ps1 | 시간별 공개 소스 ZIP | backups/, SHA256 manifest |
| submit.ps1 | 학생의 소스·보고서 최종 제출 ZIP | -StudentId, downloads/COM22417_2026H2_학번.zip |

## 백업 복원과 배포 범위

소스 백업과 소스 ZIP에는 SQL·샘플 CSV·문서·잠금 목록이 포함됩니다. 실제 Oracle 데이터·학습모델·개인 .env·Wallet·설치파일·wheel은 포함하지 않습니다. 새 폴더에 복원하고 강사의 수업 ZIP에서 설치자료와 Wallet을 준비한 뒤 setup → 계정 설정 → db-init → start를 실행합니다. DB에 기존 OML 데이터가 있으면 초기화는 보존하므로, 소스 복원으로 DB 상태까지 되돌아가지는 않습니다.

학생 ZIP은 설치자료·wheel·Wallet을 포함하되 개인 인증정보는 제외합니다. 과제는 웹의 작성 항목을 보고 submission/report.pdf, report.html, report.txt 중 하나를 직접 작성하고 submit.ps1로 소스와 보고서를 묶어 제출하세요. 백업과 소스 압축은 `scripts/source_files.py`에 정의한 디렉터리·확장자만 처리합니다. 임의 파일을 추가한 경우 목록을 검토해야 합니다. 실제 비밀번호를 Python/SQL/문서에 직접 쓰지 않습니다.


학생 ZIP에는 Markdown 문서를 포함하지 않습니다. 시작 안내는 start-here.html, 상세 안내는 웹 교재에서 제공합니다. 강사 프로젝트의 이 참조 문서는 학생 배포 대상이 아닙니다.
