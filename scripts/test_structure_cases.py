"""Offline contract tests by default; --live explicitly spends DeepSeek tokens.

Only synthetic/public example sentences are sent. No article/history reads or
learning-data writes. Reports under ignored tmp/ contain outputs, never credentials.
Semantic checks are fixture-specific guards, NOT a general grammar proof.
"""
import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from services.structure_markup import START, END, extract_structure, extract_structure_aligned

# id, sentence, acceptable minimal example, original spans, required highlighted
# phrases, phrases that must not enter the main-clause skeleton.
CASES = [
    ('story', "It's no surprise that Mary's remarkable cover story, called A New Life, is arousing much chatter.", "It's no surprise that [the] story is arousing chatter.", ["It's no surprise that", 'story', 'is arousing', 'chatter'], ['story', 'is arousing'], ['A New Life']),
    ('ellipsis', 'Tom likes tea, and Mary coffee.', 'Tom likes tea, and Mary [likes] coffee.', ['Tom likes tea, and Mary coffee'], ['Tom', 'likes', 'and', 'Mary', 'coffee'], []),
    ('object_complement', 'A turbulent business environment also has senior managers cautious.', '[The] environment has managers cautious.', ['environment', 'has', 'managers cautious'], ['environment', 'has', 'managers', 'cautious'], []),
    ('formal_object', 'The financial crisis has made it more acceptable to be between jobs or to leave a bad one.', 'The crisis has made it more acceptable to be between jobs or to leave a bad one.', ['The', 'crisis has made it more acceptable to be between jobs or to leave a bad one'], ['has made', 'it', 'acceptable', 'to be', 'or to leave'], []),
    ('inversion_do', 'Seldom does she complain about the noise.', 'Seldom does she complain.', ['Seldom does she complain'], ['Seldom', 'does', 'she', 'complain'], []),
    ('inversion_perfect', 'Never has he agreed to such a risky plan.', 'Never has he agreed.', ['Never has he agreed'], ['Never', 'has', 'he', 'agreed'], []),
    ('only_condition', 'Only after the meeting did she understand the problem.', 'Only after the meeting did she understand the problem.', ['Only after the meeting did she understand the problem'], ['Only after the meeting', 'did', 'she', 'understand', 'problem'], []),
    ('cleft', 'It was a lack of evidence that caused the delay.', 'A lack of evidence caused the delay.', ['a lack of evidence', 'caused the delay'], ['lack of evidence', 'caused', 'delay'], []),
    ('formal_subject', 'It is likely that prices will rise sharply next year.', 'It is likely that prices will rise.', ['It is likely that prices will rise'], ['It is likely that', 'prices', 'will rise'], []),
    ('relative_clause', 'The book that she bought yesterday has changed my view.', 'The book has changed my view.', ['The book', 'has changed my view'], ['book', 'has changed', 'view'], ['she bought']),
    ('concessive', 'Although sales fell, profits rose and costs declined.', 'Profits rose and costs declined.', ['profits rose and costs declined'], ['profits', 'rose', 'and', 'costs', 'declined'], ['sales fell']),
    ('passive_modal', 'The proposal may not have been approved by the committee.', 'The proposal may not have been approved.', ['The proposal may not have been approved'], ['proposal', 'may not have been approved'], []),
    ('nominal_subject', 'What matters most is whether we can finish on time.', 'What matters is whether we can finish on time.', ['What matters', 'is whether we can finish on time'], ['What matters', 'is whether', 'we can finish'], []),
    ('phrasal_verb', 'She took the new evidence into account.', 'She took the evidence into account.', ['She took the', 'evidence into account'], ['She took', 'evidence', 'into account'], []),
    ('negation_until', 'We did not discover the error until Monday.', 'We did not discover the error until Monday.', ['We did not discover the error until Monday'], ['We did not discover', 'error', 'until Monday'], []),
    ('existential', 'There are several reasons why the plan failed.', 'There are reasons.', ['There are', 'reasons'], ['There are', 'reasons'], []),
    ('formal_subject_past', 'It was clear that the team had won the match.', 'It was clear that the team had won the match.', ['It was clear that the team had won the match'], ['It was clear that', 'team', 'had won', 'match'], []),
    ('place_complement', 'She put the heavy book on the desk yesterday.', 'She put the book on the desk.', ['She put the', 'book on the desk'], ['She put', 'book', 'on the desk'], ['heavy', 'yesterday']),
    ('cleft_person', 'It was Anna who solved the difficult problem.', 'Anna solved the problem.', ['Anna', 'solved the', 'problem'], ['Anna', 'solved', 'problem'], ['It was', 'who', 'difficult']),
    ('already_minimal', 'Birds fly.', 'Birds fly.', ['Birds fly'], ['Birds fly'], []),
    ('simplified_nominal', 'That he survived was a miracle.', 'That he survived was a miracle.', ['That he survived was a miracle'], ['That he survived', 'was a miracle'], []),
]

# Precision checks are part of pass/fail, not merely informational warnings.
FADE = {
    'story': ['remarkable', 'called', 'A New Life'],
    'object_complement': ['turbulent', 'senior'],
    'cleft': ['It was', 'that'],
    'formal_subject': ['sharply', 'next year'],
    'relative_clause': ['she bought', 'yesterday'],
    'passive_modal': ['by the committee'],
    'phrasal_verb': ['new'],
    'existential': ['why the plan failed'],
}

def contains_phrase(text, phrase):
    pattern = r"[\w]+(?:['’\-][\w]+)*"
    tokens = lambda value: re.findall(pattern, value.casefold().replace('’', "'"))
    haystack, needle = tokens(text), tokens(phrase)
    return bool(needle) and any(haystack[i:i+len(needle)] == needle for i in range(len(haystack)-len(needle)+1))

def evaluate(case, highlights):
    name, _, _, _, required, forbidden = case
    joined = ' '.join(highlights)
    missing = [phrase for phrase in required if not contains_phrase(joined, phrase)]
    unwanted = [phrase for phrase in dict.fromkeys(forbidden + FADE.get(name, [])) if contains_phrase(joined, phrase)]
    return missing, unwanted

def packed(skeleton, spans):
    return 'Original first line\nExplanation\n' + START + json.dumps({'skeleton': skeleton, 'spans': spans}) + END

def decode_ranges(sentence, core):
    encoded = sentence.encode('utf-16-le')
    return [encoded[a*2:b*2].decode('utf-16-le') for a, b in core['ranges']]

def offline():
    checks = 0
    for name, sentence, skeleton, texts, required, forbidden in CASES:
        spans = [{'text': text, 'occurrence': 1} for text in texts]
        answer, core = extract_structure(packed(skeleton, spans), sentence, True)
        assert core, name
        assert answer.splitlines()[0] == skeleton, name
        assert decode_ranges(sentence, core) == texts, name
        assert evaluate((name, sentence, skeleton, texts, required, forbidden), texts) == ([], []), name
        checks += 1
        for index in range(len(spans)):
            assert extract_structure(packed(skeleton, spans[:index] + spans[index+1:]), sentence, True)[1] is None, name
            checks += 1
    # Wrong occurrence, overlap, changed word form, missing metadata and UTF-16.
    for spans in [None, [None], ['bad'], [{'text': 42, 'occurrence': 1}],
                  [{'text': 'Birds fly', 'occurrence': True}],
                  [{'text': 'Birds fly', 'occurrence': 2}]]:
        assert extract_structure(packed('Birds fly.', spans), 'Birds fly.', True)[1] is None
        checks += 1
    assert extract_structure(packed('He works.', [{'text':'He works', 'occurrence':1}]), '😀 He works.', True)[1]['ranges'] == [[3,11]]
    assert extract_structure(packed('She complains.', [{'text':'she complain', 'occurrence':1}]), 'Seldom does she complain.', True)[1] is None
    print(f'PASS: {len(CASES)} structure types, {checks + 2} offline checks', flush=True)
    repairs = [
        ("Mary's remarkable cover story is arousing chatter.", "Mary's cover story is arousing chatter.", ["Mary's cover story", 'is arousing chatter']),
        ('A turbulent business environment has senior managers cautious.', 'Environment has managers cautious.', ['business environment', 'has senior managers cautious']),
        ('It was a lack of evidence that caused the delay.', 'A lack of evidence caused the delay.', ['A lack of evidence', 'caused the delay']),
        ('😀 He works.', 'He works.', ['he works']),
    ]
    for sentence, skeleton, texts in repairs:
        raw = packed(skeleton, [{'text': t, 'occurrence': 1} for t in texts])
        assert extract_structure(raw, sentence, True)[1] is None
        assert extract_structure_aligned(raw, sentence)[1] is not None
    for sentence, skeleton in [('He said he works.', 'He works.'),
                                ('She complains.', 'She complained.'),
                                ('He works.', '[He works.]'),
                                ('He works.', 'He [works.'),
                                ('Long-term effects remain.', 'Term effects remain.')]:
        raw = packed(skeleton, [{'text': 'invalid', 'occurrence': 1}])
        assert extract_structure_aligned(raw, sentence)[1] is None
    assert extract_structure_aligned(packed('He works.', []), 'He works.')[1] is None
    print('PASS: 10 unique-alignment repair / fail-closed checks', flush=True)
    assert not contains_phrase('renewed', 'new')
    for case in CASES:
        name, sentence, _, texts, _, forbidden = case
        if forbidden or FADE.get(name):
            assert evaluate(case, [sentence])[1], name
    assert evaluate(next(c for c in CASES if c[0] == 'cleft'), ['It was a lack of evidence that caused the delay'])[1]
    assert not evaluate(next(c for c in CASES if c[0] == 'formal_subject_past'), ['It was clear that the team had won the match'])[1]
    print('PASS: over-highlighting guards and cleft/formal-subject contrast', flush=True)

async def live(args):
    import services.agent_service as service
    if urlparse(service.LLM_API_BASE).hostname != 'api.deepseek.com':
        raise RuntimeError('Not configured for DeepSeek; no request sent')
    selected = [case for case in CASES if not args.case or case[0] in args.case]
    if not selected:
        raise ValueError('No matching cases')
    report = ROOT / 'tmp' / args.report
    report.parent.mkdir(parents=True, exist_ok=True)
    results = []
    semaphore = asyncio.Semaphore(2)

    async def run(case, repeat):
        name, sentence, _, _, required, forbidden = case
        async with semaphore:
            try:
                llm = service.ChatOpenAI(model=service.LLM_MODEL, api_key=service.LLM_API_KEY,
                    base_url=service.LLM_API_BASE, streaming=True, temperature=0.1,
                    max_tokens=2600, timeout=60, max_retries=0)
                messages = service._build_messages('structure', '解释句子结构', sentence, '', '', '')
                raw = ''.join([part.content async for part in llm.astream(messages) if isinstance(part.content, str)])
                answer, core = extract_structure_aligned(raw, sentence)
                highlights = decode_ranges(sentence, core) if core else []
                missing, unexpected = evaluate(case, highlights)
                restoration_ok = name not in ('inversion_do', 'inversion_perfect', 'simplified_nominal') or '◆ 简化表达（辅助改写，非原文）' in answer
                result = dict(case=name, repeat=repeat, sentence=sentence, valid_core=bool(core),
                    required_missing=missing, unwanted_present=unexpected, highlights=highlights,
                    restoration_present=restoration_ok,
                    answer=answer, raw=raw, passed=bool(core) and not missing and not unexpected and restoration_ok)
            except Exception as error:
                # Avoid storing exception messages that might contain request secrets.
                result = dict(case=name, repeat=repeat, passed=False, error_type=type(error).__name__)
            results.append(result)
            report.write_text(json.dumps({'model': service.LLM_MODEL, 'results': results}, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({k:v for k,v in result.items() if k not in ('answer','raw','sentence')}, ensure_ascii=False), flush=True)

    await asyncio.gather(*(run(case, repeat+1) for repeat in range(args.repeat) for case in selected))
    passed = sum(item['passed'] for item in results)
    print(f'LIVE: {passed}/{len(results)} passed fixture checks; report: {report}', flush=True)
    return passed == len(results)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--case', action='append', choices=[case[0] for case in CASES])
    parser.add_argument('--repeat', type=int, choices=range(1, 6), default=1)
    parser.add_argument('--report', default='structure-live-report.json', choices=['structure-live-report.json', 'structure-live-repeat.json', 'structure-layered-report.json'])
    args = parser.parse_args()
    offline()
    if args.live:
        sys.exit(0 if asyncio.run(live(args)) else 1)
