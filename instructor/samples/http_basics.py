"""강사용 HTTP 왕복 예제. Oracle·학생 명단·환경파일을 사용하지 않습니다."""
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

HERE = Path(__file__).resolve().parent
app = FastAPI(title='강사용 HTTP 원리 실습', docs_url=None, redoc_url=None, openapi_url=None)


class EchoInput(BaseModel):
    message: str = Field(min_length=1, max_length=100)


@app.get('/')
def home():
    return FileResponse(HERE / 'http_basics.html', media_type='text/html')


@app.get('/api/course')
def course():
    return {'course': 'Python 웹 연결 원리', 'database_used': False}


@app.post('/api/echo')
def echo(data: EchoInput):
    # HTTP 입력과 응답의 관계만 관찰합니다. 저장·학습·예측은 하지 않습니다.
    return {'received': data.message, 'length': len(data.message)}


def main():
    """자기 파일 위치에서 HTML을 찾고 OS의 빈 포트로 로컬 예제를 실행합니다."""
    import argparse
    import socket
    import uvicorn
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=0, help='생략하면 OS의 빈 포트 사용')
    args = parser.parse_args()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(('127.0.0.1', args.port))
        listener.listen(128)
        port = listener.getsockname()[1]
        print(f'INSTRUCTOR_SAMPLE_URL=http://127.0.0.1:{port}', flush=True)
        print('이 주소로 접속하세요. 종료: 이 터미널에서 Ctrl+C', flush=True)
        uvicorn.Server(uvicorn.Config(app, log_level='warning')).run(sockets=[listener])


if __name__ == '__main__':
    main()
