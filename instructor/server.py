"""Render 진입점. 플랫폼 PORT 또는 명시적 실행 인자를 사용합니다."""
import argparse
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from instructor.hosting import create_hosted_app
import uvicorn
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--host',default=os.environ.get('OML_BIND_HOST','0.0.0.0'))
    parser.add_argument('--port',type=int,default=int(os.environ.get('PORT','10000')))
    args=parser.parse_args()
    if not 1<=args.port<=65535: parser.error('Invalid port')
    uvicorn.run(create_hosted_app(),host=args.host,port=args.port,workers=1)
if __name__=='__main__': main()
