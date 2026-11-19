"""같은 실제 앱을 임시 빈 포트에서 실행해 사용자의 로그인·서비스 제어와 분리합니다."""
from pathlib import Path
import socket
import sys
import uvicorn

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from app import create_app

with socket.socket() as listener:
    listener.bind(('127.0.0.1',0))
    listener.listen(128)
    print('RESEARCH_QA_URL=http://127.0.0.1:'+str(listener.getsockname()[1]),flush=True)
    uvicorn.Server(uvicorn.Config(create_app(),log_level='error')).run(sockets=[listener])
