"""Persistent global rounds, selected by three-day Shanghai calendar buckets."""
import json
import random
import uuid
from datetime import datetime
from fastapi import HTTPException

def priorities(tasks, now, tz):
    groups = {}
    for task in tasks:
        groups.setdefault(task['word_key'], []).append(task)
    today = datetime.fromtimestamp(now, tz).date()
    result = []
    for key, group in groups.items():
        if all(t['stage'] >= 6 for t in group):
            continue
        last = max(t['last_reviewed'] for t in group)
        days = max(0, (today - datetime.fromtimestamp(last, tz).date()).days) if last else None
        result.append(dict(word_key=key, last_reviewed=last, days=days, bucket=days//3 if days is not None else None))
    return result

def pack(row):
    if not row:
        return None
    return dict(id=row['id'], selected=json.loads(row['selected']), pending=json.loads(row['pending']), completed=json.loads(row['completed']))

def latest(db, username):
    return pack(db.execute('SELECT * FROM global_review_rounds WHERE owner=? ORDER BY rowid DESC LIMIT 1', (username,)).fetchone())

def start(username):
    from routers.vocabulary import connect, ensure_tasks, now_seconds, review_state
    db = connect()
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            now = now_seconds()
            ensure_tasks(db, username, now)
            state = review_state(db, username, now)
            current = state['round']
            eligible = {w['word_key'] for w in state['word_priorities']}
            if current and any(key in eligible for key in current['pending']):
                return {'review': state, 'resumed': True}
            words = list(state['word_priorities'])
            random.SystemRandom().shuffle(words)
            # Stable sort preserves random order within a bucket. Never compare precise times.
            words.sort(key=lambda w: (w['last_reviewed'] == 0, w['bucket'] if w['bucket'] is not None else 0), reverse=True)
            keys = [w['word_key'] for w in words[:20]]
            db.execute('INSERT INTO global_review_rounds(id,owner,selected,pending,completed,created_at) VALUES(?,?,?,?,?,?)',
                       (uuid.uuid4().hex, username, json.dumps(keys), json.dumps(keys), '[]', now))
        return {'review': review_state(db, username, now), 'resumed': False}
    finally:
        db.close()

def validate(db, username, round_id, word):
    row = db.execute('SELECT * FROM global_review_rounds WHERE owner=? AND id=?', (username, round_id)).fetchone()
    if not row or word not in json.loads(row['pending']):
        raise HTTPException(409, '该词不在本轮待回顾队列，请刷新')
    return row

def record(db, row, word, grade):
    pending = [key for key in json.loads(row['pending']) if key != word]
    completed = json.loads(row['completed'])
    if grade == 'known':
        completed.append(word)
    else:
        pending.append(word)
    db.execute('UPDATE global_review_rounds SET pending=?,completed=? WHERE id=?',
               (json.dumps(pending), json.dumps(completed), row['id']))
