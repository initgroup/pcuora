import csv
import io
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'deploy'))
from oml.validation import validate_csv,metrics

class DataValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.raw=(ROOT/'deploy/data/classification.csv').read_bytes()
    def changed(self,column,value,row=0):
        reader=csv.DictReader(io.StringIO(self.raw.decode('utf-8')))
        fields=reader.fieldnames; data=list(reader); data[row][column]=value
        out=io.StringIO(newline=''); w=csv.DictWriter(out,fieldnames=fields);w.writeheader();w.writerows(data)
        return out.getvalue().encode()
    def test_sample_and_bom(self):
        self.assertEqual(len(validate_csv(self.raw)),120)
        self.assertEqual(len(validate_csv(b'\xef\xbb\xbf'+self.raw)),120)
    def test_nan_infinity_and_range(self):
        for value in ['NaN','Infinity','-1','10000001']:
            with self.subTest(value=value),self.assertRaises(ValueError): validate_csv(self.changed('total_amount',value))
    def test_duplicate_customer(self):
        with self.assertRaisesRegex(ValueError,'customer_id'):validate_csv(self.changed('customer_id','1',1))
    def test_missing_future_label(self):
        with self.assertRaises(ValueError):validate_csv(self.changed('label',''))
    def test_unknown_label_and_fractional_counts(self):
        for col,value in [('label','MAYBE'),('order_count','1.5'),('split','VALIDATION')]:
            with self.subTest(column=col),self.assertRaises(ValueError): validate_csv(self.changed(col,value))
    def test_no_holdout(self):
        with self.assertRaises(ValueError):validate_csv(self.raw.replace(b',TEST',b',TRAIN'))
    def test_one_row_file(self):
        with self.assertRaises(ValueError):validate_csv(b'\n'.join(self.raw.splitlines()[:2]))
    def test_bad_encoding(self):
        with self.assertRaises(ValueError):validate_csv(b'\xff\xfe\x00')
    def test_metrics_and_training_baseline(self):
        m=metrics([{'actual':'REBUY','predicted':'REBUY','n':6},
            {'actual':'REBUY','predicted':'NO_REBUY','n':3},
            {'actual':'NO_REBUY','predicted':'REBUY','n':2},
            {'actual':'NO_REBUY','predicted':'NO_REBUY','n':12}],'NO_REBUY')
        self.assertAlmostEqual(m['accuracy'],18/23);self.assertAlmostEqual(m['precision'],6/8)
        self.assertAlmostEqual(m['recall'],6/9);self.assertAlmostEqual(m['majority_baseline'],14/23)
    def test_no_positive_predictions(self):
        m=metrics([{'actual':'REBUY','predicted':'NO_REBUY','n':3}],'NO_REBUY')
        self.assertIsNone(m['precision']);self.assertEqual(m['recall'],0)

if __name__=='__main__': unittest.main()
