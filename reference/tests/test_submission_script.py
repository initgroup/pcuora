"""Run the shipped PowerShell submission command against disposable student files."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import unittest
import venv
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from source_files import inventory


@unittest.skipUnless(os.name == 'nt', 'Windows PowerShell entry point')
class SubmissionScriptTests(unittest.TestCase):
    def test_actual_command_from_a_moved_project_and_another_working_folder(self):
        shell = shutil.which('powershell.exe')
        if not shell:
            self.skipTest('Windows PowerShell is unavailable')
        checks = []
        with tempfile.TemporaryDirectory(prefix='submit moved ', dir=ROOT / 'runtime') as directory:
            temporary = Path(directory)
            project = temporary / 'student source'
            for name, raw in inventory(audience='student').items():
                path = project / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
            env = os.environ.copy()
            # Reuse installed dependencies without installing packages or touching the live venv.
            env.update(PYTHONPATH=sysconfig.get_path('purelib'), PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
            archive = project / 'downloads/COM22417_2026H2_20260001.zip'

            def run(label, expected, student_id='20260001', message=''):
                result = subprocess.run(
                    [shell, '-NoProfile', '-NonInteractive', '-File',
                     str(project / 'scripts/submit.ps1'), '-StudentId', student_id],
                    cwd=temporary, env=env, capture_output=True, text=True,
                    encoding='utf-8', errors='replace', timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW)
                output = result.stdout + result.stderr
                self.assertEqual(result.returncode == 0, expected, output)
                if message:
                    self.assertIn(message, output)
                checks.append({'case': label, 'exit_code': result.returncode, 'ok': True})

            run('setup_required', False, message='Run scripts/setup.ps1 first.')
            # The temporary interpreter uses the already installed dependency directory above.
            venv.create(project / '.venv', with_pip=False, symlinks=False)
            run('literal_placeholder_rejected', False, student_id='본인학번')
            run('missing_presentation', False, message='Add one PPT deliverable')
            presentation = project / 'submission/presentation.pptx'
            presentation.parent.mkdir(exist_ok=True)

            def deck(text):
                # A packaging fixture, deliberately not a student presentation deliverable.
                with zipfile.ZipFile(presentation, 'w', zipfile.ZIP_DEFLATED) as packed:
                    packed.writestr('[Content_Types].xml', '<Types/>')
                    packed.writestr('ppt/presentation.xml', '<presentation/>')
                    packed.writestr('ppt/slides/slide1.xml', '<slide>' + text + '</slide>')

            deck('Packaging verification only')
            run('missing_report', False, message='Complete one report')
            report = project / 'submission/report.txt'
            report.write_text('학번: 20269999\n검증 자료', encoding='utf-8')
            run('report_student_id_mismatch', False, message='Student ID must match')
            report.write_text('학번: 20260001\n직접 실행한 검증 자료', encoding='utf-8')
            (project / 'backend/student_extra.py').write_text('# Additional student source\n', encoding='utf-8')
            (project / 'sql/student_extra.sql').write_text('-- Additional student SQL\n', encoding='utf-8')
            (project / 'submission/evidence').mkdir()
            (project / 'submission/evidence/check.txt').write_text('Isolated verification', encoding='utf-8')
            private = 'SubmissionFixturePrivate_22417'
            (project / 'security/student.env').write_text('DB_PASSWORD=' + private, encoding='utf-8')
            (project / 'security/Wallet_PCUORA.zip').write_bytes(b'Private wallet fixture')
            run('source_ppt_report_packaged', True, message='Created:')
            with zipfile.ZipFile(archive) as packed:
                prefix = 'COM22417_2026H2_20260001/'
                self.assertIsNone(packed.testzip())
                expected = inventory(project, audience='submission')
                mapping = {prefix + ('report/' + name.removeprefix('submission/')
                                    if name.startswith('submission/') else 'source/' + name): raw
                           for name, raw in expected.items()}
                manifest = json.loads(packed.read(prefix + 'MANIFEST.sha256.json'))
                self.assertEqual(set(packed.namelist()), {*mapping, prefix + 'MANIFEST.sha256.json'})
                self.assertEqual(manifest, {name: hashlib.sha256(raw).hexdigest() for name, raw in mapping.items()})
                for name, raw in mapping.items():
                    self.assertEqual(packed.read(name), raw)
                self.assertIn(prefix + 'source/backend/student_extra.py', mapping)
                self.assertIn(prefix + 'source/sql/student_extra.sql', mapping)
                self.assertIn(prefix + 'report/evidence/check.txt', mapping)
                self.assertNotIn(prefix + 'source/security/student.env', mapping)
                self.assertNotIn(prefix + 'source/security/Wallet_PCUORA.zip', mapping)
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            deck(private)
            run('presentation_secret_rejected', False, message='Configured secret detected')
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), digest)
            deck('Packaging verification only')
            (project / 'sql/classifier.sql').unlink()
            run('missing_required_sql_rejected', False, message='Required Python/DDL/procedure source missing')
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), digest)
            result = {'ok': True, 'actual_powershell_command': True, 'moved_path_with_spaces': True,
                      'different_working_directory': True, 'manifest_and_source_bytes': True,
                      'private_env_and_wallet_excluded': True, 'failure_preserves_existing_zip': True,
                      'real_database_access': False, 'checks': checks,
                      'output_example': 'downloads/COM22417_2026H2_20260001.zip'}
        (ROOT / 'runtime/submission-script-verification.json').write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    unittest.main()
