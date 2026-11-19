"""강사용 교재 생성: 현재 소스의 실제 줄·해시를 발췌합니다. DB를 변경하지 않습니다."""
import ast
import hashlib
import html
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];HERE=Path(__file__).resolve().parent

def source(path,function=None):
    text=(ROOT/path).read_text(encoding='utf-8');lines=text.splitlines();first,last=1,len(lines)
    if function:
        node=next(n for n in ast.walk(ast.parse(text)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==function)
        first=min([node.lineno,*[d.lineno for d in node.decorator_list]]);last=node.end_lineno
    content='\n'.join(lines[first-1:last])
    return {'path':path,'line':first,'end_line':last,'text':content,'sha256':hashlib.sha256(content.encode()).hexdigest()}

def build():
    specs={
      'python-example':('instructor/samples/python_basics.py',None),
      'http-example':('instructor/samples/http_basics.py',None),
      'csv-example':('instructor/samples/payload_walkthrough.py',None),
      'page':('app.py','page'),
      'query-api':('app.py','data'),
      'query':('backend/service.py','get_data'),
      'query-sql':('sql/queries/training_rows.sql',None),
      'table':('sql/schema.sql',None),
      'prediction-table':('sql/prediction_table.sql',None),
      'csv':('backend/validation.py','parse_csv'),
      'load':('backend/service.py','load_csv'),
      'insert':('sql/queries/insert_training.sql',None),
      'call':('backend/service.py','run_model'),
      'procedure':('sql/classifier.sql',None),
      'rows':('backend/db.py','rows'),
      'trace':('backend/sql_trace.py','rendered'),
      'readiness':('backend/assignment_templates.py','readiness'),
      'custom':('backend/assignment_templates.py','load_custom'),
      'confirm':('backend/service.py','confirm_model'),
      'auth':('app.py','authorized'),
    }
    snippets={key:source(*spec) for key,spec in specs.items()}
    template=(HERE/'lecture/template.html').read_text(encoding='utf-8')
    for key,item in snippets.items():
        label=f"{item['path']}:{item['line']}–{item['end_line']}"
        code='<figure class="source" data-snippet="'+key+'"><figcaption><a data-lecture-source="'+key+'" href="../'+html.escape(item['path'])+'">'+html.escape(label)+'</a><button type="button" data-copy>코드 복사</button></figcaption><pre><code>'+html.escape(item['text'])+'</code></pre></figure>'
        template=template.replace('@@'+key+'@@',code)
    template=template.replace('@@CSS@@',(HERE/'lecture/lecture.css').read_text(encoding='utf-8'))
    template=template.replace('@@JS@@',(HERE/'lecture/lecture.js').read_text(encoding='utf-8'))
    template=template.replace('@@MANIFEST@@',json.dumps(snippets,ensure_ascii=False).replace('<','\\u003c'))
    assert '@@' not in template
    (HERE/'python-web-lecture.html').write_text(template,encoding='utf-8')
    print(f'Lecture regenerated: {len(snippets)} current source excerpts. No DB changes.')
    return snippets

if __name__=='__main__':build()
