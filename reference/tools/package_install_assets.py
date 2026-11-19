"""오프라인 PC에만 별도 제공할 Python 3.12 x64 설치자료를 참조 폴더에 만듭니다."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import zipfile
ROOT=Path(__file__).resolve().parents[2]
destination=ROOT/'reference/installers/COM22417_설치자료_Python312_x64_20261120.zip'
if destination.exists(): raise SystemExit('기존 설치자료 ZIP을 덮어쓰지 않습니다.')
sources={}
installer=ROOT/'reference/installers/python-3.12.10-amd64.exe'
if not installer.is_file(): raise SystemExit('별도 Python 설치 원본이 없습니다.')
sources['installers/'+installer.name]=installer
for path in (ROOT/'reference/wheels-classifier-py312').glob('*.whl'):
    sources['wheels/'+path.name]=path
if len(sources)<20: raise SystemExit('새 분류 사이트의 오프라인 wheel 목록이 부족합니다.')
sources['requirements.lock']=ROOT/'reference/requirements.lock'
hashes={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in sources.items()}
destination.parent.mkdir(exist_ok=True)
descriptor,name=tempfile.mkstemp(prefix='.assets-',suffix='.tmp',dir=destination.parent)
os.close(descriptor); temporary=Path(name)
try:
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_STORED) as archive:
        for name,path in sorted(sources.items()): archive.write(path,name)
        archive.writestr('MANIFEST.sha256.json',json.dumps(hashes,indent=2))
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip(): raise ValueError('설치자료 ZIP 검증 실패')
    os.link(temporary,destination)
finally: temporary.unlink(missing_ok=True)
print(f'{destination.name}: {destination.stat().st_size/1024/1024:.1f} MiB')
