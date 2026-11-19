"""배포 SQL 검증기의 SQL/PLSQL 경계 보존 회귀 검사입니다. DB에 접속하지 않습니다."""
import re
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from reference.tests.verify_sql_provision_db import statements
class SqlProvisionTests(unittest.TestCase):
    def test_mixed_session_and_plsql_retains_end_semicolon(self):
        source=(ROOT/'sql/examples/run.sql').read_text(encoding='utf-8')
        source=re.sub(r'^(?:VARIABLE|PRINT)\b[^\n]*','',source,flags=re.M)
        parts=list(statements(source))
        self.assertEqual(len(parts),2)
        self.assertIn('ALTER SESSION',parts[0])
        self.assertTrue(parts[1].endswith('END;'))
        self.assertIn(':result',parts[1])
    def test_custom_files_are_contract_notes_without_basic_stock_definitions(self):
        for task in ('mission','creative'):
            for filename in ('01_tables.sql','02_procedure.sql'):
                source=(ROOT/f'sql/custom/{task}/{filename}').read_text(encoding='utf-8')
                self.assertTrue(source.strip())
                self.assertEqual(re.sub(r'--[^\n]*','',source).strip(),'')
    def test_quoted_semicolons_are_not_statement_separators(self):
        parts=list(statements("SELECT 'a;b' FROM DUAL\n;\nBEGIN\n  NULL;\nEND;\n/\n"))
        self.assertEqual(len(parts),2)
        self.assertIn("'a;b'",parts[0])
        self.assertTrue(parts[1].endswith('END;'))
if __name__=='__main__':unittest.main()
