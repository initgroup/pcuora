"""강사 시연 전용 인증 계층. 학생 앱과 동일한 FastAPI 앱을 감쌉니다."""
import base64
import binascii
import hmac
import os
from fastapi.responses import Response
from app import create_app

def create_hosted_app(environment=None):
    env=os.environ if environment is None else environment
    secret=env.get('SECRET_KEY',''); password=env.get('OML_ACCESS_PASSWORD','')
    username=env.get('OML_ACCESS_USER','instructor')
    if len(secret)<32 or len(password)<24: raise ValueError('Configure SECRET_KEY (32+) and OML_ACCESS_PASSWORD (24+).')
    hosts=['localhost','127.0.0.1','[::1]']
    for value in [env.get('RENDER_EXTERNAL_HOSTNAME',''),*env.get('OML_ALLOWED_HOSTS','').split(',')]:
        value=value.strip().lower()
        if value:
            if any(c in value for c in '/:* '): raise ValueError('Use exact allowed hostnames.')
            hosts.append(value)
    app=create_app({'SECRET_KEY':secret,'SECURE_COOKIE':True,'ALLOWED_HOSTS':hosts})
    @app.middleware('http')
    async def authenticate(request,next_call):
        if request.url.path=='/healthz': return await next_call(request)
        valid=False
        try:
            scheme,token=request.headers.get('Authorization','').split(' ',1)
            user,provided=base64.b64decode(token,validate=True).decode('utf-8').split(':',1)
            valid=scheme.lower()=='basic' and hmac.compare_digest(user.encode(),username.encode()) and hmac.compare_digest(provided.encode(),password.encode())
        except (ValueError,UnicodeError,binascii.Error): pass
        if not valid: return Response('Instructor authentication required.',401,headers={'WWW-Authenticate':'Basic realm="OML Studio", charset="UTF-8"','Cache-Control':'no-store'})
        return await next_call(request)
    return app
