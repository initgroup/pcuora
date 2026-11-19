# DB 권한

본인 계정에서 CREATE TABLE, CREATE PROCEDURE, CREATE MINING MODEL 및 DBMS_DATA_MINING 실행 권한을 확인합니다. 테이블 저장 할당량도 필요합니다.
뷰·사용자 함수·패키지는 추가 생성하지 않습니다. 다른 사용자 객체나 CREATE ANY 권한은 필요하지 않습니다.
웹의 DB 연결 성공은 ping 성공이며 모델 생성 권한까지 보장하지 않습니다. 실제 모델 생성 실패는 오류 코드로 따로 확인합니다.
