"""4단계 모델 선택과 성공 시 사용 모델 저장을 실제 DB 없이 검증합니다."""
from copy import deepcopy
import unittest
from unittest.mock import MagicMock, patch
from backend import service
from reference.tests.test_practice_evidence import fixture
from reference.tests.test_assignment_guides import AssignmentGuideTests

class PredictionChoiceTests(unittest.TestCase):
    def setUp(self):
        state,self.saved,_=fixture()
        self.saved['confirmed']='CLEAN'
        self.models=[dict(m,model_name='OML_BASIC_'+m['variant']+'_MODEL') for m in state['models']]
        self.inputs=[dict(case_id=i,stock='S'+str(i),week_ending='2026-01-01',signal=None) for i in (1,2)]
        self.rows=[dict(case_id=i,predicted='BUY',buy_probability=.7,sell_probability=.3) for i in (1,2)]
        self.conn=MagicMock();self.conn.username='STUDENT_QA';self.conn.dsn='isolated'
        patches=[
            patch.object(service,'read_state',side_effect=lambda conn:deepcopy(self.saved)),
            patch.object(service,'write_state',side_effect=lambda conn,saved:self.saved.update(saved)),
            patch.object(service,'model_rows',side_effect=lambda conn:self.models),
            patch.object(service,'query',return_value=self.inputs),
            patch.object(service,'run_model',return_value=self.rows)]
        self.mocks=[p.start() for p in patches]
        for p in patches:self.addCleanup(p.stop)

    def test_selected_raw_overrides_clean_and_saves_only_after_success(self):
        rows=service.predictions(self.conn,'RAW')
        self.assertEqual(len(rows),2)
        self.mocks[-1].assert_called_once_with(self.conn,'PREDICT','RAW')
        self.assertEqual(self.saved['confirmed'],'RAW')
        self.assertEqual(self.saved['practice_evidence']['basic']['predict']['mode'],'RAW')
        self.assertEqual(service.prediction_context(self.conn,'RAW')['model_name'],'OML_BASIC_RAW_MODEL')

    def test_direct_selection_does_not_require_previous_confirmation(self):
        self.saved['confirmed']=None
        for m in self.models:m['is_confirmed']=0
        service.predictions(self.conn,'CLEAN')
        self.assertEqual(self.saved['confirmed'],'CLEAN')

    def test_legacy_call_keeps_default_and_invalid_or_stale_mode_never_executes(self):
        service.predictions(self.conn)
        self.mocks[-1].assert_called_once_with(self.conn,'PREDICT','CLEAN')
        self.mocks[-1].reset_mock()
        for mode in ('BOTH','OTHER'):
            with self.assertRaises(ValueError):service.predictions(self.conn,mode)
        self.models[0]['is_current']=0
        with self.assertRaises(ValueError):service.predictions(self.conn,'RAW')
        self.mocks[-1].assert_not_called()

    def test_failed_or_empty_result_keeps_previous_default(self):
        self.mocks[-1].return_value=[]
        service.predictions(self.conn,'RAW')
        self.assertEqual(self.saved['confirmed'],'CLEAN')
        self.assertNotIn('predict',self.saved['practice_evidence']['basic'])
        self.mocks[-1].side_effect=RuntimeError('isolated failure')
        with self.assertRaises(RuntimeError):service.predictions(self.conn,'RAW')
        self.assertEqual(self.saved['confirmed'],'CLEAN')

    def test_api_passes_the_selected_mode_and_rejects_invalid_before_db_work(self):
        helper=AssignmentGuideTests()
        with helper.client() as (client,headers,connect),patch.object(service,'predictions',return_value=[]) as run,patch.object(service,'prediction_context',return_value={}) as context,patch('app.query',return_value=[]),patch.object(service,'read_state',return_value={}):
            response=client.post('/api/predictions/run',headers=headers,json={'variant':'RAW'})
            self.assertEqual(response.status_code,200,response.text)
            conn=connect.return_value.__enter__.return_value
            run.assert_called_once_with(conn,'RAW');context.assert_called_once_with(conn,'RAW')
            connect.reset_mock()
            self.assertEqual(client.post('/api/predictions/run',headers=headers,json={'variant':'BOTH'}).status_code,400)
            connect.assert_not_called()
        with helper.client(authenticated=False) as (client,headers,connect):
            self.assertEqual(client.post('/api/predictions/run',json={'variant':'RAW'}).status_code,403)
            token=client.get('/api/session').json()['csrf']
            self.assertEqual(client.post('/api/predictions/run',headers={'X-CSRF-Token':token},json={'variant':'RAW'}).status_code,401)
            connect.assert_not_called()
