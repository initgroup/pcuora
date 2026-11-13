"""One short-lived connection per operation; no student passwords in browser state."""
from __future__ import annotations
import os
import re
import threading
import zipfile
from pathlib import Path
from contextlib import contextmanager
import oracledb
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
_init_lock = threading.Lock()
_driver_ready = False

def settings():
    relative = os.environ.get('OML_ENV_FILE', 'security/student.env')
    path = Path(relative)
    if not path.is_absolute():
        path = ROOT / path
    values = {k: v or '' for k, v in dotenv_values(path).items()}
    for key in ('DB_USER', 'DB_PASSWORD', 'DB_DSN', 'WALLET_PASSWORD', 'WALLET_ZIP', 'WALLET_DIR', 'ORACLE_CLIENT_LIB'):
        if key in os.environ:
            values[key] = os.environ[key]
    return values

def wallet_directory(cfg):
    if cfg.get('WALLET_DIR'):
        target = Path(cfg['WALLET_DIR'])
        if not target.is_absolute(): target = ROOT / target
        if cfg.get('ORACLE_CLIENT_LIB'):
            raise ValueError('WALLET_DIR 방식은 Thin 연결용입니다. ORACLE_CLIENT_LIB를 비우세요.')
        if not all((target / name).is_file() for name in ('tnsnames.ora', 'ewallet.pem')):
            raise ValueError('Thin Wallet 폴더에 tnsnames.ora와 ewallet.pem이 필요합니다.')
        return target
    archive = ROOT / cfg.get('WALLET_ZIP', 'security/Wallet_PCUORA.zip')
    if not archive.is_file():
        raise ValueError('security/Wallet_PCUORA.zip 파일이 없습니다. 강사에게 제공받은 Wallet을 확인하세요.')
    target = ROOT / 'runtime' / 'wallet'
    target.mkdir(parents=True, exist_ok=True)
    # Only the four Oracle files needed by our driver are extracted. Never extract arbitrary paths.
    with zipfile.ZipFile(archive) as source:
        for name in ('tnsnames.ora', 'ewallet.pem', 'cwallet.sso', 'sqlnet.ora'):
            data = source.read(name)
            if name == 'tnsnames.ora':
                text = data.decode('utf-8')
                text = re.sub(r'(?i)(retry_count\s*=\s*)\d+', r'\g<1>0', text)
                text = re.sub(r'(?i)(retry_delay\s*=\s*)\d+', r'\g<1>0', text)
                text = re.sub(r'(?i)\(description\s*=', '(description=(connect_timeout=12)(transport_connect_timeout=5)', text)
                data = text.encode('utf-8')
            path = target / name
            if not path.exists() or path.read_bytes() != data:
                path.write_bytes(data)
    # Thick mode must use this project's wallet rather than the path embedded in its original sqlnet.ora.
    (target / 'sqlnet.ora').write_text(
        'WALLET_LOCATION=(SOURCE=(METHOD=file)(METHOD_DATA=(DIRECTORY="' +
        target.as_posix() + '")))\nSSL_SERVER_DN_MATCH=yes\n', encoding='utf-8')
    return target

@contextmanager
def connection():
    global _driver_ready
    cfg = settings()
    if not cfg.get('DB_USER') or not cfg.get('DB_PASSWORD'):
        raise ValueError('DB 인증정보가 없습니다. 환경 설정 가이드에 따라 security/student.env를 작성하세요.')
    with _init_lock:
        wallet = wallet_directory(cfg)
        if cfg.get('ORACLE_CLIENT_LIB') and not _driver_ready:
            client = Path(cfg['ORACLE_CLIENT_LIB'])
            if not client.is_absolute(): client = ROOT / client
            oracledb.init_oracle_client(lib_dir=str(client), config_dir=str(wallet))
        _driver_ready = True
    args = dict(user=cfg['DB_USER'], password=cfg['DB_PASSWORD'], dsn=cfg.get('DB_DSN', 'pcuora_low'))
    if oracledb.is_thin_mode():
        if not cfg.get('WALLET_PASSWORD'):
            raise ValueError('Thin 연결에는 Wallet 다운로드 당시의 비밀번호가 필요합니다. WALLET_PASSWORD를 입력하세요.')
        args.update(config_dir=str(wallet), wallet_location=str(wallet),
                    wallet_password=cfg['WALLET_PASSWORD'], tcp_connect_timeout=12, retry_count=0)
    with oracledb.connect(**args) as conn:
        conn.call_timeout = 120000
        yield conn

def rows(cursor):
    names = [c[0].lower() for c in cursor.description or []]
    def clean(value):
        if isinstance(value, oracledb.LOB):
            return value.read()
        if hasattr(value, 'isoformat'):
            return value.isoformat()
        return value
    return [dict(zip(names, map(clean, row))) for row in cursor.fetchall()]

def result_set(conn, procedure, *args):
    with conn.cursor() as cur, conn.cursor() as out:
        cur.callproc('OML_LAB.' + procedure, [*args, out])
        return rows(out)

def safe_error(error):
    """Return actionable errors without DSNs, passwords, paths, or stack traces."""
    if isinstance(error, ValueError):
        return str(error)
    import re
    text = str(error)
    code = re.search(r'(ORA-\d{5}|DPY-\d{4}|DPI-\d{4})', text)
    code = code.group(0) if code else 'DB-CONNECTION'
    hints = {
        'ORA-01017': 'DB 사용자명과 비밀번호를 확인하세요.',
        'ORA-01031': '실습 객체 생성 권한이 부족합니다. 권한 가이드를 확인하세요.',
        'ORA-28000': '계정이 잠겨 있습니다. 강사에게 계정 상태 확인을 요청하세요.',
        'ORA-00942': '초기 테이블이 없습니다. db-init 스크립트를 먼저 실행하세요.',
        'ORA-06550': 'OML_LAB 패키지가 없거나 유효하지 않습니다. db-init 결과를 확인하세요.',
        'ORA-04063': '패키지 컴파일 오류가 있습니다. db-init을 실행해 진단하세요.',
        'ORA-20001': '학습·평가 데이터가 부족하거나 라벨 구성이 맞지 않습니다.',
        'ORA-20002': '현재 데이터로 분류모델을 먼저 학습하세요.',
        'ORA-20003': '연관규칙 모델을 먼저 학습하세요.',
        'ORA-20004': '입력값 또는 실습 데이터 범위를 확인하세요.',
        'ORA-12545': 'DB 네트워크와 Wallet의 접속 주소를 확인하세요.',
        'DPY-6005': 'DB에 연결할 수 없습니다. 네트워크·Wallet·서비스명을 확인하세요.',
        'DPI-1047': 'Oracle Client 경로/64비트를 확인하거나 Thin 연결로 설정하세요.',
    }
    return code + ': ' + hints.get(code, 'Oracle 접속·권한·Wallet 설정을 확인하세요. CLI 진단에서 오류 코드를 확인할 수 있습니다.')
