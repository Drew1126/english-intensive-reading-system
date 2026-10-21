"""--live sends only these example sentences to DeepSeek, no user history."""
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
 ('social_cure', 'But in her new book Join the Club, Tina Rosenberg contends that peer pressure can also be a positive force through what she calls the social cure, in which organizations and officials use the power of group dynamics to help individuals improve their lives and possibly the world.', True),
 ('nested_actions', 'The charity uses donations from local businesses to help families buy food and pay their rent.', True),
 ('relative_nested', 'The scientists studied a protein that helps cells repair damage caused by sunlight.', True),
 ('nominal', 'That he survived was a miracle.', False),
 ('inversion', 'Only after the meeting did she understand the problem.', False),
 ('cleft', 'It was a lack of evidence that caused the delay.', False),
 ('simple', 'Birds fly.', False),
 ('necessary_place', 'She put the heavy book on the desk yesterday.', False),
]

def check(answer, core, name, nested):
    failures = []
    if not core: failures.append('no reliable original-text highlight')
    if any(label in answer for label in ['◆ 主干意思', '◆ 逐层补回信息', '主干串起来']):
        failures.append('old repetitive template')
    if name != 'simple' and '\n\n' not in answer: failures.append('no paragraph spacing')
    if nested:
        if '◆ 难点拆解' not in answer or '↳' not in answer: failures.append('missing layered explanation')
    if name == 'social_cure' and '↳↳' not in answer: failures.append('missing second action level')
    if name == 'social_cure':
        first = answer.splitlines()[0].casefold() if answer else ''
        if any(part in first for part in ['through', 'in which', 'organizations', 'help individuals']):
            failures.append('whole-sentence skeleton includes adjunct explanation')
        if not all(part in first for part in ['tina rosenberg contends that', 'peer pressure can also be a positive force']):
            failures.append('whole-sentence skeleton missing essential content')
        plain = answer.replace('**', '')
        if not re.search(r'(?m)^\s*to help individuals\s*$', plain): failures.append('help target not separated from nested action')
        if not re.search(r'(?m)^\s*improve their lives and possibly the world[.。]?\s*$', plain): failures.append('nested improve action not on own line')
    if name == 'nominal' and '◆ 简化表达（辅助改写，非原文）' not in answer: failures.append('missing labeled paraphrase')
    return failures

def offline():
    system = service._build_messages('structure', '解释句子结构', 'Birds fly.', '', '', '')[0].content
    assert '段落之间留一个空行' in system
    assert '◆ 难点拆解' in system
    assert '任何两行之间都不要插入空白行' not in system
    vocab = service._build_messages('vocabulary', '', 'Birds fly.', 'Birds', '', '')[0].content
    assert '任何两行之间都不要插入空白行' in vocab
    assert service._normalize_answer('A\n\n\nB', True) == 'A\n\nB'
    assert service._normalize_answer('A\n\nB') == 'A\nB'
    assert check('old\n◆ 主干意思\n主干串起来', {}, 'social_cure', True)
    print('PASS: structure-only formatting, vocabulary unchanged, paragraph preservation and bad-template detection', flush=True)

async def live():
    assert urlparse(service.LLM_API_BASE).hostname == 'api.deepseek.com'
    results = []
    # Sequential: stop after two consecutive connection failures instead of wasting a batch.
    connection_failures = 0
    for name, sentence, nested in CASES:
        try:
            model = service.ChatOpenAI(model=service.LLM_MODEL, api_key=service.LLM_API_KEY,
                base_url=service.LLM_API_BASE, temperature=.1, max_tokens=2600, timeout=45, max_retries=0)
            response = await model.ainvoke(service._build_messages('structure', '解释句子结构', sentence, '', '', ''))
            raw = response.content
            answer, core = extract_structure_aligned(raw, sentence)
            answer = service._normalize_answer(answer, True)
            failures = check(answer, core, name, nested)
            results.append(dict(case=name, sentence=sentence, answer=answer, core=core, raw=raw, failures=failures))
            connection_failures = 0
            print(name, 'PASS' if not failures else failures, flush=True)
        except Exception as exc:
            results.append(dict(case=name, error_type=type(exc).__name__))
            print(name, type(exc).__name__, flush=True)
            connection_failures += 1
            if connection_failures >= 2: break
    report = ROOT / 'tmp' / 'structure-presentation-report.json'
    report.parent.mkdir(exist_ok=True)
    report.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    passed = sum('failures' in r and not r['failures'] for r in results)
    print(f'LIVE: {passed}/{len(results)} returned cases passed, {len(CASES)-len(results)} unrun. Report: {report}', flush=True)
    return passed == len(CASES)

if __name__ == '__main__':
    offline()
    if '--live' in sys.argv: sys.exit(0 if asyncio.run(live()) else 1)
