"""Targeted omission/retention tests. --live uses DeepSeek, no private history."""
import asyncio
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import services.agent_service as service
from services.structure_markup import extract_structure_aligned

CASES = [
    ('social_cure', 'But in her new book Join the Club, Tina Rosenberg contends that peer pressure can also be a positive force through what she calls the social cure, in which organizations and officials use the power of group dynamics to help individuals improve their lives and possibly the world.', ['But', 'Tina Rosenberg contends that peer pressure can also be a positive force'], ['through', 'in which', 'organizations', 'improve']),
    ('new_mechanism', 'In a recent study, scientists suggest that music can reduce stress through changes in breathing, which help patients relax after surgery.', ['scientists suggest that music can reduce stress'], ['through', 'breathing', 'which', 'surgery']),
    ('new_relative', 'The manager believes that training is useful for new employees, who need time to learn the procedures.', ['manager believes that training is useful'], ['who', 'procedures']),
    ('necessary_preposition', 'The company went through a crisis last year.', ['company went through a crisis'], ['last year']),
    ('necessary_location', 'She put the heavy book on the desk yesterday.', ['She put', 'book on the desk'], ['heavy', 'yesterday']),
    ('necessary_complement', 'The news made the investors nervous during the meeting.', ['news made', 'investors nervous'], ['during the meeting']),
    ('necessary_nominal', 'What she said surprised everyone at the meeting.', ['What she said surprised everyone'], ['at the meeting']),
    ('necessary_negation', 'Only after the meeting did she realize that the plan would not work.', ['Only after the meeting did she realize that the plan would not work'], []),
]

def tokens(value):
    return re.findall(r"[\w]+(?:['’][\w]+)*", value.casefold())

def contains(text, phrase):
    a, b = tokens(text), tokens(phrase)
    return any(a[i:i+len(b)] == b for i in range(len(a)-len(b)+1))

def check(case, answer, core):
    _, sentence, required, excluded = case
    first = answer.splitlines()[0] if answer else ''
    encoded = sentence.encode('utf-16-le')
    highlighted = ' '.join(encoded[a*2:b*2].decode('utf-16-le') for a,b in core['ranges']) if core else ''
    errors = []
    for label, text in [('first line', first), ('highlight', highlighted)]:
        for phrase in required:
            if not contains(text, phrase): errors.append(f'{label} misses: {phrase}')
        for phrase in excluded:
            if contains(text, phrase): errors.append(f'{label} retains: {phrase}')
    if not core: errors.append('no reliable highlight')
    return errors

def offline():
    case = CASES[0]
    sentence = case[1]
    skeleton = 'But Tina Rosenberg contends that peer pressure can also be a positive force.'
    start = sentence.index('Tina Rosenberg')
    end = sentence.index(' through')
    core = dict(ranges=[[0,3],[start,end]])
    assert not check(case, skeleton, core)
    assert check(case, sentence, dict(ranges=[[0,len(sentence)]]))
    assert check(case, skeleton, dict(ranges=[[0,len(sentence)]]))
    assert check(case, 'Tina Rosenberg contends.', dict(ranges=[[start,start+len('Tina Rosenberg contends')]]))
    for case in CASES[3:]:
        assert check(case, 'Something happened.', {'ranges':[]})
    print('PASS: reject whole-sentence copying, over-highlighting and missing necessary complements', flush=True)

async def live():
    import httpx
    assert urlparse(service.LLM_API_BASE).hostname == 'api.deepseek.com'
    results = []
    async with httpx.AsyncClient(timeout=60) as client:
        llm = service.ChatOpenAI(model=service.LLM_MODEL, api_key=service.LLM_API_KEY,
            base_url=service.LLM_API_BASE, temperature=.1, max_tokens=2600,
            timeout=60, max_retries=0, http_async_client=client)
        connection_errors = 0
        for repeat in range(2):
            for case in CASES:
                try:
                    raw = (await llm.ainvoke(service._build_messages('structure', '解释句子结构', case[1], '', '', ''))).content
                    answer, core = extract_structure_aligned(raw, case[1])
                    errors = check(case, answer, core)
                    result = dict(case=case[0], repeat=repeat+1, sentence=case[1], answer=answer, core=core, raw=raw, failures=errors)
                    connection_errors = 0
                    print(case[0], repeat+1, answer.splitlines()[0], errors or 'PASS', flush=True)
                except Exception as exc:
                    connection_errors += 1
                    result = dict(case=case[0], repeat=repeat+1, error_type=type(exc).__name__)
                    print(case[0], result['error_type'], flush=True)
                results.append(result)
                report = ROOT / 'tmp' / 'structure-concision-report.json'
                report.parent.mkdir(exist_ok=True)
                report.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
                if connection_errors >= 2: return False
    passed = sum('failures' in r and not r['failures'] for r in results)
    print(f'LIVE: {passed}/{len(results)} passed', flush=True)
    return passed == len(results)

if __name__ == '__main__':
    offline()
    if '--live' in sys.argv: sys.exit(0 if asyncio.run(live()) else 1)
