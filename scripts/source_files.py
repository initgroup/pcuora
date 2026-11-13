"""Source inventories for backups, distribution and assignment submission."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = {
    'deploy': {'.py', '.html', '.css', '.js', '.svg', '.sql', '.csv'},
    'scripts': {'.py', '.ps1'},
    '.vscode': {'.json'},
    'reference/docs': {'.md'},
    'reference/tests': {'.py', '.js', '.ps1'},
    'reference/student': {'.md', '.html'},
    'submission': {'.md', '.html', '.pdf', '.png', '.jpg', '.jpeg', '.json', '.csv', '.txt'},
    'instructor': {'.py', '.ps1', '.sh', '.md'},
}
FILES = ('.gitignore', 'reference/requirements.in',
         'reference/requirements.lock',
         'security/student.env.example')
OPTIONAL_FILES = ('.gitattributes', 'README.md', 'AGENTS.md',
                  'reference/installers/README.md', 'start-here.html')


def safe_path(name):
    """Validate stored file paths before using a source manifest."""
    if not isinstance(name, str) or '\\' in name or ':' in name:
        return False
    path = Path(name)
    if path.is_absolute() or any(p in ('.', '..') for p in name.split('/')):
        return False
    if name in FILES or name in OPTIONAL_FILES:
        return True
    if any(p.startswith('.') or p == '__pycache__' for p in path.parts if p != '.vscode'):
        return False
    return any(name.startswith(d + '/') and path.suffix.lower() in extensions
               for d, extensions in DIRECTORIES.items())


STUDENT_SCRIPTS = {
    'common.ps1', 'setup.ps1', 'terminal-init.ps1', 'check-environment.ps1',
    'db-init.ps1', 'verify-db.ps1', 'start.ps1', 'stop.ps1', 'restart.ps1',
    'backup.ps1', 'compress.ps1', 'submit.ps1', 'source_backup.py',
    'package_submission.py', 'source_files.py', 'distribution_guard.py',
}


def inventory(root=ROOT, audience='all'):
    root = root.resolve()
    if audience not in ('all', 'student'): raise ValueError('Unknown source audience.')
    candidates = [root / name for name in FILES]
    candidates.extend(root / name for name in OPTIONAL_FILES if (root / name).is_file())
    for directory in DIRECTORIES:
        candidates.extend(p for p in (root / directory).rglob('*') if p.is_file())
    result = {}
    for path in sorted(set(candidates)):
        name = path.relative_to(root).as_posix()
        if audience == 'student':
            if path.suffix.lower() in ('.md', '.markdown'): continue
            if name == '.gitattributes': continue
            if name.startswith(('instructor/', 'reference/student/')): continue
            if name.startswith('scripts/') and path.name not in STUDENT_SCRIPTS: continue
        if not safe_path(name):
            continue
        if not path.is_file():
            raise ValueError('Missing required source: ' + name)
        if not path.resolve().is_relative_to(root):
            raise ValueError('Source points outside the project: ' + name)
        for part in (path, *path.parents):
            if part == root:
                break
            if part.is_symlink() or part.is_junction():
                raise ValueError('Linked source is not allowed: ' + name)
        result[name] = path.read_bytes()
    if audience == 'student':
        guide = root / 'reference/student/start-here.html'
        if guide.is_file():
            if not guide.resolve().is_relative_to(root) or guide.is_symlink():
                raise ValueError('Student start page points outside the project.')
            result['start-here.html'] = guide.read_bytes()
    from distribution_guard import validate_files
    validate_files(result, root)
    return result


def manifest(files):
    return json.dumps({name: hashlib.sha256(raw).hexdigest()
                       for name, raw in sorted(files.items())}, indent=2) + '\n'
