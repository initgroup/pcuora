"""Reject credentials in distributable bytes without ever printing secret values."""
from pathlib import Path
import re
from dotenv import dotenv_values


def secret_values(root):
    values = set()
    security = Path(root) / 'security'
    for path in security.glob('*'):
        if path.is_file() and '.env' in path.name.lower() and not path.name.endswith('.example'):
            for key, value in dotenv_values(path).items():
                if value and any(word in key.upper() for word in ('PASSWORD', 'SECRET', 'TOKEN')):
                    if len(value) < 8:
                        raise ValueError('A configured secret is too short for reliable distribution scanning. Review local settings.')
                    values.add(value.encode('utf-8'))
    return values


def validate_files(files, root, allow_wallet=False):
    secrets = secret_values(root)
    for name, raw in files.items():
        lower = name.lower()
        if lower == 'security/wallet_pcuora.zip' and allow_wallet:
            continue
        if ('.env' in Path(lower).name and not lower.endswith('.example')) or re.search(r'(^|/)(teacher|tearher)[^/]*', lower):
            raise ValueError('Private configuration file in distribution: ' + name)
        if Path(lower).suffix in {'.pem', '.sso', '.p12', '.key', '.log'} or 'wallet' in Path(lower).name:
            raise ValueError('Private key or runtime file in distribution: ' + name)
        if any(value in raw for value in secrets):
            raise ValueError('Configured secret detected in distribution: ' + name)
    example = files.get('security/student.env.example')
    if example is not None:
        import io
        cfg = dotenv_values(stream=io.StringIO(example.decode('utf-8')))
        if cfg.get('DB_USER') != 'STUDENT01' or cfg.get('DB_PASSWORD') or cfg.get('WALLET_PASSWORD'):
            raise ValueError('Student example must use STUDENT01 and blank passwords.')
