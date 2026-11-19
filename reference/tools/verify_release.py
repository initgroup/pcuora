"""완료 ZIP의 해시·분리·용량과 임시 폴더에서의 실행 구문을 검증합니다."""
import hashlib
import json
import re
from pathlib import Path
import tempfile
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from package_student import student_roster, GUIDE_NAME
from source_files import inventory
from distribution_guard import validate_files


def verify(archive=None):
    if archive is None:
        candidates=[path for path in (ROOT/'downloads').glob('COM22417_*_20261120.zip') if path.is_file()]
        archive=max(candidates,key=lambda path:path.stat().st_mtime_ns)
    archive = Path(archive)
    prefix = ''  # 학생이 만든 학번 폴더에 바로 풀리는 구조입니다.
    with zipfile.ZipFile(archive) as source:
        assert source.testzip() is None
        names = source.namelist()
        assert all(name in names for name in ('app.py','manage.py','templates/index.html','static/js/main.js'))
        assert all(name in names for name in ('scripts/deploy-github.ps1','scripts/git_publish.py','.gitignore','.gitattributes'))
        assert not any(b'github.com/initgroup/pcuora' in source.read(name).lower() for name in names)
        assert not any(name.startswith(archive.stem+'/') for name in names)
        hashes = json.loads(source.read(prefix + 'MANIFEST.sha256.json'))
        assert set(names) == set(hashes) | {prefix + 'MANIFEST.sha256.json'}
        for name, digest in hashes.items():
            assert hashlib.sha256(source.read(name)).hexdigest() == digest
        assert not any(n.lower().endswith(('.md', '.markdown', '.env', '.exe', '.whl', '.log')) for n in names if n!='security/student.env')
        assert not any({'instructor','.local','.venv','runtime','deploy'} & set(Path(n).parts) for n in names)
        assert [n for n in names if n.startswith('reference/')] == ['reference/student/assignment-template-guide.html']
        validate_files({name:source.read(name) for name in hashes},ROOT,allow_wallet=True,allow_student_env=True)
        assert not any('start-here' in n or 'environment-setup' in n for n in names)
        assert 'COM22417_개발환경설정.html' not in names
        assert GUIDE_NAME=='COM22417_과제설명및평가.html'
        assert source.read(prefix+GUIDE_NAME)==(ROOT/'downloads'/GUIDE_NAME).read_bytes()
        assert source.read(prefix+GUIDE_NAME)==(archive.parent/GUIDE_NAME).read_bytes()
        # ZIP 내부 해시뿐 아니라 지금 수정한 실행 소스가 그대로 포장되었는지도 확인합니다.
        current=inventory(ROOT,audience='student')
        assert all(name in names and source.read(name)==raw for name,raw in current.items()), 'ZIP differs from current public source'
        for task in ('mission','creative'):
            for filename in ('01_tables.sql','02_procedure.sql'):
                starter=source.read('sql/custom/'+task+'/'+filename).decode('utf-8')
                assert not re.sub(r'--[^\n]*','',starter).strip(), 'Executable stock SQL in custom starter'
                assert ('OML_'+task.upper()+'_') in starter
        mission_template=source.read('sql/custom/mission/guide_procedure.sql').decode('utf-8')
        assert 'CREATE OR REPLACE PROCEDURE OML_MISSION_RUN' in mission_template
        assert '{{' in mission_template
        assert 'backend/mission_guide.py' in names
        guide_html=source.read(GUIDE_NAME).decode('utf-8')
        assert [int(n) for n in re.findall(r'<b>(\d+)<span>점</span></b>',guide_html)]==[50,30,20]
        rubric=re.findall(r'<tr><th>(기본|미션|창의)(?:과제)?<strong>(\d+)점</strong></th><td>.*?</td><td>(.*?)</td>',guide_html,re.S)
        assert [(name,int(total)) for name,total,_ in rubric]==[('기본',50),('미션',30),('창의',20)]
        expected_points={'기본':[40,5,3,2],'미션':[5,20,5],'창의':[10,10]}
        for name,total,items in rubric:
            points=[int(n) for n in re.findall(r'\d+',re.sub(r'<[^>]+>','',items))]
            assert points==expected_points[name] and sum(points)==int(total)
        assert source.read(prefix + 'security/Wallet_PCUORA.zip') == (ROOT / 'security/Wallet_PCUORA.zip').read_bytes()
        student_id=archive.stem[len('COM22417_'):-len('_20261120')]
        expected=student_roster(ROOT,example=True) if student_id=='학번' else [r for r in student_roster(ROOT) if r['student_id']==student_id]
        assert json.loads(source.read(prefix + 'security/students.json')) == expected
        # 12 topics need two extra CSV pairs. Bound code and each topic separately; retain the 1 MB total cap.
        campus=source.getinfo('static/images/paichai-campus-night.jpg')
        assert campus.file_size < 500000
        topics=json.loads(source.read('data/catalog.json'))
        csv_bytes=0
        for topic in topics:
            pair_bytes=sum(source.getinfo('data/examples/'+topic[field]).compress_size for field in ('filename','prediction_filename'))
            assert pair_bytes < 15000, 'Mission CSV pair exceeds 15 KB: '+topic['key']
            csv_bytes+=pair_bytes
        assert archive.stat().st_size-campus.compress_size-csv_bytes < 400000, 'Application/metadata package exceeds 400 KB'
        assert archive.stat().st_size < 1000000
        intro=source.read('templates/login-gate.html').decode('utf-8')
        assert '/static/images/paichai-campus-night.jpg' in intro
        assert '2026년' in intro and '배재대학교' in intro and '목원대학교' not in intro
        assert '/static/css/intro.css' in source.read('templates/index.html').decode('utf-8')

        html = source.read(prefix + 'templates/index.html').decode('utf-8')
        navigation=source.read('backend/assignment_templates.py').decode('utf-8')
        assert all(path in navigation for path in ('/basic','/mission','/creative'))
        assert all('data-basic-' + key in source.read('templates/pages/basic.html').decode('utf-8') for key in ('panel','tab'))
        assert '/static/css/style.css' in html and '/static/js/main.js' in html
        assert 'model-comparison' in source.read('templates/pages/models.html').decode('utf-8')
        assert 'prediction-preview-box' in source.read('templates/pages/predictions.html').decode('utf-8')
        assert 'DBMS_DATA_MINING.CREATE_MODEL2(' in source.read('sql/classifier.sql').decode('utf-8')
        assert 'sql/procedures.sql' not in names
        for name,raw in inventory(audience='student').items():
            assert source.read(prefix+name)==raw, 'Stale release source: '+name
        assert source.read(prefix+'requirements.txt') == (ROOT/'reference/requirements.lock').read_bytes()
        assert '--size:16px' in source.read(prefix+'static/css/style.css').decode('utf-8')

        # 검증용 소스 복사본을 남기지 않습니다.
        with tempfile.TemporaryDirectory(prefix='release-check-', dir=ROOT / 'runtime') as temporary:
            destination = Path(temporary)
            for name in names:
                assert (destination / name).resolve().is_relative_to(destination.resolve())
            source.extractall(destination)
            extracted = destination
            for name in ('manage.py', 'app.py', 'backend/service.py', 'backend/identity.py'):
                compile((extracted / name).read_text(encoding='utf-8'), str(extracted / name), 'exec')

    record = {
        'archive': archive.name, 'bytes': archive.stat().st_size, 'files': len(names),
        'checks': ['public allowlist', 'current source byte identity', 'separate campus/application/per-mission CSV budgets and 1 MB total cap', 'selected mission generator and contract-only custom starters', '50/30/20 guide totals', 'example or own-only roster', 'SHA256', 'Wallet byte identity', 'no secrets/Markdown/installers',
                   'flat ZIP root for extract here', 'included and separate HTML identical', 'relocated syntax', 'temporary files removed'],
    }
    (ROOT / 'runtime/release-verification.json').write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(record, ensure_ascii=False))
    return record


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('archive',nargs='?',type=Path)
    verify(parser.parse_args().archive)
