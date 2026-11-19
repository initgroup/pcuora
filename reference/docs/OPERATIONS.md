# 로컬 운영

프로젝트 PowerShell에서 .\scripts\setup.ps1, .\scripts\start.ps1, .\scripts\stop.ps1, .\scripts\restart.ps1을 실행합니다.
기본22417이 사용 중이면 빈 포트를 선택하므로 출력의 실제 주소로 접속합니다. 스크립트는 자기 위치에서 루트를 계산합니다.
SQL은 .\scripts\db-init.ps1, 학생 배포는 .\scripts\compress.ps1, 제출은 .\scripts\submit.ps1, 소스 백업은 .\scripts\backup.ps1입니다.
DB 초기화는 기존 행을 보존하고 테이블3개·프로시저1개를 준비합니다. SQL만 수정하면 서버 재시작은 불필요하지만 전처리 저장 후 모델은 재생성·확정합니다.
미션/창의는 본인이 sql/custom의 테이블→프로시저를 F5 실행하고 안내된 고정 객체 이름4개로 연결 확인합니다.
비밀번호·전체 명단·.local·runtime·가상환경·로그는 공개 소스에 포함하지 않습니다. 설치파일은 reference/installers에만 보관합니다.
