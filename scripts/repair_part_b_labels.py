"""Apply source-page-reviewed label corrections to the initial OCR import."""
import asyncio
import json
import re
from import_part_b import CACHE, OUTPUT_DIR, run, validate

def label(p, letter):
    for key in ('sentences', 'translations'):
        p[key][0] = '[' + letter + '] ' + re.sub(r'^(?:[\[({][A-H][\])}]|[A-H]\.)\s*', '', p[key][0])
    return p

async def main():
    for year in range(2007, 2026):
        candidate = CACHE / str(year) / 'candidate.json'
        data = json.loads(candidate.read_text(encoding='utf-8'))
        if data.get('labels_reviewed'):
            continue
        ps = data['paragraphs']
        if year in (2010, 2011, 2014):
            indices = {2010:[3,4,5,6,8,9,10],2011:[4,5,6,7,9,10,11],2014:[4,5,6,7,11,12,13]}[year]
            ps = [ps[0]] + [label(ps[i], letter) for i,letter in zip(indices,'ABCDEFG')]
            data['type'] = '段落排序'
        elif year == 2009:
            ps = ps[:7] + [label(ps[i], letter) for i,letter in zip(range(8,15),'ABCDEFG')]
        if year == 2024:
            data['type'] = '信息匹配'
        # Ordering diagrams are represented as text. Source-fixed positions are
        # retained; no answers are supplied for the numbered blanks.
        diagrams = {
            2010:'41 → 42 → 43 → 44 → E → 45',
            2011:'G → 41 → 42 → E → 43 → 44 → 45',
            2014:'41 → A → 42 → E → 43 → 44 → 45',
            2017:'D → 41 → 42 → 43 → 44 → B → 45',
            2018:'41 → C → 42 → 43 → F → 44 → 45',
            2019:'41 → 42 → F → 43 → 44 → C → 45',
            2023:'41 → A → 42 → E → 43 → H → 44 → 45',
            2025:'41 → 42 → C → 43 → H → 44 → A → 45',
        }
        if year in diagrams:
            if year not in (2010,2011,2014):
                ps = ps[:-1]
            ps.append({'sentences':[diagrams[year]],'translations':[diagrams[year]]})
        data['paragraphs'] = ps
        validate(data)
        data['labels_reviewed'] = True
        candidate.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        output = OUTPUT_DIR / str(year) / 'text_5.json'
        if output.exists():
            article = json.loads(output.read_text(encoding='utf-8'))
            for i,p in enumerate(ps): p['index']=i
            article['paragraphs']=ps
            article['zhenti']['type']=data['type']
            article['title']=f'{year}年考研英语一 Part B · '+data['type']
            article['word_count']=sum(len(s.split()) for p in ps for s in p['sentences'])
            output.write_text(json.dumps(article,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        else:
            await run(year,asyncio.Semaphore(1))
        print(year, 'validated', flush=True)

if __name__=='__main__': asyncio.run(main())
