"""선택·적용 미션의 교차 실행 방지. 실제 DB 작업은 하지 않습니다."""
from copy import deepcopy
from unittest.mock import MagicMock,patch
import re
import unittest
from backend import mission_binding as binding,assignment_templates as tasks,service
from backend.mission_guide import table_sql,procedure_sql
from reference.tests import test_assignment_guides as guides


def columns(item,kind):
    return [dict(column_name=c['name'],data_type=c['type'].split('(')[0],
                 char_length=int(re.search(r'\d+',c['type'])[0]) if '(' in c['type'] else 0,
                 nullable='N' if c['nullable']=='필수' else 'Y') for c in table_sql(item,kind)['columns']]


class MissionBindingTests(unittest.TestCase):
    def setUp(self):
        self.conn=MagicMock(username='STUDENT23');self.items=binding.catalog()
        self.one,self.three=self.items[0],self.items[2]
        self.saved={};self.current=self.three;self.source_item=self.three
        self.table_items={kind:self.three for kind in ('training','prepared','prediction')}
        self.attributes_item=self.three
        cfg=tasks.assignment('mission')
        self.state=dict(ready=True,config=cfg,objects=[dict(object_name=name,object_type='PROCEDURE' if name.endswith('RUN') else 'TABLE',object_id=i,status='VALID') for i,name in enumerate([cfg[k] for k in ['training_table','prepared_table','prediction_table','procedure_name']])])
        def query(conn,path,**binds):
            if path=='schema_columns.sql':
                kind={'OML_MISSION_DATA':'training','OML_MISSION_PREPARED':'prepared','OML_MISSION_PREDICT':'prediction'}[binds['table_name']]
                return columns(self.table_items[kind],kind)
            if path=='procedure_source.sql':return [dict(text=procedure_sql(self.source_item))]
            if path=='dictionary_attributes.sql':return [dict(attribute_name=n.upper(),target='NO') for n in self.attributes_item['columns'][1:4]]+[dict(attribute_name='LABEL',target='YES')]
            raise AssertionError(path)
        self.reader=patch.object(binding,'query',side_effect=query);self.reader.start();self.addCleanup(self.reader.stop)
        self.store=patch.object(service,'read_state',side_effect=lambda c:self.saved);self.store.start();self.addCleanup(self.store.stop)

    def inspect(self,item):return binding.inspect(self.conn,item['key'],deepcopy(self.state))

    def test_switch_only_blocks_and_return_restores_same_binding(self):
        info=self.inspect(self.three)
        self.assertTrue(info['can_link']);self.assertFalse(info['ready']);self.assertEqual(self.saved,{})
        binding.bind(self.saved,info);previous=deepcopy(self.saved)
        self.assertTrue(self.inspect(self.three)['ready'])
        wrong=self.inspect(self.one)
        self.assertEqual(wrong['detected'],self.three['key']);self.assertFalse(wrong['can_link'])
        with self.assertRaises(ValueError):binding.bind(self.saved,wrong)
        self.assertEqual(self.saved,previous);self.assertTrue(self.inspect(self.three)['ready'])

    def test_partial_rebuild_wrong_run_and_object_replacement_require_validation(self):
        binding.bind(self.saved,self.inspect(self.three))
        self.table_items['training']=self.one
        self.assertFalse(self.inspect(self.one)['can_link']);self.assertFalse(self.inspect(self.three)['can_link'])
        self.table_items={kind:self.one for kind in self.table_items}
        self.assertFalse(self.inspect(self.one)['can_link'])
        self.source_item=self.one
        info=self.inspect(self.one);self.assertTrue(info['can_link']);self.assertFalse(info['ready'])
        self.saved['practice_evidence']={'mission':{'old':True},'basic':{'keep':True}}
        binding.bind(self.saved,info)
        self.assertNotIn('mission',self.saved['practice_evidence']);self.assertIn('basic',self.saved['practice_evidence'])
        self.assertTrue(self.inspect(self.one)['ready'])
        self.state['objects'][0]['object_id']=999
        self.assertFalse(self.inspect(self.one)['ready'])

    def test_datatype_length_and_nullable_are_checked(self):
        rows=columns(self.one,'prediction');rows[1]['data_type']='NUMBER'
        self.assertTrue(binding.table_issues(self.one,'prediction',rows))
        rows=columns(self.one,'prediction');rows[1]['char_length']=1
        self.assertTrue(binding.table_issues(self.one,'prediction',rows))
        rows=columns(self.one,'prediction');rows[0]['nullable']='Y'
        self.assertTrue(binding.table_issues(self.one,'prediction',rows))

    def test_model_signature_cannot_relabel_an_old_mission_model(self):
        self.assertTrue(binding.model_matches(self.conn,'OML_MISSION_RAW_MODEL',self.three['key']))
        self.assertFalse(binding.model_matches(self.conn,'OML_MISSION_RAW_MODEL',self.one['key']))

    def test_all_twelve_generated_contracts_are_uniquely_detected(self):
        for item in self.items:
            with self.subTest(mission=item['key']):
                self.source_item=item;self.table_items={kind:item for kind in self.table_items}
                info=self.inspect(item)
                self.assertEqual(info['detected'],item['key']);self.assertTrue(info['can_link']);self.assertFalse(info['ready'])

    def test_execution_rejects_mismatch_before_procedure_receipt_or_save(self):
        bad=self.inspect(self.one);state={**self.state,'mission':bad,'ready':False}
        with patch.object(tasks,'readiness',return_value=state),patch.object(service,'run_model') as run,patch.object(service,'write_state') as save:
            for action in ('evaluate','predict','prepared-data'):
                with self.assertRaises(tasks.AssignmentNotReady):tasks.run(self.conn,'mission',action,mission_key=self.one['key'])
            with self.assertRaises(ValueError):tasks.link_external(self.conn,'mission',mission=self.one['key'])
            run.assert_not_called();save.assert_not_called()

    def test_stale_browser_mission_is_rejected_at_api_before_work(self):
        with guides.AssignmentGuideTests().client() as (client,headers,connect),patch.object(tasks,'run') as run,patch.object(tasks,'link_external') as link:
            client.post('/api/assignments/mission/selection',json={'key':self.one['key']},headers=headers)
            for action in ('link','evaluate','predict'):
                response=client.post('/api/assignments/mission/'+action,json={'mission':self.three['key'],'variant':'RAW'},headers=headers)
                self.assertEqual(response.status_code,400,response.text)
            run.assert_not_called();link.assert_not_called()
