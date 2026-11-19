# 로컬 운영

프로젝트 PowerShell에서 .\scripts\setup.ps1, .\scripts\start.ps1, .\scripts\stop.ps1, .\scripts\restart.ps1을 실행합니다.
기본22417이 사용 중이면 빈 포트를 선택하므로 출력의 실제 주소로 접속합니다. 스크립트는 자기 위치에서 루트를 계산합니다.
SQL은 .\scripts\db-init.ps1, 학생 배포는 .\scripts\compress.ps1, 제출은 .\scripts\submit.ps1, 소스 백업은 .\scripts\backup.ps1입니다.
DB 초기화는 기존 행을 보존하고 테이블3개·프로시저1개를 준비합니다. SQL만 수정하면 서버 재시작은 불필요하지만 전처리 저장 후 모델은 재생성·확정합니다.
미션/창의는 본인이 sql/custom의 테이블→프로시저를 F5 실행하고 안내된 고정 객체 이름4개로 연결 확인합니다.
비밀번호·전체 명단·.local·runtime·가상환경·로그는 공개 소스에 포함하지 않습니다. 설치파일은 reference/installers에만 보관합니다.

## 강사 main 배포

프로젝트 루트에서 .\scripts\git-publish-main.ps1을 실행하면 기존 강사 배포기를 통해 main에 업로드합니다. -Preview는 원격 접속 없는 파일 목록 확인, -Prepare는 로컬 커밋만 준비합니다. 강제 push·학생 Wallet 공개·서버 재시작은 하지 않습니다. 다른 폴더에서는 이 스크립트의 전체 경로로 실행합니다. 학생 배포는 본인 저장소를 지정하는 scripts/deploy-github.ps1을 그대로 사용합니다.

학생 Render는 scripts/render-build.sh·render-start.sh와 backend/hosting.py를 사용한다. Git Provider의 본인 main을 연결하고 통합 안내의 04 Git·Render 배포를 따른다. 강사 운영의 기존 instructor/scripts 경로도 같은 공통 실행 파일에 위임한다.
