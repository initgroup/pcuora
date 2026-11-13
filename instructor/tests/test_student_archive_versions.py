from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'deploy'))
from oml.app import create_app
from oml.student_archives import archive_key, latest_student_archive, reserve_student_archive


class ArchiveVersions(unittest.TestCase):
    def setUp(self):
        parent = ROOT/'runtime'/'archive-version-tests'
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.temp.name).resolve()
        self.assertTrue(self.root.is_relative_to(parent.resolve()))
        self.addCleanup(self.temp.cleanup)
        self.downloads = self.root/'downloads'
        self.now = datetime(2026,11,13,1,tzinfo=timezone.utc)

    def complete(self, now=None):
        with reserve_student_archive(self.downloads, now=now or self.now) as output:
            with zipfile.ZipFile(output,'x') as archive: archive.writestr('sample.txt','version')
        return output

    def test_daily_sequence_and_korean_midnight(self):
        first = self.complete(); old = first.read_bytes()
        second = self.complete()
        self.assertEqual(first.name,'oml-student-kit-20261113-001.zip')
        self.assertEqual(second.name,'oml-student-kit-20261113-002.zip')
        third = self.complete(datetime(2026,11,13,16,tzinfo=timezone.utc))
        self.assertEqual(third.name,'oml-student-kit-20261114-001.zip')
        self.assertEqual(first.read_bytes(),old)
        self.assertEqual(latest_student_archive(self.downloads),third)

    def test_unfinished_package_not_downloadable(self):
        first = self.complete()
        with reserve_student_archive(self.downloads, now=self.now) as unfinished:
            unfinished.write_bytes(b'incomplete archive')
            self.assertEqual(latest_student_archive(self.downloads),first)
            with reserve_student_archive(self.downloads, now=self.now) as other:
                self.assertNotEqual(unfinished,other)
            unfinished.unlink()

    def test_concurrent_names_are_unique(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            outputs = list(pool.map(lambda _: self.complete(),range(8)))
        self.assertEqual(len(set(outputs)),8)
        self.assertEqual(sorted(archive_key(p.name)[1] for p in outputs),list(range(1,9)))

    def test_invalid_names_are_not_versions(self):
        self.downloads.mkdir()
        for name in ('oml-student-kit.zip','oml-student-kit-20261301-001.zip',
                     'oml-student-kit-20261113-000.zip','oml-student-kit-20261113-001.zip.tmp'):
            (self.downloads/name).write_bytes(b'not a version')
        self.assertIsNone(latest_student_archive(self.downloads))

    def test_web_download_uses_latest_filename(self):
        self.complete(); latest = self.complete()
        with patch('oml.app.ROOT',self.root):
            response=create_app({'TESTING':True}).test_client().get('/download/student.zip')
            self.assertEqual(response.status_code,200)
            self.assertIn(latest.name,response.headers['Content-Disposition'])
            self.assertEqual(response.data,latest.read_bytes())
            response.close()


if __name__=='__main__': unittest.main()
