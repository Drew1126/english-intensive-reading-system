import asyncio
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from services.collocations import extract_collocations, START, END
from services import agent_service as agent

def raw(items):
    return START + json.dumps({'items': items}) + END

def item(label, pieces, meaning='把……考虑在内'):
    return dict(label=label, meaning=meaning, spans=[dict(text=t,occurrence=n) for t,n in pieces])

async def main():
    sentence='They took the costs into account and put the launch off.'
    items=[item('take ... into account',[('took',1),('into account',1)]),
           item('put ... off',[('put',1),('off',1)],'推迟发布')]
    answer,data=extract_collocations(raw(items),sentence)
    assert len(data['items'])==2
    assert [[sentence[a:b] for a,b in group['ranges']] for group in data['items']]==[['took','into account'],['put','off']]
    assert '<<<' not in answer
    assert extract_collocations(raw([]),sentence)[0]=='本句中未发现明确的固定搭配。'
    for bad in [
        item('fake',[('take',1),('into account',1)]),
        item('partial',[('ook',1),('into account',1)]),
        item('reversed',[('off',1),('put',1)]),
        item('single',[('took',1)]),
        item('missing',[('took',3),('into account',1)]),
    ]:
        assert extract_collocations(raw([bad]),sentence)[1] is None
    assert len(extract_collocations(raw(items+[items[0]]),sentence)[1]['items'])==2
    repeated='They put it off and put that off.'
    entry=extract_collocations(raw([item('put ... off',[('put',2),('off',2)])]),repeated)[1]['items'][0]
    assert [repeated[a:b] for a,b in entry['ranges']]==['put','off'] and entry['ranges'][0][0]==20
    unicode=extract_collocations(raw([item('take into account',[('take into account',1)])]),'😀 take into account')[1]
    assert unicode['items'][0]['ranges']==[[3,20]]
    for broken in ['', START+'{', START+'null'+END, START+'[]'+END]:
        assert extract_collocations(broken,sentence)[1] is None
        assert '<<<' not in extract_collocations(broken,sentence)[0]
    assert agent.classify_intent('查找句中搭配','took')=='collocations'
    class Fake:
        def __init__(self, **kwargs): pass
        async def astream(self,messages):
            assert '忽略 focus' in messages[0].content
            value=raw(items)
            for piece in [value[:25],value[25:]]:
                yield SimpleNamespace(content=piece)
    with tempfile.TemporaryDirectory() as tmp, patch.object(agent,'ChatOpenAI',Fake), patch.object(agent,'CHAT_HISTORY_DIR',Path(tmp)), patch.object(agent,'_load_recent_history',return_value=''), patch.object(agent,'_load_article_context',return_value=''):
        events=[e async for e in agent.stream_agent_response('查找句中搭配',sentence,focus='took')]
        result=json.loads(events[0][6:])
        assert len(result['collocations']['items'])==2 and events[-1]=='data: [DONE]\n\n'
        history=json.loads(next(Path(tmp).glob('*.json')).read_text(encoding='utf-8'))
        assert history[0]['answer']==result['text'] and START not in history[0]['answer']
    print('PASS: collocations intent, continuous/discontinuous spans, repeated words, Unicode, malformed metadata, SSE and history')

asyncio.run(main())
