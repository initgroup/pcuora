"""Serve the classroom's actual examples online, with configurable binding."""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'deploy')]
from instructor.hosting import create_hosted_app
from waitress import serve


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default=os.environ.get('OML_BIND_HOST', '0.0.0.0'))
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', '10000')))
    parser.add_argument('--threads', type=int, default=int(os.environ.get('OML_THREADS', '4')))
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or not 1 <= args.threads <= 32:
        parser.error('Port must be 1..65535; threads must be 1..32.')
    serve(create_hosted_app(), host=args.host, port=args.port, threads=args.threads)


if __name__ == '__main__':
    main()
