"""Student kit: public source, offline assets, explicit Wallet; never personal .env."""
import zipfile
import sys
from source_files import ROOT, inventory, manifest
from distribution_guard import validate_files
sys.path.insert(0, str(ROOT / 'deploy'))
from oml.student_archives import reserve_student_archive

INSTALLERS = ('python-3.12.10-amd64.exe', 'instantclient-basiclite-windows.x64-23.26.4.0.0.zip')


def build(root=ROOT, *, now=None):
    if not (root / 'reference/student/start-here.html').is_file():
        raise ValueError('Student start page is missing: start-here.html')
    files = inventory(root, audience='student')
    assets = [root / 'security/Wallet_PCUORA.zip']
    assets += [root / 'reference/installers' / name for name in INSTALLERS]
    assets += sorted((root / 'reference/wheels').glob('*.whl'))
    if not any(path.suffix == '.whl' for path in assets):
        raise ValueError('Offline wheels missing. Prepare reference/wheels before creating the student kit.')
    for path in assets:
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('Missing or linked classroom asset: ' + path.name)
        files[path.relative_to(root).as_posix()] = path.read_bytes()
    validate_files(files, root, allow_wallet=True)
    with reserve_student_archive(root / 'downloads', now=now) as output:
        created = False
        try:
            # Exclusive creation plus the reservation prevents overwrites and partial downloads.
            with output.open('xb') as stream:
                created = True
                with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
                    for name, raw in sorted(files.items()): archive.writestr(name, raw)
                    archive.writestr('MANIFEST.sha256.json', manifest(files))
            with zipfile.ZipFile(output) as archive:
                if archive.testzip(): raise ValueError('Student ZIP integrity check failed.')
                if any(name.lower().endswith('.env') for name in archive.namelist()):
                    raise ValueError('Personal settings found in student ZIP.')
                if any(name.lower().endswith(('.md', '.markdown')) for name in archive.namelist()):
                    raise ValueError('Markdown files are not allowed in the student ZIP.')
        except BaseException:
            if created: output.unlink(missing_ok=True)
            raise
    print(f'Created {output.name}: {len(files)} files, {output.stat().st_size/1024/1024:.1f} MB')
    print('Student profile: STUDENT01 template, blank passwords; setup creates the personal student.env.')
    print('Path: ' + str(output))
    return output


if __name__ == '__main__':
    try: build()
    except ValueError as error: raise SystemExit(str(error)) from None
