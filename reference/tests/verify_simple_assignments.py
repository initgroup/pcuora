"""기존 명령 호환: 실제 과제 객체 대신 OML_QA_LAB_* 격리 검증을 수행합니다."""
from verify_oml_lab_db import verify

if __name__ == '__main__':
    verify()
