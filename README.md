# OML 분류모델 실습

메뉴 새 문서는 인증 확인 중(checking) 상태로 시작하여 세션 확인 전 인트로·업무 화면을 노출하지 않는다. 확인 실패는 준비 화면에서 재시도하며 정상 비회원 응답일 때만 인트로를 표시한다. 공통 request-progress는 task·API 요청의 토큰을 참조하여 160ms 이상 걸리는 작업에 실제 완료까지 미정 진행바를 표시하고 세션 확인 폴링은 제외한다. 임의 퍼센트·추가 DB 폴링·포커스/스크롤 이동은 만들지 않는다. info/success 알림은 4.5초 후 자동 닫고 마우스·키보드로 읽는 동안 정지하며 오류·경고·확인 레이어는 자동 닫지 않는다.

미션·창의의 전처리 표 조회와 웹 연계 성공은 구분한다. PREPARED 행이 있어도 현재 원본·프로시저 지문의 연계 기록이 없거나 달라지면 미완료이며, 미션·창의 각 탭의 SQL 실행 결과 연계 버튼에서 기존 확인 레이어·동일 link API로 연결한다. 안내는 DB 행 수·학습 제공/TEST 행과 웹 연계 필요 상태를 함께 표시하고 재전처리를 무조건 요구하지 않는다. 조회만으로 연계·성공 기록을 자동 생성하지 않는다. 연계 버튼은 현황·학습데이터·모델·예측 탭에서 같은 이름·매크로·확인 함수·기존 link API를 사용한다. 승인 후 상태와 최종 현황을 같은 응답으로 갱신하며 창의과제에는 생성 SQL을 추가하지 않는다.

기본·미션 CSV 조회는 로딩 중 기존 표·페이지 표시를 유지하고 고정된 표 높이와 데이터 구분 자리로 탭 전환의 높이 변화를 막는다. 이전·다음·다시 조회 시 창/표 스크롤과 가로 위치를 보존하며 페이지 버튼의 키보드 초점은 preventScroll로 복귀한다. 닫기·세션 변경·늦은 응답 검사는 유지하고 서버 재시작이나 DB 작업은 추가하지 않는다.

미션 스키마 팝업은 DATA → PREPARED → PREDICT → 실행 프로시저 RUN 순서로 제공한다. RUN 탭은 기존 procedure_sql 생성기를 재사용하여 선택 미션·발급 계정의 전체 정의를 표시·복사하며 DB 작업은 실행하지 않는다. 창의과제에는 생성 SQL을 추가하지 않는다.

세 과제의 학습데이터는 **① CSV 적재 → ② DATA 원본 확인 → ③ PREPARED 전처리 저장·결과 확인** 순서이며 같은 제목·카드·업로드·조회 영역을 사용합니다. 원본 조회 버튼과 원본 결과를 전처리 앞에 모았습니다. 예측 탭도 **CSV 적재 → 입력 확인 → 모델 선택·실행 → 결과** 순서로 같습니다. 기본은 화면 실행, 미션·창의는 CSV 화면 저장과 직접 SQL 작업이라는 기능 범위만 다릅니다.

최종 현황의 미완료 단계에는 **3/4 완료 · 1개 남음**처럼 세부 개수를 표시합니다. 단계 상태 버튼이나 전체 도장을 클릭하면 완료한 작업과 남은 작업을 레이어로 확인하고 해당 단계로 이동할 수 있습니다. 객체는 DATA·PREPARED·PREDICT·RUN, 학습데이터는 원본 적재·객체 연결·RAW/CLEAN 준비, 모델은 최신성·실제 TEST 평가·동일 TEST, 예측은 현재 모델·입력·성공 결과의 일치를 확인합니다. 레이어는 조회한 검증 결과를 재사용하고 추가 DB 요청을 보내지 않습니다. 실제 성공 조건과 모두 완료한 경우의 PPT 캡처 안내를 유지합니다.

기본·미션·창의 현황 상단의 최종 실습 현황은 객체 준비, RAW/CLEAN 전처리, 같은 TEST 평가, 새 입력 예측의 성공 여부를 요약한다. backend/practice_evidence.py는 실제 실행 결과의 서버 영수증을 기존 runtime 상태에 저장하고 현재 모델 지문·생성 시각·미션·예측 입력과 대조한다. 빈 결과·건수 불일치·실패·변경·확정 해제는 성공을 유지하지 않는다. 현황 조회는 기존 상태 응답을 재사용하고 평가·예측·DDL을 대신 실행하거나 폴링하지 않는다. 모두 성공일 때만 도장과 PPT 캡처 안내를 표시한다. 성공 도장은 기본과제 성공 / 미션과제 성공 / 창의과제 성공으로 구분하며 OML 검증 인장으로 표시한다. 과제명·전체 검증 완료·체크 문양과 이중 테두리를 사용하고, 미완료·검증 해제·로그아웃 때 인장을 제거한다. 기능 실행 확인이며 임의 정확도 합격선이나 과제 점수를 만들지 않는다.

기본과제 3단계는 기본 예측 모델을 지정하고 4단계에서는 RAW/CLEAN을 직접 선택해 바로 실행한다. 별도 4단계 확정 버튼은 제공하지 않으며 성공한 실행의 모델을 사용 모델로 저장한다. 확인 전 선택값을 고정하고 서버에서도 최신 모델을 검사한다. 코딩도움말·결과 모델명은 이번 선택값을 따른다. 기본의 분류·확률은 조회 결과이며 PREPARED 예측 입력과 서버 성공 요약만 저장한다.

배재대학교 소프트웨어학 · 빅데이터머신러닝 · **2026년 2학기** 실습 환경입니다. 인트로는 배재대학교 공식 홈페이지의 캠퍼스 야경과 데이터 흐름 그래픽으로 구성하며, OML은 **Oracle Machine Learning**의 약자입니다. 사진 출처·원본은 [인트로 이미지 안내](reference/branding/README.md)에 기록합니다.

세 과제는 **현황 → 학습데이터 → 모델 생성·비교 → 예측 실행**의 같은 UI를 사용하며 실행 권한과 SQL 제공 범위가 다릅니다.

로그인·메인·과제 화면은 인트로와 같은 네이비·민트 계열로 연결합니다. 제목·선택 단계는 네이비, 작업 입력은 옅은 청회색, 조회·비교 결과는 민트, 접는 설명은 옅은 보라색으로 구분합니다. SQL·소스 코드는 어두운 배경과 밝은 구문 색상을 사용합니다. 색상과 함께 기존 제목·단계 번호·상태 문구를 유지하며, 글자 크기 조절과 모바일·키보드 이동을 지원합니다. 화면별 스타일은 studio.css, 로그인·메인은 main-page.css, 코드·도움말 기반은 style.css에서 관리합니다. 메인 본문은 상단 제목과 같은 폭을 사용하고 접속 정보 카드는 흰색의 간결한 헤더로 표시합니다. 네이비 제목 강조를 카드 안에 반복하지 않습니다.

| 과제 | 데이터·스키마 확인 | 객체 생성·CSV 적재·전처리·모델 생성 | 결과 확인 |
|---|---|---|---|
| 기본 | 고정 기본 미션 1개, 데이터 조회·스키마 조회·CSV 다운로드 | 화면 버튼으로 실행 | 화면에서 조회·TEST 평가·예측 실행 |
| 미션 | 번호가 있는 예시 12개 중 선택, CSV·스키마·선택 미션 SQL 가이드 | 개발자가 SQL Developer에서 직접 실행·수정 | 만든 객체를 연결 확인한 뒤 화면에서 조회·TEST 평가·예측 실행 |
| 창의 | 본인 데이터·DB 스키마 확인, 제공 CSV·실행 SQL 없음 | 테이블·프로시저·전처리·모델은 직접 SQL, CSV는 화면 적재 | 미션과 같이 연결 확인 후 화면에서 조회·TEST 평가·예측 실행 |

기본의 고정 미션은 선택 대상이 아닙니다. 미션·창의에서는 테이블 생성·전처리·학습·삭제는 직접 SQL로 수행하고 CSV 적재는 화면에서 실행합니다. 미션 선택·다운로드·가이드 복사는 DB 작업이나 로컬 파일 저장을 자동 수행하지 않습니다.

**DB 소유자는 학번이 아니라 학생에게 발급된 DB 계정입니다.** 화면의 테이블·프로시저·모델명과 제공 SQL은 로그인한 실제 DB 계정을 붙여 표시합니다. 아래 STUDENT00.OML_MISSION_DATA의 STUDENT00은 예시이므로 본인 발급 DB 계정으로 바꿉니다. CREATE TABLE, CREATE OR REPLACE PROCEDURE, 조회·적재·호출·모델 이름에도 같은 소유자를 사용합니다. 제공 실행 SQL의 계정 확인 절차는 다른 계정에 접속한 경우 객체 생성·삭제 전에 중단하게 합니다. ALTER SESSION SET CURRENT_SCHEMA만 바꾸어 계정 검사를 우회하지 않습니다.

스키마 조회의 컬럼 행은 식별키(파랑)·설명변수(초록)·타깃변수(보라)·기타(회색)로 구분하며 역할 배지를 함께 표시합니다. 기본·미션의 DATA/PREPARED/PREDICT 생성 SQL은 선택 테이블의 COMMENT ON TABLE 및 모든 COMMENT ON COLUMN을 함께 표시·복사합니다. 기본은 sql/table_comments.sql 원문에서 해당 테이블 설명만 가져옵니다.

코딩도움말 하단의 적용 안내는 현재 작업의 핵심 3단계만 표시합니다. 계정은 한 번 표시하고 오류 해결·터미널 명령·DB 확인 SQL은 필요한 항목을 펼쳐 봅니다. 조회·미리보기에는 무관한 설치·학습 절차를 표시하지 않습니다.

기본과제의 실행 버튼은 상태에 따라 이름을 바꾸지 않습니다. 현황의 **테이블 생성 → 프로시저 최초 등록 / 프로시저 다시 등록**을 각각 실행합니다. CSV는 **최초 적재 / 교체 적재**를 구분합니다. 되돌리기는 **학습 데이터 비우기**(원본·전처리값), **선택 전처리값 비우기**, **예측 입력 비우기**, 기존 **선택 모델 삭제**, **모델 확정 해제**, **실습 오브젝트 삭제**(기본 모델 2개·테이블 3개·RUN)로 구분합니다. 모든 변경은 계정·대상 확인 레이어 후 실행하며 오브젝트 삭제는 자동 복구되지 않습니다. 미션은 초기화 SQL을 직접 실행하고 창의는 본인 SQL을 작성한 뒤 연계 확인합니다. 실제 사용자 DB의 초기화를 배포·검사 과정에서 자동 실행하지 않습니다.

핵심 모델 비교표는 높이를 제한하지 않고 내부 스크롤 없이 모든 행·열을 표시합니다. 모델 재생성 버튼은 **전체 다시 학습** 하나로 제공합니다. 새 TRAIN은 먼저 적재·전처리 저장한 뒤 같은 버튼을 실행합니다. 이전 ‘추가 TRAIN 반영’은 데이터를 추가하지 않고 전체 재생성하는 중복 동작이어서 화면에서 제거했습니다. 기존 SQL의 ADD_TRAIN 호출 호환은 유지하며 모델의 증분 갱신으로 안내하지 않습니다.

SQL 실행 안내: 스키마 조회에서 선택 테이블의 전체 SQL을 복사해 같은 DB 계정의 새 SQL Developer 워크시트에 붙여넣고 선택 해제 후 F5로 실행합니다. Ctrl+Enter는 현재 문장만 실행하므로 테이블 생성 전 마지막 COMMENT만 실행하면 ORA-00942가 납니다. 출력의 첫 CREATE 성공/첫 오류를 먼저 확인합니다. 실제 Oracle 검증은 reference/tests/verify_sql_provision_db.py(미션 30개 스키마·컬럼 설명·CSV 적재·배포 쿼리)와 verify_oml_lab_db.py(기본·미션·창의 DDL/프로시저·모델 실행)에서 OML_QA_LAB_* 객체만 사용합니다.

기본·미션의 학습데이터 원본·미리보기·전처리 조회에도 식별자(파랑)·설명변수(초록)·타깃(보라)·기타(회색) 헤더와 옅은 셀 배경·역할 배지·범례를 적용합니다. 미션 역할은 선택한 배포 catalog를 따르며 알려지지 않은 창의 컬럼을 설명변수나 타깃으로 추정하지 않습니다. 콤보박스는 입력 배경·펼침 화살표로 구분하고 전처리 실행과 저장값 조회 조건/버튼은 별도 묶음으로 표시합니다.

미션 CSV 조회 헤더는 영문 컬럼명과 한글 라벨을 줄바꿈해 표시합니다. 식별키(파랑)·설명변수(초록)·타깃변수(보라)·운영값(회색)을 헤더 색상과 역할 배지·범례로 구분하며 셀의 원본 값은 유지합니다.

미션은 **11. 온라인 주문 배송 소요 등급**, **12. 모바일 앱 사용성 등급**까지 제공합니다. 카드의 **스키마 조회 → 데이터 조회 → 이 미션 선택** 순서는 모든 미션에 같고, 선택 버튼은 채움 색상과 선택 체크로 구분합니다. 두 조회 팝업에 목적·활용 사례, 설명변수의 의미와 낮음/높음 해석, 타깃 등급을 함께 표시합니다. **정상 0~100(0·100·소수 포함) / 빈칸 결측 / unknown 형식 오류 / 999999 범위 밖** 판단은 펼쳐 확인합니다. 온실의 적합 점수는 ℃가 아닌 것처럼, 원시 측정 단위와 교육용 지수를 구분합니다. 기존 CSV·검증 기록은 보존하며 신규 두 미션의 Oracle 학습 성능은 아직 실측하지 않았습니다.

미션 12종과 카드별 3버튼(스키마 조회 → 데이터 조회 → 이 미션 선택)을 제공합니다. 다운로드 링크는 별도 줄에 표시합니다. 기존 5종의 CSV·검증 결과는 보존했으며 나머지 7종은 생성/원본/화면 검증만 수행하고 Oracle 학습·성능 기준은 아직 측정하지 않았습니다.

미션 카드의 ‘스키마 조회’는 선택 CSV에 맞춘 ① DATA → ② PREPARED → ③ PREDICT 순서의 탭에서 컬럼명·Oracle 타입·필수 여부·기본값/제약과 CREATE TABLE/컬럼 설명 SQL을 제공합니다. 원본 오류 보존용 VARCHAR2와 전처리 NUMBER, CHECK와 NOT NULL을 구분합니다. 실제 DB를 조회·변경하지 않습니다.

미션 예시 카드의 ‘데이터 조회’에서 DB 테이블 생성 전에도 학습·TEST/예측 CSV를 50행씩 조회하고 전체 원본을 다운로드할 수 있습니다. 식별자 키·설명변수·타깃변수와 컬럼별 역할·유효값을 함께 제공합니다. TRAIN/TEST 필터는 조회에만 적용되며 다운로드·DB 데이터는 바꾸지 않습니다.

2026-11-18 안내 정리: 단문 알림에는 ‘자세히 보기’를 표시하지 않습니다. 미션·창의는 DB 접속 상태와 객체 준비 상태를 구분합니다. 미션은 선택 예시의 실행 SQL 가이드를 제공하고 창의는 누락·컴파일·입출력 진단만 제공합니다. 같은 계정에서 실행한 뒤 ‘테이블·프로시저 확인’을 누르면 연결됩니다. 배포용 실습 문서와 강사용 OML 교재는 실행 순서·확인할 결과를 먼저, 코드와 웹 연결 설명은 펼침으로 제공합니다.

2026-11-18 전처리 저장: **원본 DATA → PREPARE의 INSERT SELECT → PREPARED 저장값·FIT_YN 확인 → 모델 생성 → 같은 TEST 평가 → 예측** 순서로 실습합니다. RAW/CLEAN은 라디오로 표시하며 서로 독립된 준비행과 모델을 만듭니다. 모델 생성 SQL은 준비 테이블을 단순 SELECT하고 전처리를 다시 실행하지 않습니다.

현재 구조는 원본 DATA·예측 원본 PREDICT·전처리 저장 PREPARED의 테이블 3개와 독립 프로시저 RUN 1개입니다. 최신 전처리 저장 요청에 따라 이전의 테이블 2개 구조를 확장했습니다. 모든 화면은 제목·대상·조건 → 실행 버튼 → 결과 표 순서이며, 긴 교육 설명·설정·딕셔너리·기록은 펼침이나 도움말로 제공합니다.

세 과제의 네 단계는 큰 굵은 글자와 선택 배경으로 구분합니다. 단계 사이의 화살표를 클릭하면 바로 오른쪽 단계로 이동하며, DB 변경 작업 중에는 같은 전환 차단 규칙을 적용합니다. 좁은 화면에서는 단계 영역을 좌우로 스크롤할 수 있고 선택한 단계가 보이도록 맞춥니다.

기본과제는 고정 기본 미션의 데이터 조회·스키마 조회·CSV 다운로드를 제공합니다. 학습·예측 탭에서는 해당 CSV를 화면에서 적재할 수 있습니다. 미션·창의의 같은 위치에는 CSV 화면 적재·직접 전처리·모델 생성 후 DB 상태를 새로 확인하는 흐름을 안내합니다.

세 과제는 `_DATA`(학습·TEST 원본), `_PREPARED`(전처리 저장), `_PREDICT`(예측 원본), `_RUN`(실행 프로시저)의 고정 이름 4개를 읽기 전용으로 표시합니다. 학생이 같은 계정에 해당 DB 객체를 만들면 연결 확인으로 사용합니다.

기본과제의 실제 DB 접두어도 `OML_BASIC_`로 통일했습니다. 미션은 `OML_MISSION_`, 창의는 `OML_CREATIVE_`입니다. 기본 모델 이름은 `STUDENT00.OML_BASIC_RAW_MODEL` / `STUDENT00.OML_BASIC_CLEAN_MODEL`입니다. 2026-11-17 STUDENT23의 기존 테이블·모델은 이름만 변경해 행·테이블/모델 ID·TEST 평가·예측 결과를 보존했고, 실행 프로시저를 새 이름으로 적용한 뒤 구 프로시저를 제거했습니다. 이관 전 원문·데이터와 단계 기록은 배포하지 않는 `.local/basic-names-before-20261117/`에 보관합니다.

브라우저 기본 alert/confirm 대신 이동식 레이어 메시지를 사용합니다. 적재·교체·전처리 저장·모델 삭제 확인은 확인 버튼을 눌렀을 때만 진행하며 취소·닫기·ESC는 실행하지 않습니다. 확인 레이어와 오류·완료 상세 창은 제목을, 하단 알림은 메시지 글을 드래그하거나 포커스 후 방향키로 이동합니다.

모델 딕셔너리는 상위 펼침(▶/▼) → 모델명 → 조회 항목(▷/▽) → 상세 내용·SQL(＋/−)을 들여쓰기와 안내선으로 구분합니다.

모델 학습·관리에는 선택 모델명을 큰 독립 영역으로 표시합니다. ‘Oracle 모델 딕셔너리 → 모델 정보 조회’는 USER_MINING_MODELS·ATTRIBUTES·SETTINGS·VIEWS·XFORMS와 USER_OBJECTS의 실제 결과를 조회합니다. 기본과제의 옆 ?는 선택 모델의 실제 메타데이터 SQL·Python·파일 위치를 제공합니다. DM$ + 구분 코드 2자 + 지정 모델명을 분리해 설명하고 USER_OBJECTS·USER_TAB_COLUMNS로 실제 자동 생성 테이블/뷰·컬럼을 조회합니다. 의사결정나무의 VC(예측 비용), VM(학습 비용) 등 공개 뷰 코드는 Oracle 공식 문서와 실제 VIEW_TYPE을 기준으로 안내하며 P5·PH·PJ 등의 세부 내부 의미를 추정하지 않습니다. 각 객체의 일반 컬럼은 실제 최대 20행과 실행한 소유자 한정 SELECT를 표시·복사합니다. XMLTYPE은 XML 문자열로 표시하고 RAW/BLOB 등은 컬럼 정의만 표시합니다. 비용 행렬 0행과 TEST 혼동 행렬을 구분합니다. 모델·데이터·확정 상태를 바꾸지 않으며 미생성·정상 0행·조회 실패를 구분합니다.

코딩도움말은 버튼의 실제 바인드 호출 SQL·Python 원문과 DB 정의 적용 방법을 구분합니다. `sql/classifier.sql` 저장만으로 Oracle이 바뀌지 않습니다. 같은 계정의 SQL Developer에서 전체 F5 실행하거나 `.\scripts\db-init.ps1`로 적용한 뒤 VALID·USER_ERRORS·USER_SOURCE를 확인합니다. 모델 버튼은 `call_classifier.sql`로 이미 저장된 프로시저를 호출합니다. SQL만 적용하면 서버 재시작은 필요 없습니다. 모델 선택·확정은 검증 후 서버 `runtime/model-choice-*.json`에 선택값을 저장하며 Oracle 모델 상태를 바꾸지 않습니다. 코딩도움말·관련 소스 창의 제목줄에서 이동·최대화·최소화·복원이 가능합니다.

## 실행

Python 3.12.x / 3.13.x / 3.14.x x64를 지원합니다. 현재 실제 검증 환경은 3.12 x64입니다. VS Code에서 이 폴더를 열고 PowerShell 터미널에서 실행합니다.

```powershell
.\scripts\setup.ps1
.\scripts\start.ps1
```

setup은 프로젝트 .venv에 설치하고 현재 터미널을 활성화합니다. 필요할 때 `. .\scripts\terminal-init.ps1`로 복구합니다. 편집기 Python 인터프리터 선택은 별도이며 프로젝트 .venv를 선택합니다. 전역 PATH·프로필·VS Code 글자 크기는 바꾸지 않습니다.
시작 출력의 실제 주소로 접속합니다. 기본 22417이 사용 중이면 다음 빈 포트로 자동 선택합니다. `-Port`로 시작 포트를 지정하며 runtime/service.json에 선택된 포트와 프로젝트 프로세스를 기록합니다. 다른 프로젝트 서버를 종료하지 않습니다.

```powershell
.\scripts\stop.ps1
.\scripts\restart.ps1
```

security/student.env의 ORACLE_CLIENT_LIB는 비우고 WALLET_PASSWORD에 Wallet 다운로드 당시 암호를 설정합니다. DB 비밀번호와 별개입니다. security/students.json에 본인 학번·이름·db_user를 등록합니다. 로컬 웹 로그인에서 입력한 DB 비밀번호로 실제 Oracle 접속을 확인한 후에만 student.env에 저장합니다. 로그인 전에는 인트로가 보이며 로그인 버튼을 누르면 메인 본문에 입력 폼이 표시됩니다. 취소하면 인트로로 돌아갑니다. 로그인 후 첫 화면은 과제가 아닌 메인입니다. 중앙 카드에 학번·이름·학과·학년·발급 DB 계정과 실제 접속 계정/스키마, 웹 주소·DB 별칭·서비스·서버 및 로그인/연결 확인 시각을 표시합니다. 연결 테스트 결과와 함께 캡처해 PPT에 넣으세요. 비밀번호는 카드에 표시하지 않습니다. 과제는 메인 아래 또는 메뉴에서 선택합니다. 입력값 저장은 선택 사항이며 공용 PC에서는 선택하지 않습니다.

## DB 구조와 수정 위치

| 역할 | 실제 객체·파일 | 검색 키워드 |
|---|---|---|
| 학습·평가 원본 | STUDENT00.OML_BASIC_DATA · sql/schema.sql | CREATE-TABLE |
| 새 입력 | STUDENT00.OML_BASIC_PREDICT · sql/prediction_table.sql | CREATE-TABLE |
| 전처리 저장값·학습제공여부 | STUDENT00.OML_BASIC_PREPARED · sql/prepared_table.sql | CREATE-PREPARED-TABLE |
| 전처리 저장·학습·평가·예측 | STUDENT00.OML_BASIC_RUN · sql/classifier.sql | SQL-PREPARE / SQL-TRAIN / SQL-EVALUATE / SQL-PREDICT |
| OML 모델 등록 | 같은 프로시저 안의 CREATE_MODEL2 | CREATE-MODEL |
| Python 프로시저 호출 | backend/service.py · run_model | CALL-PROCEDURE |
| 조회·CSV 적재 | sql/queries/*.sql · backend/sql_files.py | DATA-SELECT / CSV-INSERT / EXECUTE-SQL |
| 버튼 이벤트 | static/js/main.js | api / loadRows / modelAction |
| HTTP API | app.py | data / import_data / train / predict |
| 화면 | templates/pages/*.html | 각 버튼 id |

원본 DATA의 문자열·오류를 보존하고 PREPARE가 선택 방식의 TRAIN·TEST·제외 행을 PREPARED에 저장합니다. RAW/CLEAN 모두 숫자 변환 실패와 빈 셀을 NULL로 처리하며 CLEAN만 범위 밖 숫자도 NULL로 저장합니다. 종목은 공백 제거·대문자화합니다. 결함은 빈 셀·unknown·999999이며 중앙값·분위수 계산 없이 Decision Tree가 결측을 처리합니다.

학습 SQL은 `PREP_MODE='RAW' 또는 'CLEAN' AND SOURCE_KIND='TRAIN' AND FIT_YN='Y'`인 저장행만 사용합니다. 원본 USE_YN과 준비행 FIT_YN은 별도 역할입니다. TEST·예측·원본 N 행은 학습하지 않으며 TEST 평가에는 같은 Y/TEST 전체를 사용합니다. PREPARE 후 SQL Developer에서 준비값·FIT_YN을 직접 수정하고 COMMIT하면 학습에 반영됩니다. **PREPARE 재실행은 선택 방식의 TRAIN/TEST 준비행을 교체하므로 수동 변경도 덮어씁니다.**

프로시저 인자는 p_action(PREPARE/INIT/RETRAIN/ADD_TRAIN/DELETE/VALIDATE/EVALUATE/PREDICT, TRAIN 호환), p_mode(RAW/CLEAN), p_result OUT SYS_REFCURSOR, p_sql OUT CLOB입니다. p_sql은 결과 조회·모델 학습 SELECT 또는 모델 삭제 PL/SQL 원문입니다. CREATE_MODEL2의 data_query에는 PREPARED의 단순 SELECT만 전달합니다. 고정 SELECT 문자열을 사용하며 가변 SQL 조립이나 임의 SQL 입력 기능은 없습니다. SETTING_LIST는 Oracle 모델 설정 인자입니다.

숫자 변환 `TO_NUMBER(컬럼 DEFAULT NULL ON CONVERSION ERROR)`과 범위 검사 CASE는 전처리 내부 프로시저의 INSERT SELECT에 있습니다. `sql/session.sql`의 `NLS_NUMERIC_CHARACTERS='.,'`를 웹·SQL Developer 모두 적용합니다. PREDICT는 예측 원본에서 선택 방식으로 준비한 값을 PREPARED의 SOURCE_KIND='PREDICT'에 저장한 뒤 단순 SELECT의 `d`로 `PREDICTION(모델 USING d.*)`를 실행합니다. 학습·TEST 준비행은 바꾸지 않습니다.

```powershell
.\scripts\db-init.ps1
```

기본과제 테이블 3개·프로시저 1개·한글 코멘트를 적용합니다. 웹의 ‘테이블·프로시저 준비’도 같은 작업입니다. 기존 원본 행·테이블과 모델을 보존하며 새 PREPARED를 추가합니다. CREATE TABLE 수정은 기존 컬럼에 자동 반영되지 않으므로 기존 구조 변경은 별도 ALTER가 필요합니다. DDL·모델 삭제/생성은 자동 커밋됩니다. CSV 교체와 PREPARE는 DELETE+INSERT 실패 시 기존 행을 복원합니다.
웹은 원본·DB 프로시저·준비값·모델 정보를 실제 DB에서 확인합니다. 기본은 원본·프로시저 변경 후 화면의 전처리 저장 → 학습을 실행합니다. 미션·창의는 같은 작업을 직접 SQL로 실행·COMMIT한 뒤 연결과 DB 상태를 다시 확인합니다. 모델 최신 여부와 모델 확정은 구분하며 runtime은 배포하지 않습니다. PREPARED_AT만 달라지는 동일 값 재준비나 다른 방식·예측 입력 준비는 해당 모델을 오래된 상태로 만들지 않습니다.

## 실행 전 확인

프로시저 등록·재등록, CSV 적재·교체, 전처리 저장, 모델 생성·재학습·삭제·확정, 예측 실행과 연계/미션 선택 저장은 대상과 작업을 레이어 확인창에 표시합니다. 확인해야 진행하며 취소·닫기·ESC에서는 실행하지 않습니다. 조회·미리보기·다운로드·코드 복사는 바로 제공합니다.

## 본문과 안내의 중복 정리

실습 순서와 SQL 수정 안내는 메인·각 과제의 본문과 버튼 옆 코딩도움말에서 제공합니다. 같은 내용을 반복하던 왼쪽 하단·상단·모바일의 공통 실습가이드 진입과 가이드 팝업/목록 API는 제거했습니다. 오류 진단의 관련 소스 파일 보기, 배포용 실습 문서, 강사용 OML 교재는 필요한 위치에서 제공합니다.

## 코딩도움말

모델 선택·확정은 SELECT로 데이터·프로시저·모델의 최신 여부를 검증한 후 `service.confirm_model()`이 선택값을 `runtime/model-choice-*.json`에 저장하는 웹 동작입니다. 해당 도움말에는 선택한 RAW/CLEAN 호출값과 실제 Python 검증·저장 함수를 표시하고 SELECT는 관련 쿼리로 구분합니다. 도움말 조회는 선택값을 저장하지 않습니다.

기본·미션의 **? 코딩도움말**은 **화면 버튼(Jinja) → 이벤트(JavaScript) → API(FastAPI) → 서비스(Python) → DB 연결 → 실행 SQL(Oracle)**의 여섯 단계로 표시합니다. 흐름의 상자는 같은 순서로 유지하고 각 단계 아래에 실제로 관여하는 파일·함수를 순서대로 나열합니다. 상자를 선택하면 왼쪽 소스 탐색기에 파일별 단락과 들여쓴 코드 구간 목록이 나옵니다. 오른쪽에는 파일 전체가 표시되며 같은 파일의 항목을 누르면 해당 줄로 스크롤하고 강조합니다. 다른 파일을 누를 때만 원문을 교체합니다. 파일 경로·전체 행 수·선택 줄 범위를 표시하며 선택 구간 복사와 파일 전체 복사를 각각 제공합니다. 좁은 화면에서는 목록 아래에 코드를 표시합니다. 실제 SQL 단계는 별도 색상으로 강조합니다.

화면 버튼에서 출발해 관련 이벤트와 호출 경로를 확인하며, 현재 필터·RAW/CLEAN·선택 미션 정보를 유지합니다. CSV 미리보기처럼 DB를 쓰지 않으면 해당 단계에 미사용을 표시합니다. 미션의 직접 실행 SQL 가이드는 가이드 생성 경로와 SQL Developer에서 수행할 코드를 구분합니다. 로컬 원문과 생성한 SQL을 구분하고 서로 떨어진 코드를 하나의 실행문으로 합치지 않습니다. 이 흐름은 실행 전 소스 안내이며 실제 DB 실행 결과나 DB 저장 원문과의 일치를 보장하는 추적 로그는 아닙니다. 상세 적용 방법은 아래 펼침 안내에서 확인합니다. 창의에는 안내 쿼리를 제공하지 않습니다.
로그아웃·세션 만료 때 도움말 코드 영역을 지웁니다. 비밀번호·DSN·Wallet·명단을 노출하지 않습니다. 소스는 인증된 허용 목록만 읽습니다. 팝업 제목 드래그·방향키 이동·ESC·포커스 복귀·선택 구간 복사를 지원합니다.
VS Code Ctrl+P로 표시된 경로 열기 → Ctrl+G로 줄 이동 또는 Ctrl+Shift+F로 함수명을 찾습니다. Python 변경은 restart.ps1, HTML·JS·CSS 변경은 Ctrl+F5로 반영합니다.

실행 SQL 단계에는 원본과 **현재 선택값 · 실행용 SQL**이 함께 나옵니다. 실행용 SQL은 발급 계정의 테이블·RAW/CLEAN·조회 조건을 반영하며 전체를 복사해 SQL Developer에서 F5로 실행합니다. RUN 호출은 OUT 변수 선언·PRINT를 포함합니다. 도움말에서는 실행하지 않습니다. CSV 행과 알 수 없는 입력값은 SQL로 펼치지 않습니다. 같은 계정·미션·조건으로 방금 조회한 성공 기록이 있으면 **마지막 실제 조회**도 별도로 표시합니다. 이 기록은 현재 브라우저 세션의 제한된 메모리에만 보관하며 변경 작업·로그아웃 시 비웁니다. 창의과제에는 안내 SQL을 제공하지 않습니다.

런타임 SQL 검사는 `python -m unittest reference.tests.test_runtime_sql`과 `node reference/tests/verify_coding_flow_browser.cjs --runtime-only`로 수행하며 원본 보존, 실제 바인드 값, F5 호출, CSV 비확장, 복사·조건/세션 격리·모바일을 확인합니다.

검증은 `python -m unittest reference.tests.test_coding_flow reference.tests.test_coding_help reference.tests.test_assignment_guides`와 `node reference/tests/verify_coding_flow_browser.cjs`로 수행합니다. 원문 구간·미션 선택값·도움말의 DB 미실행·인증 경계와 단계/파일 선택·복사·좁은 화면·확대·창 복원을 확인합니다. 브라우저 검사는 격리된 합성 로그인/데이터만 사용하며 결과는 `runtime/coding-flow-browser-verification.json`에 기록합니다. CSV 적재 도움말은 데이터 행을 INSERT 문자열로 확장하지 않습니다. 로컬 파일 명령·첫 줄 헤더 검사·500행 executemany·바인드 SQL 한 문장을 실제 소스로 표시합니다.

## 영향도 검토와 검증 범위

배포 원본의 기준은 scripts/source_files.py의 APP_FILES·STUDENT_SCRIPTS·CONFIG입니다. 변경한 기능과 직접 호출하는 화면·API·서비스·SQL·공통 모듈부터 검토하고, 필요한 검증 스크립트와 fixture만 별도로 선택합니다. .local, runtime 실행 산출물, 가상환경, 백업·과거 사본·임시 파일은 기본 영향도 검토에서 제외합니다. runtime의 보고서는 검증 결과 확인에만 읽습니다. reference 전체를 검색하지 않으며 학생 배포 목록에 명시한 안내 원본과 선택한 개발 검증 도구를 구분합니다.

코딩도움말은 작업별 등록된 파일을 읽으며 폴더 전체를 재귀 검색하지 않습니다. 실제 원문 경로는 학생 배포 목록에 속해야 하며 선택 미션의 생성 SQL은 별도 생성 항목으로 집계합니다. 2026-11-19에 보고한 **363개는 파일 수가 아니라 16개 버튼에서 확인한 코드 항목의 누계**입니다. 원문 항목 344회와 생성 SQL 19회이며, 원문의 중복을 제거하면 **41개 배포 파일·121개 코드 구간**입니다. 이전 응답 형식용 메타데이터까지 읽은 원본 42개도 모두 학생 ZIP에 포함되고 임시/.local 파일은 읽지 않았습니다.

일반 수정은 해당 작업과 직접 의존하는 기능만 검사합니다. 공통 흐름·인증·배포 규약을 바꿀 때 범위를 넓히며, 문서나 결과 집계만 바뀐 경우 전체 화면/실제 DB 검사를 반복하지 않습니다. 검증 보고서에는 항목 검증 누계와 중복 제거한 파일 수를 함께 기록합니다.

## 예측 컬럼 연결

기본과제 예측 실행 탭의 `templates/pages/prediction-contract.html` 안내에서 이름·순서·타입·키·타깃·추가·누락의 관계를 확인합니다. 모델은 학습 SELECT의 최종 컬럼 이름으로 대응하므로 순서는 달라도 됩니다. 숫자 4개와 종목은 의미·단위·전처리를 맞춥니다. 원본 VARCHAR2와 PREPARED에 저장한 NUMBER를 구분합니다.

`USING d.*`는 모델의 설명변수를 이름으로 찾으며, 고유키로 지정한 CASE_ID·타깃으로 지정한 SIGNAL·불필요한 추가 컬럼은 설명변수로 사용하지 않습니다. PREDICTION 함수에는 CASE_ID·SIGNAL이 없어도 되지만 이 웹의 고정 테이블은 적재·결과 연결을 위해 두 컬럼을 유지합니다. 예측 CSV에서 SIGNAL은 생략하거나 비울 수 있습니다.

숫자 문자열은 NUMBER로 변환될 수 있으나 unknown은 ORA-01722, 변환 불가 DATE·RAW는 ORA-00932가 날 수 있습니다. 설명변수 누락·오타도 실행에 성공할 수 있으므로 성공 여부만으로 입력이나 예측 품질을 판단하지 않습니다. `verify_prediction_contract.py`의 실제 Oracle 읽기 전용 20조건 검증 결과와 한계를 화면의 접힌 상세에서 확인할 수 있습니다.

## 과제별 실습 방식

기본과제는 고정 주식 미션 1개의 데이터·스키마를 먼저 확인합니다. 화면에서 테이블·프로시저 준비 → 제공 CSV 적재 → RAW/CLEAN 전처리 → 학습 → TEST 평가·예측을 실행합니다. SQL 직접 수정 없이 전체 흐름을 실습하고 코드 도움말로 동작을 설명합니다.

미션과제는 12종 중 하나를 선택합니다. 선택한 CSV의 컬럼·분류 이름을 반영한 **선택 미션 SQL 가이드**를 사용합니다. 스키마 조회의 생성 탭은 **① 원본 DATA → ② 전처리 PREPARED → ③ 예측 PREDICT** 순서입니다. 테이블과 RUN 생성 SQL을 복사·실행하거나 내려받아 `sql/custom/mission/01_tables.sql`·`02_procedure.sql`에 직접 저장·수정합니다. 선택·다운로드는 파일을 자동으로 덮어쓰거나 DB를 실행하지 않습니다. 현황 아래의 기본 주식 예제 생성 팝업은 제공하지 않습니다.

본인 발급 DB 계정으로 접속한 SQL Developer에서 계정 확인 → 테이블 → RUN 프로시저 전체를 F5 실행합니다. CSV 적재 도움말의 로컬 파일 명령으로 묶음 적재하거나 SQL Developer 데이터 가져오기를 사용하고, 선택 미션의 SQL 가이드로 PREPARE → INIT 또는 재학습을 실행합니다. 웹의 연결·상태 확인 후 원본·준비값·모델을 조회하고 TEST 평가·예측을 실행합니다. 전처리·TRAIN 오류행의 학습 제외 기준과 사유(FIT_YN·EXCLUDE_REASON)를 점검·보완해 설명합니다. 고정 TEST와 정답은 보존합니다.

창의과제는 문제·데이터·특성·타깃·전처리·모델·검증을 직접 설계합니다. `sql/custom/creative/01_tables.sql`·`02_procedure.sql`에는 고정 이름·입출력 규칙만 남기며 실행 답안 SQL은 제공하지 않습니다. 학생이 직접 테이블과 프로시저를 작성·적용합니다. 테이블 생성·전처리·모델 생성은 직접 SQL로 수행하고 CSV는 화면에서 업로드·적재합니다. 웹은 연결·객체·컬럼·인자·실행 가능 여부를 확인하고 원본·준비값·모델 조회와 TEST 평가·예측 실행을 제공하며 안내 쿼리는 제공하지 않습니다.

미션·창의는 DATA·PREPARED·PREDICT·RUN 이름, CASE_ID와 PREPARED의 PREP_MODE·SOURCE_KIND·USE_YN·FIT_YN·EXCLUDE_REASON·PREPARED_AT 운영 컬럼, p_action·p_mode·p_result·p_sql 인자를 유지합니다. EVALUATE 결과는 VARIANT·ACTUAL·PREDICTED·N, PREDICT 결과는 CASE_ID·PREDICTED·PROBABILITY입니다. 같은 계약을 유지하면 웹 소스 수정 없이 본인 SQL을 실행합니다.

세 과제는 현황·학습데이터·모델 생성·비교·예측 실행 네 단계로 진행합니다. 객체 준비 완료와 CSV 적재·전처리 저장·모델 생성 완료는 별개입니다. 파일 저장만으로 DB는 바뀌지 않고 SQL만 적용하면 서버 재시작은 필요 없습니다. 창의 원본 사례는 TRAIN·TEST·별도 예측 합계 10,000건 이하이며 직접 SQL 생성과 누적 적재도 포함합니다. 웹의 파일별 5,000행 / 2 MiB 제한과 구분합니다.

## 데이터와 평가

기본 CSV는 UCI Dow Jones Index(CC BY 4.0)의 실제 2011년 주간 시세를 가공했습니다. 다음 주 종가 > 시가이면 BUY, 나머지는 SELL입니다. 이번 주 등락률·고저폭·거래량 증감률·종가·종목만 특성으로 씁니다. 날짜·분할·사용 여부·미래 가격은 특성에서 제외합니다.
TRAIN 330행(1/7~3/18), TEST 360행(4/1~6/17), 경계 주 3/25는 N 30행, 별도 예측 6/24는 30행입니다. 결함 시드 20261120. data/stock-source.json에 출처·가공을 기록합니다. 생성기·원본 아카이브·복구표는 reference/에만 둡니다. 학습 직전 TRAIN 정답 기간의 TEST 중첩을 검사합니다. 같은 TEST로 정확도·BUY 정밀도/재현율·오분류를 비교하며 정제의 성능 향상을 보장하지 않습니다.
기본 50점(본인 수행·이해도 40, 데이터·전처리 5, 검증·해석 3, 재현성·제출 2), 미션 30점(문제 5, 구현 20, 제약 5), 창의 20점(설계 10, 이유·활용 10)입니다. 학생 직접 코딩·AI 보조 활용을 권장합니다. 복제 제공자와 이용자 모두 감점하며 공통 샘플과 정상 개념 토론은 구분합니다.

## 학생 배포·제출

```powershell
.\scripts\compress.ps1
```

downloads/COM22417_학번_20261120.zip을 갱신하며, 기존 downloads/COM22417_과제설명및평가.html을 ZIP 루트에 같은 이름·내용으로 포함합니다. 통합 안내 원본은 압축 과정에서 덮어쓰지 않고 별도 개발환경설정 HTML을 생성하지 않습니다. 검증 실패 시 이전 ZIP을 보존합니다. 개별 배포는 -StudentId, 경로 변경은 -Output을 사용합니다. 학생은 본인 학번 폴더를 만들고 ‘여기에 압축 풀기’를 사용합니다. ZIP 안에는 포장용 상위 폴더가 없습니다.
공통 ZIP의 명단은 가상 예시만, 개별 ZIP은 본인 한 명만 포함합니다. student.env는 공개 예제에서 만들며 DB_USER·DB_PASSWORD·WALLET_PASSWORD는 비어 있습니다. 원본 Wallet은 포함합니다. Markdown·운영문서·개인 설정·실제 전체 명단·강사 교재·설치파일·wheel·runtime·가상환경·로그·.local은 제외합니다. 다른 폴더로 옮긴 후에는 .venv를 새로 설치합니다.
설치자료는 reference/installers에 두고 오프라인 PC에만 별도 제공합니다. 온라인 설치가 기본이며 확장은 VS Code에서 누락분만 설치합니다. VC++ Runtime은 Thin에는 필요 없고 Thick 로드 오류 시 경로·x64·버전부터 확인합니다.

학생 Git 명령은 scripts/deploy-github.ps1이며 본인 HTTPS 저장소 주소를 필수로 받습니다. 기본 미리보기, 선택 -Prepare, 명시적 -Push이며 강제 push하지 않습니다. 강사 Git·Render 운영은 instructor/입니다. 강사 Git 대상은 https://github.com/initgroup/pcuora.git 입니다. 학생도 본인 Git·Render에 배포할 수 있습니다. scripts/render-build.sh·render-start.sh와 backend/hosting.py를 공유하며 서비스별 본인 DB 계정 하나·프로세스 하나·메인 로그인을 사용합니다. 실제 비밀번호는 문서에 쓰지 않습니다.


강사용 main 배포는 프로젝트 루트에서 다음 명령으로 실행합니다. 기본 실행은 기존 강사 배포기의 허용 목록·비밀값 검사·이력 보존을 거쳐 업로드합니다. 학생용 ZIP/Git에는 이 진입점을 포함하지 않습니다.

~~~powershell
Set-Location 'D:\work\pcu\2026H2\COM22417\V01041'
.\scripts\git-publish-main.ps1
~~~

미리보기는 -Preview, 업로드 없이 로컬 커밋 준비는 -Prepare입니다. 이 파일은 자신의 위치에서 루트를 계산하므로 다른 작업 폴더에서는 스크립트의 전체 경로로 호출할 수 있습니다.

보고서는 submission/report.pdf, report.html, report.txt 중 하나, PPT는 submission/presentation.pptx 또는 presentation.ppt를 직접 작성합니다. 첫 접속 증빙으로 메인 로그인 정보·DB 연결 테스트 결과 카드를 캡처해 포함합니다. scripts/submit.ps1은 source/에 Python·SQL·웹 소스, report/에 PPT·보고서를 담습니다. 필수 자료 누락 시 중단합니다. Wallet·인증정보는 제출에서 제외합니다. 제출은 2026-12-18(금) 18:00 KST까지 별도 수업 공지 경로이며 웹은 제출 접수 시스템이 아닙니다.

## 강사 교재·검증

화면 디자인 검사는 실제 DB 대신 격리된 합성 응답을 사용합니다. node reference/tests/verify_workspace_visual_browser.cjs는 세 과제의 네 단계·SQL·스키마·데이터·도움말을 1440·768·390·320px에서 검사하고 runtime/workspace-visual-browser-verification.json에 기록합니다. verify_main_browser.cjs는 로그인·메인·계정 전환·로그아웃 후 재진입·만료를 확인합니다. 이 검사는 Oracle 실행 검증과 구분합니다. 도움말은 비동기로 내용이 늘어나도 창을 화면 안으로 보정하며 닫으면 호출 버튼으로 키보드 초점을 돌려줍니다.

로그인한 모든 학생은 하단 ‘과제 설명 및 평가’ 메뉴에서 기존 통합 HTML을 새 탭으로 엽니다. 개발 원본은 downloads/COM22417_과제설명및평가.html이며 학생 ZIP에서는 루트의 같은 파일을 사용합니다. 문서 본문은 최종 소스의 수행 순서·평가·제출 기준에 맞춰 현행화합니다. 강사(V01041)에게만 그 위에 ‘강사용 OML 교재’ 메뉴가 표시됩니다. instructor/python-web-lecture.html과 코드 발췌 주소는 인증된 강사만 열 수 있습니다. 학생 ZIP/Git/제출에서는 교재·샘플·생성기를 제외합니다. 직접 파일을 열어도 읽을 수 있습니다. instructor/build_lecture.py로 재생성하고 verify_lecture.py로 현재 소스·줄·해시를 대조합니다.

```powershell
python -m unittest discover -s reference/tests -p "test_*.py"
python reference/tests/verify_final_ddl.py
python reference/tests/verify_simple_db.py
python reference/tests/verify_simple_http.py
python reference/tests/verify_simple_assignments.py
python reference/tests/verify_prediction_contract.py
node reference/tests/verify_simple_browser.cjs
python instructor/verify_lecture.py
python reference/tools/verify_release.py
python reference/tools/audit_student_content.py
```

verify_simple_db는 현재 기본 샘플 모델을 재생성·확정해 검증합니다. 원본 행은 보존합니다. verify_prediction_contract는 현재 CLEAN 모델에 20가지 컬럼 구성을 전달하는 읽기 전용 검증이며 데이터·모델을 변경하지 않습니다. HTTP/브라우저 검증은 실제 로그인과 조회·예측을 수행합니다. 결과는 runtime/에 기록합니다. 2026-11-17 전환 전 공개 소스는 backups/, 구형 DB 원문·행·DDL과 제거 기록은 .local/simple-before-20261117/에 보관했습니다. 현재 기본 구조는 STUDENT00.OML_BASIC_DATA·STUDENT00.OML_BASIC_PREDICT·OML_BASIC_RUN과 RAW/CLEAN OML 모델입니다. 구형 활성 객체는 없으며 휴지통의 OML_CLS_STATE와 종속 인덱스만 백업 후 정리했습니다. 현재 모델의 DM$ 내부 객체와 일반 마당서점 객체는 유지합니다.


`verify_final_ddl.py`는 학생 배포 목록·기존 공통 ZIP의 최종 정의 파일과 과제별 템플릿, 실제 DB의 기본 객체 VALID·컴파일 오류·프로시저 원문·컬럼 이름/타입을 읽기 전용으로 대조합니다. 결과는 `runtime/final-ddl-verification.json`입니다. 빈 계정의 신규 생성 검증과는 구분합니다. 기본과제는 `scripts/db-init.ps1` 적용 → CSV 적재 → 전처리 저장 → 최초 학습 → TEST 평가 → 모델 확정 순서로 준비합니다. 미션은 선택 미션에서 내려받거나 수정한 `01_tables.sql` → `02_procedure.sql`을, 창의는 직접 작성한 두 파일을 같은 계정에서 F5 실행합니다. `.local` 이관 파일은 필요 없으며 기존 컬럼 변경은 별도 ALTER로 적용합니다.

## 모델 학습·관리 (2026-11-18)

모델 코딩도움말 원문 대조(2026-11-19): 내부 프로시저 선언부·학습 SELECT·실행 분기를 따로 잘라 하나의 PL/SQL처럼 이어 붙이지 않습니다. 각 블록은 로컬 파일의 연속된 원문 구간이며 파일·시작/끝 줄과 선언/실행 역할을 표시합니다. INIT은 모드 확인 → 모델 존재 검사 → p_sql 지정 → validate_source/validate_prepared → CREATE → 결과 반환 순서를 보여주고 공통 실행부의 IF~END IF 전체를 보존합니다. 실제 SQL Developer 호출 예제는 별도입니다. SELECT는 전체 파일의 몇 번째 q 문자열인지로 고르지 않고 해당 TRAIN/EVALUATE/PREDICT 구간에서 선택하며, 구조가 달라 위치를 확정할 수 없으면 전체 원문을 표시합니다. 도움말은 로컬 정의이며 DB 저장 원문과의 일치는 USER_SOURCE 또는 읽기 전용 verify_final_ddl.py로 확인합니다.

미션 예시 선택(2026-11-19): 미션 현황 첫 화면에서 e스포츠 팀 경기력·캠퍼스 축제 혼잡도·OTT 예상 별점·중고거래 판매 속도·우주 탐사 후보 등급·캠퍼스 Wi-Fi 품질·공유 자전거 수요·메이커 작품 완성도·재활용 포장 적합도·스마트 온실 환경·온라인 주문 배송 소요·모바일 앱 사용성 12종과 학습·TEST/별도 예측 CSV 링크를 바로 제공합니다. 예시 목록은 배포된 data/catalog.json으로 서버에서 렌더링하므로 DB 객체 준비 여부와 관계없이 볼 수 있습니다. 현황 카드와 학습데이터의 선택 목록은 동기화하고 선택한 주제를 예측 단계에도 표시합니다. 주제 선택·다운로드는 DB 생성·적재를 수행하지 않습니다. 제공 CSV의 컬럼에 맞게 미션 SQL을 작성·F5 적용한 뒤 파일을 선택하고 CSV 교체 적재를 누르세요. 로컬 명령과 SQL Developer 가져오기도 사용할 수 있습니다. TRAIN 1,200행·고정 TEST 300행·별도 예측 30행을 유지합니다.

중첩 스크롤(2026-11-19): 웹페이지·레이어 팝업·강사용 교재의 코드 박스는 `overscroll-behavior: auto`를 사용합니다. 내부 박스의 위·아래 끝에서는 브라우저 기본 동작에 따라 상위 스크롤 영역으로 이어집니다. 표·팝업 본문 등 다른 스크롤 박스도 기본 `auto` 동작을 유지하며 휠·터치 이벤트를 가로채지 않습니다.

조회 표 표시(2026-11-19): 기본·미션·창의의 원본·전처리·예측 입력·예측/평가 결과와 CSV 미리보기는 헤더에 실제 컬럼명과 제공 설명을 함께 표시합니다. 셀에는 조회값에 매수/매도 문구·%·NULL 대시를 덧붙이지 않으며 NULL은 빈 셀, 확률은 조회된 0~1 값으로 표시합니다. 문자열의 공백과 줄바꿈은 유지하고 HTML 특수문자는 안전하게 표시합니다. 표 밖의 성능 요약과 비교 지표는 별도로 계산한 표시값입니다.

원본 테이블 재생성·적재(2026-11-19 점검): 업로드된 CSV 전체를 Python 메모리에 읽어 검사한 뒤 `STUDENT00.OML_BASIC_DATA DROP → CREATE → 단일 INSERT에 500행씩 바인드(executemany) → COMMIT`으로 다시 적재합니다. 원본 테이블에서 SELECT하여 복구하는 방식이 아닙니다. `INSERT SELECT`는 그 다음 별도로 실행하는 전처리 저장(DATA → PREPARED)입니다. 공통 준비는 기존 PREPARED·PREDICT의 행을 보존하고 없는 테이블을 추가하며 RUN 정의·코멘트를 적용합니다. 코딩도움말의 SQL 단계에서 원본 재생성·CSV 적재 순서와 관련 객체 정의를 개별 항목으로 확인합니다. CSV 바인드는 웹이 전달하므로 코드 전체를 SQL Developer에서 F5 실행하는 것만으로 파일이 적재되지는 않습니다.

일반 CSV 교체는 INSERT 실패 시 기존 행이 복원되지만, 재생성의 DROP·CREATE는 자동 커밋되므로 INSERT 실패 시 새 빈 테이블로 돌아갑니다. DROP 이후 실패하면 현황을 다시 조회하고, 생성된 테이블에 같은 CSV를 일반 교체 적재하여 복구합니다. 테이블이 없으면 준비 후 적재합니다. 원본 교체 성공 또는 DROP 완료 시 이전 웹 전처리·학습·확정 기록을 해제하므로 같은 CSV라도 전처리 저장 → 재학습 → 확정이 필요합니다. `verify_oml_lab_db.py`는 QA 객체에서 실제 재적재 720행·원본 ID 변경·다른 테이블 보존·두 종류의 롤백·재생성 없는 복구까지 검증합니다. `verify_oml_lab_browser.cjs --recreate-fixture-only`는 도움말 시작 위치·선택 CSV 표시·실패 후 상태 재조회를 DB 변경 없이 검증합니다.

2026-11-19 화면 상태 안내: 기본·미션·창의는 확인 전 / 확인 중 / 객체 준비 필요 / 준비 완료 / 조회 실패를 구분합니다. 준비 완료는 테이블·프로시저의 사용 가능 상태이며 CSV 적재·전처리·모델 생성 완료와 별개입니다. 기본과제 준비 버튼은 조회가 끝나면 다시 사용할 수 있고, 준비 완료 후에는 ‘프로시저 다시 등록’으로 표시합니다. 모델 작업 버튼 아래에는 이미 생성됨·모델 없음·전처리 필요·학습 제공 0행 등 실제 사용 불가 사유를 표시합니다. 예측 화면은 최신 모델·확정·입력 적재 조건을 각각 안내합니다. `node reference/tests/verify_oml_lab_browser.cjs --status-fixtures-only`는 브라우저 응답만 바꾸어 지연·실패·복구·버튼 상태를 검증하며 DB 변경 API를 호출하지 않습니다.

세 과제에 `templates/model-lab.html`을 공통 적용합니다. RAW/CLEAN은 준비 방식과 작업 대상 모델 하나를 선택합니다. RAW를 전처리 저장·학습한 뒤 CLEAN도 따로 저장·학습하여 같은 TEST와 예측 입력으로 비교합니다.

- PREPARE: 선택 방식의 원본을 INSERT SELECT하여 PREPARED에 저장·COMMIT. 모델은 만들지 않습니다.
- INIT: 선택한 모델이 없을 때 준비된 FIT_YN=Y 행으로 CREATE_MODEL2.
- RETRAIN: 준비값·FIT_YN·학습 설정을 반영하여 DROP_MODEL → CREATE_MODEL2.
- ADD_TRAIN: SQL Developer에서 원본 TRAIN INSERT → VALIDATE → COMMIT → PREPARE 후 전체 FIT_YN=Y를 DROP_MODEL → CREATE_MODEL2. 기본은 준비·모델 작업을 화면에서 실행하고 미션·창의는 직접 SQL로 실행합니다. 데이터가 2배·3배여도 같은 흐름이며 증분 갱신이 아닙니다.
- DELETE: 선택 모델만 DROP_MODEL로 정리. DM$ 내부 객체는 직접 삭제하지 않습니다.

Oracle 명령은 단일 프로시저 안의 create_raw_model/create_clean_model, drop_raw_model/drop_clean_model에 실제 모델명을 명시합니다. 고정 SELECT를 data_query에 전달하며 별도 SQL 조립 프레임워크를 사용하지 않습니다. 기본 ?는 화면 버튼에서 시작하며 실행 SQL 단계에서 Oracle 명령·SELECT 원문과 SQL Developer 호출 예제를 선택합니다. Python 호출은 서비스·DB 연결 단계에서 확인합니다. 미션은 선택 미션에 맞는 실행 SQL을 제공하며 창의에는 안내 쿼리를 제공하지 않습니다.

행 추가·수정·삭제 UI는 제공하지 않습니다. 학습·예측 탭 상단에는 소유자까지 포함한 테이블명을 크게 표시합니다. 세 과제 모두 화면 CSV 적재·교체를 제공하며 기본은 재학습·삭제도 제공하고 변경 전 이동식 확인창을 사용합니다. 미션·창의의 테이블 생성·전처리·학습은 직접 SQL로 수행하며 화면은 CSV 적재·연결·상태·조회·평가·예측을 제공합니다.

미션·창의의 고정 입출력 계약은 OML_MISSION_/OML_CREATIVE_의 DATA, PREPARED, PREDICT, RUN을 사용합니다. CASE_ID·준비 운영 컬럼과 네 프로시저 인자를 유지하고 특성·타깃·라벨은 SQL에서 자유롭게 바꿉니다. CSV는 실제 원본 컬럼 메타데이터에 맞춰 적재합니다. EVALUATE 출력은 VARIANT·ACTUAL·PREDICTED·N, PREDICT 출력은 CASE_ID·PREDICTED·PROBABILITY이며 추가 출력도 표시됩니다. 웹 소스 수정 없이 두 SQL 파일에서 구현합니다.

원본이나 프로시저를 직접 변경하면 PREPARE부터 다시 실행합니다. 기본은 화면에서 실행하고 미션·창의는 직접 SQL로 실행한 뒤 웹 상태를 갱신합니다. 준비값·FIT_YN만 직접 수정한 경우에는 COMMIT 후 재학습하며 다시 PREPARE할 필요가 없습니다. 같은 값을 재준비하며 시각만 달라졌다면 모델은 최신 상태를 유지합니다. 예측 CSV 적재와 실행은 분리하며 같은 입력 해시의 이전 성공 결과와만 분류·확률 변화 행 수를 비교합니다. 기록은 새로고침·로그아웃 시 초기화됩니다.

검증: `python reference/tests/verify_oml_lab_db.py`는 배포 DDL을 OML_QA_LAB_* 격리 이름으로 신규 생성하고 최초/추가/재학습/삭제·최신 여부 차단·자유 컬럼/라벨을 실제 Oracle에서 확인한 뒤 정리합니다. `node reference/tests/verify_oml_lab_browser.cjs`는 실제 로그인·메타데이터 조회와 화면·도움말·반응형 배치를 검증합니다. 결과는 runtime/에만 둡니다.


로그인 세션은 마지막 인증 작업 후 유휴 30분 기준으로 서버가 만료를 판단한다. /api/session 조회·화면 타이머는 연장하지 않으며 /api/session/extend POST는 유효한 로그인과 CSRF를 검사한다. 우측 상단에 남은 시간·시간 연장·로그아웃을 제공한다. 만료 시 전용 이동 레이어로 사유를 안내하고 확인/ESC로 닫은 뒤 로그인 인트로로 이동한다. 다른 탭의 연장과 계정 전환·로그아웃·서버 재시작을 구분하며, 만료 세션의 재연장을 허용하지 않는다.

실습 중에는 실행 프로세스를 유지합니다. 자동 reload는 꺼져 있으며 HTML·JS·CSS는 브라우저 새로고침, 조회용 SQL은 다음 요청에 반영됩니다. Python 변경만 명시적 재시작이 필요하고 재시작 시 로그인 상태는 종료됩니다. 다른 로컬 앱과 쿠키가 섞이지 않도록 프로젝트 경로별 전용 OML 쿠키를 사용합니다. DB 풀 유휴 60초는 웹 로그인 30분과 별개이며 연결 종료·DB 오류만으로 로그아웃하지 않습니다. 세션 경계·메뉴 이동·수동 연장·쿠키 충돌 검사는 reference/tests/test_session_runtime.py에서 실제 DB 없이 수행합니다.

미션 스키마 조회와 sql/custom/mission/01_tables.sql은 각 CREATE TABLE 바로 위의 짧은 PL/SQL에서 USER_TABLES로 해당 테이블만 존재 확인 후 DROP한다. 별도 초기화 박스·파일을 제공하지 않는다. 기존 행 삭제·DDL 취소 불가를 안내하며 프로시저·모델·다른 테이블을 함께 삭제하지 않는다. 미션 변경 후에는 수정한 프로시저 적용·CSV 적재·전처리·재학습을 진행한다. 웹 조회·선택만으로 SQL을 실행하지 않는다.

기본과제 DB 준비 버튼은 준비 전 「테이블·프로시저 준비」, 준비 완료 후 「프로시저 다시 등록」으로 표시한다. 완료 후에는 바로 실습 가능하며 sql/classifier.sql 수정 시에만 다시 등록하고 기존 테이블·데이터를 유지한다는 설명과 도움말 이름을 함께 맞춘다.

상단 .tools의 글자 크기·시간 연장·로그인/로그아웃 버튼은 studio.css의 전용 연한 hover 배경과 짙은 글자색을 유지한다. 일반 기본 버튼의 진한 hover 배경 규칙에서 .tools button을 제외한다.

미션 선택은 로그인 명단의 학번·DB 계정별로 runtime/mission-selection-해시.json에 원자적으로 저장한다. 인증·CSRF가 필요한 미션 선택 API를 사용하며 재로그인·화면 재진입·서버 재시작 후 복원한다. 로그아웃은 화면 선택만 비우고 저장값은 지우지 않는다. CSV 적재·테이블 생성·모델 상태와 선택 기록은 분리하고 지연 응답이 다른 계정의 선택을 덮어쓰지 않도록 한다.

미션 12종의 이름은 catalog의 고정 순서에 따라 1~12번을 함께 표시한다. 카드·학습데이터 선택 목록·현황/모델/예측 안내·CSV/스키마/SQL 가이드는 같은 catalog 제목을 사용하며, 선택 저장 키와 CSV/DB 식별자는 변경하지 않는다.

코딩도움말의 화면 원문은 클릭한 버튼/매크로 호출 부분을 강조하고 HTML의 긴 줄을 줄바꿈해 표시합니다. 선택 구간 복사는 해당 줄의 원문을, 파일 전체 복사는 마지막 줄바꿈까지 전체 원문을 유지합니다. 기본과제의 현재 탭을 요청에 전달하고 미션 상단 새로고침(GET 조회)과 객체·모델 연계 확인(POST 연계 저장)의 호출 흐름을 구분합니다. 전체 렌더링 버튼 점검은 reference/tests/verify_coding_flow_browser.cjs --all-buttons를 사용하며 실제 DB 변경을 수행하지 않습니다.


## CSV 파일 적재와 자원 관리

기본과제는 기존 파일 선택·미리보기·화면 적재를 사용합니다. 미션·창의는 직접 만든 본인 테이블에 CSV를 업로드하여 적재합니다. CSV 첫 줄은 영문 컬럼명, 구분자는 쉼표, 인코딩은 UTF-8/BOM이며 헤더 순서가 달라도 이름으로 대응합니다. 빈 셀은 NULL, unknown·범위 밖 값은 원문으로 보존합니다. 파일당 2 MiB / 5,000행 제한을 유지합니다.

미션 도움말에서 선택한 주제·파일·발급 DB 계정을 반영한 아래 명령을 복사합니다. 프로젝트 터미널에서 실행하며 STUDENT00은 본인 발급 계정으로 바꿉니다. 파일은 --file에 절대 경로 또는 프로젝트 루트 기준 경로를 지정합니다.

~~~powershell
& .\.venv\Scripts\python.exe .\scripts\load_mission_csv.py --mission esports --kind training --file "data/examples/esports.csv" --owner STUDENT00
~~~

첫 실행은 검사만 합니다. 대상 테이블의 기존 행 전체 교체에 동의하면 명령 끝에 --replace를 붙입니다. 예측 CSV는 --kind prediction과 해당 예측 파일을 지정합니다. 비밀번호·Wallet은 프로젝트 security/student.env 설정을 사용하며 명령행에 넣지 않습니다. 스크립트는 테이블·모델을 만들지 않습니다. 생성은 SQL 가이드로 먼저 완료하세요. SQL Developer의 데이터 가져오기를 쓰는 경우에도 첫 줄 헤더·쉼표 구분으로 컬럼을 대응하고 본인 계정과 적재 결과를 확인합니다.

- 적재 경로: scripts/load_mission_csv.py → backend/csv_import.py → backend/sql_files.py → custom_insert.sql. 파일은 256 KiB 초과 시 임시 디스크에 보관하고 검사 후 같은 스냅샷을 읽습니다. 기본 업로드의 파싱 목록도 기존 2 MiB/5,000행 한도 안에서만 유지하며 전체 바인드 목록을 추가 복제하지 않습니다.
- SQL은 한 문장, 바인드는 최대 500행씩, 커서는 작업당 하나입니다. 1,500행은 executemany 3회이며 행별 SQL 문자열을 생성하지 않습니다. DELETE와 모든 묶음은 한 트랜잭션으로 마지막에만 COMMIT, 오류 시 전체 ROLLBACK합니다. 원본 테이블 재생성의 DROP/CREATE는 DDL이므로 이 롤백 범위에 포함되지 않습니다.
- 실행 기록에는 SQL·전체 행 수·묶음 수만 담고 CSV 값 전체를 되돌려 보내지 않습니다. 기록은 요청당 최대 100개이며 초과 건수는 omitted_records로 표시합니다.
- 웹 DB 작업의 기존 단일 실행 잠금을 유지하며 python-oracledb 풀은 프로세스당 min=0/max=1입니다. 유휴 timeout=60초(Thin 드라이버 점검 주기에 따라 최대 약 120초), 대여 대기 최대 5초, 세션 최대 수명 30분, statement cache 30개입니다. 새 물리 연결만 session.sql을 적용하고 작업 후 미커밋 변경을 롤백하여 반환합니다. 웹 로그인 유효시간과 DB 풀 수명은 별개입니다.
- 로그인/연결 테스트는 입력 비밀번호를 새 연결로 검증합니다. 인증 성공·계정 변경·로그아웃·세션 만료 감지·프로세스 종료 시 풀을 정리하며 진행 중 작업은 반환할 때 닫습니다. Wallet 압축 해제는 새 연결 설정 준비 시 파일 변경을 확인해 재사용합니다. Wallet 교체 후 서버를 재시작하세요.
- RAW/CLEAN 모델 최신성 비교에서는 원본·프로시저 조회 결과를 한 호출 안에서 공유합니다. 변경 감지를 생략하는 전역 결과 캐시는 사용하지 않습니다. JSON 해시는 같은 형식을 조각 단위로 처리하여 기존 판정값을 보존합니다.

검증: reference/tests/test_csv_resources.py는 묶음 수·원문 보존·잘못된 헤더·늦은 실패의 전체 롤백·계정 검사·풀 재사용/퇴출을 학생 DB 변경 없이 확인합니다. 실제 DB 연결 검증은 SELECT 및 세션 설정만 수행하며 실제 CSV 교체 적재와 구분합니다. 공식 근거: [python-oracledb 배열 적재](https://python-oracledb.readthedocs.io/en/v3.4.1/user_guide/batch_statement.html), [연결 풀](https://python-oracledb.readthedocs.io/en/v3.4.1/user_guide/connection_handling.html#connection-pooling).

파일 탐색 응답은 flow.version=2이며 flow.files에 실제 파일과 생성 예제의 원문을 각각 한 번씩 담습니다. 구간은 file_id와 line/end_line으로 참조합니다. 같은 경로의 생성 SQL과 실제 파일은 합치지 않습니다. 파일과 AST 캐시는 도움말 요청 한 번 안에서만 공유하고 다음 요청은 최신 로컬 파일을 읽습니다. 화면 이동은 DB 실행을 하지 않습니다.

미션·창의의 학습/예측 CSV 파일 선택은 로그인 후 DB 객체 준비와 관계없이 사용할 수 있습니다. 대상 테이블이 있으면 CSV 교체 적재로 업로드할 수 있습니다. 미션·창의 모두 CSV 업로드를 제공하며 테이블 생성·전처리·학습은 직접 SQL로 수행합니다. 미션을 바꾸거나 로그아웃하면 파일 선택을 비웁니다.

통합 학생 안내는 downloads/COM22417_과제설명및평가.html에서 관리한다. 최종 소스 기준으로 개발환경 설정·과제 수행방법·과제 평가 기준·Git/Render 배포 4개 메뉴를 현행화했다. 변경 후에는 해당 안내와 객체 규약 부록의 흐름을 맞추고 학생 ZIP 루트에 통합 HTML을 같은 이름·바이트로 포함하여 검증한다. 별도 개발환경설정 HTML은 생성하지 않는다.


공통 흐름·세부 현황 검사는 `node reference/tests/verify_coding_flow_browser.cjs --workspace-flow-only`로 수행합니다. 세 과제의 단계 순서·동일한 스타일·버튼과 결과 인접 배치·3/4 부분 완료·상세 레이어의 추가 요청 없음·초점 복귀·모바일·로그아웃 정리를 확인합니다. CSV 저장 검사는 `node reference/tests/verify_assignment_files_browser.cjs --upload`로 수행하며 실제 학생 DB를 교체하지 않습니다.


12종 학생 ZIP의 크기 검사는 앱·설정·안내·메타데이터(캠퍼스 사진·미션 CSV 제외) 400 KB, 미션별 학습/예측 CSV 압축 합 15 KB, 캠퍼스 원본 500 KB로 구분하며 전체 ZIP은 1,000,000바이트 미만을 유지합니다. 미션 파일 수가 늘어난 것을 코드 비대화로 계산하지 않으며 허용 목록·원본 일치·비밀값·경로 이동 검증도 함께 수행합니다.

미션·창의 모델 비교표는 기본과제와 같은 compare-table·model-comparison-wrap·score-row·compare-model-name 스타일을 사용한다. 모델명은 열 제목, 모델 상태는 배지, 정확도는 강조 숫자, 정답/TEST·오분류는 같은 행으로 표시한다. 상태 조회 실패·로그아웃·미생성·현재 모델과 다른 평가 결과를 성공으로 표시하지 않으며 기본과제 전용 확정 동작을 임의로 추가하지 않는다.

강사 Git 배포는 격리 checkout에서 기존 manifest 관리 파일을 갱신한다. 폐기 파일은 경로·링크·기존 SHA256을 확인한 뒤에만 삭제하며 Git의 CRLF/LF 변환만 허용한다. 관리 밖 파일·실제 내용 변경·경로 탈출은 중단한다. 원격 main 이력을 보존하고 강제 push하지 않는다. 검증은 reference/tests/test_instructor_git.py의 로컬 임시 저장소를 사용한다.

학생 Render 설정은 통합 안내의 ‘04 Git·Render 배포’를 따릅니다. Source는 본인 Git Provider 저장소, Branch는 main, Root Directory는 비움, Build는 bash scripts/render-build.sh, Start는 bash scripts/render-start.sh, Health Check Path는 /healthz입니다. /healthz는 DB 연결을 조회하지 않으므로 메인 연결 테스트도 수행합니다. 환경변수·Wallet은 Render에서 등록하고 본인 한 명의 security/students.json은 본인 Git에 포함합니다. Render는 학번·이름으로 db_user를 찾아 환경변수 DB_PASSWORD로 인증하며 비밀번호 입력·로컬 파일 저장은 하지 않습니다.

강사 운영·검증 파일 허용 목록은 reference/distribution/public-files.json으로 분리하며 학생 실행 허용 목록은 scripts/source_files.py에 둡니다. 참조 목록은 학생 ZIP/Git에 포함하지 않습니다. 학생 Git에는 ZIP 루트의 통합 안내 HTML을 포함하여 Render에서도 안내 메뉴를 제공합니다.

학생 Git은 본인 한 행의 security/students.json만 검증하여 명시적으로 포함합니다. 강사 전체 명단은 강사 Git·공통 학생 ZIP에서 제외하며 학생.env·Wallet·비밀번호는 학생 Git에도 포함하지 않습니다. Render는 Git의 security/students.json을 우선 읽습니다. OML_ROSTER_FILE은 Git 명단이 없는 기존 강사 운영의 대체 경로입니다.

통합 안내의 개발환경 설정 4단계는 student.env 항목별 입력값과 students.json 필드·JSON 문법을 설명합니다. ‘파일 수정 → 본인 Git → Render 연결 관계’에서 로컬 환경파일 제외·본인 JSON 포함·운영 환경변수 재입력과 Wallet Secret Files를 구분합니다. GitHub main의 JSON 확인 후 Render 등록 순서를 따릅니다.

- 강사용 git-publish-main.ps1도 운영 Git에 본인 한 행의 security/students.json을 포함한다. instructor/scripts/git_publish.py의 publication_files가 경로·한 행·허용 필드·비밀번호 미포함을 검사하고 해당 파일만 명시적으로 add한다. 일반 소스 백업·공통 학생 ZIP의 명단 범위는 변경하지 않으며 전체 명단·환경파일·Wallet은 Git에 포함하지 않는다. 검증은 reference/tests/test_instructor_git.py의 실제 로컬 Git 저장소를 사용한다.

VS Code 탐색기에서는 runtime 하위 배포·검증 복제 저장소를 자동 탐색하지 않습니다. 실제 소스의 Git 장식은 유지하고 파일명의 Problems 색상·배지만 끕니다. 오류·경고는 Problems 패널과 편집기에서 확인합니다. 설정 반영 후에도 기존 표시가 남으면 명령 팔레트의 Developer: Reload Window를 실행하세요. 로컬 웹 서버를 재시작할 필요는 없습니다.

Git 전체 재배포는 `scripts/git-republish-main.ps1`을 사용합니다. 전체 배포 허용 목록을 격리 checkout에 동기화하고 내용이 같아도 새 커밋을 만들어 main에 push합니다. Git은 동일 파일을 중복 전송하지 않으며 기존 커밋 이력을 유지합니다. `-Preview`는 목록만, `-Prepare`는 로컬 커밋까지만 수행합니다. Render 자동 배포에는 연결된 Git Provider·main·On Commit 설정이 필요합니다. 일반 `git-publish-main.ps1`은 변경이 없으면 커밋·push 없이 Already up to date로 종료합니다. 개인 운영 명령은 Git 제외 `.local/operations-commands.txt`에 둡니다.
