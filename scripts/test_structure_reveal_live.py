"""Actual production stream against DeepSeek; only example text and temporary history."""
import asyncio
import json
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
import services.agent_service as service

async def main():
    fixture=json.loads((ROOT/'frontend/preview-reveal-data.json').read_text(encoding='utf-8'))
    service._load_recent_history=lambda *args: ''
    service._load_article_context=lambda *args: ''
    with tempfile.TemporaryDirectory() as tmp:
        service.CHAT_HISTORY_DIR=Path(tmp)
        events=[event async for event in service.stream_agent_response('解释句子结构',fixture['sentence'])]
        payload=json.loads(events[0][6:])
        report=ROOT/'tmp/structure-reveal-production.json'
        report.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
        assert events[-1]=='data: [DONE]\n\n'
        assert payload.get('core'), 'No reliable core returned'
        assert payload['core'].get('reveal'), 'No valid reveal graph returned; plain explanation fallback used'
        nodes=payload['core']['reveal']['nodes']
        print('Core:',payload['text'].splitlines()[0])
        for node in nodes: print(node['id'],node['text'],'depends_on',node['depends_on'])
        print('PASS: production SSE contains validated reveal graph; no real user history written')

if __name__=='__main__': asyncio.run(main())
