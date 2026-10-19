"""Private, account-scoped vocabulary with per-sentence definitions."""
import hashlib
import sqlite3
import time
import json
from datetime import datetime, timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from config import DATA_DIR
from services.auth_service import get_user_by_token, get_user_info

router = APIRouter(prefix='/data/vocabulary', tags=['vocabulary'])
DB_PATH = DATA_DIR / 'vocabulary.sqlite3'
LOCAL_TZ = timezone(timedelta(hours=8))

def word_key(word):
    return ' '.join(word.split()).casefold()

def now_seconds():
    return int(time.time())

def local_day(now):
    return datetime.fromtimestamp(now, LOCAL_TZ).date().isoformat()

class TaskVersion(BaseModel):
    task_id: str = Field(max_length=100)
    version: int = Field(ge=0)

class Rating(BaseModel):
    task_id: str = Field(max_length=100)
    version: int = Field(ge=0)
    grade: Literal['again', 'hard', 'known']
    session_id: str = Field(default='', max_length=100)
    combined: bool = False
    targets: list[TaskVersion] = Field(default_factory=list, max_length=500)
    round_id: str = Field(default='', max_length=100)

class ArticleReview(BaseModel):
    article_id: str = Field(min_length=1, max_length=200)

class WordAction(BaseModel):
    word: str = Field(min_length=1, max_length=300)

class Entry(BaseModel):
    word: str = Field(min_length=1, max_length=300)
    meaning: str = Field(min_length=1, max_length=20000)
    article_id: str = Field(min_length=1, max_length=200)
    article_title: str = Field(max_length=1000)
    sentence: str = Field(min_length=1, max_length=20000)
    sentence_idx: str = Field(default='', max_length=50)

class Batch(BaseModel):
    entries: list[Entry] = Field(max_length=50)

def owner(authorization):
    token = authorization.removeprefix('Bearer ') if authorization.startswith('Bearer ') else ''
    username = get_user_by_token(token)
    if not username or not get_user_info(username):
        raise HTTPException(401, '请重新登录')
    return username

def connect():
    db = sqlite3.connect(str(DB_PATH), timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('''CREATE TABLE IF NOT EXISTS vocabulary (
        owner TEXT NOT NULL, id TEXT NOT NULL, word TEXT NOT NULL,
        meaning TEXT NOT NULL, article_id TEXT NOT NULL, article_title TEXT NOT NULL,
        sentence TEXT NOT NULL, sentence_idx TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(owner,id))''')
    db.execute('''CREATE TABLE IF NOT EXISTS vocabulary_reviews (
        owner TEXT NOT NULL, id TEXT NOT NULL, word_key TEXT NOT NULL,
        kind TEXT NOT NULL, source_id TEXT NOT NULL DEFAULT '',
        stage INTEGER NOT NULL DEFAULT 0, due_at INTEGER NOT NULL,
        last_advanced_day TEXT NOT NULL DEFAULT '', last_reviewed INTEGER NOT NULL DEFAULT 0,
        version INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(owner,id))''')
    db.execute('''CREATE TABLE IF NOT EXISTS vocabulary_review_log (
        owner TEXT NOT NULL, task_id TEXT NOT NULL, reviewed_at INTEGER NOT NULL,
        grade TEXT NOT NULL, old_stage INTEGER NOT NULL, new_stage INTEGER NOT NULL)''')
    db.commit()
    db.execute('''CREATE TABLE IF NOT EXISTS article_review_sessions (
        id TEXT PRIMARY KEY, owner TEXT NOT NULL, article_id TEXT NOT NULL,
        tasks TEXT NOT NULL, signature TEXT NOT NULL, completed TEXT NOT NULL,
        created_at INTEGER NOT NULL, consumed INTEGER NOT NULL DEFAULT 0)''')
    db.execute('''CREATE TABLE IF NOT EXISTS article_checkins (
        owner TEXT NOT NULL, article_id TEXT NOT NULL, session_id TEXT PRIMARY KEY,
        created_at INTEGER NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS global_review_rounds (
        id TEXT PRIMARY KEY, owner TEXT NOT NULL, selected TEXT NOT NULL,
        pending TEXT NOT NULL, completed TEXT NOT NULL, created_at INTEGER NOT NULL)''')
    db.commit()
    return db

def ensure_tasks(db, username, now):
    for entry in db.execute('SELECT id,word FROM vocabulary WHERE owner=?', (username,)).fetchall():
        key = word_key(entry['word'])
        for task_id, kind, source_id in [('context_'+entry['id'], 'context', entry['id'])]:
            db.execute('INSERT OR IGNORE INTO vocabulary_reviews(owner,id,word_key,kind,source_id,due_at) VALUES(?,?,?,?,?,?)',
                       (username, task_id, key, kind, source_id, now))

def review_state(db, username, now):
    tasks = [dict(row) for row in db.execute("SELECT id,word_key,kind,source_id,stage,due_at,last_reviewed,version FROM vocabulary_reviews WHERE owner=? AND kind='context'", (username,))]
    groups = {}
    for task in tasks:
        groups.setdefault(task['word_key'], []).append(task)
    from services.global_review import priorities, latest
    word_priorities = priorities(tasks, now, LOCAL_TZ)
    due = [t for t in tasks if t['stage'] < 6]
    return dict(tasks=tasks, now=now, timezone='Asia/Shanghai',
                due_count=len(due), due_words=len({t['word_key'] for t in due}),
                new_words=len({t['word_key'] for t in due if all(not x['last_reviewed'] for x in groups[t['word_key']])}),
                mastered=[key for key, group in groups.items() if all(t['stage'] == 6 for t in group)],
                word_priorities=word_priorities, available_words=len(word_priorities),
                round=latest(db, username))

@router.get('')
def list_entries(authorization: str = Header(default='')):
    username = owner(authorization)
    db = connect()
    try:
        now = now_seconds()
        with db:
            ensure_tasks(db, username, now)
        entries = [dict(r) for r in db.execute('SELECT id,word,meaning,article_id,article_title,sentence,sentence_idx FROM vocabulary WHERE owner=? ORDER BY updated_at DESC,rowid DESC', (username,))]
        for entry in entries:
            entry['word_key'] = word_key(entry['word'])
        return {'entries': entries, 'review': review_state(db, username, now)}
    finally:
        db.close()

@router.post('')
def save_entries(batch: Batch, authorization: str = Header(default='')):
    username = owner(authorization)
    db = connect()
    try:
        with db:
            for e in batch.entries:
                word = ' '.join(e.word.split())
                if not word or not e.sentence.strip():
                    raise HTTPException(422, '词条和原句不能为空')
                key = hashlib.sha256((word.casefold()+'\0'+e.article_id+'\0'+e.sentence_idx+'\0'+e.sentence).encode()).hexdigest()
                db.execute('''INSERT INTO vocabulary(owner,id,word,meaning,article_id,article_title,sentence,sentence_idx)
                    VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(owner,id) DO UPDATE SET
                    meaning=excluded.meaning, article_title=excluded.article_title, updated_at=CURRENT_TIMESTAMP''',
                    (username,key,word,e.meaning,e.article_id,e.article_title,e.sentence,e.sentence_idx))
            ensure_tasks(db, username, now_seconds())
        return {'saved': len(batch.entries)}
    finally:
        db.close()

@router.post('/rate')
def rate(req: Rating, authorization: str = Header(default='')):
    username = owner(authorization)
    db = connect()
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            task = db.execute('SELECT * FROM vocabulary_reviews WHERE owner=? AND id=?', (username, req.task_id)).fetchone()
            if not task:
                raise HTTPException(404, '复习任务不存在')
            if task['kind'] != 'context':
                raise HTTPException(409, '常见义任务已停用，请刷新页面后复习句中义')
            now = now_seconds()
            session = None
            if req.session_id:
                from services.checkin_service import validate
                session = validate(db, username, req.session_id, now)
                if req.task_id not in json.loads(session['tasks']) or req.task_id in json.loads(session['completed']):
                    raise HTTPException(409, '该任务不属于本轮回顾或已完成')
            if task['version'] != req.version:
                raise HTTPException(409, '进度已更新，请刷新复习队列')
            if session:
                # Article check-in practice never mutates global spaced-review state or logs.
                from services.checkin_service import pack
                completed = json.loads(session['completed'])
                if req.grade == 'known':
                    completed.append(req.task_id)
                if req.combined and req.grade == 'known':
                    allowed = set(json.loads(session['tasks']))
                    related = db.execute('SELECT id FROM vocabulary_reviews WHERE owner=? AND word_key=?', (username, task['word_key'])).fetchall()
                    completed = sorted(set(completed) | {row['id'] for row in related if row['id'] in allowed})
                db.execute('UPDATE article_review_sessions SET completed=? WHERE id=?', (json.dumps(completed), session['id']))
                if req.grade != 'known':
                    order = json.loads(session['tasks'])
                    related = {r['id'] for r in db.execute('SELECT id FROM vocabulary_reviews WHERE owner=? AND word_key=?', (username, task['word_key']))}
                    order = [t for t in order if t not in related] + [t for t in order if t in related]
                    db.execute('UPDATE article_review_sessions SET tasks=? WHERE id=?', (json.dumps(order), session['id']))
                session_data = pack(db.execute('SELECT * FROM article_review_sessions WHERE id=?', (session['id'],)).fetchone())
                return {'stage': task['stage'], 'due_at': task['due_at'], 'review': review_state(db, username, now), 'session': session_data}
            if task['stage'] == 6:
                raise HTTPException(409, '该任务已掌握')
            global_round = None
            if req.round_id:
                from services.global_review import validate as validate_round
                global_round = validate_round(db, username, req.round_id, task['word_key'])
            selected = {req.task_id: req.version}
            for target in req.targets:
                if target.task_id in selected and selected[target.task_id] != target.version:
                    raise HTTPException(409, '进度已更新，请刷新')
                selected[target.task_id] = target.version
            batch = []
            for task_id, version in selected.items():
                item = db.execute('SELECT * FROM vocabulary_reviews WHERE owner=? AND id=?', (username, task_id)).fetchone()
                if not item or item['word_key'] != task['word_key'] or item['kind'] != 'context' or item['version'] != version or item['stage'] == 6:
                    raise HTTPException(409, '原句复习进度已变化，请刷新后重试')
                batch.append(item)
            for item in batch:
                stage, advanced = item['stage'], item['last_advanced_day']
                if req.grade == 'again':
                    stage, due = 0, 0
                elif req.grade == 'hard':
                    due = 0
                else:
                    if advanced != local_day(now):
                        stage = min(6, stage + 1)
                        advanced = local_day(now)
                    due = 0
                db.execute('UPDATE vocabulary_reviews SET stage=?,due_at=?,last_advanced_day=?,last_reviewed=?,version=version+1 WHERE owner=? AND id=?',
                           (stage, due, advanced, now, username, item['id']))
                db.execute('INSERT INTO vocabulary_review_log VALUES(?,?,?,?,?,?)', (username, item['id'], now, req.grade, item['stage'], stage))
            if global_round:
                from services.global_review import record
                record(db, global_round, task['word_key'], req.grade)
        return {'stage': stage, 'due_at': due, 'review': review_state(db, username, now), 'session': None}
    finally:
        db.close()

@router.post('/article-review')
def start_article_review(req: ArticleReview, authorization: str = Header(default='')):
    from services.checkin_service import start
    return start(owner(authorization), req.article_id)

@router.post('/global-review')
def start_global_review(authorization: str = Header(default='')):
    from services.global_review import start
    return start(owner(authorization))

@router.post('/restore')
def restore(req: WordAction, authorization: str = Header(default='')):
    username = owner(authorization)
    db = connect()
    try:
        with db:
            cursor = db.execute('UPDATE vocabulary_reviews SET stage=0,due_at=?,last_reviewed=0,version=version+1 WHERE owner=? AND word_key=?',
                                (now_seconds(), username, word_key(req.word)))
            if not cursor.rowcount:
                raise HTTPException(404, '词条不存在')
        return {'restored': True}
    finally:
        db.close()

def delete_word(db, username, key):
    db.execute('DELETE FROM vocabulary_review_log WHERE owner=? AND task_id IN (SELECT id FROM vocabulary_reviews WHERE owner=? AND word_key=?)', (username, username, key))
    db.execute('DELETE FROM vocabulary_reviews WHERE owner=? AND word_key=?', (username, key))
    ids = [r['id'] for r in db.execute('SELECT id,word FROM vocabulary WHERE owner=?', (username,)) if word_key(r['word']) == key]
    db.executemany('DELETE FROM vocabulary WHERE owner=? AND id=?', [(username, i) for i in ids])

@router.post('/delete')
def remove(req: WordAction, authorization: str = Header(default='')):
    username = owner(authorization)
    db = connect()
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            delete_word(db, username, word_key(req.word))
        return {'deleted': True}
    finally:
        db.close()

@router.post('/delete-mastered')
def remove_mastered(authorization: str = Header(default='')):
    username = owner(authorization)
    db = connect()
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            ensure_tasks(db, username, now_seconds())
            mastered = review_state(db, username, now_seconds())['mastered']
            for key in mastered:
                delete_word(db, username, key)
        return {'deleted': len(mastered)}
    finally:
        db.close()
