"""Exercise publication against local bare repositories; never contacts GitHub."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'instructor/scripts'))
from source_files import FILES, inventory, safe_path
from git_publish import MARKER, PROJECT, git, publish


class SourceDistribution(unittest.TestCase):
    def setUp(self):
        parent = ROOT / 'runtime' / 'distribution-tests'
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='case-', dir=parent)
        self.base = Path(self.temp.name).resolve()
        self.assertTrue(self.base.is_relative_to(parent.resolve()))
        self.addCleanup(self.temp.cleanup)
        self.project = self.base / 'project with spaces'
        self.project.mkdir()
        for name in FILES:
            self.write(name, '# Example\n' if name != '.gitignore' else '*.env\n*.zip\n')
        self.write('security/student.env.example', 'DB_USER=STUDENT01\nDB_PASSWORD=\nWALLET_PASSWORD=\n')
        self.write('deploy/main.py', 'print("classroom")\n')
        self.remote = self.base / 'remote.git'
        git(self.base, 'init', '--bare', str(self.remote))

    def write(self, name, value):
        target = self.project / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value, encoding='utf-8')

    def publish(self, push=True):
        with contextlib.redirect_stdout(io.StringIO()):
            return publish(self.project, str(self.remote), 'main', 'Classroom test',
                           push=push, author_name='Test Author', author_email='test@example.invalid')

    def test_private_material_excluded(self):
        for name in ('security/teacher.env', 'security/student.env', 'security/Wallet_PCUORA.zip',
                     'runtime/server.log', '.venv/secret.py', 'backups/backup.zip',
                     'reference/installers/tool.exe', 'reference/wheels/package.whl',
                     'deploy/.env', 'scripts/key.pem', 'deploy/__pycache__/cached.py',
                     '.local/operations-commands.txt'):
            self.write(name, 'PRIVATE_TEST_MARKER')
        files = inventory(self.project)
        self.assertIn('deploy/main.py', files)
        self.assertIn('security/student.env.example', files)
        self.assertFalse(any(b'PRIVATE_TEST_MARKER' in value for value in files.values()))

    def test_local_commands_are_git_ignored_and_not_published(self):
        self.write('.gitignore',(ROOT/'.gitignore').read_text(encoding='utf-8'))
        self.write('.local/operations-commands.txt','PRIVATE_LOCAL_OPERATIONS')
        git(self.project,'init')
        ignored=git(self.project,'check-ignore','--no-index','.local/operations-commands.txt')
        self.assertIn('.local/operations-commands.txt',ignored.stdout)
        checkout=self.publish()
        self.assertNotIn('.local/',git(checkout,'ls-files').stdout)

    def test_manifest_paths_cannot_escape(self):
        for name in ('../outside.py', '/absolute.py', 'deploy/../../secret.py',
                     'deploy\\..\\secret.py', 'C:/private.py', '.git/config',
                     'security/teacher.env', 'deploy/a/../../../x.py', 'deploy/a.py:stream'):
            self.assertFalse(safe_path(name), name)

    def test_prepare_does_not_push(self):
        checkout = self.publish(push=False)
        self.assertTrue((checkout / MARKER).is_file())
        self.assertEqual(git(self.remote, 'for-each-ref').stdout.strip(), '')

    def test_initial_publish_update_and_removed_source(self):
        first = self.publish()
        first_id = git(first, 'rev-parse', 'HEAD').stdout.strip()
        self.write('deploy/main.py', 'print("updated")\n')
        self.write('deploy/removed.py', 'pass\n')
        second = self.publish()
        self.assertEqual(git(second, 'rev-parse', 'HEAD^').stdout.strip(), first_id)
        (self.project / 'deploy/removed.py').unlink()
        third = self.publish()
        self.assertFalse((third / 'deploy/removed.py').exists())
        self.assertNotIn('deploy/removed.py', git(third, 'ls-files').stdout)
        self.assertEqual(git(self.remote, 'rev-parse', 'refs/heads/main').stdout,
                         git(third, 'rev-parse', 'HEAD').stdout)

    def test_unmanaged_remote_refused_without_push(self):
        checkout = self.publish()
        (checkout / 'unrelated.txt').write_text('Preserve me', encoding='utf-8')
        git(checkout, 'add', 'unrelated.txt')
        git(checkout, 'commit', '-m', 'Unmanaged file')
        git(checkout, 'push')
        old_head = git(self.remote, 'rev-parse', 'refs/heads/main').stdout
        with self.assertRaisesRegex(ValueError, 'unmanaged'):
            self.publish()
        self.assertEqual(old_head, git(self.remote, 'rev-parse', 'refs/heads/main').stdout)

    def test_unsafe_remote_manifest_refused(self):
        checkout = self.publish()
        (checkout / MARKER).write_text(json.dumps({'project': PROJECT, 'files': {'../escape.py': 'x'}}), encoding='utf-8')
        git(checkout, 'add', MARKER)
        git(checkout, 'commit', '-m', 'Invalid manifest')
        git(checkout, 'push')
        with self.assertRaisesRegex(ValueError, 'Unsafe path'):
            self.publish()


if __name__ == '__main__':
    unittest.main()
