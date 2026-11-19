"""제공 SQL 검증: 10개 미션 스키마와 배포 쿼리를 OML_QA_LAB_* 객체에서만 검사합니다."""
import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import oracledb
from backend.db import connection,student_settings,safe_error
from backend import assignment_templates as tasks
from backend.sql_files import read_sql

PREFIX='OML_QA_LAB_SQL'
NAMES={suffix:PREFIX+'_'+suffix for suffix in ('DATA','PREDICT','PREPARED','RUN')}
CREATED=set()
REPORT={'generated_schemas':[],'queries':[],'source_files':[]}
def statements(source):
    for part in re.split(r'^/\s*$',source,flags=re.M):
        plain=re.sub(r'--[^\n]*','',part).strip().upper()
        if not plain:continue
        if plain.startswith(('CREATE OR REPLACE PROCEDURE','BEGIN','DECLARE')):
            yield part.strip()
        else:
            for statement in re.split(r'^;\s*$',part,flags=re.M):
                if re.sub(r'--[^\n]*','',statement).strip():
                    text=statement.strip()
                    plain=re.sub(r'--[^\n]*','',text).strip().upper()
                    yield text if plain.startswith(('BEGIN','DECLARE','CREATE OR REPLACE PROCEDURE')) else text.rstrip(';')
def generated_schemas():
    code="""const fs=require('fs'),vm=require('vm'),path=require('path'),root=process.argv[1];
const source=fs.readFileSync(path.join(root,'static/js/mission-schema.js'),'utf8');
const start=source.indexOf('function missionSchemaDefinition('),end=source.indexOf('function renderMissionSchema(');
if(start<0||end<start)throw Error('Schema generator boundary missing');
const build=vm.runInNewContext(source.slice(start,end)+';missionSchemaDefinition');
const items=JSON.parse(fs.readFileSync(path.join(root,'data/catalog.json'),'utf8'));
process.stdout.write(JSON.stringify(items.flatMap(item=>['training','prediction','prepared'].map(kind=>({key:item.key,kind,...build(item,kind)})))));
"""
    result=subprocess.run(['node','-e',code,str(ROOT)],check=True,capture_output=True,encoding='utf-8')
    return json.loads(result.stdout)
def qa_name(name):
    if not re.fullmatch(r'OML_QA_LAB_[A-Z0-9_]+',name) or len(name)>30:raise AssertionError('Unsafe QA identifier')
    return name
def execute_definition(conn,source):
    count=0
    for statement in statements(source):
        plain=re.sub(r'--[^\n]*','',statement).strip()
        target=re.match(r'(?:CREATE TABLE|CREATE OR REPLACE PROCEDURE|COMMENT ON (?:TABLE|COLUMN))\s+([A-Z0-9_]+)',plain,re.I)
        if target:
            name=qa_name(target[1])
        elif plain.upper().startswith('DECLARE'):
            # Only the exact shipped single-table existence/drop block is allowed.
            match=re.search(r"WHERE TABLE_NAME = '([A-Z0-9_]+)'",plain)
            assert match,'Missing guarded table name'
            name=qa_name(match[1])
            expected=("DECLARE\n  v_exists PLS_INTEGER;\nBEGIN\n  SELECT COUNT(*) INTO v_exists FROM USER_TABLES WHERE TABLE_NAME = '"+name+"';\n  IF v_exists > 0 THEN\n    EXECUTE IMMEDIATE 'DROP TABLE "+name+"';\n  END IF;\nEND;")
            assert plain==expected,'Unexpected destructive SQL in QA definition'
        elif not plain.upper().startswith('ALTER SESSION'):
            raise AssertionError('Unexpected definition statement')
        with conn.cursor() as cursor:cursor.execute(statement)
        if plain.upper().startswith(('CREATE TABLE','CREATE OR REPLACE PROCEDURE')):CREATED.add(name)
        count+=1
    return count
def drop(conn,name,kind='TABLE'):
    qa_name(name)
    if name not in CREATED:return
    with conn.cursor() as cursor:cursor.execute('DROP '+kind+' '+name+(' PURGE' if kind=='TABLE' else ''))
    CREATED.remove(name)
def snapshot(conn):
    with conn.cursor() as cursor:
        cursor.execute("SELECT OBJECT_NAME,OBJECT_TYPE,OBJECT_ID,STATUS FROM USER_OBJECTS WHERE OBJECT_NAME NOT LIKE 'OML_QA_LAB_%' AND OBJECT_TYPE IN ('TABLE','PROCEDURE','MINING MODEL') ORDER BY OBJECT_NAME,OBJECT_TYPE")
        return cursor.fetchall()
def expect_error(conn,sql,binds,code):
    try:
        with conn.cursor() as cursor:cursor.execute(sql,binds)
    except oracledb.DatabaseError as error:
        assert 'ORA-'+code in str(error),(code,str(error))
        conn.rollback();return
    raise AssertionError('Expected ORA-'+code)
def verify():
    catalog=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
    samples={item['key']:item for item in catalog}
    with connection(student_settings()) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT OBJECT_NAME FROM USER_OBJECTS WHERE OBJECT_NAME LIKE 'OML_QA_LAB_%'")
            assert not cursor.fetchall(),'Existing QA objects must be inspected first'
            cursor.execute("SELECT USER FROM DUAL");REPORT['user']=cursor.fetchone()[0]
        before=snapshot(conn)
        try:
            # 사용자 오류와 같은 COMMENT 문장을 존재하지 않는 QA 테이블에서 재현합니다.
            missing='OML_QA_LAB_SQL_MISSING'
            expect_error(conn,"COMMENT ON COLUMN "+missing+".UPDATED_AT IS 'SQL audit'",{},'00942')
            REPORT['missing_table_comment_error_reproduced']='ORA-00942'
            schemas=generated_schemas()
            assert len(schemas)==len(catalog)*3
            for index,schema in enumerate(schemas):
                name=qa_name('OML_QA_LAB_S'+str(index).zfill(2))
                source=schema['sql'].replace(schema['name'],name)
                count=execute_definition(conn,source)
                # Repeat with existing rows: only this table is replaced.
                with conn.cursor() as cursor:
                    cursor.execute("SELECT OBJECT_ID FROM USER_OBJECTS WHERE OBJECT_NAME=:name AND OBJECT_TYPE='TABLE'",name=name)
                    previous_id=cursor.fetchone()[0]
                execute_definition(conn,source)
                with conn.cursor() as cursor:
                    cursor.execute("SELECT OBJECT_ID FROM USER_OBJECTS WHERE OBJECT_NAME=:name AND OBJECT_TYPE='TABLE'",name=name)
                    assert cursor.fetchone()[0]!=previous_id
                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM USER_TAB_COLUMNS WHERE TABLE_NAME=:name",name=name)
                    assert cursor.fetchone()[0]==len(schema['columns'])
                    cursor.execute("SELECT COUNT(*) FROM USER_COL_COMMENTS WHERE TABLE_NAME=:name AND COMMENTS IS NOT NULL",name=name)
                    assert cursor.fetchone()[0]==len(schema['columns'])
                if schema['kind'] in ('training','prediction'):
                    item=samples[schema['key']]
                    file=item['filename'] if schema['kind']=='training' else item['prediction_filename']
                    payload=(ROOT/'data/examples'/file).read_bytes()
                    values,total=tasks.csv_payload(payload)
                    tasks.load_custom(conn,{'training_table':name,'prediction_table':name},values,prediction=schema['kind']=='prediction')
                    with conn.cursor() as cursor:
                        cursor.execute('SELECT COUNT(*) FROM '+name)
                        assert cursor.fetchone()[0]==total
                    if schema['kind']=='training':
                        expect_error(conn,'INSERT INTO '+name+" (CASE_ID,SPLIT) VALUES (999999,'DEV')",{},'02290')
                        expect_error(conn,'INSERT INTO '+name+" (CASE_ID,SPLIT) VALUES (999999,NULL)",{},'01400')
                REPORT['generated_schemas'].append({'mission':schema['key'],'kind':schema['kind'],'ddl_and_comments':count,'columns':len(schema['columns']),'csv_rows':total if schema['kind']!='prepared' else None})
                drop(conn,name)
                if schema['kind']=='prepared':print('Mission schema checked: '+schema['key'],flush=True)
            # 기본 배포 정의를 새 객체명으로 실행하여 모든 쿼리의 대상 스키마를 준비합니다.
            transform=lambda source:source.replace('OML_BASIC_',PREFIX+'_')
            for name in ('schema.sql','prediction_table.sql','prepared_table.sql','classifier.sql','table_comments.sql','session.sql'):
                execute_definition(conn,transform(read_sql(name)));REPORT['source_files'].append(name)
            with conn.cursor() as cursor:
                cursor.execute('SELECT LINE,TEXT FROM USER_ERRORS WHERE NAME=:name ORDER BY SEQUENCE',name=NAMES['RUN'])
                assert not cursor.fetchall(),'QA procedure compilation failed'
            values,total=tasks.csv_payload((ROOT/'data/classification.csv').read_bytes())
            tasks.load_custom(conn,{'training_table':NAMES['DATA'],'prediction_table':NAMES['PREDICT']},values)
            for path in sorted((ROOT/'sql/queries').glob('*.sql')):
                source=transform(path.read_text(encoding='utf-8-sig'))
                table=NAMES['PREPARED'] if path.name.startswith('prepared_') else NAMES['DATA']
                replacements={'table':table,'columns':'CASE_ID, SPLIT','values':':case_id, :split','view':NAMES['DATA']}
                for key,value in replacements.items():source=source.replace('{{'+key+'}}',value)
                assert '{{' not in source
                statement=list(statements(source))
                assert len(statement)==1,path.name
                plain=re.sub(r'--[^\n]*','',statement[0]).strip().upper()
                with conn.cursor() as cursor:
                    if path.name=='call_classifier.sql':
                        result=cursor.var(oracledb.DB_TYPE_CURSOR);sql=cursor.var(oracledb.DB_TYPE_CLOB)
                        cursor.execute(statement[0],p_action='VALIDATE',p_mode='RAW',p_result=result,p_sql=sql)
                        returned=result.getvalue()
                        if returned:returned.close()
                    else:
                        assert plain.startswith(('SELECT','INSERT','UPDATE','DELETE')),path.name
                        cursor.parse(statement[0])
                REPORT['queries'].append({'file':path.relative_to(ROOT).as_posix(),'check':'execute VALIDATE' if path.name=='call_classifier.sql' else 'Oracle parse'})
            # SQL Developer/SQLcl 호출 예시의 VARIABLE/PRINT는 클라이언트 명령입니다.
            source=transform(read_sql('examples/run.sql')).replace('{{procedure}}',NAMES['RUN']).replace('{{action}}','VALIDATE').replace('{{mode}}','RAW')
            variables=re.findall(r'^VARIABLE\s+(\w+)\s+(REFCURSOR|CLOB)\s*$',source,re.M)
            assert variables==[('result','REFCURSOR'),('executed_sql','CLOB')]
            source=re.sub(r'^(?:VARIABLE|PRINT)\b[^\n]*','',source,flags=re.M)
            with conn.cursor() as cursor:
                outputs={name:cursor.var(oracledb.DB_TYPE_CURSOR if kind=='REFCURSOR' else oracledb.DB_TYPE_CLOB) for name,kind in variables}
                for statement in statements(source):
                    binds={key:value for key,value in outputs.items() if ':'+key in statement}
                    cursor.execute(statement,binds)
                result=outputs['result'].getvalue()
                if result:result.close()
            REPORT['source_files'].append('examples/run.sql')
            # 명시적 원본 재생성 SQL도 격리 이름만 DROP하는지 실제 실행합니다.
            source=transform(read_sql('recreate_training.sql'))
            assert re.sub(r'--[^\n]*','',source).strip().startswith('DROP TABLE '+NAMES['DATA'])
            with conn.cursor() as cursor:
                for statement in statements(source):cursor.execute(statement)
            CREATED.remove(NAMES['DATA']);REPORT['source_files'].append('recreate_training.sql')
        finally:
            for name in list(CREATED):
                drop(conn,name,'PROCEDURE' if name==NAMES['RUN'] else 'TABLE')
        assert snapshot(conn)==before,'Original object metadata changed'
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM USER_OBJECTS WHERE OBJECT_NAME LIKE 'OML_QA_LAB_%'")
            assert cursor.fetchone()[0]==0,'QA cleanup failed'
        REPORT['production_objects_preserved']=True;REPORT['qa_objects_removed']=True
    REPORT['source_hashes']={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'sql').rglob('*.sql')}
    REPORT['scope']='Generated DDL/comments/CSV insertion; all query SQL Oracle parse; direct VALIDATE calls. Separate verify_oml_lab_db.py covers three task definitions and model execution.'
    (ROOT/'runtime/sql-provision-verification.json').write_text(json.dumps(REPORT,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'ok':True,'generated_schema_count':len(REPORT['generated_schemas']),'query_count':len(REPORT['queries']),'source_file_count':len(REPORT['source_hashes']),'qa_objects_removed':True,'production_objects_preserved':True}))
if __name__=='__main__':
    try:verify()
    except Exception as error:
        print(safe_error(error) if isinstance(error,oracledb.DatabaseError) else str(error),file=sys.stderr)
        raise
