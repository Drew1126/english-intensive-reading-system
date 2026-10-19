"""One check-in per completed, article-scoped review session."""
import hashlib
import json
import re
import uuid
from fastapi import HTTPException
from config import ARTICLES_DIR, DATA_DIR

def require_article(article_id):
    match = re.fullmatch(r'zhenti_(\d{4})_([1-5])', article_id)
    if match:
        path = DATA_DIR / 'zhenti' / match[1] / ('text_'+match[2]+'.json')
    elif re.fullmatch(r'article_\d+', article_id):
        path = ARTICLES_DIR / (article_id+'.json')
    else:
        raise HTTPException(404, '文章不存在')
    if not path.is_file():
        raise HTTPException(404, '文章已删除或不存在')

def snapshot(db, username, article_id):
    rows = db.execute('SELECT id,word,meaning FROM vocabulary WHERE owner=? AND article_id=? ORDER BY id', (username, article_id)).fetchall()
    tasks = set()
    for row in rows:
        tasks.add('context_'+row['id'])
    signature = hashlib.sha256(('context-only-v1:' + json.dumps([dict(r) for r in rows], ensure_ascii=False, sort_keys=True)).encode()).hexdigest()
    return sorted(tasks), signature

def pack(row):
    return dict(id=row['id'], article_id=row['article_id'], task_ids=json.loads(row['tasks']), completed=json.loads(row['completed']))

def start(username, article_id):
    from routers.vocabulary import connect, ensure_tasks, now_seconds, review_state
    require_article(article_id)
    db=connect()
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            ensure_tasks(db, username, now_seconds())
            tasks, signature = snapshot(db, username, article_id)
            existing = db.execute('SELECT * FROM article_review_sessions WHERE owner=? AND article_id=? AND consumed=0 ORDER BY created_at DESC LIMIT 1', (username, article_id)).fetchone()
            resumed = bool(existing and existing['signature'] == signature and now_seconds()-existing['created_at'] <= 86400)
            if resumed:
                session_id = existing['id']
            else:
                db.execute('DELETE FROM article_review_sessions WHERE owner=? AND article_id=? AND consumed=0', (username,article_id))
                session_id=uuid.uuid4().hex
                db.execute('INSERT INTO article_review_sessions(id,owner,article_id,tasks,signature,completed,created_at) VALUES(?,?,?,?,?,?,?)',
                           (session_id,username,article_id,json.dumps(tasks),signature,'[]',now_seconds()))
        row=db.execute('SELECT * FROM article_review_sessions WHERE id=?',(session_id,)).fetchone()
        return {'session':pack(row),'review':review_state(db,username,now_seconds()), 'resumed':resumed}
    finally:
        db.close()

def validate(db, username, session_id, now):
    row=db.execute('SELECT * FROM article_review_sessions WHERE id=? AND owner=?',(session_id,username)).fetchone()
    if not row or row['consumed']:
        raise HTTPException(409,'本篇回顾已失效或已用于打卡，请重新开始')
    if now-row['created_at']>86400:
        raise HTTPException(409,'本篇回顾已超过 24 小时，请重新开始')
    require_article(row['article_id'])
    _,signature=snapshot(db,username,row['article_id'])
    if row['signature']!=signature:
        raise HTTPException(409,'本篇生词已变化，请重新开始本篇回顾')
    return row

def extra_counts(username=None, article_id=None):
    from routers.vocabulary import connect
    db=connect()
    try:
        query='SELECT owner,article_id,COUNT(*) AS count FROM article_checkins WHERE 1=1'
        params=[]
        if username is not None: query+=' AND owner=?'; params.append(username)
        if article_id is not None: query+=' AND article_id=?'; params.append(article_id)
        return [dict(r) for r in db.execute(query+' GROUP BY owner,article_id',params)]
    finally:
        db.close()

def counts(username):
    from services.auth_service import _get_users
    result={article:1 for article in _get_users().get(username,{}).get('checkins',{})}
    for row in extra_counts(username): result[row['article_id']]=result.get(row['article_id'],0)+row['count']
    return result

def consume(username, article_id, session_id):
    from routers.vocabulary import connect, now_seconds
    from services.auth_service import _get_users
    require_article(article_id)
    legacy=int(article_id in _get_users().get(username,{}).get('checkins',{}))
    db=connect()
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            existing=db.execute('SELECT 1 FROM article_checkins WHERE session_id=? AND owner=? AND article_id=?',(session_id,username,article_id)).fetchone()
            if not existing:
                session=validate(db,username,session_id,now_seconds())
                if session['article_id']!=article_id:
                    raise HTTPException(409,'回顾记录不属于这篇文章')
                if set(json.loads(session['tasks']))!=set(json.loads(session['completed'])):
                    raise HTTPException(409,'请先完成本篇全部生词回顾')
                db.execute('INSERT INTO article_checkins(owner,article_id,session_id,created_at) VALUES(?,?,?,?)',(username,article_id,session_id,now_seconds()))
                db.execute('UPDATE article_review_sessions SET consumed=1 WHERE id=?',(session_id,))
            count=legacy+db.execute('SELECT COUNT(*) FROM article_checkins WHERE owner=? AND article_id=?',(username,article_id)).fetchone()[0]
        return {'checked_in':True,'count':count}
    finally:
        db.close()
