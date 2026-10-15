"""Import English-I Part B from original-paper pages, preserving source order."""
import asyncio
import argparse
import json
import re
import subprocess
from datetime import date
from pathlib import Path
from import_zhenti_books import POPPLER, TESSERACT, ROOT, OUTPUT_DIR, BOOKS, parse_json, _call_llm

BOOKS['middle'] = Path('D:/Downloads/历年考研英语真题解析及复习思路(珍藏版)  (2014-2021) .pdf')
CACHE = ROOT / 'tmp/pdfs/part-b'
SYSTEM = '''Extract ONLY English-I Part B from these scanned original exam pages. Stop at Part C. Ignore preceding Part A questions and page footers. Never reconstruct an answered passage: preserve original order, all numbered blanks 41-45, all lettered options (A-G or A-H), headings, and fixed ordering positions. Include short instructions as the first paragraph. Do not add answers, explanations, or invented text. Correct only obvious OCR typos. Split prose into sentences within original paragraphs; keep labels on their associated first sentence. Translate every sentence faithfully into Chinese, preserving labels and blanks. Return JSON only: {"type":"小标题匹配|段落排序|七选五|信息匹配", "paragraphs":[{"sentences":["..."],"translations":["..."]}]}. Include every original option even when short or unused. Do not apply a minimum paragraph length.'''

def source(year):
    key, start = ('base', 2007) if year <= 2013 else (('middle', 2014) if year <= 2021 else ('recent', 2022))
    return BOOKS[key], 14 + 16 * (year - start)

def ocr(year, refresh=False):
    folder = CACHE / str(year)
    folder.mkdir(parents=True, exist_ok=True)
    raw_path = folder / 'ocr.txt'
    if raw_path.exists() and not refresh:
        return raw_path.read_text(encoding='utf-8')
    pdf, first = source(year)
    subprocess.run([str(POPPLER), '-f', str(first), '-l', str(first+2), '-r', '180', '-png', str(pdf), str(folder/'page')], check=True, capture_output=True)
    texts = []
    for image in sorted(folder.glob('page-*.png')):
        result = subprocess.run([str(TESSERACT), str(image), 'stdout', '-l', 'eng', '--psm', '6'], check=True, capture_output=True, text=True, encoding='utf-8')
        texts.append(result.stdout)
    raw = '\n\n'.join(texts)
    raw_path.write_text(raw, encoding='utf-8')
    return raw

def validate(data):
    assert data.get('type') in ['小标题匹配','段落排序','七选五','信息匹配'], 'Unknown type'
    ps = data['paragraphs']
    assert ps, 'No paragraphs'
    for p in ps:
        p['sentences'] = [re.sub(r'^[{(]([A-H])\]', r'[\1]', s) for s in p['sentences']]
        p['sentences'] = [re.sub(r'^([A-H])\]', r'[\1]', s) for s in p['sentences']]
        assert p['sentences'] and len(p['sentences']) == len(p['translations']), 'Translation alignment'
        assert all(isinstance(s,str) and s.strip() for s in p['sentences'] + p['translations']), 'Empty text'
    text = ' '.join(s for p in ps for s in p['sentences'])
    assert len(text.split()) > 250, 'Incomplete passage'
    assert not re.search(r'Part\s+C\b', text), 'Part C contamination'
    for label in 'ABCDEFG':
        assert re.search(r'(?:\['+label+r'\]|\('+label+r'\)|\b'+label+r'\.)', text), 'Missing option '+label

async def run(year, sem, refresh=False):
    output = OUTPUT_DIR / str(year) / 'text_5.json'
    if output.exists() and not refresh:
        print(f'{year}: exists, skipped', flush=True)
        return
    async with sem:
        raw = await asyncio.to_thread(ocr, year, refresh)
        print(f'{year}: OCR ready', flush=True)
        candidate = CACHE/str(year)/'candidate.json'
        data = json.loads(candidate.read_text(encoding='utf-8')) if candidate.exists() and not refresh else parse_json(await _call_llm(SYSTEM + ' Attach each label to its own paragraph. Classify comments/statements matching as 信息匹配. Retain H in A-H questions.', f'Year {year}. OCR:\n{raw}'))
        (CACHE/str(year)/'candidate.json').write_text(json.dumps(data,ensure_ascii=False,indent=2), encoding='utf-8')
        validate(data)
        pdf, first = source(year)
        for i,p in enumerate(data['paragraphs']): p['index'] = i
        article = dict(title=f'{year}年考研英语一 Part B · '+data['type'], source=f'考研英语一 {year} · Part B', category='考研真题', date=date.today().isoformat(), id=f'zhenti_{year}_5', article_index=-1, zhenti=dict(year=year,text=5,part='B',type=data['type']), paragraphs=data['paragraphs'], word_count=sum(len(s.split()) for p in data['paragraphs'] for s in p['sentences']), provenance=dict(pdf=pdf.name,pages=list(range(first,first+3)),method='OCR; LLM sentence alignment and translation; original question order'))
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(article,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(f'{year}: saved {article["word_count"]} words / {data["type"]}',flush=True)

async def main():
    import services.pdf_service as pdf_service
    pdf_service._API_LIMITER = asyncio.Semaphore(2)
    parser=argparse.ArgumentParser()
    parser.add_argument('--years', nargs='*',type=int,default=list(range(2007,2026)))
    parser.add_argument('--refresh', action='store_true')
    args=parser.parse_args()
    sem=asyncio.Semaphore(3)
    results=await asyncio.gather(*(run(y,sem,args.refresh) for y in args.years),return_exceptions=True)
    failures=[(y,str(r)) for y,r in zip(args.years,results) if isinstance(r,Exception)]
    if failures: raise SystemExit(str(failures))

if __name__=='__main__': asyncio.run(main())
