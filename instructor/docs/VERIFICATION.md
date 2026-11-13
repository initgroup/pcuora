# 검증 기록

학생 ZIP 날짜-순번 및 로컬 운영 명령 모음 변경:

- 파일명은 한국 날짜 기준 oml-student-kit-YYYYMMDD-NNN.zip이며 완료된 기존 파일은 덮어쓰지 않는다. 기존 고정 이름 ZIP은 내용 변경 없이 20261113-001로 보존했고 새 버전은 20261113-002로 생성했다.
- 웹 /download/student.zip은 생성 중인 예약 파일을 제외하고 날짜·순번상 최신 완료본을 선택한다. 실제 내려받는 이름도 버전 파일명이다.
- 학생용 18개와 강사용 27개 Python 검사 통과. 한국시간 날짜 경계·일일 순번·동시 생성의 이름 충돌 방지·실패 후 부분 ZIP 제거·이전 버전 보존·최신 다운로드 이름을 확인했다.
- .local/operations-commands.txt에 (.venv) PowerShell의 서비스 시작·중지·재시작·백업·학생 ZIP 생성·Git 배포 명령을 주석과 함께 모았다. 텍스트 파일이므로 명령을 선택해 실행하며 일괄 실행용 스크립트가 아니다.
- /.local/ Git 무시 규칙, 전체/학생 소스 허용 목록 제외, 임시 로컬 저장소 배포에서 로컬 명령 파일 미포함을 확인했다. 실제 GitHub에는 push하지 않았다.

웹 소스·수정 안내 추가:

- /sources에 제공 파일 10개의 실제 경로·목적·읽기 링크, OML_LAB 프로시저 7개 그룹, SQL 쿼리 위치, 변경 목표별 연관 파일, DB·웹 반영 절차와 읽기 전용 진단 쿼리를 제공한다.
- 초기화 코드의 실제 동작을 확인해 기존 CREATE TABLE 중복은 건너뛰며 기존 컬럼은 자동 변경하지 않음을 설명한다. 사용자 작성 추가 SQL은 자동 실행되지 않으며 직접 반영해야 함을 명시한다.
- SQL 컴파일, 데이터 재생성, Python 재시작, 모델 재학습과 브라우저 새로고침을 구분한다. 추가 과제의 구현 소스는 제공하지 않는다.
- Python/Flask 검사 18개 통과. 공개 소스 허용 목록 10개·JSON 응답·DB 비호출·개인 설정 경로 거부를 확인했다. 10개 페이지의 내부 링크·절·실습 탭 241개, 모든 소스 경로와 문서의 프로시저명이 실제 정의와 일치함을 확인했다.

학생용 Markdown 제외 변경:

- 학생용 배포·제출 목록은 .md/.MD/.markdown 파일을 모두 제외한다. 루트 README·AGENTS·설치 안내·운영 문서·보고서 양식도 제외 대상이다. 강사 프로젝트의 README.md·AGENTS.md는 로컬에서 계속 유지한다.
- 학생 시작 안내는 start-here.html, 상세 안내는 웹 교재에서 제공한다. AI 작업 지침 파일을 다른 확장자로 바꾸어 제공하지 않는다.
- 직접 코딩을 권장하며 AI는 보조적으로 활용한다는 내용을 웹에 반영했다. 보고서는 학생이 report.pdf/report.html/report.txt 중 하나로 직접 작성한다.
- 학생용 17개 및 강사용 19개 Python 검사 통과. 대소문자 Markdown 제외, 보고서 누락·텍스트 학번 불일치·HTML 보고서·복수 형식 충돌·잘못된 PDF 헤더를 검사했다. 강사 문서 없이 실행하는 학생 백업·제출 경로를 별도로 확인한다.

최근 변경: Git·Render 운영 도구·문서·검사는 instructor/로 분리했습니다. 학생 웹에서는 배포 안내를 제거하고 학생 ZIP은 전용 README·AGENTS와 학생 도구 허용 목록을 사용합니다. VS Code 편집기·터미널의 프로젝트 fontSize 강제값을 제거했습니다. 웹 교재의 큰 글자 설정은 유지합니다.

Render는 실제 예제의 lab 모드를 기본으로 실행합니다. Build Command는 `bash instructor/scripts/render-build.sh`, Start Command는 `bash instructor/scripts/render-start.sh`입니다. Git Bash에서 두 스크립트의 문법 및 다른 작업 폴더에서 Build(동봉 wheel로 오프라인 검사)·Start 도움말의 정상 동작을 확인했습니다. 실제 Render Linux 배포 및 Thin 접속은 이 검증과 구분합니다.

검증일: 2026-11-13 (한국 표준시 기준)

## 실제 Oracle Cloud

- 기존 VS Code 연결 PCUORA_TEACHER01의 실제 계정 TEACHER01 사용.
- DB 반환 버전: `23.26.4.1.0`.
- CREATE TABLE / VIEW / PROCEDURE / MINING MODEL 권한 확인.
- 독립 OML_ 테이블·뷰·OML_LAB 패키지 생성 및 컴파일 성공.
- 기존 마당서점 테이블은 변경하지 않음. 학생 20개 계정은 변경하지 않음.
- 도서 8종, 고객 120명, 주문 상세 1,017행, TRAIN 97명 / TEST 23명.
- OML_REBUY_DT 생성, 노드 3개·설정 15개 조회.
- 기본 입력 (6회, 180,000원, 경과 7일, 분야 3개): REBUY 58.49%, NO_REBUY 41.51%.
- TEST 혼동행렬: TP 6 / TN 12 / FP 2 / FN 3. 정확도 78.26%, 정밀도 75.00%, 재현율 66.67%, F1 70.59%.
- TRAIN 다수 클래스(NO_REBUY)를 항상 예측하는 기준의 TEST 정확도: 60.87%.
- TRAIN 주문 횟수·총액 Pearson r: 0.963538.
- OML_BASKET_AR 생성 및 거래형 상세 뷰에서 규칙 6개 조회.

이는 합성 데이터의 동작 검증 결과이며 실제 고객에 대한 일반화 성능이 아닙니다. 모델·데이터를 바꾸면 값도 달라집니다.

## 연결과 코드

- 기존 Oracle Client 21c를 사용한 Thick 연결 성공.
- 배포할 Instant Client Basic Light 23.26.4를 프로젝트 상대경로에서 로드한 연결 성공.
- 위 배포용 Client로 실제 DB API 검사 18개 통과: CSV 검증·업로드, 잘못된 CSV의 비변경, 데이터 변경 후 예측 차단, 재학습, 확률 합계·정렬, 잘못된 숫자 거부, 평가·구조·설정·상관·규칙·결과 JSON·샘플 복원.
- 마지막 상태는 원본 샘플 복원 후 분류모델 학습 완료.
- Python/Flask 검사 17개 통과: 결측·중복·NaN/Infinity·범위·라벨·분리 검증, 평가 수식, 모든 교재/자산 HTTP 200, CSRF, Host 검사, 비밀 경로 차단, 업로드 크기 제한.
- Python 컴파일 및 JavaScript 문법 검사 통과.
- Python 설치파일 PSF 서명 Valid, Oracle Client ZIP의 공식 SHA256 일치.
- 학생 ZIP을 공백이 있는 다른 경로 `runtime/relocation check/COM22417/20260001`에 풀어 새로운 가상환경을 만들고, 동봉 wheel만으로 오프라인 설치 성공.
- 다른 작업 디렉터리에서 새 경로의 Wallet·Instant Client를 이용한 실제 DB 연결 성공. 인증은 기존 강사 설정 파일을 읽었고 복사본에 저장하지 않음.
- 이동한 복사본의 시작·재시작·종료 스크립트 정상 동작. 검증용 복사본 서버는 종료함.
- 학생 ZIP 파일별 SHA256 검증, 원본 Wallet 일치, 개인 .env·비밀번호·runtime·개인 도구 미포함 확인.
- 교재 내부 링크·절 앵커 209개 정적 검증 통과.
- 실행 중인 Waitress 서버에서 실제 HTTP로 교재·자산·DB 상태·모델·규칙·상관 조회, CSRF 쿠키를 포함한 예측 POST, 학생 ZIP 다운로드 응답(200)을 확인함.

실행별 자세한 결과는 배포 제외인 `runtime/db-verification.json`, `runtime/api-verification.json`에 남습니다.

## 환경 가이드·배포 스크립트·큰 글자 추가 검증

- 2026-11-13: Python 검사 23개 통과. 기존 17개에 공개 소스 제외 목록, 경로 이탈 거부, 로컬 prepare의 원격 비변경, 최초 배포·수정·소스 삭제, 관리되지 않은 원격 파일 보존, 잘못된 원격 manifest 거부 검사를 추가함.
- Git 배포 검사는 임시 로컬 bare 저장소에서 수행함. 실제 GitHub 저장소는 읽기 전용 ls-remote에서 참조가 없는 상태였으며 원격 push는 실행하지 않음.
- Node.js 동작 검사 2개 통과: 기본 22px, 크기 변경·페이지 이동 후 저장값 적용·초기화, 18~30px 경계, 손상된 설정·저장소 차단 대응. 이는 DOM 대역을 사용한 동작 검사이며 실제 브라우저 시각 검사는 아님.
- 전체 PowerShell 스크립트 구문 검사 통과. Git 배포 기본 미리보기를 다른 작업 폴더에서 실행해 공개 소스 66개 확인.
- VS Code에 구성한 것과 동일한 PowerShell -NoProfile -NoExit -ExecutionPolicy Bypass -File 명령을 다른 작업 폴더에서 실행하여 프로젝트 루트 이동, Python 3.12.9, .venv 실행파일 경로, 가상환경 여부 True 확인.
- check-environment 스크립트 확인: 기본 PATH의 Python은 Anaconda 3.6.10, 프로젝트는 3.12.9 x64, pip check 정상. 설치 확장 Python 2026.10.0 / Pylance 2026.4.1 / Debugger 2026.6.0 / Oracle SQL Developer 26.3.1 확인.
- start·stop·restart로 강사 프로필 서버 재시작 성공. 라이브 HTTP로 교재·글자 조절 자산·DB 상태 등 6개 경로 200 확인. TEACHER01, Oracle 23.26.4.1.0, 학습 준비 상태 True 유지.
- 10개 페이지의 내부 링크·앵커·실습 탭 218개 확인. 모든 페이지에 글자 조절 컨트롤 존재 확인. 상세 응답은 runtime/ui-verification.json에 저장.
- 이번 브라우저 도구도 localhost 접근에서 ERR_BLOCKED_BY_CLIENT를 반환하여 실제 화면 캡처 검증은 완료하지 못함.

## 검증 범위의 한계

이번 과제 안내·배포 보호·Render 설정 추가(2026-11-13):

- 참고 PDF 1쪽을 이미지로 확인하여 평가 요소·실행 증거·제출 구조만 참고함. 기존 과목의 기능 목록·50점 배점·PPT 필수 조건은 복사하지 않음.
- 사용자 지정 마감 2026-12-18 18:00 KST, 금요일임을 확인. 제출처는 미지정이므로 별도 공지로 표시.
- 본인 수행·이해도 40점 중심의 100점 평가와 코드 없는 과제 설명 12개, AI 활용·복제 제출 기준, 시연 질문, 보고서 양식과 제출 ZIP 스크립트 추가.
- Python 검사 32개 통과. 새 검사는 학생 ZIP의 개인 .env 제외·빈 학생 설정, 소스에 복사된 비밀값 차단·실패 시 이전 ZIP 보존, 오타 환경파일 차단, 보고서 미완성·학번 불일치 검사, Render guide의 DB 비호출·Wallet 차단, lab 인증·CSRF·호스트·필수 비밀값, Thin Secret Files 경로 처리를 확인함.
- 글자 크기 동작 검사 2개, JS/Python/PowerShell 구문 검사 통과. 10개 페이지의 내부 링크·앵커·실습 탭 223개 확인.
- 기존 teacher 프로필 서버 재시작 성공. Render 설정값은 실제 비밀값 없이 reference/docs/RENDER.md에 별도 정리함.
- Render 원격 배포 및 Oracle Thin 실제 접속은 수행하지 않음. 해당 Wallet 암호는 미확보이며 기본 Windows Thick 연결과 구분함.

- 브라우저 전용 호스트가 사용 불가했고, Windows Computer Use는 현재 브라우저 URL을 신뢰성 있게 확인할 수 없어 중단했습니다. 따라서 화면 캡처·브라우저 버튼 조작·모바일 실기기 시각 검증은 미완료입니다. HTTP/Flask/Oracle 검증과 구분합니다.
- 학생 계정별 DB 비밀번호·잠금·할당량·권한은 확인하지 않았습니다. 각자 db-init 연결 점검에서 확인해야 합니다.
- Thin 모드는 코드와 공식 문서 기준으로 지원하지만, Wallet 암호가 제공되지 않아 실제 Thin 연결 검증은 수행하지 않았습니다. 검증 완료한 기본 경로는 Thick입니다.
- Oracle Cloud 연결에는 인터넷이 필요합니다. 오프라인 wheel은 Python 패키지 설치를 위한 것입니다.

## 기본 포트 변경 검증 (2026-11-13)

- 과목 번호에 맞춰 기본 로컬 포트를 22417로 변경함. CLI, PowerShell 시작·재시작, VS Code 디버그, 교재 및 시작 안내를 일치시킴. Render의 PORT 환경변수 처리는 유지함.
- 실행 중인 강사 서버를 관리 스크립트로 22417로 이동함. 새 주소의 교재·상태 조회 HTTP 200, TEACHER01 실제 DB 연결 및 학습 준비 상태를 확인함.
- 학생 ZIP oml-student-kit-20261113-003.zip 생성. 실행 설정의 22417 반영, 79개 파일 SHA256 및 ZIP 무결성, 개인 환경파일·강사 도구·로컬 명령 모음·프로젝트 Markdown 제외를 확인함.
- 기존 Python 검사 18개와 PowerShell 구문 검사 통과. 자세한 결과: 배포 제외 runtime/port-verification.json.
