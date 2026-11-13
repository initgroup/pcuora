from __future__ import annotations
import csv
import hmac
import io
import secrets
import threading
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, send_file, abort
from werkzeug.exceptions import HTTPException
from .db import ROOT, connection, rows, result_set, safe_error, settings
from .validation import validate_csv, summary, numeric, metrics, COLUMNS
from .lessons import LESSONS
from .assignment import RUBRIC, IDEAS
from .source_guide import SOURCE_CATALOG, PROCEDURES
from .student_archives import latest_student_archive

_operation=threading.Lock()
SOURCE_FILES={key: item['path'] for key,item in SOURCE_CATALOG.items()}

def evaluate(conn):
    confusion=result_set(conn,'EVALUATE_MODEL')
    with conn.cursor() as cur:
        cur.execute("SELECT LABEL FROM OML_FEATURES WHERE SPLIT='TRAIN' GROUP BY LABEL ORDER BY COUNT(*) DESC,LABEL FETCH FIRST 1 ROW ONLY")
        majority=cur.fetchone()[0]
    return confusion,metrics(confusion,majority)

def create_app(test_config=None):
    app=Flask(__name__)
    app.config.update(SECRET_KEY=secrets.token_hex(32),MAX_CONTENT_LENGTH=2*1024*1024+65536,
                      SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Strict',
                      ALLOWED_HOSTS={'localhost','127.0.0.1','[::1]'},ENABLE_LAB=True,ALLOW_STUDENT_KIT=True)
    if test_config: app.config.update(test_config)
    mode = 'lab' if app.config['ENABLE_LAB'] else 'guide'

    @app.before_request
    def protect():
        host=request.host.rsplit(':',1)[0].lower() if ':' in request.host and not request.host.endswith(']') else request.host.lower()
        if host not in app.config['ALLOWED_HOSTS'] and not app.testing: abort(400)
        if request.path == '/healthz': return None
        if not app.config['ALLOW_STUDENT_KIT'] and request.path == '/download/student.zip':
            return jsonify(error='학생 ZIP은 강사가 안내한 수업 배포 경로에서 받으세요.'),403
        if mode == 'guide' and request.path.startswith('/api/') and not request.path.startswith('/api/source/'):
            return jsonify(error='공개 교재 모드입니다. DB 실습은 자기 PC와 STUDENT 계정에서 실행하세요.'),403
        if 'csrf' not in session: session['csrf']=secrets.token_hex(24)
        if request.method=='POST':
            token=request.headers.get('X-CSRF-Token','')
            if not hmac.compare_digest(token,session['csrf']):
                return jsonify(error='페이지를 새로고침한 뒤 다시 시도하세요.'),403

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'self'"
        if request.path.startswith(('/api/','/download/')): response.headers['Cache-Control']='no-store'
        return response

    @app.context_processor
    def common(): return dict(lessons=LESSONS,csrf=session.get('csrf',''),site_mode=mode,remote_site=not app.config['ALLOW_STUDENT_KIT'])

    @app.get('/healthz')
    def health(): return jsonify(status='ok')

    @app.get('/')
    def home(): return render_template('home.html',active='home',title='학습 대시보드')

    @app.get('/lesson/<slug>')
    def lesson(slug):
        if slug not in LESSONS: abort(404)
        return render_template('lesson.html',active=slug,title=LESSONS[slug]['title'],lesson=LESSONS[slug],slug=slug,
                               assignment_rubric=RUBRIC,assignment_ideas=IDEAS)

    @app.get('/lab')
    def lab(): return render_template('lab_remote_guide.html' if mode=='guide' else 'lab.html',active='lab',title='마당서점 실습실')

    @app.get('/sources')
    def sources(): return render_template('sources.html',active='sources',title='소스 구조와 수정 위치',
                                          source_catalog=SOURCE_CATALOG,procedures=PROCEDURES)

    def db_api(fn):
        @wraps(fn)
        def wrapper(*args,**kwargs):
            if not _operation.acquire(blocking=False):
                return jsonify(error='현재 DB 작업이 진행 중입니다. 완료 후 다시 시도하세요.'),409
            try:
                with connection() as conn: return fn(conn,*args,**kwargs)
            except Exception as e:
                if isinstance(e,HTTPException): raise
                return jsonify(error=safe_error(e)),400 if isinstance(e,ValueError) else 503
            finally: _operation.release()
        return wrapper

    @app.get('/api/status')
    @db_api
    def status(conn):
        with conn.cursor() as cur:
            cur.execute('SELECT USER USERNAME FROM DUAL'); user=cur.fetchone()[0]
            cur.execute('SELECT * FROM OML_LAB_STATE WHERE ID=1'); state=rows(cur)[0]
            cur.execute('SELECT SPLIT,LABEL,COUNT(*) N FROM OML_FEATURES GROUP BY SPLIT,LABEL ORDER BY SPLIT,LABEL'); counts=rows(cur)
            cur.execute("SELECT MODEL_NAME,MINING_FUNCTION,ALGORITHM FROM USER_MINING_MODELS WHERE MODEL_NAME IN ('OML_REBUY_DT','OML_BASKET_AR')"); models=rows(cur)
        return jsonify(user=user,version=conn.version,state=state,counts=counts,models=models,
                       ready=state['model_rev']==state['data_rev'] and state['model_rev'] is not None)

    @app.get('/api/data')
    @db_api
    def data(conn):
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM OML_FEATURES ORDER BY CUSTOMER_ID FETCH FIRST 120 ROWS ONLY')
            return jsonify(rows=rows(cur),limit=120)

    @app.post('/api/upload/validate')
    def preview_upload():
        try:
            if 'file' not in request.files: raise ValueError('CSV 파일을 선택하세요.')
            return jsonify(summary(validate_csv(request.files['file'].read())))
        except ValueError as e: return jsonify(error=str(e)),400

    @app.post('/api/upload')
    @db_api
    def upload(conn):
        if 'file' not in request.files: raise ValueError('CSV 파일을 선택하세요.')
        data=validate_csv(request.files['file'].read())
        with conn.cursor() as cur:
            cur.execute('DELETE FROM OML_FEATURES')
            cur.executemany('INSERT INTO OML_FEATURES VALUES(:1,:2,:3,:4,:5,:6,:7)',[[r[c] for c in COLUMNS] for r in data])
            cur.execute("UPDATE OML_LAB_STATE SET DATA_REV=DATA_REV+1,MODEL_REV=NULL,SOURCE_NAME='uploaded CSV' WHERE ID=1")
            conn.commit()
        return jsonify(message='검증한 CSV로 교체했습니다. 현재 데이터로 모델을 다시 학습하세요.',**summary(data))

    @app.post('/api/sample')
    @db_api
    def sample(conn):
        with conn.cursor() as cur: cur.callproc('OML_LAB.REFRESH_SAMPLE')
        conn.commit()
        return jsonify(message='원본 주문에서 특성과 라벨을 다시 계산했습니다. 모델을 다시 학습하세요.')

    @app.post('/api/train')
    @db_api
    def train(conn):
        with conn.cursor() as cur: cur.callproc('OML_LAB.TRAIN_CLASSIFIER')
        result,scores=evaluate(conn)
        return jsonify(message='Oracle에서 분류모델 학습을 완료했습니다.',confusion=result,metrics=scores)

    @app.post('/api/predict')
    @db_api
    def predict(conn):
        values=request.get_json(silent=True) or {}
        args=[numeric(values.get(k),k) for k in ('order_count','total_amount','recency_days','category_count')]
        return jsonify(predictions=result_set(conn,'PREDICT_RANK',*args))

    @app.get('/api/model')
    @db_api
    def model(conn):
        confusion,scores=evaluate(conn)
        return jsonify(nodes=result_set(conn,'MODEL_DETAILS'),settings=result_set(conn,'MODEL_SETTINGS'),
                       confusion=confusion,metrics=scores)

    @app.get('/api/correlation')
    @db_api
    def correlation(conn):
        stats=result_set(conn,'CORRELATION')
        with conn.cursor() as cur:
            cur.execute("SELECT ORDER_COUNT,TOTAL_AMOUNT FROM OML_FEATURES WHERE SPLIT='TRAIN' ORDER BY CUSTOMER_ID FETCH FIRST 1000 ROWS ONLY")
            points=rows(cur)
        return jsonify(stats=stats[0],points=points)

    @app.post('/api/rules/train')
    @db_api
    def train_rules(conn):
        with conn.cursor() as cur: cur.callproc('OML_LAB.TRAIN_RULES')
        return jsonify(rules=result_set(conn,'RULES'))

    @app.get('/api/rules')
    @db_api
    def rules(conn): return jsonify(rules=result_set(conn,'RULES'))

    @app.get('/api/source/<name>')
    def source(name):
        if name not in SOURCE_FILES: abort(404)
        return jsonify(path=SOURCE_FILES[name],source=(ROOT/SOURCE_FILES[name]).read_text(encoding='utf-8'))

    @app.get('/download/sample.csv')
    def download_csv(): return send_file(ROOT/'deploy/data/classification.csv',as_attachment=True,download_name='classification.csv')

    @app.get('/download/student.zip')
    def download_zip():
        archive=latest_student_archive(ROOT/'downloads')
        if archive is None: return jsonify(error='배포 ZIP이 없습니다. scripts/package.ps1을 먼저 실행하세요.'),404
        return send_file(archive,as_attachment=True,download_name=archive.name)

    @app.get('/api/export')
    @db_api
    def export_result(conn):
        confusion,scores=evaluate(conn)
        with conn.cursor() as cur:
            cur.execute('SELECT DATA_REV,MODEL_REV,TRAINED_AT,SOURCE_NAME FROM OML_LAB_STATE WHERE ID=1')
            state=rows(cur)[0]
        return jsonify(dataset=state,metrics=scores,confusion=confusion,
                       settings=result_set(conn,'MODEL_SETTINGS'),note='소규모 합성 데이터 실습 결과. 일반화 성능의 증명이 아닙니다.')

    @app.errorhandler(413)
    def large(_): return jsonify(error='업로드 한도는 2MB입니다.'),413

    @app.errorhandler(404)
    def missing(_): return render_template('error.html',title='페이지를 찾을 수 없습니다',active='',message='주소를 확인하거나 학습 대시보드로 이동하세요.'),404

    return app
