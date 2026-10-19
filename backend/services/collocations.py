"""Sentence collocations with validated original-text highlight ranges."""
import json
import re
from services.structure_markup import extract_structure, START as CORE_START, END as CORE_END

START = '<<<COLLOCATIONS>>>'
END = '<<<END_COLLOCATIONS>>>'
PROMPT = """查找整个 sentence 中值得整体理解的固定搭配、短语动词和明确的配对结构，包括不连续表达。
忽略 focus、discussion_topic 和历史话题的目标限制。只查当前句子，不罗列句外例句或其他用法，不生成词义卡，不分析整个句式。
宁缺毋滥：普通相邻词、临时修饰关系、来自不同专名的片段不属于固定搭配；没有明确依据时不合并。最多列出八组，按阅读价值选择，不凑数量。
每组给出搭配名称和简短中文句中义。连续短语用一个原文片段；不连续搭配分为多个片段，排除中间插入的宾语或修饰语。
只输出以下机器格式，不使用 Markdown 或额外正文：
<<<COLLOCATIONS>>>{"items":[{"label":"take ... into account","meaning":"在本句中表示把……考虑在内","spans":[{"text":"take","occurrence":1},{"text":"into account","occurrence":1}]}]}<<<END_COLLOCATIONS>>>
示例仅说明格式，不套用到别的句子。spans.text 必须逐字复制 sentence 中实际出现的完整词或连续词组，保持原有词形、大小写和空格。occurrence 是该片段在原句中从左到右出现的序号，从1开始。片段按原文顺序排列、不重叠。不同搭配可以共享词。
label 可以使用词典原形或省略号，但定位片段绝不能使用原文不存在的原形或省略号。不能确认位置就不列该组。
如果本句没有明确搭配，返回 <<<COLLOCATIONS>>>{"items":[]}<<<END_COLLOCATIONS>>>。"""

def extract_collocations(raw, sentence):
    failed = ('搭配结果未能可靠解析，请重新生成。', None)
    try:
        data = json.loads(raw.split(START, 1)[1].split(END, 1)[0]) if START in raw and END in raw else None
        items = data['items']
        if not isinstance(items, list) or len(items) > 8:
            return failed
        result, seen = [], set()
        for item in items:
            try:
                label, meaning, spans = item['label'], item['meaning'], item['spans']
                if not isinstance(label, str) or not 1 <= len(label.strip()) <= 120 or not isinstance(meaning, str) or not 1 <= len(meaning.strip()) <= 600:
                    continue
                _, core = extract_structure(CORE_START + json.dumps({'spans': spans}) + CORE_END, sentence)
                if not core or len(re.findall(r"[A-Za-z]+(?:['’-][A-Za-z]+)*", ' '.join(s['text'] for s in spans))) < 2:
                    continue
                key = tuple(tuple(pair) for pair in core['ranges'])
                if key in seen:
                    continue
                seen.add(key)
                result.append(dict(label=label.strip(), meaning=meaning.strip(), ranges=core['ranges']))
            except (ValueError, TypeError, KeyError, IndexError):
                continue
        if items and not result:
            return failed
        answer = '\n'.join(str(i+1)+'. '+item['label']+'：'+item['meaning'] for i,item in enumerate(result)) or '本句中未发现明确的固定搭配。'
        if len(result) < len(items):
            answer += '\n部分搭配未能准确定位，已略去。'
        return answer, dict(sentence=sentence, items=result)
    except (ValueError, TypeError, KeyError, IndexError):
        return failed
