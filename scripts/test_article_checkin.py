"""Check-in gates and global-review isolation, with temporary data only."""
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers import vocabulary as v, auth as auth_router
from services import checkin_service as c, auth_service as auth

def main():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp); (root/'zhenti/2020').mkdir(parents=True)
        for name in ['article_1.json','article_2.json','zhenti/2020/text_1.json','zhenti/2020/text_5.json']:
            (root/name).write_text('{}',encoding='utf-8')
        users={'alice':{'name':'alice','checkins':{'article_1':True}},'bob':{'name':'bob','checkins':{}}}
        resolve=lambda t: {'a':'alice','b':'bob'}.get(t)
        with patch.object(v,'DB_PATH',root/'test.sqlite3'), patch.object(c,'DATA_DIR',root), patch.object(c,'ARTICLES_DIR',root), patch.object(v,'get_user_by_token',side_effect=resolve), patch.object(v,'get_user_info',return_value={'name':'user'}), patch.object(auth_router,'get_user_by_token',side_effect=resolve), patch.object(auth,'_get_users',return_value=users):
            app=FastAPI();app.include_router(v.router);app.include_router(auth_router.router);client=TestClient(app)
            headers={'Authorization':'Bearer a'}
            entry=dict(word='cloud',meaning='definition',article_id='article_1',article_title='One',sentence='Cloud their reputations.',sentence_idx='0-0')
            client.post('/data/vocabulary',headers=headers,json={'entries':[entry,dict(entry,article_id='article_2',sentence='Cloud the issue.')]})
            def start(article='article_1'):
                res=client.post('/data/vocabulary/article-review',headers=headers,json={'article_id':article})
                assert res.status_code==200,res.text
                return res.json()
            def check(session,article='article_1',token='a'):
                return client.post('/data/auth/checkin/'+article,params={'token':token,'session_id':session})
            def snapshot():
                db=v.connect()
                try: return ([tuple(r) for r in db.execute('SELECT * FROM vocabulary_reviews ORDER BY id')],[tuple(r) for r in db.execute('SELECT * FROM vocabulary_review_log')])
                finally: db.close()
            def complete(data,grade):
                for task in data['review']['tasks']:
                    if task['id'] in data['session']['task_ids'] and task['id'] not in data['session']['completed']:
                        result=client.post('/data/vocabulary/rate',headers=headers,json={'task_id':task['id'],'version':task['version'],'grade':grade,'session_id':data['session']['id']})
                        assert result.status_code==200,result.text
                return data['session']['id']
            assert check('').status_code==409
            assert client.post('/data/vocabulary/article-review',json={'article_id':'article_1'}).status_code==401
            before=snapshot()
            for i,grade in enumerate(['again','hard','known']):
                data=start(); assert len(data['session']['task_ids'])==1  # only this article's context
                sid=data['session']['id']; assert check(sid).status_code==409
                assert check(sid,token='b').status_code==409
                complete(data,grade)
                assert snapshot()==before, 'Article practice changed global progress/logs'
                if grade != 'known':
                    assert check(sid).status_code==409
                    complete(data,'known')  # immediately allowed, no delay or global mutation
                    assert snapshot()==before
                assert check(sid,article='article_2').status_code==409
                assert check(sid).json()['count']==i+2  # old boolean counts as one
                assert check(sid).json()['count']==i+2  # retry cannot double-count
            assert client.get('/data/auth/checkin-summary',params={'token':'a'}).json()['counts']['article_1']==4
            status=client.get('/data/auth/checkin-status/article_1').json()['checkins']
            assert status[0]['count']==4 and len(status)==1
            assert 'article_1' in auth.get_user_checkins('alice')
            # Both exam parts can check in without any collected vocabulary.
            for article in ['zhenti_2020_1','zhenti_2020_5']:
                data=start(article); assert data['session']['task_ids']==[]
                assert check(data['session']['id'],article).json()['count']==1
            # Reopening resumes rather than discarding unfinished progress.
            old=start();new=start();assert old['session']['id']==new['session']['id'] and new['resumed']
            # Changes to the source collection invalidate completion, not silently bypass it.
            sid=complete(new,'known')
            resumed=start()
            assert resumed['session']['completed']==resumed['session']['task_ids']
            client.post('/data/vocabulary',headers=headers,json={'entries':[dict(entry,meaning='updated meaning')]})
            assert check(sid).status_code==409
            assert client.post('/data/vocabulary/article-review',headers=headers,json={'article_id':'zhenti_2020_4'}).status_code==404
            # Mastered and not-yet-due tasks are reviewable without changing global fields.
            db=v.connect()
            try:
                with db: db.execute('UPDATE vocabulary_reviews SET stage=6,due_at=0,version=version+1')
            finally: db.close()
            before=snapshot();complete(start(),'again');assert snapshot()==before
            db=v.connect()
            try:
                with db: db.execute('UPDATE vocabulary_reviews SET stage=2,due_at=?,version=version+1',(v.now_seconds()+86400,))
            finally: db.close()
            before=snapshot();complete(start(),'hard');assert snapshot()==before
            # Combined card completes this word's common meaning and every local context,
            # but never another word or the same word's context in another article.
            client.post('/data/vocabulary',headers=headers,json={'entries':[
                dict(entry,sentence='Cloud the outlook.',sentence_idx='0-1'),
                dict(entry,word='outlook',sentence='Cloud the outlook.',sentence_idx='0-1')
            ]})
            data=start(); before=snapshot()
            task=next(t for t in data['review']['tasks'] if t['id'] in data['session']['task_ids'] and t['word_key']=='cloud')
            result=client.post('/data/vocabulary/rate',headers=headers,json={
                'task_id':task['id'],'version':task['version'],'grade':'known',
                'session_id':data['session']['id'],'combined':True
            })
            assert result.status_code==200,result.text
            done=set(result.json()['session']['completed'])
            expected={t['id'] for t in data['review']['tasks'] if t['word_key']=='cloud' and t['id'] in data['session']['task_ids']}
            assert done==expected and len(done)==2
            assert snapshot()==before
            assert check(data['session']['id']).status_code==409  # outlook still needs review
            reopened=start()
            assert reopened['resumed'] and reopened['session']['id']==data['session']['id']
            assert set(reopened['session']['completed'])==done
            assert check(reopened['session']['id']).status_code==409
            # Server persists failed-word ordering as well, independent of page memory.
            complete(reopened,'known')
            assert check(reopened['session']['id']).status_code==200
            fresh=start();assert fresh['session']['id']!=reopened['session']['id'] and not fresh['session']['completed']
            target=next(t for t in fresh['review']['tasks'] if t['id']==fresh['session']['task_ids'][0])
            result=client.post('/data/vocabulary/rate',headers=headers,json={'task_id':target['id'],'version':target['version'],'grade':'again','session_id':fresh['session']['id'],'combined':True})
            assert result.status_code==200
            reloaded=start()
            assert reloaded['session']['task_ids']==result.json()['session']['task_ids']
            related={t['id'] for t in fresh['review']['tasks'] if t['word_key']==target['word_key'] and t['id'] in fresh['session']['task_ids']}
            assert set(reloaded['session']['task_ids'][-len(related):])==related
            print('PASS: article gate, no cross-article/account bypass, all grades isolated from global state/logs, legacy counts, repeated checkins, idempotency, Part A/B, empty vocabulary, stale sessions, changed sources, mastered/future tasks')

if __name__=='__main__':main()
