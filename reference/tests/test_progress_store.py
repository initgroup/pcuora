"""공유 저장소·계정 격리·버전 충돌·1회 이관을 실제 파일 SQL로 검증합니다."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from backend import progress_store as store, service, practice_evidence as evidence, assignment_templates as tasks
from reference.tests.test_practice_evidence import fixture


class Connection:
    def __init__(self, records, owner='STUDENT23', dsn='alias-a'):
        self.records,self.username,self.dsn,self.schema=records,owner,dsn,owner
    def cursor(self):
        conn=self
        class Cursor:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def var(self,*args):return SimpleNamespace(value=0,getvalue=lambda:self.out.value)
            def setinputsizes(self,**kwargs):pass
            def execute(self,sql,binds=None):
                binds=binds or {}
                key=(conn.username,binds.get('state_key'))
                if sql.lstrip().startswith('-- 같은 DB'):
                    revision,payload=conn.records.get(key,(None,None))
                    self.data=[dict(session_user=conn.username,current_schema=conn.schema,revision=revision,state_json=payload)]
                elif ':written' in sql:
                    if conn.schema!=conn.username:raise ValueError('CURRENT_SCHEMA')
                    old=conn.records.get(key,(0,None))[0]
                    self.out=binds['written'];self.out.value=int(old==binds['revision'])
                    if self.out.value:conn.records[key]=(old+1,binds['payload'])
        return Cursor()


class ProgressStoreTests(unittest.TestCase):
    def setUp(self):
        self.records={};self.local=Connection(self.records);self.remote=Connection(self.records,dsn='another-service')
        self.reader=patch.object(store,'rows',side_effect=lambda cursor:deepcopy(cursor.data));self.reader.start();self.addCleanup(self.reader.stop)

    def test_servers_and_aliases_share_all_three_assignments_and_revocation(self):
        for key in ('basic','mission','creative'):
            state,saved,inputs=fixture(key)
            current=store.load(self.local);current.update(saved);store.save(self.local,current)
            topic='festival' if key=='mission' else ''
            for mode in evidence.MODES:
                self.assertTrue(evidence.record(self.local,key,'evaluate',mode,[dict(variant=mode,actual='A',predicted='A',n=4)],mission_key=topic))
            self.assertTrue(evidence.record(self.local,key,'predict','CLEAN',[dict(case_id=i,predicted='A',probability=.6) for i in (1,2)],inputs=inputs,mission_key=topic))
            options=dict(mission={'key':topic,'baseline':{'test_rows':4}}) if topic else {}
            self.assertTrue(evidence.summarize(key,state,service.read_state(self.remote),inputs=inputs,**options)['complete'])
            evidence.begin(self.remote,key,'predict')
            self.assertFalse(evidence.summarize(key,state,service.read_state(self.local),inputs=inputs,**options)['complete'])

    def test_stale_writer_cannot_overwrite_another_server(self):
        a=store.load(self.local);b=store.load(self.remote)
        a['confirmed']='RAW';store.save(self.local,a)
        b['confirmed']='CLEAN'
        with self.assertRaisesRegex(ValueError,'다른 환경'):store.save(self.remote,b)
        self.assertEqual(store.load(self.remote)['confirmed'],'RAW')
        self.assertEqual(b.revision,0)

    def test_account_schema_and_student_selection_are_isolated(self):
        person=dict(student_id='one',db_user='STUDENT23');second={**person,'student_id':'two'}
        tasks.mission_selection(self.local,person,{'festival'},'festival')
        self.assertEqual(tasks.mission_selection(self.remote,person,{'festival'}),'festival')
        self.assertEqual(tasks.mission_selection(self.remote,second,{'festival'}),'')
        self.assertEqual(store.load(Connection(self.records,owner='STUDENT02')),{'models':{}})
        self.remote.schema='STUDENT02'
        with self.assertRaisesRegex(ValueError,'CURRENT_SCHEMA'):store.load(self.remote)
        with self.assertRaises(ValueError):store.save(Connection(self.records,owner='STUDENT02'),store.load(self.local))

    def test_legacy_import_is_once_and_never_replaces_a_database_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'runtime').mkdir()
            path=store.legacy_path(self.local,root);path.write_text(json.dumps({'models':{},'confirmed':'RAW'}),encoding='utf-8')
            person=dict(student_id='one',db_user='STUDENT23')
            self.assertEqual(store.migrate(self.local,person,root),['practice','mission'])
            state=store.load(self.remote);state['confirmed']=None;store.save(self.remote,state)
            self.assertEqual(store.migrate(self.local,person,root),[])
            self.assertIsNone(store.load(self.local)['confirmed'])
            self.assertEqual(json.loads(path.read_text())['confirmed'],'RAW')

    def test_failed_db_read_has_no_local_fallback_and_large_write_is_rejected(self):
        with patch.object(store,'rows',side_effect=RuntimeError('network unavailable')):
            with self.assertRaisesRegex(RuntimeError,'network'):service.read_state(self.local)
        state=store.load(self.local);state['bad']='x'*store.MAX_BYTES
        with self.assertRaises(ValueError):store.save(self.local,state)
        self.assertFalse(self.records)


if __name__=='__main__':unittest.main()
