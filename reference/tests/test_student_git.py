"""외부 GitHub에 접속하지 않고 실제 로컬 Git 저장소로 학생 배포를 검증합니다."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import git_publish as student_git
from source_files import inventory, student_git_path, STUDENT_GUIDE


class StudentGitTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='student-git-test-', dir=ROOT / 'runtime')
        self.addCleanup(self.cleanup_repository)
        self.folder = Path(self.temporary.name)
        self.root = self.folder / 'student source'
        self.root.mkdir()
        self.write('app.py', 'print("student source")\n')
        self.write('.gitignore', (ROOT / '.gitignore').read_text(encoding='utf-8'))
        self.write('security/student.env.example', 'DB_USER=\nDB_PASSWORD=\nWALLET_PASSWORD=\n')
        self.write('security/students.example.json', '[]')
        self.write('sql/custom/mission.sql', '-- own procedure\n')
        self.write('templates/creative.html', '<main>My task</main>')
        self.write('security/student.env', 'DB_PASSWORD=PrivateOnly_22417\n')
        self.write('security/students.json', '[{"student_id":"20260001","name":"Example Student","db_user":"STUDENT01"}]')
        self.write('security/Wallet_PCUORA.zip', 'private-wallet')
        self.write('instructor/private.py', '# instructor only')
        self.write('submission/report.txt', 'private report')
        self.write('.local/private.py', '# local only')
        self.remote = self.folder / 'remote.git'
        # 임시 폴더에서만 검증하며 사용자의 Git 설정은 변경하지 않습니다.
        self.env = patch.dict(os.environ, {
            'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1',
            'GIT_TERMINAL_PROMPT': '0', 'GIT_AUTHOR_NAME': 'Student Test',
            'GIT_AUTHOR_EMAIL': 'student@example.invalid', 'GIT_COMMITTER_NAME': 'Student Test',
            'GIT_COMMITTER_EMAIL': 'student@example.invalid',
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.real_git = student_git.git
        self.real_git(self.folder, 'init', '--bare', '--initial-branch=main', str(self.remote))

    def cleanup_repository(self):
        # Git/Windows 인덱서가 해제하는 짧은 파일 잠금은 정리 단계에서만 재시도합니다.
        assert self.folder.resolve().is_relative_to((ROOT / 'runtime').resolve())
        for attempt in range(10):
            try:
                self.temporary.cleanup()
                return
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(.2)

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    def local_git(self, cwd, *args, **kwargs):
        # URL 검증은 실제 함수를 사용하고 clone의 전송 대상만 로컬 bare 저장소로 바꿉니다.
        if args[0] == 'clone':
            args = (*args[:-2], str(self.remote), args[-1])
        return self.real_git(cwd, *args, **kwargs)

    def publish(self, **kwargs):
        with patch.object(student_git, 'git', side_effect=self.local_git), redirect_stdout(io.StringIO()):
            return student_git.publish(self.root, 'https://github.com/student-test/oml-task.git',
                                       author_name='Student Test', author_email='student@example.invalid', **kwargs)

    def head(self):
        return self.real_git(self.remote, 'rev-parse', '--verify', 'refs/heads/main', check=False)

    def test_repository_required_and_protected_before_any_git_call(self):
        for value in ('', 'http://github.com/student-test/task',
                      'https://user:token@github.com/student-test/task',
                      'https://github.com/student-test/task?token=x',
                      'https://example.com/student-test/task',
                      'https://github.com/student-test/../task',
                      'https://github.com/YOUR_GITHUB_ID/YOUR_REPOSITORY.git',
                      'https://github.com/initgroup/pcuora.git',
                      'https://GITHUB.COM/InitGroup/PCUORA/',
                      'https://github.com/initgroup/pcuora.GIT'):
            with self.subTest(value=value), patch.object(student_git, 'git') as git:
                with self.assertRaises(ValueError):
                    student_git.publish(self.root, value, push=True)
                git.assert_not_called()
        self.assertEqual(student_git.repository_url('https://github.com/student-test/task/'),
                         'https://github.com/student-test/task.git')

    def test_preview_has_no_git_calls_and_uses_student_inventory(self):
        output = io.StringIO()
        with patch.object(student_git, 'ROOT', self.root), patch.object(student_git, 'git') as git, \
                patch.object(student_git, 'inventory', side_effect=lambda **kw: inventory(self.root, **kw)), \
                patch.object(sys, 'argv', ['git_publish.py', '--repository', 'https://github.com/student-test/task']), \
                redirect_stdout(output):
            student_git.main()
        git.assert_not_called()
        self.assertIn('sql/custom/mission.sql', output.getvalue())
        self.assertNotIn('private', output.getvalue())
        self.assertNotIn('security/student.env\n', output.getvalue())

    def test_inventory_includes_extensions_and_rejects_secret_leak(self):
        files = inventory(self.root, audience='student-git')
        self.assertEqual(set(files), {'app.py', '.gitignore', 'security/student.env.example',
                                     'security/students.example.json', 'sql/custom/mission.sql',
                                     'templates/creative.html', 'security/students.json'})
        for name in ('../outside.py', '/outside.py', 'instructor/private.py',
                     '.local/private.py', 'sql/.hidden/test.sql', 'sql/a/../../outside.sql'):
            self.assertFalse(student_git_path(name), name)
        self.write('backend/leak.py', 'password = "PrivateOnly_22417"')
        with self.assertRaisesRegex(ValueError, 'Configured secret'):
            inventory(self.root, audience='student-git')

    def test_invalid_or_multiple_roster_is_rejected_before_any_git_call(self):
        for value in ('[]','[{"student_id":"1","name":"A","db_user":"STUDENT01","password":"bad"}]',
                      '[{"student_id":"1","name":"A","db_user":"STUDENT01"},{"student_id":"2","name":"B","db_user":"STUDENT02"}]'):
            with self.subTest(value=value):
                self.write('security/students.json',value)
                with patch.object(student_git,'git') as git, self.assertRaises(ValueError):
                    inventory(self.root,audience='student-git')
                git.assert_not_called()

    def test_root_assignment_guide_is_included_in_student_git(self):
        self.write(STUDENT_GUIDE, '<main>My assignment guide</main>')
        self.assertIn(STUDENT_GUIDE, inventory(self.root, audience='student-git'))
        self.assertTrue(student_git_path(STUDENT_GUIDE))

    def test_prepare_push_update_and_delete_use_real_git(self):
        checkout = self.publish()
        self.assertNotEqual(self.head().returncode, 0)
        self.assertTrue((checkout / 'sql/custom/mission.sql').is_file())
        self.assertFalse((self.root / '.git').exists())
        self.publish(push=True)
        first = self.head().stdout
        self.assertEqual(self.head().returncode, 0)
        names = self.real_git(self.remote, 'ls-tree', '-r', '--name-only', 'main').stdout.splitlines()
        self.assertIn('security/students.example.json', names)
        self.assertNotIn('security/student.env', names)
        self.assertIn('security/students.json', names)
        self.assertNotIn('security/Wallet_PCUORA.zip', names)
        self.assertNotIn('instructor/private.py', names)
        self.write('app.py', 'print("updated")\n')
        (self.root / 'sql/custom/mission.sql').unlink()
        self.publish(push=True)
        self.assertNotEqual(first, self.head().stdout)
        self.assertEqual(self.real_git(self.remote, 'show', 'main:app.py').stdout, 'print("updated")\n')
        names = self.real_git(self.remote, 'ls-tree', '-r', '--name-only', 'main').stdout.splitlines()
        self.assertNotIn('sql/custom/mission.sql', names)
        second = self.head().stdout
        self.publish(push=True)
        self.assertEqual(second, self.head().stdout)

    def test_existing_unmanaged_repository_is_not_overwritten(self):
        seed = self.folder / 'seed'
        self.real_git(self.folder, 'clone', str(self.remote), str(seed))
        (seed / 'README.md').write_text('Existing work', encoding='utf-8')
        self.real_git(seed, 'add', 'README.md')
        self.real_git(seed, 'commit', '-m', 'Existing work')
        self.real_git(seed, 'push', 'origin', 'main')
        previous = self.head().stdout
        with self.assertRaisesRegex(ValueError, '관리한 저장소'):
            self.publish(push=True)
        self.assertEqual(previous, self.head().stdout)

    def test_unsafe_remote_manifest_is_not_pushed(self):
        checkout = self.publish(push=True)
        marker = checkout / student_git.MARKER
        data = json.loads(marker.read_text(encoding='utf-8'))
        data['files']['../outside.py'] = 'invalid'
        marker.write_text(json.dumps(data), encoding='utf-8')
        self.real_git(checkout, 'add', student_git.MARKER)
        self.real_git(checkout, 'commit', '-m', 'Invalid manifest fixture')
        self.real_git(checkout, 'push', 'origin', 'main')
        previous = self.head().stdout
        with self.assertRaisesRegex(ValueError, '허용되지 않은 경로'):
            self.publish(push=True)
        self.assertEqual(previous, self.head().stdout)


if __name__ == '__main__':
    unittest.main()
