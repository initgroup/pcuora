# 설치자료 관리

현재 실행 환경은 FastAPI·Uvicorn·python-oracledb이며 기본 DB 연결은 Thin이다.
지원 Python은 3.12~3.14 x64, 준비된 오프라인 설치자료는 Python 3.12 x64용이다.

- python-3.12.10-amd64.exe: 기존 공식 Python x64 설치 원본. 지원 Python이 이미 있으면 설치하지 않는다.
- ../wheels-classifier-py312/: reference/requirements.lock에 맞는 현재 분류 사이트의 wheel 23개.
- instantclient-basiclite-windows.x64-23.26.4.0.0.zip: 기존 Thick 연결을 쓰는 PC의 선택 설치 원본. 기본 Thin에는 필요 없다.

구형 Flask·Waitress용 reference/wheels는 삭제했다.
온라인 설치를 기본으로 한다. VS Code Extensions에서 필요한 확장을 확인하고 scripts/setup.ps1로 패키지를 설치한다.
설치자료 ZIP은 인터넷을 사용할 수 없는 PC에만 별도 제공한다.
오프라인 설치는 setup.ps1 -AssetsPath로 별도 설치자료 폴더를 지정하며 -InstallExtensions는 생략한다. 확장은 별도 VSIX로 설치한다.
현재 setup은 Oracle Client ZIP을 자동으로 설치하지 않는다. 기존 Thick Client의 실제 경로를 ORACLE_CLIENT_LIB에 지정한다.
정상 DB 연결 중에는 Client나 VC++ Runtime 재설치를 안내하지 않는다.
DPI-1047 발생 시 경로·Python/Client x64 일치를 먼저 확인하고, Runtime 미설치·버전 부족일 때만 공식 x64 설치본을 사용한다.

공식 출처:
- https://www.python.org/downloads/release/python-31210/
- https://www.oracle.com/database/technologies/instant-client/winx64-64-downloads.html
- https://code.visualstudio.com/Download
- https://aka.ms/vc14/vc_redist.x64.exe

기존 원본 SHA-256:
- Python: 67b5635e80ea51072b87941312d00ec8927c4db9ba18938f7ad2d27b328b95fb
- Instant Client: 7586c02a2926f619a0b16a9ae32e85bb3605798aa177155b065fffb48a1ee0b8

학생 소스 ZIP에는 설치자료를 넣지 않는다.
설치자료는 reference/installers/COM22417_설치자료_Python312_x64_20261120.zip에 보관하며 오프라인 PC에만 제공한다. Wallet·비밀번호·VS Code 설치본·확장 VSIX는 포함하지 않는다.
