"""성공 기록과 현재 상태가 일치할 때만 증적을 발급합니다. 실제 DB는 사용하지 않습니다."""
from copy import deepcopy
import unittest
from unittest.mock import MagicMock, patch
from backend import practice_evidence as evidence
from reference.tests.test_assignment_guides import AssignmentGuideTests

def fixture(key='basic'):
    models=[dict(variant=m,exists=1,is_current=1,is_confirmed=int(m=='CLEAN')) for m in evidence.MODES]
    state=dict(initialized=True,ready=True,state={'total_rows':14},prediction_storage={'rows':2},models=models,preparation={m:dict(ready=True,fit_rows=10,test_rows=4) for m in evidence.MODES})
    stamps={m:dict(fingerprint=m+'-source-v1',created='2026-11-19T01:00:00') for m in evidence.MODES}
    saved={'models':deepcopy(stamps),'assignments':{key:deepcopy(stamps)}}
    inputs=[dict(case_id=1,value='original'),dict(case_id=2,value='original')]
    return state,saved,inputs

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.conn=MagicMock()
        self.state,self.saved,self.inputs=fixture()
        self.read=patch.object(evidence.service,'read_state',side_effect=lambda conn:deepcopy(self.saved))
        self.write=patch.object(evidence.service,'write_state',side_effect=lambda conn,saved:self.saved.update(saved))
        self.read.start();self.write.start()
        self.addCleanup(self.read.stop);self.addCleanup(self.write.stop)

    def complete(self,key='basic',topic=''):
        for mode in evidence.MODES:
            self.assertTrue(evidence.record(self.conn,key,'evaluate',mode,[dict(variant=mode,actual='A',predicted='B',n=4)],mission_key=topic))
        self.assertTrue(evidence.record(self.conn,key,'predict','CLEAN',[dict(case_id=i,predicted='A',probability=.6) for i in (1,2)],inputs=self.inputs,mission_key=topic))

    def summary(self,key='basic',**kwargs):
        return evidence.summarize(key,self.state,self.saved,inputs=self.inputs,**kwargs)

    def test_real_success_required_and_zero_accuracy_is_not_an_invented_failure(self):
        self.assertEqual(self.summary()['passed'],2)
        self.complete()
        self.assertTrue(self.summary()['complete'])
        self.assertIn('0.0%',self.summary()['steps'][2]['detail'])

    def test_changed_source_model_selection_input_and_preparation_revoke_success(self):
        self.complete();baseline=deepcopy(self.saved)
        self.saved['models']['CLEAN']['fingerprint']='changed'
        self.assertFalse(self.summary()['complete'])
        self.saved=deepcopy(baseline);self.inputs[0]['value']='edited'
        self.assertFalse(self.summary()['steps'][3]['success'])
        self.inputs[0]['value']='original';self.state['models'][1]['is_current']=0
        self.assertFalse(self.summary()['steps'][2]['success'])
        self.state['models'][1]['is_current']=1;self.state['models'][1]['is_confirmed']=0
        self.assertFalse(self.summary()['complete'])
        self.state['models'][1]['is_confirmed']=1;self.state['preparation']['CLEAN']['ready']=False
        self.assertFalse(self.summary()['steps'][1]['success'])

    def test_failed_empty_or_invalid_latest_execution_cannot_keep_old_stamp(self):
        self.complete()
        evidence.begin(self.conn,'basic','predict')
        self.assertFalse(self.summary()['complete'])
        for rows in ([],[dict(case_id=1,predicted='A',probability=.8)],
                     [dict(case_id=1,predicted='A',probability=.8)]*2,
                     [dict(case_id=i,predicted='A',probability=2) for i in (1,2)]):
            self.assertFalse(evidence.record(self.conn,'basic','predict','CLEAN',rows,inputs=self.inputs))
        for n in (float('nan'),-1,1.5,0):
            self.assertFalse(evidence.record(self.conn,'basic','evaluate','RAW',[dict(variant='RAW',actual='A',predicted='A',n=n)]))

    def test_both_modes_and_same_full_test_are_required(self):
        self.complete()
        self.saved['practice_evidence']['basic']['evaluate'].pop('RAW')
        self.assertFalse(self.summary()['steps'][2]['success'])
        self.complete();self.state['preparation']['RAW']['test_rows']=5
        self.assertFalse(self.summary()['steps'][2]['success'])

    def test_missions_creative_and_accounts_are_isolated(self):
        for key in ('mission','creative'):
            self.state,self.saved,self.inputs=fixture(key)
            topic='festival' if key=='mission' else ''
            self.complete(key,topic)
            opts={'mission':dict(key=topic,baseline=dict(test_rows=4))} if topic else {}
            self.assertTrue(self.summary(key,**opts)['complete'])
            if topic:
                self.assertFalse(self.summary(key,mission=dict(key='bike'))['complete'])
                self.assertFalse(self.summary(key,mission_columns=False,**opts)['complete'])
            self.assertFalse(self.summary('basic')['complete'])
        self.saved={}
        self.assertFalse(self.summary('creative')['complete'])

    def test_snapshot_reuses_supplied_state_and_never_runs_work_sql(self):
        self.complete()
        with patch.object(evidence.service,'status') as status,patch.object(evidence,'query',return_value=self.inputs),patch.object(evidence.service,'run_model') as run:
            self.assertTrue(evidence.collect(self.conn,'basic',state=self.state)['complete'])
            status.assert_not_called();run.assert_not_called()

    def test_endpoint_auth_owner_allowlist_and_read_only(self):
        helper=AssignmentGuideTests()
        with helper.client(authenticated=False) as (client,headers,connect),patch.object(evidence,'collect') as collect:
            self.assertEqual(client.get('/api/practice/basic/evidence').status_code,401)
            collect.assert_not_called();connect.assert_not_called()
        with helper.client() as (client,headers,connect),patch.object(evidence,'collect',return_value=self.summary()) as collect:
            for key in ('basic','mission','creative'):
                response=client.get('/api/practice/'+key+'/evidence')
                self.assertEqual(response.status_code,200,response.text)
                self.assertNotIn('fingerprint',str(response.json()))
            self.assertEqual(client.get('/api/practice/other/evidence').status_code,404)
            self.assertEqual(client.post('/api/practice/basic/evidence',headers=headers,json={'complete':True}).status_code,405)
            count=collect.call_count
            connect.return_value.__enter__.return_value.username='OTHER'
            self.assertEqual(client.get('/api/practice/basic/evidence').status_code,400)
            self.assertEqual(collect.call_count,count)


    def test_three_objects_out_of_four_show_missing_run(self):
        self.state['initialized']=False
        self.state['objects']=[dict(object_name='OML_BASIC_'+suffix,object_type='TABLE',status='VALID') for suffix in ('DATA','PREPARED','PREDICT')]
        step=self.summary()['steps'][0]
        self.assertEqual((step['completed'],step['total'],step['remaining']),(3,4,1))
        self.assertFalse(step['success'])
        self.assertIn('RUN',next(c['label'] for c in step['checks'] if not c['success']))

    def test_partial_data_reports_only_remaining_clean_work(self):
        self.state['preparation']['CLEAN']['ready']=False
        step=self.summary()['steps'][1]
        self.assertEqual((step['completed'],step['total'],step['remaining']),(3,4,1))
        self.assertEqual([c['label'] for c in step['checks'] if not c['success']],['CLEAN 전처리·학습/TEST 준비'])

    def test_evaluation_and_prediction_details_follow_real_receipts(self):
        self.complete()
        self.saved['practice_evidence']['basic']['evaluate'].pop('RAW')
        step=self.summary()['steps'][2]
        self.assertEqual(step['remaining'],1)
        self.assertIn('RAW TEST',next(c['label'] for c in step['checks'] if not c['success']))
        self.complete();self.inputs[0]['value']='changed'
        step=self.summary()['steps'][3]
        self.assertEqual((step['completed'],step['total'],step['remaining']),(4,5,1))
        self.assertEqual([c['label'] for c in step['checks'] if not c['success']],['현재 예측 입력 일치'])

    def test_success_counts_are_consistent_for_every_assignment(self):
        for key in ('basic','mission','creative'):
            self.state,self.saved,self.inputs=fixture(key)
            topic='festival' if key=='mission' else ''
            self.complete(key,topic)
            result=self.summary(key,mission={'key':topic,'baseline':{'test_rows':4}} if topic else None)
            for step in result['steps']:
                self.assertEqual(step['success'],all(c['success'] for c in step['checks']))
                self.assertEqual(step['completed']+step['remaining'],step['total'])
                self.assertEqual(step['remaining'],0)

    def test_unexecuted_custom_uploads_use_count_and_existing_tables_only(self):
        from backend.assignment_templates import ASSIGNMENTS
        self.conn.username='STUDENT23';self.saved={}
        state=dict(ready=False,config=ASSIGNMENTS['creative'],objects=[
            dict(object_name='OML_CREATIVE_'+suffix,object_type='TABLE',status='VALID') for suffix in ('DATA','PREPARED','PREDICT')])
        with patch.object(evidence,'execute',return_value=[{'rows_count':12}]) as execute,patch.object(evidence,'query') as query:
            result=evidence.collect(self.conn,'creative',state=state)
            self.assertEqual(execute.call_count,2);query.assert_not_called()
            for args,kwargs in execute.call_args_list:
                self.assertEqual(args[1],'queries/custom_count.sql')
                self.assertTrue(kwargs['replacements']['table'].startswith('STUDENT23.'))
            self.assertTrue(result['steps'][1]['checks'][0]['success'])
            self.assertTrue(result['steps'][3]['checks'][1]['success'])
            self.assertFalse(result['complete'])

    def test_count_failure_is_not_recorded_as_zero_or_success(self):
        from backend.assignment_templates import ASSIGNMENTS
        self.conn.username='STUDENT23';self.saved={}
        state=dict(ready=False,config=ASSIGNMENTS['creative'],objects=[dict(object_name='OML_CREATIVE_DATA',object_type='TABLE',status='VALID')])
        with patch.object(evidence,'execute',side_effect=RuntimeError('COUNT failed')):
            with self.assertRaisesRegex(RuntimeError,'COUNT failed'):evidence.collect(self.conn,'creative',state=state)

    def test_status_input_counts_are_reused_without_another_count(self):
        from backend.assignment_templates import ASSIGNMENTS
        self.conn.username='STUDENT23';self.saved={}
        state=dict(ready=False,config=ASSIGNMENTS['creative'],objects=[],state={'total_rows':17},prediction_storage={'rows':4})
        with patch.object(evidence,'execute') as execute,patch.object(evidence,'query') as query:
            result=evidence.collect(self.conn,'creative',state=state)
            execute.assert_not_called();query.assert_not_called()
            self.assertTrue(result['steps'][1]['checks'][0]['success'])
            self.assertTrue(result['steps'][3]['checks'][1]['success'])
