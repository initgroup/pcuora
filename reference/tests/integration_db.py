"""Run explicitly on the classroom sample schema: replaces feature rows with the sample and retrains."""
import io
import json
import sys
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'deploy'))
from oml.app import create_app

def main():
    app=create_app({'TESTING':True})
    checks=[]
    with app.test_client() as c:
        c.get('/')
        with c.session_transaction() as s:headers={'X-CSRF-Token':s['csrf']}
        def call(method,url,expected=200,**kwargs):
            response=getattr(c,method)(url,headers=headers,**kwargs)
            assert response.status_code==expected,(url,response.status_code,response.json)
            checks.append({'method':method,'path':url,'status':expected});return response.json
        status=call('get','/api/status');assert status['user']
        assert len(call('get','/api/data')['rows'])==120
        raw=(ROOT/'deploy/data/classification.csv').read_bytes()
        preview=call('post','/api/upload/validate',data={'file':(io.BytesIO(raw),'sample.csv')})
        assert preview['train']==97 and preview['test']==23
        # Malformed files must leave the currently loaded data version unchanged.
        call('post','/api/upload',expected=400,data={'file':(io.BytesIO(b'bad,csv\n1,2'),'bad.csv')})
        unchanged=call('get','/api/status');assert unchanged['state']['data_rev']==status['state']['data_rev']
        call('post','/api/upload',data={'file':(io.BytesIO(raw),'sample.csv')})
        call('post','/api/predict',expected=503,json={'order_count':6,'total_amount':180000,'recency_days':7,'category_count':3})
        trained=call('post','/api/train');assert trained['metrics']['n']==23
        predicted=call('post','/api/predict',json={'order_count':6,'total_amount':180000,'recency_days':7,'category_count':3})
        assert abs(sum(p['probability'] for p in predicted['predictions'])-1)<1e-8
        assert predicted['predictions'][0]['probability']>=predicted['predictions'][1]['probability']
        call('post','/api/predict',expected=400,json={'order_count':-1,'total_amount':0,'recency_days':7,'category_count':3})
        model=call('get','/api/model');assert model['nodes'] and model['settings']
        corr=call('get','/api/correlation');assert corr['stats']['n']==97 and len(corr['points'])==97
        rules=call('post','/api/rules/train');assert rules['rules']
        call('get','/api/rules')
        report=call('get','/api/export');assert report['dataset']['data_rev']==report['dataset']['model_rev']
        call('post','/api/sample')
        call('post','/api/train')
        final=call('get','/api/status');assert final['ready']
        report.update(checked_at=datetime.now(timezone(timedelta(hours=9))).isoformat(),
                      database_version=status['version'],checks=checks,
                      correlation=corr['stats'],prediction=predicted['predictions'],rule_count=len(rules['rules']))
        (ROOT/'runtime/api-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'PASS: {len(checks)} real DB API checks. Sample restored and classifier trained.')
        print(json.dumps(report['metrics'],ensure_ascii=False))

if __name__=='__main__':main()
