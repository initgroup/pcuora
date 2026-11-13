# 계정별 실습 권한

기존 STUDENT01~STUDENT20 계정을 사용하며 이 프로젝트는 새 계정을 만들거나 비밀번호를 변경하지 않습니다. 학생 자신의 스키마에서 실습합니다.

필요 권한: CREATE SESSION, CREATE TABLE, CREATE VIEW, CREATE PROCEDURE, CREATE MINING MODEL, DBMS_DATA_MINING 실행 및 저장공간 할당량. 테이블스페이스 이름과 할당 정책은 관리자가 확인합니다. DBMS_DATA_MINING 권한이 PUBLIC 등으로 이미 제공될 수 있으므로 중복 권한 부여를 자동 수행하지 않습니다.

관리자가 기존 계정에 적용할 수 있는 예시(학생이 실행하는 스크립트가 아닙니다):

```sql
GRANT CREATE SESSION, CREATE TABLE, CREATE VIEW,
      CREATE PROCEDURE, CREATE MINING MODEL TO STUDENT01;
-- 필요한 환경에서만 직접 실행 권한 부여
GRANT EXECUTE ON SYS.DBMS_DATA_MINING TO STUDENT01;
```

무제한 테이블스페이스 권한, CREATE ANY MINING MODEL, 다른 학생 객체에 대한 SELECT/ALTER/DROP 권한은 필요하지 않습니다. 소규모 실습에 맞는 할당량은 관리자가 실제 사용량을 확인해 정하세요. 강사 연결에서는 위 객체 생성·학습이 가능한 것을 실제로 검증했습니다. 20개 학생 계정의 비밀번호·권한을 일괄 조회하거나 변경하지 않았습니다.

직접 SQL 실행 시 `01_schema.sql`은 최초 생성용입니다. 재실행 가능한 기본 경로는 `scripts/db-init.ps1`입니다. 초기화가 중단되면 권한·패키지 오류를 해결한 후 재실행하세요.
