"""수집 오류가 TRAIN에만 들어가고 정상 TEST·정답이 보존되는지 확인합니다."""
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from reference.tools.make_mission_samples import sample,encode,SPECS


class MissionDataTests(unittest.TestCase):
    def test_labels_holdout_and_prediction_survive_corruption(self):
        for index in range(len(SPECS)):
            dirty,item=sample(index);pristine,_=sample(index,corrupt=False)
            self.assertEqual([(r['case_id'],r['label'],r['split']) for r in dirty],[(r['case_id'],r['label'],r['split']) for r in pristine])
            self.assertEqual(dirty[1200:],pristine[1200:])
            fields=item['columns'][1:4]
            valid=0
            for row in dirty[:1200]:
                errors=[row[f] in ('','unknown','999999') for f in fields]
                self.assertIn(sum(errors),(0,3))
                valid+=not any(errors)
            self.assertGreater(valid,200);self.assertLess(valid,300)

    def test_release_csv_and_actual_baselines_match(self):
        catalog=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
        for index,item in enumerate(catalog):
            dirty,metadata=sample(index)
            self.assertEqual(item['layout'],metadata['layout'])
            raw=(ROOT/'data/examples'/item['filename']).read_bytes()
            actual=list(csv.DictReader(io.StringIO(raw.decode('utf-8'))))
            expected=list(csv.DictReader(io.StringIO(encode(dirty[:1500],metadata['columns']))))
            self.assertEqual(actual,expected)
            score=item.get('baseline')
            if score:
                self.assertEqual(hashlib.sha256(raw).hexdigest(),score['sha256'])
                self.assertLess(score['raw_accuracy'],50)
                self.assertGreater(score['clean_accuracy'],score['raw_accuracy'])
                self.assertGreater(score['control_accuracy'],score['raw_accuracy'])
                self.assertEqual(score['min_percent_node'],10)
                self.assertEqual(score['test_rows'],300)
            else:
                self.assertEqual(hashlib.sha256(raw).hexdigest(),item['csv_sha256'])
            prediction=list(csv.DictReader(io.StringIO((ROOT/'data/examples'/item['prediction_filename']).read_text(encoding='utf-8'))))
            self.assertEqual(len(prediction),30)
            self.assertEqual(list(prediction[0]),item['columns'][:4])


    def test_twelve_topics_have_concrete_purpose_and_feature_interpretations(self):
        from scripts.source_files import APP_FILES
        catalog=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
        self.assertEqual(len(catalog),12)
        self.assertEqual([item['key'] for item in catalog[-2:]],['delivery','appux'])
        for index,item in enumerate(catalog):
            self.assertTrue(item['title'].startswith(str(index+1)+'. '))
            self.assertGreater(len(item['learning']['purpose']),15)
            self.assertGreater(len(item['learning']['use_case']),15)
            self.assertTrue(item['layout'][4]['meaning'])
            for field in item['layout'][1:4]:
                self.assertEqual(field['valid'],'숫자 0~100, 단위 없음')
                for key in ('meaning','low_meaning','high_meaning'):self.assertTrue(field[key])
            self.assertIn('data/examples/'+item['filename'],APP_FILES)
            self.assertIn('data/examples/'+item['prediction_filename'],APP_FILES)



if __name__=='__main__':unittest.main()
