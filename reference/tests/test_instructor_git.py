"""Managed legacy cleanup is tested against disposable local repositories only."""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
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

    def run_publication(self, failure=None, roster=None):
        with temporary_repository() as directory:
            base=Path(directory);source=base/'source';source.mkdir();remote=base/'remote.git';seed=base/'seed'
            if roster is not None:
                (source/'security').mkdir()
                (source/'security/students.json').write_text(json.dumps(roster),encoding='utf-8')
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
                with patch.object(publish,'inventory',return_value={'app.py':b'new app\n','.gitignore':b'security/*\n'}),redirect_stdout(io.StringIO()):
                    if failure:
                        for republish in (False,True):
                            with self.assertRaises(ValueError):publish.publish(source,str(remote),'main','Final release',push=True,republish=republish)
                        self.assertEqual(publish.git(remote,'rev-parse','main').stdout.strip(),initial)
                    else:
                        checkout=publish.publish(source,str(remote),'main','Final release',push=False)
                        self.assertEqual(publish.git(remote,'rev-parse','main').stdout.strip(),initial)
                        self.assertFalse((checkout/'deploy/oml/old.py').exists())
                        if roster is not None:
                            self.assertEqual(json.loads((checkout/'security/students.json').read_text(encoding='utf-8')),roster)
                            self.assertIn('security/students.json',publish.git(checkout,'ls-files').stdout.splitlines())

                        self.assertEqual((checkout/'app.py').read_bytes(),b'new app\n')
                        self.assertEqual(publish.git(checkout,'rev-parse','HEAD^').stdout.strip(),initial)
                        publish.git(checkout,'push','origin','HEAD:main')
                        self.assertEqual(publish.git(remote,'rev-parse','main').stdout.strip(),publish.git(checkout,'rev-parse','HEAD').stdout.strip())

    def test_retired_cleanup_preserves_history_and_prepare_does_not_push(self):
        self.run_publication()

    def test_instructor_publication_includes_own_roster(self):
        self.run_publication(roster=[{'student_id':'V01041','name':'Instructor Test','db_user':'STUDENT01'}])

    def test_multiple_or_password_roster_stops_before_git(self):
        for roster in ([{'student_id':'1','name':'A','db_user':'STUDENT01'}]*2,
                       [{'student_id':'1','name':'A','db_user':'STUDENT01','password':'invalid'}]):
            with self.subTest(rows=len(roster)), temporary_repository() as directory:
                root=Path(directory);(root/'security').mkdir()
                (root/'security/students.json').write_text(json.dumps(roster),encoding='utf-8')
                with patch.object(publish,'inventory',return_value={}), patch.object(publish,'git') as git:
                    for republish in (False,True):
                        with self.assertRaises(ValueError):
                            publish.publish(root,'https://example.invalid/own.git','main','No upload',push=True,republish=republish)
                    git.assert_not_called()

    def test_modified_unmanaged_and_unsafe_remote_files_stop_publication(self):
        for failure in ('modified','unmanaged','unsafe'):
            with self.subTest(failure=failure):self.run_publication(failure)

    def test_unchanged_publish_and_full_republish_preserve_tree_and_history(self):
        with temporary_repository() as directory:
            base=Path(directory);source=base/'source';source.mkdir();remote=base/'remote.git'
            environment={'GIT_CONFIG_GLOBAL':os.devnull,'GIT_CONFIG_NOSYSTEM':'1','GIT_TERMINAL_PROMPT':'0',
                         'GIT_AUTHOR_NAME':'Release Test','GIT_AUTHOR_EMAIL':'release@example.invalid',
                         'GIT_COMMITTER_NAME':'Release Test','GIT_COMMITTER_EMAIL':'release@example.invalid'}
            files={'app.py':b'unchanged source\n','.gitignore':b'runtime/\n.local/\n'}
            with patch.dict(os.environ,environment), patch.object(publish,'inventory',return_value=files):
                publish.git(base,'init','--bare','--initial-branch=main',str(remote))
                with redirect_stdout(io.StringIO()):
                    publish.publish(source,str(remote),'main','Initial',push=True)
                initial=publish.git(remote,'rev-parse','main').stdout.strip()
                tree=publish.git(remote,'rev-parse','main^{tree}').stdout.strip()
                output=io.StringIO()
                with patch.object(publish,'git',wraps=publish.git) as calls,redirect_stdout(output):
                    publish.publish(source,str(remote),'main','No changes',push=True)
                self.assertIn('Already up to date',output.getvalue())
                self.assertNotIn('Published to',output.getvalue())
                self.assertFalse(any(call.args[1]=='push' for call in calls.call_args_list))
                self.assertEqual(publish.git(remote,'rev-parse','main').stdout.strip(),initial)
                with redirect_stdout(io.StringIO()):
                    prepared=publish.publish(source,str(remote),'main','Prepared redeploy',push=False,republish=True)
                self.assertEqual(publish.git(prepared,'rev-parse','HEAD^').stdout.strip(),initial)
                self.assertEqual(publish.git(prepared,'rev-parse','HEAD^{tree}').stdout.strip(),tree)
                self.assertEqual(publish.git(remote,'rev-parse','main').stdout.strip(),initial)
                for attempt in range(2):
                    with self.subTest(attempt=attempt),redirect_stdout(io.StringIO()):
                        previous=publish.git(remote,'rev-parse','main').stdout.strip()
                        publish.publish(source,str(remote),'main','Redeploy complete source',push=True,republish=True)
                        current=publish.git(remote,'rev-parse','main').stdout.strip()
                        self.assertNotEqual(current,previous)
                        self.assertEqual(publish.git(remote,'rev-parse','main^').stdout.strip(),previous)
                        self.assertEqual(publish.git(remote,'rev-parse','main^{tree}').stdout.strip(),tree)
                        names=publish.git(remote,'ls-tree','-r','--name-only','main').stdout.splitlines()
                        self.assertEqual(set(names),set(files)|{publish.MARKER})

class InstructorMainEntryTests(unittest.TestCase):
    def test_main_entry_delegates_modes_from_another_working_directory(self):
        shell=shutil.which('powershell') or shutil.which('pwsh')
        if not shell:self.skipTest('PowerShell is unavailable')
        with temporary_repository() as directory:
            base=Path(directory);source=base/'instructor source';scripts=source/'scripts'
            scripts.mkdir(parents=True);target=source/'instructor/scripts';target.mkdir(parents=True)
            for entry_name,republish in (('git-publish-main.ps1',False),('git-republish-main.ps1',True)):
                entry=scripts/entry_name
                shutil.copyfile(ROOT/'scripts'/entry_name,entry)
                stub=target/'deploy-github.ps1'
                stub.write_text("""param([string]$Branch,[string]$Message,[string]$AuthorName,[string]$AuthorEmail,[switch]$Push,[switch]$Prepare,[switch]$Republish)
$PSBoundParameters | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'call.json') -Encoding utf8
if ($Message -eq 'fail') { throw 'Publication failed' }
""",encoding='utf-8')
                def invoke(*args):
                    return subprocess.run([shell,'-NoProfile','-NonInteractive','-File',str(entry),*args],
                                          cwd=base,capture_output=True,timeout=30)
                for args,mode in (((), 'Push'),(('-Push',),'Push'),(('-Preview',),None),(('-Prepare',),'Prepare')):
                    with self.subTest(entry=entry_name,args=args):
                        result=invoke(*args,'-Message','Main update','-AuthorName','Teacher')
                        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
                        call=json.loads((target/'call.json').read_text(encoding='utf-8-sig'))
                        self.assertEqual(call['Branch'],'main')
                        self.assertEqual(call['Message'],'Main update')
                        self.assertEqual(call['AuthorName'],'Teacher')
                        self.assertEqual(bool(call.get('Push')),mode=='Push')
                        self.assertEqual(bool(call.get('Prepare')),mode=='Prepare')
                        self.assertEqual(bool(call.get('Republish')),republish)
                self.assertNotEqual(invoke('-Push','-Preview').returncode,0)
                self.assertNotEqual(invoke('-Message','fail').returncode,0)
                stub.unlink()
                self.assertNotEqual(invoke('-Preview').returncode,0)

    def test_main_entry_is_instructor_distribution_only(self):
        from source_files import inventory, student_git_path
        for name in ('scripts/git-publish-main.ps1','scripts/git-republish-main.ps1'):
            self.assertIn(name,inventory(ROOT))
            self.assertNotIn(name,inventory(ROOT,audience='student'))
            self.assertFalse(student_git_path(name))
