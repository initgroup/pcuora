-- 격리 검증 객체만 검사합니다. 실제 과제 객체는 변경하지 않습니다.
SELECT OBJECT_NAME
  FROM USER_OBJECTS
 WHERE OBJECT_NAME LIKE 'OML_QA_LAB_%'
;
/
DROP PROCEDURE {{procedure}}
;
/
DROP TABLE {{prediction}} PURGE
;
/
DROP TABLE {{training}} PURGE
;
/
BEGIN
  DBMS_DATA_MINING.DROP_MODEL(:model_name);
END;
/
-- 5: 전처리 저장소도 이 검증의 격리 이름만 제거합니다.
DROP TABLE {{prepared}} PURGE
;
/
-- 6: 원본 TRAIN은 그대로 두고 준비행의 학습 제공만 끕니다.
UPDATE {{prepared}}
   SET FIT_YN = 'N'
     , EXCLUDE_REASON = 'QA: 학습 제공 제외'
 WHERE PREP_MODE = 'RAW'
   AND SOURCE_KIND = 'TRAIN'
;
/
-- 7: PREPARED_AT을 포함해 실패한 준비 작업의 전체 롤백을 확인합니다.
SELECT *
  FROM {{prepared}}
 WHERE PREP_MODE = :selected_mode
 ORDER BY SOURCE_KIND
     , CASE_ID
;
/
-- 8: DELETE 다음 INSERT 실패가 기존 준비행을 복원하는지 확인합니다.
CREATE OR REPLACE TRIGGER {{trigger}}
BEFORE INSERT ON {{prepared}}
FOR EACH ROW
BEGIN
  IF :NEW.PREP_MODE = 'RAW' THEN
    RAISE_APPLICATION_ERROR(-20991, 'QA PREPARE insert failure');
  END IF;
END;
/
-- 9
DROP TRIGGER {{trigger}}
;
/
