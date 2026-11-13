"""Timestamped source snapshots; never includes Wallet, credentials or DB rows."""
import argparse
from datetime import datetime
import zipfile
from source_files import ROOT, inventory, manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('kind', choices=('folder', 'zip'))
    args = parser.parse_args()
    files = inventory()
    files['MANIFEST.sha256.json'] = manifest(files).encode('utf-8')
    destination = ROOT / 'backups'
    destination.mkdir(exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    output = destination / ('oml-source-' + stamp)
    if args.kind == 'folder':
        output.mkdir()
        for name, raw in files.items():
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
    else:
        output = output.with_suffix('.zip')
        with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED) as archive:
            for name, raw in files.items():
                archive.writestr(name, raw)
        with zipfile.ZipFile(output) as archive:
            if archive.testzip() is not None:
                raise RuntimeError('Archive verification failed.')
    print('Created: ' + str(output))
    print(f'{len(files)-1} source files + SHA256 manifest; no Wallet or personal settings.')


if __name__ == '__main__':
    main()
