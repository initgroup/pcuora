"""실제 학생 ZIP을 한글·공백 폴더에 풀어 새 가상환경과 서비스 명령을 확인합니다.

검증용 가상환경은 별도로 만들며 기존 서비스·개인 설정·DB 객체는 변경하지 않습니다.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def verify(archive):
    archive = Path(archive).resolve()
    runtime = (ROOT / 'runtime').resolve()
    checks = []
    environment = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}
    # TemporaryDirectory의 재귀 정리 대상이 이 프로젝트의 runtime 안인지 먼저 확인합니다.
    with tempfile.TemporaryDirectory(prefix='portable-', dir=runtime) as temporary:
        sandbox = Path(temporary).resolve()
        assert sandbox.is_relative_to(runtime)
        destination = sandbox / '학생 실습 [이동 폴더]' / '20260001'
        destination.mkdir(parents=True)  # 학생이 먼저 학번 폴더를 만든 뒤 '여기에 풀기'를 수행합니다.
        with zipfile.ZipFile(archive) as source:
            assert source.testzip() is None
            assert 'app.py' in source.namelist()
            assert not any(name.startswith(archive.stem+'/') for name in source.namelist())
            assert all((destination / name).resolve().is_relative_to(destination.resolve())
                       for name in source.namelist())
            source.extractall(destination)
        project = destination
        assert (project/'app.py').is_file() and (project/'templates/index.html').is_file()
        checks.append('extract here directly into a pre-created student-ID folder')
        python = project / '.venv/Scripts/python.exe'
        command_number = 0

        def run(arguments, expected=0):
            nonlocal command_number
            command_number += 1
            # 백그라운드 서버가 상속한 PIPE 때문에 수집이 멈추지 않도록 파일로 기록합니다.
            log = sandbox / f'command-{command_number}.log'
            with log.open('w', encoding='utf-8') as stream:
                result = subprocess.run(arguments, cwd=ROOT / 'reference', env=environment,
                                        stdin=subprocess.DEVNULL, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=180)
            output = log.read_text(encoding='utf-8', errors='replace')
            if result.returncode != expected:
                raise AssertionError(output)
            return output

        def script(name, *arguments, expected=0):
            return run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                        str(project / 'scripts' / name), *map(str, arguments)], expected)

        # 다른 작업 폴더에서 상대 AssetsPath를 넘겨도 프로젝트를 기준으로 해석해야 합니다.
        wheels = os.path.relpath(ROOT / 'reference/wheels-classifier-py312', project)
        setup_check = sandbox / 'check-setup.ps1'
        setup_check.write_text('''param($Setup,$BasePython,$Assets,$Venv)
$ErrorActionPreference='Stop'
$previousPath=$env:PATH
$userPath=[Environment]::GetEnvironmentVariable('PATH','User')
$machinePath=[Environment]::GetEnvironmentVariable('PATH','Machine')
& $Setup -PythonExe $BasePython -AssetsPath $Assets
if ($env:VIRTUAL_ENV -ne $Venv) { throw 'Setup did not activate the current terminal.' }
if ((Get-Command python).Source -ne (Join-Path $Venv 'Scripts/python.exe')) { throw 'Setup selected another Python.' }
python -c "import sys; assert sys.prefix != sys.base_prefix"
if ($LASTEXITCODE -ne 0) { throw 'Setup did not activate a real venv.' }
deactivate
if ($env:PATH -ne $previousPath) { throw 'Deactivate did not restore terminal PATH.' }
if ([Environment]::GetEnvironmentVariable('PATH','User') -ne $userPath) { throw 'User PATH changed.' }
if ([Environment]::GetEnvironmentVariable('PATH','Machine') -ne $machinePath) { throw 'Machine PATH changed.' }
''', encoding='utf-8')
        run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
             str(setup_check), str(project/'scripts/setup.ps1'), sys._base_executable, wheels, str(project/'.venv')])
        checks.append('fresh venv and offline setup from foreign working directory')
        checks.append('setup activates current terminal; deactivate restores PATH; user/machine PATH unchanged')
        script('terminal-init.ps1')
        activation_check = sandbox / 'check-activation.ps1'
        activation_check.write_text('''param($Entry,$Venv)
$ErrorActionPreference='Stop'
$previousPath=$env:PATH
& $Entry
if ($env:VIRTUAL_ENV -ne $Venv) { throw 'Wrong VIRTUAL_ENV.' }
if ((Get-Command python).Source -ne (Join-Path $Venv 'Scripts/python.exe')) { throw 'Wrong active Python.' }
deactivate
if ($env:PATH -ne $previousPath) { throw 'PATH was not restored.' }
& $Entry
& $Entry
deactivate
if ($env:PATH -ne $previousPath) { throw 'Repeated activation changed PATH.' }
''', encoding='utf-8')
        run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
             str(activation_check), str(project/'scripts/terminal-init.ps1'), str(project/'.venv')])
        script('check-environment.ps1')
        checks.append('terminal activation and environment check')

        probe = '''import os,sys
from pathlib import Path
root=Path(sys.argv[1]); sys.path.insert(0,str(root))
os.environ['OML_ENV_FILE']='security/student.env'
os.environ['OML_ROSTER_FILE']='security/students.json'
from backend import db,identity,sql_files
from backend.validation import parse_csv
assert db.ROOT==root
assert identity.ROSTER==root/'security/students.json'
assert identity.roster()
cfg=db.settings(); assert cfg['WALLET_ZIP']=='security/Wallet_PCUORA.zip'
wallet=db.wallet_directory(cfg)
assert wallet==root/'runtime/wallet'
assert wallet.as_posix() in (wallet/'sqlnet.ora').read_text(encoding='utf-8')
assert (sql_files.SQL_ROOT/'schema.sql').is_file()
assert parse_csv((root/'data/classification.csv').read_bytes())
print('Wallet, roster, SQL, CSV and env resolve against relocated source root.')
'''
        run([str(python), '-c', probe, str(project)])
        checks.append('relative env/roster and relocated Wallet/SQL/CSV')
        # 비어 있는 초기 인증정보로는 DB에 접속하지 않고 중단하는지만 확인합니다.
        message = script('db-init.ps1', expected=1)
        assert 'Connection check failed.' in message
        checks.append('DB initialization resolves files and stops before authentication')

        with socket.socket() as port_probe:
            port_probe.bind(('127.0.0.1', 0))
            port = port_probe.getsockname()[1]
        address = f'http://127.0.0.1:{port}'
        try:
            # 다른 프로그램이 포트를 사용하는 상태에서도 배포본은 빈 포트로 시작해야 합니다.
            with socket.socket() as occupied:
                occupied.bind(('127.0.0.1', port))
                occupied.listen()
                output=script('start.ps1', '-Port', port)
                assert 'Using free port' in output
                state_path=project/'runtime/service.json'
                selected=json.loads(state_path.read_text(encoding='utf-8-sig'))
                assert selected['port']!=port
                assert occupied.getsockopt(socket.SOL_SOCKET,socket.SO_ACCEPTCONN)==1
                port=selected['port']
                address=f'http://127.0.0.1:{port}'
                assert 'Already running:' in script('start.ps1')
                with urllib.request.urlopen(address+'/healthz',timeout=10) as response:
                    assert response.status==200
            checks.append('occupied port selects free port; existing listener survives; plain start reuses actual port')
            assert 'Already running:' in script('start.ps1', '-Port', port)
            for path in ('/healthz', '/', '/data', '/models', '/predictions',
                         '/static/css/style.css', '/static/css/studio.css',
                         '/static/js/main.js', '/api/session'):
                with urllib.request.urlopen(address + path, timeout=10) as response:
                    assert response.status == 200
            state_path = project / 'runtime/service.json'
            before = json.loads(state_path.read_text(encoding='utf-8-sig'))
            assert Path(before['root']) == project
            script('restart.ps1')
            after = json.loads(state_path.read_text(encoding='utf-8-sig'))
            assert after['pid'] != before['pid'] and after['port'] == port
            checks.append('start, duplicate start, four pages, assets and restart')
        finally:
            script('stop.ps1')
        assert not state_path.exists()
        assert 'No tracked server.' in script('stop.ps1')
        checks.append('stop and repeated stop')
        # 패키지 설치가 빠진 환경의 시작 오류도 해당 프로젝트 로그에 남아야 합니다.
        run([str(python), '-S', str(project/'manage.py'), 'serve', '--log-files'], expected=1)
        assert 'ModuleNotFoundError' in (project/'runtime/server.err.log').read_text(encoding='utf-8')
        checks.append('startup dependency failure written to relocated log')

        # 제출 수집만 확인하는 최소 PPTX 구조이며 실제 학생 발표자료를 만들지 않습니다.
        submission = project / 'submission'
        submission.mkdir()
        (submission / 'report.txt').write_text('학번: 20260001\n경로 이동 검증 기록', encoding='utf-8')
        with zipfile.ZipFile(submission / 'presentation.pptx', 'w') as deck:
            deck.writestr('[Content_Types].xml', '<Types/>')
            deck.writestr('ppt/presentation.xml', '<presentation/>')
            deck.writestr('ppt/slides/slide1.xml', '<slide>Path verification fixture</slide>')
        script('submit.ps1', '-StudentId', '20260001')
        output = project / 'downloads/COM22417_2026H2_20260001.zip'
        with zipfile.ZipFile(output) as submitted:
            assert submitted.testzip() is None
            assert any(name.endswith('/source/sql/classifier.sql') for name in submitted.namelist())
            assert any(name.endswith('/report/presentation.pptx') for name in submitted.namelist())
            assert not any(name.lower().endswith('.env') for name in submitted.namelist())
        checks.append('submission ZIP created under relocated project')

    record = {'archive': str(archive.relative_to(ROOT)), 'checks': checks,
              'temporary_files_removed': not sandbox.exists(), 'db_objects_modified': False}
    (runtime / 'portability-verification.json').write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(record, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    verify(parser.parse_args().archive)
