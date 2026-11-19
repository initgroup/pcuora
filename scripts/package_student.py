"""예시 명단 또는 본인 한 명의 명단만 담아 검증한 최신 ZIP으로 교체합니다."""
import argparse
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile
from source_files import ROOT,inventory,manifest,APP_FILES,STUDENT_SCRIPTS
from distribution_guard import validate_files

def student_roster(root, *, example=False):
    """로컬 명단 또는 가상 예시를 검증합니다. 배포 범위 선택은 build에서 수행합니다."""
    path=Path(root)/('security/students.example.json' if example else 'security/students.json')
    source=json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else []
    if not isinstance(source,list): raise ValueError('students.json은 JSON 배열이어야 합니다.')
    roster=[]; seen=set()
    for row in source:
        if not isinstance(row,dict) or any(key not in row for key in ('student_id','name','db_user')):
            raise ValueError('명단에 student_id, name, db_user가 필요합니다.')
        if not isinstance(row['student_id'],(str,int)) or isinstance(row['student_id'],bool):
            raise ValueError('명단의 학번 형식을 확인하세요.')
        student_id=str(row['student_id']).strip()
        if not student_id or student_id in seen or not isinstance(row['name'],str) or not row['name'].strip():
            raise ValueError('명단의 학번 중복·이름을 확인하세요.')
        if not isinstance(row['db_user'],str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,127}',row['db_user'].strip()):
            raise ValueError('명단의 db_user를 확인하세요.')
        person={key:row[key] for key in ('student_id','name','department','grade','db_user') if key in row}
        person['db_user']=person['db_user'].strip().upper()
        person.update(student_id=student_id,name=row['name'].strip())
        roster.append(person); seen.add(student_id)
    return roster

GUIDE_NAME='COM22417_과제설명및평가.html'


def student_environment(root):
    """배포용 환경설정은 공개 예시만 사용하며 개인 환경파일은 읽지 않습니다."""
    source=Path(root)/'security/student.env.example'
    if source.is_symlink() or not source.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError('Linked student environment is not allowed.')
    return source.read_bytes()


def build(root=ROOT,*,student_id='학번',output=None,replace=False):
    root=Path(root).resolve()
    if student_id!='학번' and not re.fullmatch(r'[A-Za-z0-9_-]{4,20}',student_id):
        raise ValueError('ZIP 파일명에 사용할 학번은 영문·숫자·밑줄·하이픈 4~20자리로 지정하세요.')
    files=inventory(root,audience='student')
    for name in (*APP_FILES,*('scripts/'+n for n in STUDENT_SCRIPTS),'.gitignore','.gitattributes','requirements.txt','security/student.env.example'):
        if name not in files: raise ValueError('필수 소스 누락: '+name)
    roster=student_roster(root,example=student_id=='학번')
    if student_id!='학번':
        matches=[r for r in roster if r['student_id']==student_id]
        if len(matches)!=1: raise ValueError('등록 명단에 학번이 정확히 한 번 있어야 합니다.')
        roster=matches
    files['security/students.json']=(json.dumps(roster,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    files['security/student.env']=student_environment(root)
    wallet=root/'security/Wallet_PCUORA.zip'
    if not wallet.is_file() or wallet.is_symlink() or not zipfile.is_zipfile(wallet): raise ValueError('원본 Wallet ZIP이 필요합니다.')
    files['security/Wallet_PCUORA.zip']=wallet.read_bytes()
    guide=root/'downloads'/GUIDE_NAME
    if not guide.is_file() or guide.is_symlink() or not guide.resolve().is_relative_to(root):
        raise ValueError('downloads/'+GUIDE_NAME+' 통합 안내 HTML 원본이 필요합니다.')
    files[GUIDE_NAME]=guide.read_bytes()
    if any(b'github.com/initgroup/pcuora' in raw.lower() for raw in files.values()):
        raise ValueError('학생 배포 자료에 강사용 GitHub 주소가 포함되어 있습니다.')
    validate_files(files,root,allow_wallet=True,allow_student_env=True)
    if any(Path(n).suffix.lower() in ('.md','.markdown') for n in files): raise ValueError('Markdown 금지')
    destination=Path(output or root/'downloads')
    if not destination.is_absolute(): destination=root/destination
    destination.mkdir(parents=True,exist_ok=True)
    target=destination/f'COM22417_{student_id}_20261120.zip'
    if target.exists() and not replace: raise FileExistsError('최신 ZIP 갱신은 compress.ps1을 사용하세요: '+target.name)
    descriptor,name=tempfile.mkstemp(prefix='.student-',suffix='.tmp',dir=destination)
    os.close(descriptor); temporary=Path(name)
    # 학생이 만든 학번 폴더에서 '여기에 풀기'를 사용합니다.
    # ZIP 안에는 포장용 최상위 폴더 없이 app.py·templates/ 등이 바로 들어갑니다.
    packed=files
    try:
        with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
            for name,raw in sorted(packed.items()):
                archive.writestr(name,raw,compress_type=zipfile.ZIP_STORED if name.endswith('Wallet_PCUORA.zip') else zipfile.ZIP_DEFLATED)
            archive.writestr('MANIFEST.sha256.json',manifest(packed))
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip(): raise ValueError('ZIP 검증 실패')
        # 같은 폴더에서 검증한 ZIP을 교체합니다. 압축·검증 실패 시 기존 ZIP은 남습니다.
        # 안내서도 ZIP에 넣은 바로 그 바이트를 따로 제공하므로 두 버전이 같습니다.
        # downloads의 통합 안내가 유일한 원본입니다. 기본 출력에서는 원본을 다시 쓰지 않습니다.
        if (destination/GUIDE_NAME).resolve()!=guide.resolve():
            fd,guide_temp=tempfile.mkstemp(prefix='.guide-',suffix='.tmp',dir=destination)
            try:
                with os.fdopen(fd,'wb') as stream: stream.write(files[GUIDE_NAME])
                os.replace(guide_temp,destination/GUIDE_NAME)
            finally: Path(guide_temp).unlink(missing_ok=True)
        if replace: os.replace(temporary,target)
        else: os.link(temporary,target)
    finally: temporary.unlink(missing_ok=True)
    print(f'ZIP: {target} ({target.stat().st_size/1024:.1f} KiB)')
    print(f'Guide: {destination/GUIDE_NAME} (also included in ZIP)')
    print('Extract here inside your student-ID folder; app.py is at the ZIP root.')
    return target

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--student-id',default='학번')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--replace',action='store_true')
    args=parser.parse_args()
    try: build(student_id=args.student_id,output=args.output,replace=args.replace)
    except (OSError,ValueError,KeyError) as error: raise SystemExit(str(error)) from None
