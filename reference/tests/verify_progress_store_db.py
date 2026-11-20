"""Oracle의 별도 OML_QA 객체만 사용합니다. 실습 테이블·모델은 변경하지 않습니다."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import uuid
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from backend import db,progress_store as store,practice_evidence as evidence
from reference.tests.test_practice_evidence import fixture


def summaries(conn):
    saved=store.load(conn)
    result=[]
    for key in ('basic','mission','creative'):
        state,_,inputs=fixture(key)
        mission={'key':'festival','baseline':{'test_rows':4}} if key=='mission' else None
        result.append(evidence.summarize(key,state,saved,inputs=inputs,mission=mission)['passed'])
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--owner',required=True);parser.add_argument('--probe');args=parser.parse_args()
    if args.probe:
        if not args.probe.startswith('OML_QA_WEB_'):raise ValueError('QA table required')
        store.TABLE=args.probe
        with db.connection() as conn:
            assert conn.username.upper()==args.owner.upper()
            print(json.dumps(summaries(conn)))
        return
    token=uuid.uuid4().hex[:8].upper();table='OML_QA_WEB_'+token;pending='OML_QA_TX_'+token
    store.TABLE=table;created=[]
    with db.connection() as conn:
        assert conn.username.upper()==args.owner.upper()
        with conn.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM USER_OBJECTS WHERE OBJECT_NAME IN (:a,:b)',dict(a=table,b=pending))
            assert cursor.fetchone()[0]==0
        try:
            store.initialize(conn);created.append(table)
            with conn.cursor() as cursor:cursor.execute('CREATE TABLE '+pending+' (ID NUMBER)')
            created.append(pending)
            for key in ('basic','mission','creative'):
                _,saved,inputs=fixture(key)
                state=store.load(conn)
                state.setdefault('assignments',{}).update(saved['assignments'])
                state['models']=saved['models'];store.save(conn,state)
                topic='festival' if key=='mission' else ''
                for mode in evidence.MODES:
                    assert evidence.record(conn,key,'evaluate',mode,[dict(variant=mode,actual='A',predicted='A',n=4)],mission_key=topic)
                assert evidence.record(conn,key,'predict','CLEAN',[dict(case_id=i,predicted='A',probability=.6) for i in (1,2)],inputs=inputs,mission_key=topic)
            assert summaries(conn)==[4,4,4]
            probe=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--owner',args.owner,'--probe',table],cwd=ROOT,capture_output=True,text=True,timeout=45)
            assert probe.returncode==0,probe.stderr
            assert json.loads(probe.stdout)==[4,4,4]
            with conn.cursor() as cursor:cursor.execute('INSERT INTO '+pending+' (ID) VALUES (1)')
            state=store.load(conn);state['confirmed']='CLEAN';store.save(conn,state)
            conn.rollback()
            with conn.cursor() as cursor:
                cursor.execute('SELECT COUNT(*) FROM '+pending);assert cursor.fetchone()[0]==0
            assert store.load(conn)['confirmed']=='CLEAN'
            a=store.load(conn);b=store.load(conn);a['confirmed']='RAW';store.save(conn,a)
            b['confirmed']='CLEAN'
            try:store.save(conn,b)
            except ValueError:pass
            else:raise AssertionError('Stale write succeeded')
            assert store.load(conn)['confirmed']=='RAW'
            a=store.load(conn);a['models']['RAW']['fingerprint']='x'*40000;store.save(conn,a)
            assert len(store.load(conn)['models']['RAW']['fingerprint'])==40000
            report=dict(ok=True,real_database=True,qa_objects_only=True,independent_process_reads_same_success=True,three_assignments=[4,4,4],caller_uncommitted_rows_rolled_back=True,autonomous_state_remains_committed=True,stale_writer_rejected=True,large_clob_roundtrip=True,student_rows_and_models_unchanged=True)
        finally:
            conn.rollback()
            for name in reversed(created):
                assert name in (table,pending) and name.startswith('OML_QA_')
                with conn.cursor() as cursor:cursor.execute('DROP TABLE '+name+' PURGE')
        report['qa_objects_removed']=True
    (ROOT/'runtime/progress-db-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':main()
