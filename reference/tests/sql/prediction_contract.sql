-- 읽기 전용 검증 SQL. {{normalized}}는 실제 OML_BASIC_RUN의 PREDICT/CLEAN 반환 SQL에서 얻습니다.
-- 입력 원본·모델·객체를 변경하지 않으며 결과는 ROW_NO로 비교합니다.
-- @section read_only
SET TRANSACTION READ ONLY
-- @section model
SELECT MODEL_NAME
     , MINING_FUNCTION
     , ALGORITHM
     , CREATION_DATE
  FROM USER_MINING_MODELS
 WHERE MODEL_NAME = 'OML_BASIC_CLEAN_MODEL'
;
-- @section attributes
SELECT ATTRIBUTE_NAME
     , DATA_TYPE
     , ATTRIBUTE_TYPE
     , TARGET
  FROM USER_MINING_MODEL_ATTRIBUTES
 WHERE MODEL_NAME = 'OML_BASIC_CLEAN_MODEL'
 ORDER BY ATTRIBUTE_NAME
;
-- @section score
WITH normalized AS
     (
      {{normalized}}
     )
SELECT d.ROW_NO
     , PREDICTION(OML_BASIC_CLEAN_MODEL USING {{using}}) PREDICTED
     , PREDICTION_PROBABILITY(OML_BASIC_CLEAN_MODEL, 'BUY' USING {{using}}) BUY_PROBABILITY
     , PREDICTION_PROBABILITY(OML_BASIC_CLEAN_MODEL, 'SELL' USING {{using}}) SELL_PROBABILITY
  FROM
     (
      {{projection}}
        FROM normalized
     ) d
 ORDER BY d.ROW_NO
;
-- @section using_all
d.*
-- @section using_unqualified
*
-- @section using_explicit
d.RETURN_PCT AS RETURN_PCT, d.RANGE_PCT AS RANGE_PCT,
       d.VOLUME_CHANGE_PCT AS VOLUME_CHANGE_PCT, d.CLOSE_PRICE AS CLOSE_PRICE, d.STOCK AS STOCK
-- @section using_alias
d.RETURN_PCCT AS RETURN_PCT, d.RANGE_PCT AS RANGE_PCT,
       d.VOLUME_CHANGE_PCT AS VOLUME_CHANGE_PCT, d.CLOSE_PRICE AS CLOSE_PRICE, d.STOCK AS STOCK
-- @section baseline
SELECT CASE_ID ROW_NO
     , CASE_ID
     , RETURN_PCT
     , RANGE_PCT
     , VOLUME_CHANGE_PCT
     , CLOSE_PRICE
     , STOCK
-- @section reversed_columns
SELECT STOCK
     , CLOSE_PRICE
     , VOLUME_CHANGE_PCT
     , RANGE_PCT
     , RETURN_PCT
     , CASE_ID
     , CASE_ID ROW_NO
-- @section target_buy
SELECT CASE_ID ROW_NO
     , normalized.*
     , 'BUY' SIGNAL
-- @section target_sell
SELECT CASE_ID ROW_NO
     , normalized.*
     , 'SELL' SIGNAL
-- @section target_null
SELECT CASE_ID ROW_NO
     , normalized.*
     , CAST(NULL AS VARCHAR2(100)) SIGNAL
-- @section case_id_changed
SELECT CASE_ID ROW_NO
     , CASE_ID + 100000 CASE_ID
     , RETURN_PCT
     , RANGE_PCT
     , VOLUME_CHANGE_PCT
     , CLOSE_PRICE
     , STOCK
-- @section case_id_absent
SELECT CASE_ID ROW_NO
     , RETURN_PCT
     , RANGE_PCT
     , VOLUME_CHANGE_PCT
     , CLOSE_PRICE
     , STOCK
-- @section extra_columns
SELECT CASE_ID ROW_NO
     , normalized.*
     , 'unknown' EXTRA_TEXT
     , 999999 EXTRA_NUMBER
     , DATE '2026-11-17' EXTRA_DATE
     , TIMESTAMP '2026-11-17 00:00:00' UPDATED_AT
     , 'N' USE_YN
     , 'TEST' SPLIT
     , '2099-12-31' WEEK_ENDING
-- @section name_typo
SELECT CASE_ID ROW_NO
     , RETURN_PCT RETURN_PCCT
     , RANGE_PCT
     , VOLUME_CHANGE_PCT
     , CLOSE_PRICE
     , STOCK
-- @section missing_return
SELECT CASE_ID ROW_NO
     , RANGE_PCT
     , VOLUME_CHANGE_PCT
     , CLOSE_PRICE
     , STOCK
-- @section stock_only
SELECT CASE_ID ROW_NO
     , STOCK
-- @section numeric_strings
SELECT CASE_ID ROW_NO
     , TO_CHAR(RETURN_PCT, 'TM9', 'NLS_NUMERIC_CHARACTERS=''.,''') RETURN_PCT
     , TO_CHAR(RANGE_PCT, 'TM9', 'NLS_NUMERIC_CHARACTERS=''.,''') RANGE_PCT
     , TO_CHAR(VOLUME_CHANGE_PCT, 'TM9', 'NLS_NUMERIC_CHARACTERS=''.,''') VOLUME_CHANGE_PCT
     , TO_CHAR(CLOSE_PRICE, 'TM9', 'NLS_NUMERIC_CHARACTERS=''.,''') CLOSE_PRICE
     , STOCK
-- @section invalid_numeric_string
SELECT CASE_ID ROW_NO
     , 'unknown' RETURN_PCT
     , RANGE_PCT
     , VOLUME_CHANGE_PCT
     , CLOSE_PRICE
     , STOCK
-- @section numeric_date
SELECT CASE_ID ROW_NO
     , DATE '2026-11-17' RETURN_PCT
     , RANGE_PCT
     , VOLUME_CHANGE_PCT
     , CLOSE_PRICE
     , STOCK
-- @section numeric_binary
SELECT CASE_ID ROW_NO
     , HEXTORAW('CAFE') RETURN_PCT
     , RANGE_PCT
     , VOLUME_CHANGE_PCT
     , CLOSE_PRICE
     , STOCK
-- @section stock_number
SELECT CASE_ID ROW_NO
     , RETURN_PCT
     , RANGE_PCT
     , VOLUME_CHANGE_PCT
     , CLOSE_PRICE
     , 1 STOCK
-- @section stock_unknown
SELECT CASE_ID ROW_NO
     , RETURN_PCT
     , RANGE_PCT
     , VOLUME_CHANGE_PCT
     , CLOSE_PRICE
     , 'UNKNOWN' STOCK
