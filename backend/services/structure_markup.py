"""Validate original-text spans independently of the visible explanation."""
import json
import re

START = '<<<CORE_SPANS>>>'
END = '<<<END_CORE_SPANS>>>'
RULES = '''
额外的机器定位输出（只在结构分析任务中使用）：完成全部讲解后，最后追加一行：
<<<CORE_SPANS>>>{"spans":[{"text":"原句中连续的主干片段","occurrence":1}]}<<<END_CORE_SPANS>>>
这不是讲解正文。必须使用严格 JSON，无代码围栏。text 必须逐字复制当前 sentence 的原文，包括大小写；occurrence 为该片段在原文中从左到右出现的次数，从 1 开始。优先使用能唯一定位的完整词或连续短语，不用单个字母或标点。片段按原文顺序排列，不重叠，不漏掉主干中的否定、情态、必要补语。非连续成分分成多项，不把省略号写进原文片段。
这里只标记原句中的对应成分，不得使用还原后改变了词形或语序的文字。例如分析时还原了倒装，定位仍须复制原句的动词形式；重复词用 occurrence 区分。原句中全部内容都必要时可以保留全句。不确定主干位置时返回 {"spans":[]}，不能猜测位置。
'''

def extract_structure(raw, sentence):
    if START not in raw:
        # Hide a truncated protocol marker instead of leaking it into the explanation.
        return raw.split('<<<CORE')[0].rstrip(), None
    answer, metadata = raw.split(START, 1)
    try:
        if END not in metadata:
            return answer.rstrip(), None
        data = json.loads(metadata.split(END, 1)[0])
        spans = data['spans']
        if not isinstance(spans, list) or not 1 <= len(spans) <= 80:
            return answer.rstrip(), None
        ranges = []
        last = 0
        for span in spans:
            text, occurrence = span['text'], span['occurrence']
            if not isinstance(text, str) or not text or not re.search(r'\w', text) or type(occurrence) is not int or occurrence < 1:
                return answer.rstrip(), None
            matches = list(re.finditer(re.escape(text), sentence))
            if occurrence > len(matches):
                return answer.rstrip(), None
            start, end = matches[occurrence - 1].span()
            if start < last or (start and (sentence[start-1].isalnum() or sentence[start-1] in "_'-’") and text[0].isalnum()) or (end < len(sentence) and (sentence[end].isalnum() or sentence[end] in "_'-’") and text[-1].isalnum()):
                return answer.rstrip(), None
            # Browser indices use UTF-16 code units, unlike Python indices.
            ranges.append([len(sentence[:start].encode('utf-16-le'))//2, len(sentence[:end].encode('utf-16-le'))//2])
            last = end
        return answer.rstrip(), {'sentence': sentence, 'ranges': ranges}
    except (ValueError, TypeError, KeyError, IndexError):
        return answer.rstrip(), None
