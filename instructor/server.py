"""기존 강사 진입점도 학생과 같은 운영 실행 코드를 사용합니다."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.hosting import main

if __name__ == '__main__':
    main()
