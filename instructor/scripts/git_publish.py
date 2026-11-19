"""Publish only the public inventory from an isolated checkout. Never force-push."""
import argparse
import hashlib
import re
import json
from pathlib import Path
import subprocess
import tempfile
import sys
from urllib.parse import urlsplit
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from source_files import ROOT, inventory, manifest
from distribution_guard import validate_files, validate_student_roster

MARKER = 'OML_SOURCE_MANIFEST.json'
PROJECT = 'pcuora-oml-classroom'
DEFAULT_REPO = 'https://github.com/initgroup/pcuora.git'


def git(cwd, *args, check=True):
    result = subprocess.run(['git', *args], cwd=cwd, text=True, encoding='utf-8',
                            errors='replace', capture_output=True, timeout=180)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'Git failed.')
    return result



def managed_path(name):
    """과거 manifest 경로도 검증하되 최신 배포 목록에 있을 것을 요구하지 않습니다."""
    if not isinstance(name, str) or not name or re.search(r'[\\\\:<>"|?*\x00]', name):
        return False
    parts = name.split('/')
    if any(not part or part in ('.', '..') or part.endswith((' ', '.')) for part in parts):
        return False
    if any(part.startswith('.') for part in parts):
        return name in ('.gitignore', '.gitattributes') or (
            parts[0] == '.vscode' and all(not part.startswith('.') for part in parts[1:]))
    return True


def retired_content_matches(raw, expected):
    candidates = [raw]
    # Git checkout의 CRLF/LF 변환만 허용하며 다른 내용 변경은 폐기하지 않습니다.
    if b'\0' not in raw:
        try:
            raw.decode('utf-8')
            lf = raw.replace(b'\r\n', b'\n')
            candidates.extend((lf, lf.replace(b'\n', b'\r\n')))
        except UnicodeDecodeError:
            pass
    return expected in {hashlib.sha256(value).hexdigest() for value in candidates}


def publication_files(root):
    """운영 Git에는 전체 명단 대신 본인 한 행의 로그인 매핑을 포함합니다."""
    root = Path(root).resolve()
    files = inventory(root)
    path = root / 'security/students.json'
    if path.is_file():
        if not path.resolve().is_relative_to(root) or path.is_symlink() or path.parent.is_symlink() or path.parent.is_junction():
            raise ValueError('Linked roster is not allowed.')
        raw = path.read_bytes()
        validate_student_roster(raw)
        validate_files({'security/students.json': raw}, root)
        files['security/students.json'] = raw
    return files


def publish(root, repository, branch, message, push=False, author_name='', author_email=''):
    files = publication_files(root)
    git(root, 'check-ref-format', '--branch', branch)
    runtime = root / 'runtime'
    runtime.mkdir(exist_ok=True)
    checkout = Path(tempfile.mkdtemp(prefix='github-', dir=runtime))
    print('Review checkout: ' + str(checkout))
    # No hooks from user/global templates; remote contents are data, never executed.
    git(root, 'clone', '--no-checkout', '--template=', '--', repository, str(checkout))
    no_hooks = checkout / '.git' / 'oml-no-hooks'
    no_hooks.mkdir()
    git(checkout, 'config', 'core.hooksPath', str(no_hooks))
    refs = git(checkout, 'for-each-ref', '--format=%(refname)', 'refs/remotes/origin/').stdout.splitlines()
    wanted = 'refs/remotes/origin/' + branch
    if wanted in refs:
        git(checkout, 'checkout', '-B', branch, wanted)
    elif refs:
        raise ValueError(f'Remote is not empty and branch {branch} is absent. Choose its existing branch explicitly.')
    else:
        git(checkout, 'checkout', '--orphan', branch)
    tracked = set(git(checkout, 'ls-files', '-z').stdout.rstrip('\0').split('\0')) - {''}
    previous = set()
    marker = checkout / MARKER
    if tracked:
        if MARKER not in tracked or marker.is_symlink():
            raise ValueError('Existing repository is not managed by this script. No files changed or pushed.')
        data = json.loads(marker.read_text(encoding='utf-8'))
        if data.get('project') != PROJECT or not isinstance(data.get('files'), dict):
            raise ValueError('Unrecognized source manifest. No files changed or pushed.')
        previous = set(data['files'])
        if any(not managed_path(name) or name == MARKER for name in previous):
            raise ValueError('Unsafe path in remote source manifest.')
        # Do not publish unexpected tracked files, even if added outside this script.
        if tracked - previous - {MARKER}:
            raise ValueError('Repository contains unmanaged tracked files. Review them manually before publishing.')
    for name in set(files) | previous | {MARKER}:
        target = checkout / name
        if not target.resolve().is_relative_to(checkout.resolve()):
            raise ValueError('Remote path escapes checkout: ' + name)
        for part in (target, *target.parents):
            if part == checkout:
                break
            if part.is_symlink() or part.is_junction():
                raise ValueError('Remote contains linked path: ' + name)
    retired = previous - files.keys()
    if previous - tracked:
        raise ValueError('Remote manifest names files absent from tracked source.')
    for name in retired:
        target = checkout / name
        if not retired_content_matches(target.read_bytes(), data['files'][name]):
            raise ValueError('Retired managed file differs from its manifest; preserve and review: ' + name)
    for name in retired:
        (checkout / name).unlink()

    for name, raw in files.items():
        target = checkout / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    marker.write_text(json.dumps({'project': PROJECT, 'files': json.loads(manifest(files))}, indent=2) + '\n', encoding='utf-8')
    # Only the reviewed inventory and removals from its previous manifest are staged.
    paths = sorted(set(files) | previous | {MARKER})
    # .gitignore는 실제 전체 명단을 보호하며, 검증한 본인 명단 한 파일만 명시적으로 추가합니다.
    paths = [name for name in paths if name != 'security/students.json']
    for offset in range(0, len(paths), 50):
        git(checkout, 'add', '-A', '--', *paths[offset:offset+50])
    if 'security/students.json' in files:
        git(checkout, 'add', '-f', '--', 'security/students.json')
    elif 'security/students.json' in previous:
        git(checkout, 'add', '-A', '--', 'security/students.json')
    print(git(checkout, 'diff', '--cached', '--stat').stdout.strip() or 'No source changes.')
    changed = git(checkout, 'diff', '--cached', '--quiet', check=False).returncode
    if changed not in (0, 1):
        raise RuntimeError('Could not inspect staged changes.')
    if changed:
        if author_name:
            git(checkout, 'config', 'user.name', author_name)
        if author_email:
            git(checkout, 'config', 'user.email', author_email)
        git(checkout, 'commit', '-m', message)
    if push:
        git(checkout, 'push', '--set-upstream', 'origin', 'HEAD:refs/heads/' + branch)
        print('Published to ' + repository + ' (' + branch + ').')
    else:
        print('Local commit prepared; nothing pushed. Inspect this checkout with git log / git show.')
    return checkout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository', default=DEFAULT_REPO)
    parser.add_argument('--branch', default='main')
    parser.add_argument('--message', default='Update OML classroom source')
    parser.add_argument('--author-name', default='')
    parser.add_argument('--author-email', default='')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--prepare', action='store_true')
    mode.add_argument('--push', action='store_true')
    args = parser.parse_args()
    # Authentication belongs to Git Credential Manager, not repository URLs.
    url = urlsplit(args.repository)
    if url.scheme != 'https' or url.username or url.password or url.query or url.fragment:
        parser.error('Use an HTTPS repository URL without embedded credentials.')
    if not (args.prepare or args.push):
        files = publication_files(ROOT)
        print('PREVIEW ONLY: ' + args.repository + ' [' + args.branch + ']')
        for name in files:
            print('  ' + name)
        print(f'{len(files)} public source files. No remote changes. Use -Prepare or -Push explicitly.')
        return
    publish(ROOT, args.repository, args.branch, args.message, args.push, args.author_name, args.author_email)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        raise SystemExit(str(error)) from None
