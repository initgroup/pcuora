"""운영 환경의 세션 쿠키·허용 호스트를 설정합니다. 로그인은 메인 앱에서 처리합니다."""
import os
from app import create_app


def create_hosted_app(environment=None):
    env = os.environ if environment is None else environment
    secret = env.get('SECRET_KEY', '')
    if len(secret) < 32:
        raise ValueError('Configure SECRET_KEY (32+).')
    hosts = ['localhost', '127.0.0.1', '[::1]']
    for value in [env.get('RENDER_EXTERNAL_HOSTNAME', ''), *env.get('OML_ALLOWED_HOSTS', '').split(',')]:
        value = value.strip().lower()
        if value:
            if any(c in value for c in '/:* '):
                raise ValueError('Use exact allowed hostnames.')
            hosts.append(value)
    return create_app({'SECRET_KEY': secret, 'SECURE_COOKIE': True, 'ALLOWED_HOSTS': hosts})
