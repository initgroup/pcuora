"""Instructor/student CLI. Paths resolve from this file, not the current directory."""
import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from oml.db import ROOT, connection, result_set, rows, safe_error

SQL = ROOT/'deploy/sql'
DATA = ROOT/'deploy/data'

def initialize(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM USER_TABLES WHERE TABLE_NAME='OML_LAB_STATE'")
        existed=cur.fetchone()[0]>0
        for file in ('01_schema.sql','02_package.sql'):
            # Scripts use a slash on its own line after EVERY statement, including SQL DDL.
            import re
            for block in re.split(r'^/\s*$',(SQL/file).read_text(encoding='utf-8'),flags=re.M):
                block=block.strip()
                if not block: continue
                is_package='CREATE OR REPLACE PACKAGE' in block.upper()
                if not is_package: block=block.rstrip(';')
                try: cur.execute(block)
                except Exception as error:
                    if getattr(error.args[0],'code',None)==955 and 'CREATE TABLE OML_' in block: continue
                    raise
        cur.execute("SELECT LINE,POSITION,TEXT FROM USER_ERRORS WHERE NAME='OML_LAB' ORDER BY SEQUENCE")
        errors=cur.fetchall()
        if errors: raise RuntimeError('Package compile errors: '+repr(errors))
        cur.execute('SELECT COUNT(*) FROM OML_LAB_STATE')
        if cur.fetchone()[0]==0:
            cur.execute("INSERT INTO OML_LAB_STATE(ID,DATA_REV,SOURCE_NAME) VALUES(1,1,'initial')")
        cur.execute('SELECT COUNT(*) FROM OML_CUSTOMER')
        if cur.fetchone()[0]==0:
            for name,sql in (
                ('books.csv','INSERT INTO OML_BOOK VALUES(:1,:2,:3,:4)'),
                ('customers.csv','INSERT INTO OML_CUSTOMER VALUES(:1,:2)'),
                ('orders.csv',"INSERT INTO OML_ORDERS VALUES(:1,:2,:3,TO_DATE(:4,'YYYY-MM-DD'),:5)")):
                with (DATA/name).open(encoding='utf-8-sig',newline='') as f:
                    data=list(csv.reader(f))[1:]
                cur.executemany(sql,data)
            cur.callproc('OML_LAB.REFRESH_SAMPLE')
        conn.commit()
        print('Schema ready. Existing data preserved.' if existed else 'Schema and fictional sample created.')

def status(conn):
    with conn.cursor() as cur:
        cur.execute('SELECT USER USERNAME FROM DUAL'); user=cur.fetchone()[0]
        cur.execute("SELECT PRIVILEGE FROM SESSION_PRIVS WHERE PRIVILEGE IN ('CREATE MINING MODEL','CREATE TABLE','CREATE VIEW','CREATE PROCEDURE')")
        privs=[r[0] for r in cur.fetchall()]
        print(json.dumps({'user':user,'version':conn.version,'privileges':privs},ensure_ascii=False))

def export(conn):
    with conn.cursor() as cur:
        cur.execute('SELECT * FROM OML_FEATURES ORDER BY CUSTOMER_ID')
        with (DATA/'classification.csv').open('w',encoding='utf-8',newline='') as f:
            w=csv.writer(f); w.writerow([c[0].lower() for c in cur.description]); w.writerows(cur.fetchall())
    print('Exported deploy/data/classification.csv')

def verify(conn):
    status(conn)
    with conn.cursor() as cur:
        cur.callproc('OML_LAB.TRAIN_CLASSIFIER')
        cur.callproc('OML_LAB.TRAIN_RULES')
    report={
        'checked_at':datetime.now().isoformat(),
        'predictions':result_set(conn,'PREDICT_RANK',6,180000,7,3),
        'confusion':result_set(conn,'EVALUATE_MODEL'),
        'nodes':result_set(conn,'MODEL_DETAILS'),
        'settings':result_set(conn,'MODEL_SETTINGS'),
        'correlation':result_set(conn,'CORRELATION'),
        'rules':result_set(conn,'RULES')}
    assert len(report['predictions'])==2
    assert abs(sum(x['probability'] for x in report['predictions'])-1)<1e-6
    assert sum(x['n'] for x in report['confusion'])>0
    assert report['nodes'] and report['rules']
    out=ROOT/'runtime'; out.mkdir(exist_ok=True)
    (out/'db-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Verified real Oracle training, ranking, holdout evaluation, model details, correlation and rules.')
    print(json.dumps({k:len(v) for k,v in report.items() if isinstance(v,list)}))

def main():
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['check','init','export','verify','serve']); p.add_argument('--port',type=int,default=22417)
    a=p.parse_args()
    if a.command=='serve':
        from waitress import serve
        from oml.app import create_app
        print(f'OML Classroom: http://127.0.0.1:{a.port}',flush=True)
        serve(create_app(),host='127.0.0.1',port=a.port,threads=4)
        return
    try:
        with connection() as conn:
            {'check':status,'init':initialize,'export':export,'verify':verify}[a.command](conn)
    except Exception as e:
        if isinstance(e,RuntimeError): print(str(e),file=sys.stderr)
        else: print(safe_error(e),file=sys.stderr)
        sys.exit(1)

if __name__=='__main__': main()
