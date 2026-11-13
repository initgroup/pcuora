"""Publish only the public inventory from an isolated checkout. Never force-push."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import sys
from urllib.parse import urlsplit
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from source_files import ROOT, inventory, manifest, safe_path

MARKER = 'OML_SOURCE_MANIFEST.json'
PROJECT = 'pcuora-oml-classroom'
DEFAULT_REPO = 'https://github.com/initgroup/pcuora.git'


def git(cwd, *args, check=True):
    result = subprocess.run(['git', *args], cwd=cwd, text=True, encoding='utf-8',
                            errors='replace', capture_output=True, timeout=180)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'Git failed.')
    return result


def publish(root, repository, branch, message, push=False, author_name='', author_email=''):
    files = inventory(root)
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
        if any(not safe_path(name) for name in previous):
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
    for name in previous - files.keys():
        (checkout / name).unlink(missing_ok=True)
    for name, raw in files.items():
        target = checkout / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    marker.write_text(json.dumps({'project': PROJECT, 'files': json.loads(manifest(files))}, indent=2) + '\n', encoding='utf-8')
    # Only the reviewed inventory and removals from its previous manifest are staged.
    paths = sorted(set(files) | previous | {MARKER})
    for offset in range(0, len(paths), 50):
        git(checkout, 'add', '-A', '--', *paths[offset:offset+50])
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
        files = inventory()
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
