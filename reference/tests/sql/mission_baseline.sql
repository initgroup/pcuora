-- 강사용 검증 전용 모델. 기본과제와 학생 과제 객체를 참조·변경하지 않습니다.
DECLARE
  v_settings DBMS_DATA_MINING.SETTING_LIST;
BEGIN
  v_settings('ALGO_NAME') := 'ALGO_DECISION_TREE';
  v_settings('PREP_AUTO') := 'ON';
  v_settings('TREE_TERM_MAX_DEPTH') := '6';
  -- 두 모델에 같은 최소 잎 크기를 적용합니다. 10은 전체 학습 행의 10%입니다.
  -- 다량의 오류 행이 정상 범위 분할을 방해하는 수업용 고정 기준입니다.
  v_settings('TREE_TERM_MINPCT_NODE') := '10';
  DBMS_DATA_MINING.CREATE_MODEL2(
        model_name          => :model_name
       , mining_function     => 'CLASSIFICATION'
       , data_query          => :data_query
       , set_list            => v_settings
       , case_id_column_name => 'CASE_ID'
       , target_column_name  => 'LABEL'
       );
END;
/
