"""현재 안내·코딩도움말·공개 경로·DB 오브젝트 구조를 실제 소스와 대조합니다."""
import ast,json,re,sys
from html.parser import HTMLParser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]

class Page(HTMLParser):
    def __init__(self,html):super().__init__();self.ids=[];self.links=[];self.feed(html)
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if attrs.get('id'):self.ids.append(attrs['id'])
        if attrs.get('href'):self.links.append(attrs['href'])

def audit():
    from source_files import inventory,APP_FILES,STUDENT_SCRIPTS,CONFIG,PUBLIC
    from backend import coding_help,source_help,sql_files,mission_guide
    from fastapi.testclient import TestClient
    from app import create_app
    public=inventory(ROOT,audience='student')
    for name in APP_FILES:
        if name.endswith('.js'):
            assert not re.search(r'\b(?:alert|confirm|prompt)\s*\(',(ROOT/name).read_text(encoding='utf-8')),name+' browser-native dialog remains'
    assert all((ROOT/name).is_file() for name in PUBLIC),'Stale public source path'
    assert all(name in public for name in (*APP_FILES,*('scripts/'+n for n in STUDENT_SCRIPTS),*CONFIG))
    paths=['README.md','AGENTS.md','downloads/COM22417_과제설명및평가.html','reference/student/assignment-template-guide.html',*APP_FILES]
    stale=('sql/preprocess.sql','sql/train_model.sql','sql/evaluate_model.sql','sql/predict.sql','sql/internal/workspace.sql','02_package.sql','OML_BASIC_INPUT_')
    for name in paths:
        if Path(name).suffix not in ('.html','.py','.js','.md'):continue
        text=(ROOT/name).read_text(encoding='utf-8')
        assert '\ufffd' not in text, name+' encoding replacement character'
        assert not any(old in text for old in stale),name+' stale source reference'
    for key,(name,keyword) in source_help.SOURCES.items():
        text=(ROOT/name).read_text(encoding='utf-8')
        assert keyword in text,(key,keyword)
        item=source_help.read_source(key)
        assert keyword in text.splitlines()[item['line']-1],key+' line mismatch'
    checked=0
    for assignment in ('basic',):
        for operation in coding_help.OPERATIONS:
            if assignment!='basic' and operation in ('preview','prediction-preview','save','delete','initialize','recreate','confirm','status','columns','prediction-data','model-dictionary'):continue
            item=coding_help.describe(operation,assignment=assignment,user='AUDIT',use_yn='Y',split='TRAIN')
            for source in item['sources']:
                assert (ROOT/source['path']).is_file(),source['path']
                assert not source['keyword'] or source['keyword'] in source['content'],(operation,source['path'],source['keyword'])
            checked+=1
    with TestClient(create_app()) as client:
        for route in ('/basic','/mission','/creative'):
            response=client.get(route);assert response.status_code==200
            page=Page(response.text);assert len(page.ids)==len(set(page.ids)),route+' duplicate IDs'
            for target in page.links:
                if target.startswith('#') and target!='#':assert target[1:] in page.ids,(route,target)
        for route in ('/api/coding-help','/api/sources/schema'):
            assert client.get(route).status_code==401
        assert client.get('/security/student.env').status_code==404
        assert client.get('/instructor/python-web-lecture.html').status_code==401
    for name in ('downloads/COM22417_과제설명및평가.html','reference/student/assignment-template-guide.html'):
        html=(ROOT/name).read_text(encoding='utf-8');p=Page(html)
        assert len(p.ids)==len(set(p.ids)),name+' duplicate IDs'
        for target in p.links:
            if target.startswith('#') and target!='#':assert target[1:] in p.ids,(name,target)
        for command in re.findall(r'\.\\scripts\\([a-z-]+\.ps1)',html):assert (ROOT/'scripts'/command).is_file(),command
        assert '02_procedure.sql' in html and '코딩도움말' in html
    base='\n'.join((ROOT/'sql'/name).read_text(encoding='utf-8') for name in sql_files.definition_files())
    assert len(re.findall(r'^CREATE TABLE ',base,re.M))==3
    assert len(re.findall(r'^CREATE OR REPLACE PROCEDURE ',base,re.M))==1
    assert not re.search(r'^CREATE.*\b(?:PACKAGE|VIEW|FUNCTION)\b',base,re.M)
    for key in ('mission','creative'):
        for filename in ('01_tables.sql','02_procedure.sql'):
            custom=(ROOT/'sql/custom'/key/filename).read_text(encoding='utf-8')
            assert not re.sub(r'--[^\n]*','',custom).strip(), 'Custom starter must only describe the student contract'
    missions=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
    assert len(missions)==12
    for item in missions:
        for kind in ('training','prepared','prediction'):
            schema=mission_guide.table_sql(item,kind)
            assert 'CREATE TABLE '+schema['name'] in schema['sql']
            assert '{{' not in schema['sql']
        procedure=mission_guide.procedure_sql(item)
        assert 'CREATE OR REPLACE PROCEDURE OML_MISSION_RUN' in procedure
        assert 'RETURN_PCT' not in procedure and '{{' not in procedure
        for mode in ('RAW','CLEAN'):
            guide=mission_guide.generate(item,'prepare',mode)
            assert guide['procedure_sql']==procedure
            assert 'OML_MISSION_RUN(' in guide['script']
    result={'ok':True,'student_files':len(public),'coding_help_operations':checked,'source_locations':len(source_help.SOURCES),'stale_references':0,'core_tables':3,'core_procedures':1,'guides_and_routes':True,'generated_mission_guides':len(missions),'creative_query_starters':0}
    (ROOT/'runtime/content-audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result));return result

if __name__=='__main__':audit()
