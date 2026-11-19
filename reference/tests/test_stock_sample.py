"""출처 일치·미래 정보 누수·기간 분리·교육용 결함의 재현성을 검증합니다."""
import csv
from datetime import date, timedelta
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from backend.validation import COLUMNS, FEATURES, parse_csv, quality


class StockSampleTests(unittest.TestCase):
    def test_source_labels_and_feature_provenance(self):
        with zipfile.ZipFile(ROOT/'reference/datasets/dow-jones/uci-dow-jones.zip') as archive:
            original=archive.read('dow_jones_index.data')
        from datetime import datetime
        source=list(csv.DictReader(io.StringIO(original.decode('ascii'))))
        source.sort(key=lambda r:(datetime.strptime(r['date'],'%m/%d/%Y'),r['stock']))
        manifest=json.loads((ROOT/'data/stock-source.json').read_text(encoding='utf-8'))
        self.assertEqual(hashlib.sha256(original).hexdigest(),manifest['source_sha256'])
        changes=json.loads((ROOT/'reference/datasets/dow-jones/classroom-changes.json').read_text(encoding='utf-8'))
        defects={(r['case_id'],r['column']):r for r in changes}
        training=parse_csv((ROOT/'data/classification.csv').read_bytes())
        prices=lambda value:Decimal(value.removeprefix('$'))
        for row in training:
            src=source[row['case_id']-1]
            self.assertEqual(row['signal'],'BUY' if prices(src['next_weeks_close'])>prices(src['next_weeks_open']) else 'SELL')
            expected={
                'return_pct':src['percent_change_price'],
                'range_pct':format(100*(prices(src['high'])-prices(src['low']))/prices(src['open']),'.6f'),
                'volume_change_pct':src['percent_change_volume_over_last_wk'],
                'close_price':src['close'].removeprefix('$'), 'stock':src['stock'],
            }
            for key,value in expected.items():
                change=defects.get((row['case_id'],key))
                if change:
                    self.assertEqual(change['original'],value)
                    value=change['stored']
                self.assertEqual(row[key],value)

    def test_time_split_and_prediction_are_disjoint(self):
        data=parse_csv((ROOT/'data/classification.csv').read_bytes())
        prediction=parse_csv((ROOT/'data/prediction.csv').read_bytes(),prediction=True)
        train=[r for r in data if r['split']=='TRAIN' and r['use_yn']=='Y']
        test=[r for r in data if r['split']=='TEST' and r['use_yn']=='Y']
        self.assertEqual((len(data),len(train),len(test),len(prediction)),(720,330,360,30))
        self.assertLess(date.fromisoformat(max(r['week_ending'] for r in train))+timedelta(days=7),date.fromisoformat(min(r['week_ending'] for r in test)))
        self.assertLess(max(r['week_ending'] for r in test),min(r['week_ending'] for r in prediction))
        self.assertFalse({r['case_id'] for r in data}&{r['case_id'] for r in prediction})
        self.assertEqual({r['week_ending'] for r in data if r['use_yn']=='N'},{'2011-03-25'})
        self.assertTrue(all(not r['signal'] for r in prediction))
        self.assertEqual(quality(data)['invalid_target'],0)
        self.assertEqual(FEATURES,('return_pct','range_pct','volume_change_pct','close_price','stock'))
        self.assertNotIn('next_weeks_close',COLUMNS)

    def test_only_missing_invalid_and_large_outlier_defects(self):
        changes=json.loads((ROOT/'reference/datasets/dow-jones/classroom-changes.json').read_text(encoding='utf-8'))
        self.assertEqual({c['kind'] for c in changes},{'missing','invalid_string','out_of_range'})
        self.assertTrue(all(c['stored'] in ('','unknown','999999') for c in changes))
        for name,prediction in [('classification.csv',False),('prediction.csv',True)]:
            data=parse_csv((ROOT/'data'/name).read_bytes(),prediction=prediction)
            for row in data:
                self.assertRegex(row['stock'],r'^[A-Z][A-Z0-9.]*$')
                for key in FEATURES[:4]:
                    value=row[key]
                    if value in ('','unknown'):
                        continue
                    Decimal(value)  # 단위가 붙은 숫자 문자열은 허용하지 않습니다.
                    self.assertFalse(any(unit in value for unit in ('%','$','USD')))

    def test_future_inputs_and_invalid_dates_rejected(self):
        raw=(ROOT/'data/prediction.csv').read_bytes()
        with self.assertRaises(ValueError):
            parse_csv(raw.replace(b'close_price',b'next_weeks_close'),prediction=True)
        with self.assertRaisesRegex(ValueError,'week_ending'):
            parse_csv(raw.replace(b'2011-06-24',b'2011-02-30'),prediction=True)

    def test_regeneration_is_identical(self):
        from importlib.util import spec_from_file_location, module_from_spec
        files=[ROOT/'data'/name for name in ('classification.csv','prediction.csv','stock-source.json')]
        before=[path.read_bytes() for path in files]
        spec=spec_from_file_location('stock_generator',ROOT/'reference/tools/make_stock_sample.py')
        module=module_from_spec(spec);spec.loader.exec_module(module)
        module.build()
        self.assertEqual(before,[path.read_bytes() for path in files])


if __name__=='__main__':unittest.main()
