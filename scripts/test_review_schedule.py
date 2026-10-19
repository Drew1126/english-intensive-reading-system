"""Deterministic tests with a temporary database and simulated Shanghai time."""
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers import vocabulary as v

def main():
    clock = [int(datetime(2026, 10, 17, 23, 50, tzinfo=v.LOCAL_TZ).timestamp())]
    with tempfile.TemporaryDirectory() as tmp, patch.object(v, 'DB_PATH', Path(tmp)/'reviews.sqlite3'), patch.object(v, 'get_user_by_token', side_effect=lambda t: {'a':'alice','b':'bob'}.get(t)), patch.object(v, 'get_user_info', return_value={"name":"test"}), patch.object(v, 'now_seconds', side_effect=lambda: clock[0]):
        app=FastAPI(); app.include_router(v.router); client=TestClient(app)
        a={'Authorization':'Bearer a'}; b={'Authorization':'Bearer b'}
        entry=dict(word='cloud',meaning='definition',article_id='article_1',article_title='One',sentence='Cloud my judgment.',sentence_idx='0-0')
        def save(e):
            assert client.post('/data/vocabulary', headers=a,json={'entries':[e]}).status_code==200
        def state(): return client.get('/data/vocabulary',headers=a).json()['review']
        def rate(t,grade='known',headers=a):
            return client.post('/data/vocabulary/rate',headers=headers,json={'task_id':t['id'],'version':t['version'],'grade':grade})
        def task(kind): return next(t for t in state()['tasks'] if t['kind']==kind)
        save(entry)
        initial=state(); assert len(initial['tasks'])==1 and initial['due_words']==1 and initial['new_words']==1
        context=task('context')
        assert rate(context,headers=b).status_code==404
        assert rate(context,headers={}).status_code==401
        first=rate(context).json(); assert first['stage']==1
        assert first['due_at']==0
        assert rate(context).status_code==409  # stale duplicate
        assert rate(task('context')).json()['stage']==1  # same-day rating allowed; no extra upgrade
        save(entry); assert task('context')['stage']==1
        client.post('/data/vocabulary/restore',headers=a,json={'word':'cloud'})
        context=task('context')
        # No delay gate, but still no repeated same-day advancement.
        again=rate(context,'again').json(); assert again['due_at']==0 and again['stage']==0
        clock[0]+=600
        known=rate(task('context')).json(); assert known['stage']==1
        # Restore then try known in the same day: no second increment.
        client.post('/data/vocabulary/restore',headers=a,json={'word':'cloud'})
        result=rate(task('context')).json(); assert result['stage']==0
        assert state()['mastered']==[]
        clock[0]+=86400
        t=task('context'); previous=t['stage']; result=rate(t,'hard').json()
        assert result['stage']==previous and result['due_at']==0
        for expected in range(1,7):
            t=task('context'); clock[0]=max(clock[0]+86400,t['due_at'])
            result=rate(t).json(); assert result['stage']==expected
            assert result['due_at']==0
        assert state()['mastered']==['cloud']
        assert state()['due_count']==0
        # New source makes the word unmastered but keeps old tracks mastered.
        save(dict(entry,article_id='zhenti_2012_5',sentence='Cloud their reputations.'))
        s=state(); assert not s['mastered'] and len(s['tasks'])==2
        assert s['new_words']==0  # new context is not a brand-new word
        assert sum(t['stage']==6 for t in s['tasks'])==1
        assert client.post('/data/vocabulary/delete-mastered',headers=a).json()['deleted']==0
        pending=next(t for t in s['tasks'] if t['stage']<6)
        # Deletion is account-scoped and removes sources and logs.
        client.post('/data/vocabulary/delete',headers=b,json={'word':'cloud'})
        assert len(state()['tasks'])==2
        client.post('/data/vocabulary/delete',headers=a,json={'word':'cloud'})
        assert state()['tasks']==[]
        assert client.get('/data/vocabulary',headers=a).json()['entries']==[]
        assert rate(pending).status_code==404
        # Legacy source rows gain review tasks without changing their definitions.
        db = v.connect()
        try:
            with db:
                db.execute('INSERT INTO vocabulary(owner,id,word,meaning,article_id,article_title,sentence,sentence_idx) VALUES(?,?,?,?,?,?,?,?)',
                           ('alice','legacy','legacy','old definition','old_article','Old title','Original old sentence.','0-0'))
        finally:
            db.close()
        migrated=client.get('/data/vocabulary',headers=a).json()
        assert migrated['entries'][0]['meaning']=='old definition' and len(migrated['review']['tasks'])==1
        assert all(t['stage']==0 for t in migrated['review']['tasks'])
        save(dict(entry,word='keep'))
        db=v.connect()
        try:
            with db:
                db.execute("UPDATE vocabulary_reviews SET stage=6 WHERE owner='alice' AND word_key='legacy'")
        finally:
            db.close()
        assert client.post('/data/vocabulary/delete-mastered',headers=a).json()['deleted']==1
        remaining=client.get('/data/vocabulary',headers=a).json()['entries']
        assert len(remaining)==1 and remaining[0]['word']=='keep'
        assert client.post('/data/vocabulary/rate',headers=a,json={'task_id':'x','version':0,'grade':'bad'}).status_code==422
        db = v.connect()
        try:
            assert db.execute('SELECT COUNT(*) FROM vocabulary_review_log').fetchone()[0]==0
        finally:
            db.close()
        # Old common-meaning rows remain stored but cannot block mastery or be rated.
        db=v.connect()
        try:
            with db:
                db.execute("INSERT INTO vocabulary_reviews(owner,id,word_key,kind,source_id,due_at) VALUES('alice','old_word','keep','word','',0)")
                db.execute("UPDATE vocabulary_reviews SET stage=6 WHERE owner='alice' AND word_key='keep' AND kind='context'")
        finally: db.close()
        assert state()['mastered']==['keep'] and state()['due_count']==0
        assert rate({'id':'old_word','version':0}).status_code==409
        # Multiple due sources of one word advance atomically from a single card.
        save(dict(entry,word='batch',sentence='First context.'))
        save(dict(entry,word='batch',sentence='Second context.',sentence_idx='0-1'))
        group=[t for t in state()['tasks'] if t['word_key']=='batch']
        payload=dict(task_id=group[0]['id'],version=0,grade='known',targets=[
            dict(task_id=t['id'],version=t['version']) for t in group])
        stale=dict(payload,targets=[dict(task_id=group[1]['id'],version=99)])
        assert client.post('/data/vocabulary/rate',headers=a,json=stale).status_code==409
        assert all(t['stage']==0 for t in state()['tasks'] if t['word_key']=='batch')
        result=client.post('/data/vocabulary/rate',headers=a,json=payload)
        assert result.status_code==200,result.text
        assert all(t['stage']==1 for t in state()['tasks'] if t['word_key']=='batch')
        assert client.post('/data/vocabulary/rate',headers=a,json=payload).status_code==409
        print('PASS: context-only progress, no delay gate, same-day cap, duplicate rejection, account isolation, mastery, deletion and migration')

if __name__=='__main__': main()
