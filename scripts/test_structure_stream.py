"""Exercise SSE and history without external API calls or user-data writes."""
import asyncio
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import services.agent_service as service

class FakeLLM:
    invalid_graph = False
    def __init__(self, **kwargs):
        pass
    async def astream(self, messages):
        assert '<<<CORE_SPANS>>>' in messages[0].content
        metadata = {'skeleton':'Birds fly.', 'spans':[{'text':'Birds','occurrence':1},{'text':'fly','occurrence':1}],
                    'nodes':[{'id':'n1','spans':[{'text':'often','occurrence':1}], 'meaning':'经常',
                              'depends_on':['missing' if self.invalid_graph else 'core'], 'references':[]}]}
        for text in ['句子主干：Birds fly.\n\n鸟会飞。\n\n◆ 补充信息\n**频率？**\noften\n经常。', '<<<CORE_SPANS>>>',
                     json.dumps(metadata),
                     '<<<END_CORE_SPANS>>>']:
            yield SimpleNamespace(content=text)

async def main():
    service.ChatOpenAI = FakeLLM
    service._load_article_context = lambda *args: ''
    service._load_recent_history = lambda *args: ''
    with tempfile.TemporaryDirectory() as tmp:
        service.CHAT_HISTORY_DIR = Path(tmp)
        events = [event async for event in service.stream_agent_response('解释句子结构', 'Birds often fly.')]
        assert events[-1] == 'data: [DONE]\n\n'
        payload = json.loads(events[0][6:])
        assert payload['core']['ranges'] == [[0,5],[12,15]]
        assert payload['core']['reveal']['nodes'][0]['ranges'] == [[6,11]]
        assert payload['text'] == 'Birds fly.\n\n鸟会飞。\n\n◆ 补充信息\n**频率？**\noften\n经常。'
        history = json.loads(next(Path(tmp).glob('*.json')).read_text(encoding='utf-8'))
        assert history[0]['answer'] == payload['text']
        assert '<<<CORE' not in history[0]['answer']
        FakeLLM.invalid_graph = True
        invalid = [event async for event in service.stream_agent_response('解释句子结构', 'Birds often fly.')]
        fallback = json.loads(invalid[0][6:])
        assert fallback['text'] == payload['text']
        assert fallback['core']['ranges'] == payload['core']['ranges']
        assert 'reveal' not in fallback['core']
        FakeLLM.invalid_graph = False
    print('Structure SSE: metadata delivered separately and excluded from history passed')

asyncio.run(main())
