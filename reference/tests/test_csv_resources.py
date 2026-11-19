"""CSV 메모리/왕복/트랜잭션과 연결 수명 검증. 학생 DB는 사용하지 않습니다."""
import csv
import io
import json
import hashlib
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch
from backend import db, sql_files, sql_trace, service
from backend.csv_import import mission_rows, validate_csv, load_mission_csv, csv_snapshot

ROOT = Path(__file__).resolve().parents[2]
ITEM = json.loads((ROOT / 'data/catalog.json').read_text(encoding='utf-8'))[0]


class FakeConnection:
    username = 'STUDENT23'
    def __init__(self, fail_batch=0):
        self.data = [{'case_id': 9000}]
        self.before = list(self.data)
        self.batches = []
        self.commits = self.rollbacks = 0
        self.fail_batch = fail_batch
    @contextmanager
    def cursor(self):
        conn = self
        class Cursor:
            rowcount = 0
            def execute(self, sql, binds):
                if sql.startswith('DELETE'):
                    self.rowcount = len(conn.data)
                    conn.data.clear()
            def executemany(self, sql, values):
                conn.batches.append((sql, len(values)))
                if len(conn.batches) == conn.fail_batch:
                    raise RuntimeError('batch failure')
                conn.data.extend(values)
                self.rowcount = len(values)
        yield Cursor()
    def commit(self):
        self.commits += 1
        self.before = list(self.data)
    def rollback(self):
        self.rollbacks += 1
        self.data = list(self.before)


class CsvResourcesTests(unittest.TestCase):
    def source(self):
        return (ROOT / 'data/examples' / ITEM['filename']).open(encoding='utf-8-sig', newline='')

    def test_three_array_calls_one_commit_no_literal_sql_or_duplicate_trace_data(self):
        conn = FakeConnection()
        sql_trace.begin()
        with self.source() as stream:
            self.assertEqual(validate_csv(stream,ITEM),1500)
            self.assertEqual(load_mission_csv(conn,stream,ITEM,'STUDENT23'),1500)
        self.assertEqual([size for _,size in conn.batches],[500,500,500])
        self.assertEqual(len(set(sql for sql,_ in conn.batches)),1)
        self.assertEqual((conn.commits,conn.rollbacks),(1,0))
        trace = sql_trace.records()
        self.assertNotIn('batch_binds',str(trace))
        self.assertLess(len(json.dumps(trace)),5000)
        self.assertEqual(trace[-1]['batch_count'],1500)
        self.assertEqual(trace[-1]['batches'],3)

    def test_later_batch_failure_restores_original_rows(self):
        conn = FakeConnection(fail_batch=2)
        with self.source() as stream:
            validate_csv(stream,ITEM)
            with self.assertRaisesRegex(RuntimeError,'batch failure'):
                load_mission_csv(conn,stream,ITEM,'STUDENT23')
        self.assertEqual(conn.data,[{'case_id':9000}])
        self.assertEqual((conn.commits,conn.rollbacks),(0,1))

    def test_foreign_owner_is_rejected_before_delete(self):
        conn = FakeConnection()
        with self.source() as stream, self.assertRaises(ValueError):
            load_mission_csv(conn,stream,ITEM,'STUDENT24')
        self.assertEqual(conn.data,[{'case_id':9000}])
        self.assertEqual(conn.batches,[])

    def test_header_order_quotes_empty_unknown_and_newline_are_preserved(self):
        columns = list(reversed(ITEM['columns']))
        values = dict(zip(ITEM['columns'],['7','unknown','',' a, b\n c ','FULL','TRAIN','Y']))
        stream=io.StringIO(newline='')
        writer=csv.DictWriter(stream,fieldnames=columns)
        writer.writeheader();writer.writerow(values);stream.seek(0)
        row=list(mission_rows(stream,ITEM))[0]
        self.assertEqual(row['case_id'],7)
        self.assertEqual(row['team_score'],'unknown')
        self.assertIsNone(row['objective_score'])
        self.assertEqual(row['teamwork_score'],' a, b\n c ')

    def test_duplicate_header_key_and_bad_delimiter_fail_validation(self):
        for content in ('case_id;team_score\n1;2\n','case_id,case_id\n1,2\n'):
            with self.subTest(content=content), self.assertRaises(ValueError):
                validate_csv(io.StringIO(content),ITEM)
        with self.source() as source:
            text=source.read()
        with self.assertRaisesRegex(ValueError,'중복'):
            validate_csv(io.StringIO(text+text.splitlines()[1]+'\n'),ITEM)

    def test_prevalidation_rejects_late_error_before_any_database_connection(self):
        import scripts.load_mission_csv as cli
        with self.source() as source:
            text=source.read()
        @contextmanager
        def snapshot(path):
            yield io.StringIO(text+text.splitlines()[1]+'\n')
        args=['loader','--mission','esports','--file','ignored.csv','--owner','STUDENT23','--replace']
        with patch('sys.argv',args),patch.object(cli,'csv_snapshot',snapshot),patch.object(cli,'connection') as connect,patch('sys.stderr',io.StringIO()):
            self.assertEqual(cli.main(),1)
            connect.assert_not_called()

    def test_snapshot_limit_and_bounded_trace(self):
        with csv_snapshot(ROOT / 'data/examples' / ITEM['filename']) as stream:
            self.assertEqual(validate_csv(stream,ITEM),1500)
        sql_trace.begin()
        for _ in range(1000): sql_trace.add('SELECT :value',{'value':1})
        self.assertEqual(len(sql_trace.records()),sql_trace.MAX_RECORDS)
        self.assertEqual(sql_trace.records()[-1]['omitted_records'],900)

    def test_hash_compatibility_and_two_models_share_source_query(self):
        material=[[{'x':None,'한글':'값'}],[{'text':'procedure'}]]
        self.assertEqual(service.json_fingerprint(material),
                         hashlib.sha256(json.dumps(material,sort_keys=True,default=str).encode()).hexdigest())
        with patch.object(service,'query',return_value=[{'model_name':'OML_BASIC_RAW_MODEL'},{'model_name':'OML_BASIC_CLEAN_MODEL'}]),patch.object(service,'read_state',return_value={}),patch.object(service,'fingerprint_source',return_value=material) as source,patch.object(service,'prepared_values',return_value=[]):
            service.model_rows(MagicMock())
            source.assert_called_once()


class Pool:
    def __init__(self, **kwargs):
        self.kwargs=kwargs;self.closed=0;self.new=True;self.acquires=0
        self.conn=MagicMock()
    @contextmanager
    def acquire(self):
        self.acquires+=1
        if self.new:
            self.new=False
            self.kwargs['session_callback'](self.conn,None)
        try: yield self.conn
        finally: self.conn.rollback();self.conn.close()
    def close(self):
        self.closed+=1


class PoolTests(unittest.TestCase):
    def setUp(self):
        db.close_connections()
        self.pools=[]
        def make(**kwargs):
            pool=Pool(**kwargs);self.pools.append(pool);return pool
        self.patches=[patch.object(db,'connection_args',return_value={}),
                      patch.object(db.oracledb,'create_pool',side_effect=make),
                      patch.object(db,'initialize_session')]
        for p in self.patches:p.start()
        self.cfg={'DB_USER':'STUDENT23','DB_PASSWORD':'fixture-only'}
    def tearDown(self):
        db.close_connections()
        for p in reversed(self.patches):p.stop()
    def test_reuse_bound_size_and_session_initialize_once(self):
        for _ in range(3):
            with db.connection(self.cfg):pass
        self.assertEqual(len(self.pools),1)
        pool=self.pools[0]
        self.assertEqual(pool.acquires,3)
        self.assertEqual((pool.kwargs['min'],pool.kwargs['max'],pool.kwargs['timeout']),(0,1,60))
        db.initialize_session.assert_called_once()
        self.assertEqual(pool.conn.rollback.call_count,3)
    def test_authentication_always_uses_fresh_connection(self):
        with db.connection(self.cfg):pass
        with patch.object(db.oracledb,'connect') as direct:
            with db.connection(self.cfg,pooled=False):pass
            direct.assert_called_once()
        self.assertEqual(self.pools[0].acquires,1)
    def test_credential_change_replaces_pool(self):
        with db.connection(self.cfg):pass
        with db.connection(dict(self.cfg,DB_PASSWORD='changed')):pass
        self.assertEqual(len(self.pools),2)
        self.assertEqual(self.pools[0].closed,1)
    def test_logout_retires_active_pool_after_return(self):
        with db.connection(self.cfg):
            db.close_connections()
            self.assertEqual(self.pools[0].closed,0)
        self.assertEqual(self.pools[0].closed,1)
        self.assertIsNone(db._pool_entry)
    def test_failed_acquire_and_exception_release_lease(self):
        with self.assertRaises(RuntimeError):
            with db.connection(self.cfg):raise RuntimeError('operation failed')
        self.assertEqual(db._pool_entry['users'],0)
        self.assertEqual(self.pools[0].conn.close.call_count,1)


if __name__ == '__main__':
    unittest.main()
