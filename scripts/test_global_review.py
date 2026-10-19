"""Three-day word selection, persistent rounds and no waiting; isolated data only."""
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers import vocabulary as v
from services.global_review import priorities

def main():
    now=int(datetime(2026,10,20,0,1,tzinfo=v.LOCAL_TZ).timestamp())
    def ago(days, hour=23):
        day=datetime(2026,10,20,tzinfo=v.LOCAL_TZ)-timedelta(days=days)
        return int(day.replace(hour=hour,minute=59).timestamp())
    rows=[dict(word_key=str(d),stage=0,last_reviewed=ago(d)) for d in [0,1,2,3,5,6,8,9]]
    result={w['word_key']:w for w in priorities(rows,now,v.LOCAL_TZ)}
    assert [result[str(d)]['bucket'] for d in [0,1,2,3,5,6,8,9]]==[0,0,0,1,1,2,2,3]
    # Only two minutes elapsed, but Shanghai midnight changes the calendar date.
    assert result['1']['days']==1
    merged=priorities([dict(word_key='x',stage=0,last_reviewed=ago(9)),dict(word_key='x',stage=0,last_reviewed=ago(3))],now,v.LOCAL_TZ)
    assert merged[0]['bucket']==1
    with tempfile.TemporaryDirectory() as tmp, patch.object(v,'DB_PATH',Path(tmp)/'test.db'), patch.object(v,'get_user_by_token',side_effect=lambda t:{'a':'alice','b':'bob'}.get(t)), patch.object(v,'get_user_info',return_value={'name':'test'}), patch.object(v,'now_seconds',return_value=now):
        app=FastAPI();app.include_router(v.router);client=TestClient(app)
        headers={'Authorization':'Bearer a'}
        entries=[dict(word='w'+str(i),meaning='◆ 在本句中 meaning',article_id='article_1',article_title='Test',sentence='Sentence '+str(i),sentence_idx=str(i)) for i in range(25)]
        assert client.post('/data/vocabulary',headers=headers,json={'entries':entries}).status_code==200
        db=v.connect()
        try:
            with db:
                for i in range(25):
                    # w0 never reviewed; remaining buckets: 0..7. All old due dates in future.
                    db.execute('UPDATE vocabulary_reviews SET last_reviewed=?,due_at=? WHERE word_key=?',(0 if i==0 else ago(i),now+999999,'w'+str(i)))
                db.execute("UPDATE vocabulary_reviews SET stage=6 WHERE word_key='w24'")
        finally: db.close()
        def start(): return client.post('/data/vocabulary/global-review',headers=headers).json()
        first=start();state=first['review'];round=state['round']
        assert not first['resumed'] and len(round['selected'])==20 and len(set(round['selected']))==20
        assert round['selected'][0]=='w0' and 'w24' not in round['selected']
        bykey={w['word_key']:w for w in state['word_priorities']}
        buckets=[bykey[key]['bucket'] for key in round['selected'][1:]]
        assert buckets==sorted(buckets,reverse=True)
        assert start()['review']['round']==round
        def rate(state,key,grade,auth=headers):
            task=next(t for t in state['tasks'] if t['word_key']==key)
            return client.post('/data/vocabulary/rate',headers=auth,json={'task_id':task['id'],'version':task['version'],'grade':grade,'round_id':state['round']['id']})
        assert rate(state,'w0','known',{'Authorization':'Bearer b'}).status_code==404
        response=rate(state,'w0','again');assert response.status_code==200,response.text
        updated=response.json()['review'];assert updated['round']['pending'][-1]=='w0'
        assert updated['round']['completed']==[]
        assert start()['review']['round']==updated['round']
        response=rate(updated,'w0','known');assert response.status_code==200,response.text
        updated=response.json()['review'];assert 'w0' not in updated['round']['pending']
        assert updated['round']['completed']==['w0']
        assert rate(updated,'w0','known').status_code==409
        assert next(w for w in updated['word_priorities'] if w['word_key']=='w0')['bucket']==0
        for key in list(updated['round']['pending']):
            response=rate(updated,key,'known');assert response.status_code==200,response.text
            updated=response.json()['review']
        assert not updated['round']['pending'] and len(updated['round']['completed'])==20
        next_round=start()
        assert not next_round['resumed'] and next_round['review']['round']['id']!=round['id']
        assert client.post('/data/vocabulary/global-review').status_code==401
        # Same-bucket priority ignores exact timestamps: reverse shuffled order survives sorting.
        db=v.connect()
        try:
            with db:
                db.execute("DELETE FROM global_review_rounds WHERE owner='alice'")
                db.execute("UPDATE vocabulary_reviews SET last_reviewed=?,stage=0",(ago(3),))
                db.execute("UPDATE vocabulary_reviews SET last_reviewed=? WHERE word_key='w1'",(ago(5),))
        finally: db.close()
        with patch('services.global_review.random.SystemRandom.shuffle',side_effect=lambda xs:xs.reverse()):
            expected=list(reversed([w['word_key'] for w in client.get('/data/vocabulary',headers=headers).json()['review']['word_priorities']]))[:20]
            assert start()['review']['round']['selected']==expected
    print('PASS: 3-day calendar buckets, never-reviewed priority, random tie order, 20-word cap, resume, tail retry, no due gate, isolation, new round')

if __name__=='__main__': main()
