"""Hosting configuration for the same classroom application and Oracle examples."""
import hmac
import os
from flask import request, Response
from oml.app import create_app


def create_hosted_app(environment=None):
    env = os.environ if environment is None else environment
    mode = env.get('OML_SITE_MODE', 'lab')
    if mode not in ('lab', 'guide'):
        raise ValueError('OML_SITE_MODE must be lab or guide.')
    secret = env.get('SECRET_KEY', '')
    password = env.get('OML_ACCESS_PASSWORD', '')
    username = env.get('OML_ACCESS_USER', 'instructor')
    if len(secret) < 32:
        raise ValueError('Set SECRET_KEY to at least 32 random characters.')
    if mode == 'lab' and len(password) < 24:
        raise ValueError('Online lab requires OML_ACCESS_PASSWORD of at least 24 random characters.')
    hosts = {'localhost', '127.0.0.1', '[::1]'}
    for host in [env.get('RENDER_EXTERNAL_HOSTNAME', ''), *env.get('OML_ALLOWED_HOSTS', '').split(',')]:
        host = host.strip().lower()
        if host:
            if any(token in host for token in ('/', ':', '*', ' ')):
                raise ValueError('Use exact hostnames in OML_ALLOWED_HOSTS.')
            hosts.add(host)
    app = create_app({'SECRET_KEY': secret, 'SESSION_COOKIE_SECURE': True,
                      'ALLOWED_HOSTS': hosts, 'ENABLE_LAB': mode == 'lab',
                      'ALLOW_STUDENT_KIT': False})

    def authenticate():
        if request.path == '/healthz' or mode != 'lab':
            return None
        auth = request.authorization
        if (not auth or auth.type != 'basic'
            or not hmac.compare_digest((auth.username or '').encode(), username.encode())
            or not hmac.compare_digest((auth.password or '').encode(), password.encode())):
            return Response('Instructor authentication required.', 401,
                            {'WWW-Authenticate': 'Basic realm="OML Demo", charset="UTF-8"',
                             'Cache-Control': 'no-store'})
    app.before_request_funcs.setdefault(None, []).insert(0, authenticate)
    return app
