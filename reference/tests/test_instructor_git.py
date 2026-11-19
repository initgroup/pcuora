"""Managed legacy cleanup is tested against disposable local repositories only."""
import hashlib
import importlib.util
import json
import os
from contextlib import redirect_stdout, contextmanager
import io
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('instructor_publish',ROOT/'instructor/scripts/git_publish.py')
publish=importlib.util.module_from_spec(spec);spec.loader.exec_module(publish)

@contextmanager
def temporary_repository():
    temporary=tempfile.TemporaryDirectory(prefix='instructor-git-check-',dir=ROOT/'runtime')
    assert Path(temporary.name).resolve().is_relative_to((ROOT/'runtime').resolve())
    try:
        yield temporary.name
    finally:
        # Windows Git/인덱서의 짧은 핸들 유지가 실제 검증 결과를 가리지 않도록 정리를 재시도합니다.
        for attempt in range(10):
            try:
                temporary.cleanup()
                break
            except PermissionError:
                if attempt==9:raise
                time.sleep(.2)

class InstructorGitTests(unittest.TestCase):
    def test_prior_paths_reject_traversal_and_git_metadata(self):
        for name in ('../app.py','/app.py','a//b','a/../b','.git/config','a\\\\b','C:/a','a./b',''):
            self.assertFalse(publish.managed_path(name),name)
        self.assertTrue(publish.managed_path('deploy/oml/old.py'))
        self.assertTrue(publish.managed_path('.vscode/settings.json'))
        self.assertTrue(publish.retired_content_matches(b'old\n',hashlib.sha256(b'old\r\n').hexdigest()))
        self.assertFalse(publish.retired_content_matches(b'changed\n',hashlib.sha256(b'old\n').hexdigest()))

    def run_publication(self, failure=None):
        with temporary_repository() as directory:
            base=Path(directory);source=base/'source';source.mkdir();remote=base/'remote.git';seed=base/'seed'
            with patch.dict(os.environ,{'GIT_CONFIG_GLOBAL':os.devnull,'GIT_CONFIG_NOSYSTEM':'1','GIT_TERMINAL_PROMPT':'0','GIT_AUTHOR_NAME':'Release Test','GIT_AUTHOR_EMAIL':'release@example.invalid','GIT_COMMITTER_NAME':'Release Test','GIT_COMMITTER_EMAIL':'release@example.invalid'}):
                publish.git(base,'init','--bare','--initial-branch=main',str(remote))
                publish.git(base,'clone',str(remote),str(seed))
                old=seed/'deploy/oml/old.py';old.parent.mkdir(parents=True);old.write_bytes(b'old\n')
                files={'app.py':b'old app\n','deploy/oml/old.py':b'old\r\n'}
                (seed/'app.py').write_bytes(files['app.py'])
                marker={'project':publish.PROJECT,'files':{n:hashlib.sha256(v).hexdigest() for n,v in files.items()}}
                if failure=='modified':old.write_bytes(b'other owner edit\n')
                if failure=='unmanaged':(seed/'other.txt').write_text('preserve',encoding='utf-8')
                if failure=='unsafe':marker['files']['../escape.py']='0'*64
                (seed/publish.MARKER).write_text(json.dumps(marker),encoding='utf-8')
                publish.git(seed,'add','-A');publish.git(seed,'commit','-m','Existing managed release')
                publish.git(seed,'push','origin','HEAD:main')
                initial=publish.git(remote,'rev-parse','main').stdout.strip()
                with patch.object(publish,'inventory',return_value={'app.py':b'new app\n'}),redirect_stdout(io.StringIO()):
                    if failure:
                        with self.assertRaises(ValueError):publish.publish(source,str(remote),'main','Final release',push=True)
                        self.assertEqual(publish.git(remote,'rev-parse','main').stdout.strip(),initial)
                    else:
                        checkout=publish.publish(source,str(remote),'main','Final release',push=False)
                        self.assertEqual(publish.git(remote,'rev-parse','main').stdout.strip(),initial)
                        self.assertFalse((checkout/'deploy/oml/old.py').exists())
                        self.assertEqual((checkout/'app.py').read_bytes(),b'new app\n')
                        self.assertEqual(publish.git(checkout,'rev-parse','HEAD^').stdout.strip(),initial)
                        publish.git(checkout,'push','origin','HEAD:main')
                        self.assertEqual(publish.git(remote,'rev-parse','main').stdout.strip(),publish.git(checkout,'rev-parse','HEAD').stdout.strip())

    def test_retired_cleanup_preserves_history_and_prepare_does_not_push(self):
        self.run_publication()

    def test_modified_unmanaged_and_unsafe_remote_files_stop_publication(self):
        for failure in ('modified','unmanaged','unsafe'):
            with self.subTest(failure=failure):self.run_publication(failure)
