# 다른 PC에서 같은 환경 만들기

기준: Windows 10/11 x64, CPython 3.12. 관리자 권한이 없는 학생도 Python 사용자 설치와 프로젝트 가상환경을 사용할 수 있습니다. 기본 Windows Thick 연결에는 호환되는 Microsoft VC++ v14 x64 Runtime이 필요하지만, 이미 설치되어 정상 연결되는 PC는 추가 설치하지 않습니다.

1. `python-3.12.10-amd64.exe`: 공식 Windows 설치 원본. 실행해서 Python 3.12 x64를 설치합니다. 이미 Python 3.12가 있으면 생략 가능합니다.
2. VC++ x64 Runtime은 일괄 재설치하지 않습니다. db-init이 정상 연결되면 이 단계를 생략합니다. DPI-1047 등으로 Oracle Client가 로드되지 않으면 먼저 setup 실행 여부·Client 경로·Python/Client의 x64 일치를 확인하세요. Runtime이 없거나 버전이 부족한 경우에만 [Microsoft 공식 설치파일](https://aka.ms/vc14/vc_redist.x64.exe)로 설치·업데이트합니다. Windows 설정 → 앱 → 설치된 앱에서 Microsoft Visual C++ v14 계열 Redistributable (x64)을 확인할 수 있습니다. 설치 시 관리자 승인이 필요할 수 있습니다. Visual Studio 전체 설치는 필요하지 않습니다. Oracle Client를 사용하지 않는 Thin 연결에는 이 Client용 설치가 필요하지 않습니다. [Microsoft 안내](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist).
3. `instantclient-basiclite-windows.x64-23.26.4.0.0.zip`: setup.ps1이 프로젝트의 runtime/instantclient 아래에 풀어 둡니다. PATH나 기존 Oracle 설치를 변경하지 않습니다. 원본에 포함된 라이선스·안내파일을 보존합니다.
4. `scripts/setup.ps1`은 reference/wheels의 고정 버전 패키지를 사용합니다. ARM64/macOS/Linux에서는 이 Windows 패키지를 사용하지 않습니다. 해당 OS의 Python과 드라이버를 별도로 설치하고 Thin 연결을 사용해야 합니다.

공식 원본:

- [Python 3.12.10](https://www.python.org/downloads/release/python-31210/)
- [Oracle Instant Client Windows x64](https://www.oracle.com/database/technologies/instant-client/winx64-64-downloads.html)
- [Instant Client ZIP 설치](https://docs.oracle.com/en/database/oracle/oracle-database/26/ntcli/installing-oracle-instant-client-using-zip-files.html)
- [VS Code 설치](https://code.visualstudio.com/download)
- [VS Code Python 환경 선택](https://code.visualstudio.com/docs/python/environments)

SHA256:

```text
python-3.12.10-amd64.exe
67b5635e80ea51072b87941312d00ec8927c4db9ba18938f7ad2d27b328b95fb

instantclient-basiclite-windows.x64-23.26.4.0.0.zip
7586c02a2926f619a0b16a9ae32e85bb3605798aa177155b065fffb48a1ee0b8
```

Python 설치파일의 Authenticode 서명은 Python Software Foundation / Valid로 확인했습니다. Oracle ZIP은 공식 다운로드 페이지의 SHA256과 비교합니다. 이 교육용 잠금 환경을 갱신할 때는 wheel·잠금 목록·설치 안내·검증 기록을 함께 갱신하세요.
