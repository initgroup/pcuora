"""교재 발췌·줄·해시·독립 예제와 학생 배포 제외를 검증합니다."""
import hashlib
import io
import json
import re
import runpy
import sys
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]

def verify():
    from fastapi.testclient import TestClient
    from app import create_app
    from source_files import inventory
    text=(ROOT/'instructor/python-web-lecture.html').read_text(encoding='utf-8')
    manifest=json.loads(re.search(r'id="source-manifest">(.*?)</script>',text,re.S)[1])
    for key,item in manifest.items():
        actual='\n'.join((ROOT/item['path']).read_text(encoding='utf-8').splitlines()[item['line']-1:item['end_line']])
        assert actual==item['text'],key
        assert hashlib.sha256(actual.encode()).hexdigest()==item['sha256'],key
    assert '@@' not in text and 'OML_CLASSIFIER' not in text and '02_package.sql' not in text
    for name in ('python_basics','payload_walkthrough'):
        with redirect_stdout(io.StringIO()) as stream:runpy.run_path(str(ROOT/'instructor/samples'/f'{name}.py'),run_name='__main__')
        assert stream.getvalue()
    for audience in ('student','student-git','submission'):
        assert not any(n.startswith('instructor/') for n in inventory(ROOT,audience=audience))
    for path in (ROOT/'downloads').glob('*.zip'):
        with zipfile.ZipFile(path) as z:assert not any(n.startswith('instructor/') for n in z.namelist())
    with TestClient(create_app()) as client:assert client.get('/instructor/python-web-lecture.html').status_code==401
    report={'ok':True,'actual_source_excerpts':len(manifest),'source_lines_and_hashes_match':True,'student_distribution_excluded':True,'anonymous_http_status':401}
    (ROOT/'runtime/instructor-lecture-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))

if __name__=='__main__':verify()
