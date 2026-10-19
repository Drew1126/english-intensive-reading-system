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
    def __init__(self, **kwargs):
        pass
    async def astream(self, messages):
        assert '<<<CORE_SPANS>>>' in messages[0].content
        for text in ['句子主干：Birds fly.', '<<<CORE_SPANS>>>',
                     '{"spans":[{"text":"Birds","occurrence":1},{"text":"fly","occurrence":1}]}',
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
        assert payload['text'] == '句子主干：Birds fly.'
        history = json.loads(next(Path(tmp).glob('*.json')).read_text(encoding='utf-8'))
        assert history[0]['answer'] == payload['text']
        assert '<<<CORE' not in history[0]['answer']
    print('Structure SSE: metadata delivered separately and excluded from history passed')

asyncio.run(main())
