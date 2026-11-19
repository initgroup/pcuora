"""모델 수명주기 전제조건·추가 실패 롤백·DDL 이후 부분 실패와 삭제 범위를 검증합니다."""
import sys,unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from backend import service,coding_help

class ModelLifecycleTests(unittest.TestCase):
    def test_preconditions_do_not_clear_existing_choice(self):
        conn=MagicMock()
        with patch.object(service,'query',return_value=[{'model_name':'OML_BASIC_RAW_MODEL'}]),patch.object(service,'write_state') as write:
            with self.assertRaises(ValueError):service.train_model(conn,'RAW','INIT')
            write.assert_not_called()
        with patch.object(service,'query',return_value=[]),patch.object(service,'write_state') as write:
            with self.assertRaises(ValueError):service.train_model(conn,'RAW','RETRAIN')
            write.assert_not_called()

    def test_append_rejects_test_and_rolls_back_invalid_train_before_commit(self):
        conn=MagicMock();models=[{'model_name':'OML_BASIC_RAW_MODEL'}]
        with patch.object(service,'query',return_value=models),patch.object(service,'execute') as execute:
            with self.assertRaises(ValueError):service.append_training(conn,[{'split':'TEST','use_yn':'Y'}],'RAW')
            execute.assert_not_called()
        with patch.object(service,'query',return_value=models),patch.object(service,'execute'),patch.object(service,'run_model',side_effect=ValueError('date overlap')),patch.object(service,'write_state') as write:
            with self.assertRaises(ValueError):service.append_training(conn,[{'split':'TRAIN','use_yn':'Y','signal':'BUY'}],'RAW')
            conn.rollback.assert_called_once();conn.commit.assert_not_called();write.assert_not_called()

    def test_append_commit_then_training_failure_is_explicit(self):
        conn=MagicMock();events=[]
        conn.commit.side_effect=lambda:events.append('commit')
        with patch.object(service,'query',return_value=[{'model_name':'OML_BASIC_RAW_MODEL'}]),patch.object(service,'execute'),patch.object(service,'run_model',side_effect=lambda *args:events.append(args[1])),patch.object(service,'prepare_model_data',side_effect=lambda *args:events.append('PREPARE')),patch.object(service,'read_state',return_value={'confirmed':'RAW'}),patch.object(service,'write_state'),patch.object(service,'train_model',side_effect=RuntimeError('DDL failed')):
            with self.assertRaisesRegex(ValueError,'적재되었습니다.*재학습은 실패'):service.append_training(conn,[{'split':'TRAIN','use_yn':'Y','signal':'BUY'}],'RAW')
        self.assertEqual(events,['VALIDATE','commit','PREPARE']);conn.rollback.assert_not_called()

    def test_delete_preserves_other_model(self):
        conn=MagicMock();saved={'models':{'RAW':{'x':1},'CLEAN':{'x':2}},'confirmed':'CLEAN'}
        with patch.object(service,'run_model',return_value=[]) as run,patch.object(service,'read_state',return_value=saved),patch.object(service,'write_state'):
            service.delete_model(conn,'RAW');run.assert_called_once_with(conn,'DELETE','RAW')
        self.assertEqual(saved,{'models':{'CLEAN':{'x':2}},'confirmed':'CLEAN'})

    def test_help_has_real_lifecycle_actions_and_append_save_boundary(self):
        for operation,action in [('initial-train','INIT'),('retrain','RETRAIN'),('delete-model','DELETE')]:
            result=coding_help.describe(operation,variant='CLEAN')
            self.assertIn(f"OML_BASIC_RUN('{action}', 'CLEAN'",result['direct_script'])
        with self.assertRaises(ValueError):coding_help.describe('append-train',variant='RAW')
        result=coding_help.describe('retrain',variant='RAW')
        self.assertIn("DBMS_DATA_MINING.DROP_MODEL('OML_BASIC_RAW_MODEL')",result['script'])
        self.assertIn("OML_BASIC_RUN('RETRAIN', 'RAW'",result['direct_script'])


if __name__=='__main__':unittest.main()
