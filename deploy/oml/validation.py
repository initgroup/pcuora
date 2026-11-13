"""Validate the entire file before deleting or changing a single database row."""
import csv
import io
import math
from collections import Counter

COLUMNS=['customer_id','order_count','total_amount','recency_days','category_count','label','split']
LIMITS={'customer_id':(1,999999999),'order_count':(1,100),'total_amount':(0,10000000),
        'recency_days':(0,92),'category_count':(1,8)}

def numeric(value, name):
    try: n=float(value)
    except (TypeError,ValueError): raise ValueError(f'{name}: 숫자가 필요합니다.')
    lo,hi=LIMITS[name]
    if not math.isfinite(n) or n<lo or n>hi:
        raise ValueError(f'{name}: {lo}~{hi} 범위의 유한한 숫자를 입력하세요.')
    if name!='total_amount' and n!=int(n): raise ValueError(f'{name}: 정수여야 합니다.')
    return n if name=='total_amount' else int(n)

def validate_csv(raw):
    if len(raw)>2*1024*1024: raise ValueError('CSV는 2MB 이하여야 합니다.')
    try: text=raw.decode('utf-8-sig')
    except UnicodeDecodeError: raise ValueError('UTF-8 CSV로 저장하세요. Excel에서는 CSV UTF-8을 선택하세요.')
    reader=csv.DictReader(io.StringIO(text,newline=''))
    if reader.fieldnames!=COLUMNS: raise ValueError('CSV 헤더와 순서가 샘플과 일치해야 합니다: '+', '.join(COLUMNS))
    records=[]; seen=set()
    try:
        for line,row in enumerate(reader,2):
            if len(records)>=1000: raise ValueError('최대 1,000행까지 사용할 수 있습니다.')
            if None in row or any(v is None or not v.strip() for v in row.values()):
                raise ValueError(f'{line}행: 누락값 또는 열 개수 오류가 있습니다.')
            record={name:numeric(row[name].strip(),name) for name in LIMITS}
            if record['customer_id'] in seen: raise ValueError(f'{line}행: customer_id가 중복됩니다. 고객 단위 분리가 필요합니다.')
            seen.add(record['customer_id'])
            record['label']=row['label'].strip(); record['split']=row['split'].strip()
            if record['label'] not in ('REBUY','NO_REBUY'): raise ValueError(f'{line}행: 라벨은 REBUY 또는 NO_REBUY입니다.')
            if record['split'] not in ('TRAIN','TEST'): raise ValueError(f'{line}행: split은 TRAIN 또는 TEST입니다.')
            records.append(record)
    except csv.Error: raise ValueError('CSV 형식이 올바르지 않습니다.')
    if len(records)<30: raise ValueError('최소 30행이 필요합니다.')
    counts=Counter((r['split'],r['label']) for r in records)
    if any(counts[s,l]<3 for s in ('TRAIN','TEST') for l in ('REBUY','NO_REBUY')):
        raise ValueError('TRAIN과 TEST 각각에 두 라벨이 모두 최소 3행씩 필요합니다.')
    return records

def summary(records):
    counts=Counter((r['split'],r['label']) for r in records)
    return {'rows':len(records),'train':sum(r['split']=='TRAIN' for r in records),
            'test':sum(r['split']=='TEST' for r in records),'preview':records[:8],
            'groups':[{'split':s,'label':l,'n':counts[s,l]} for s in ('TRAIN','TEST') for l in ('REBUY','NO_REBUY')]}

def metrics(confusion, baseline_label):
    counts={(x['actual'],x['predicted']):x['n'] for x in confusion}
    tp=counts.get(('REBUY','REBUY'),0); tn=counts.get(('NO_REBUY','NO_REBUY'),0)
    fp=counts.get(('NO_REBUY','REBUY'),0); fn=counts.get(('REBUY','NO_REBUY'),0)
    total=tp+tn+fp+fn
    def div(a,b): return a/b if b else None
    return {'tp':tp,'tn':tn,'fp':fp,'fn':fn,'n':total,'accuracy':div(tp+tn,total),
            'precision':div(tp,tp+fp),'recall':div(tp,tp+fn),'f1':div(2*tp,2*tp+fp+fn),
            'baseline_label':baseline_label,
            'majority_baseline':div(tp+fn if baseline_label=='REBUY' else tn+fp,total)}
