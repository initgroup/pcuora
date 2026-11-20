"""API 격리 검사의 공유 저장소 대역. 실제 저장 모듈 검사는 별도로 수행합니다."""
from contextlib import contextmanager
from copy import deepcopy
from unittest.mock import patch
from backend import progress_store as store


@contextmanager
def memory_progress():
    records = {}
    def load(conn, key=store.PRACTICE):
        owner=str(conn.username).upper()
        revision,data=records.get((owner,key),(0,{'models':{}} if key==store.PRACTICE else {}))
        return store.Snapshot(deepcopy(data),key,revision,owner)
    def save(conn, state):
        key=(str(conn.username).upper(),state.key)
        if records.get(key,(0,None))[0]!=state.revision:
            raise ValueError('다른 환경에서 검증 기록이 변경되었습니다.')
        state.revision+=1;records[key]=(state.revision,deepcopy(dict(state)))
    with patch.object(store,'load',side_effect=load),patch.object(store,'save',side_effect=save),patch.object(store,'initialize'),patch.object(store,'migrate',return_value=[]):
        yield records
