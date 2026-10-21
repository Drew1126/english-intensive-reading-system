"""Validate original-text spans independently of the visible explanation."""
import json
import re
from collections import Counter

START = '<<<CORE_SPANS>>>'
END = '<<<END_CORE_SPANS>>>'
RULES = '''
额外的机器定位输出（只在结构分析任务中使用）：完成全部讲解后，最后追加一行：
<<<CORE_SPANS>>>{"skeleton":"与正文首行相同的主干句","spans":[{"text":"原句中连续的主干片段","occurrence":1}]}<<<END_CORE_SPANS>>>
这不是讲解正文。必须使用严格 JSON，无代码围栏。text 必须逐字复制当前 sentence 的原文，包括大小写；occurrence 为该片段在原文中从左到右出现的次数，从 1 开始。优先使用能唯一定位的完整词或连续短语，不用单个字母或标点。片段按原文顺序排列，不重叠，不漏掉主干中的否定、情态、必要补语。非连续成分分成多项，不把省略号写进原文片段。
这里只标记原句中的对应成分，不得使用还原后改变了词形或语序的文字。例如分析时还原了倒装，定位仍须复制原句的动词形式；重复词用 occurrence 区分。原句中全部内容都必要时可以保留全句。不确定主干位置时返回 {"spans":[]}，不能猜测位置。
先确定原文必要成分，再根据这些成分写 skeleton 和正文首行，两者必须一致。每个保留的分句必须保留自己的主语、谓语和必要宾语、补足语；形式主语 it 后的真正主语从句也不能漏掉从句主语。名词短语省略修饰语后必须保留中心名词。
skeleton 中每个未加方括号的英文词都必须与 spans 中的词一一对应（包括重复次数），不得漏标或多标。允许调整语序，但首行保留原文词形，倒装的词形还原另在正文解释。确需补冠词、补省略词时用 [the]、[likes] 这样的方括号明确标记，并在正文说明补词原因；补词不进入 spans，也不能用补词替代原文已有的必要成分。不要为规避定位校验而把原文主语放进方括号。
例如原文 Mary's remarkable story is causing debate. 可输出 skeleton 为 "[The] story is causing debate."，spans 为 story 和 is causing debate；story 绝不能因新增 [The] 而漏标。并列省略 Tom likes tea, and Mary coffee. 可写 "Tom likes tea, and Mary [likes] coffee."，定位只包含原文中的成分。
并列骨架中的 and、or、but 等连接词同样必须进入 spans，不只标主语和动词。上述并列省略示例的 spans 可直接取 Tom likes tea, and Mary coffee。不要把原文已有的否定词、助动词或连接词当成补词。提交前逐词对照 skeleton 和 spans，包括冠词、所有格、连接词及重复次数。
正文首行因句首需要可以大写，但 spans.text 绝不能照抄首行的大写形式：例如原文 A turbulent environment has managers cautious. 的定位是 environment（小写），不是 Environment。请从 sentence 复制，不从 skeleton 复制。
skeleton 是用于定位的原文骨架，不是后文“还原理解”的改写句。spans 仅含核心成分；已判为普通修饰或强调框架的内容不要重新带入 spans。新增的冠词或省略词只存在于 skeleton 的方括号内，不得在原文中寻找另一个同名词替代。
JSON 的 skeleton 必须逐字使用正文第一行已经精简的整句主干，不能扩展回原句或把后文的片段内部主干并入；spans 只定位该精简骨架。定位输出不是另做一次主干分析。
每次结构回答在全部解释之后必须输出完整的 CORE_SPANS 和 END_CORE_SPANS 标记及 JSON；包括简单句和强调句也不能漏掉。解释的段落、加粗、缩进只影响正文，不影响这一机器定位协议。
'''

def extract_structure(raw, sentence, require_skeleton=False):
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
        if require_skeleton:
            skeleton = data.get('skeleton')
            if not isinstance(skeleton, str) or not skeleton.strip() or '\n' in skeleton:
                return answer.rstrip(), None
            # Added words are explanation-only; all other words must be highlighted.
            original = re.sub(r'\[[^\[\]]+\]', '', skeleton)
            if '[' in original or ']' in original:
                return answer.rstrip(), None
            def words(value):
                return Counter(re.findall(r"[\w]+(?:['’][\w]+)*", value.casefold()))
            located = ' '.join(span['text'] for span in spans)
            if not words(original) or words(original) != words(located):
                return answer.rstrip(), None
            # The displayed skeleton and the validated locations share one source.
            lines = answer.strip().splitlines()
            answer = skeleton.strip() + ('\n' + '\n'.join(lines[1:]) if len(lines) > 1 else '')
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


def extract_structure_aligned(raw, sentence):
    """Repair location metadata only when the skeleton has ONE source alignment.

    Does not infer grammar, stem words, invent tokens, or choose among repeated
    occurrences. Existing valid occurrence-qualified metadata stays authoritative.
    """
    answer, core = extract_structure(raw, sentence, require_skeleton=True)
    if core:
        return answer, core
    try:
        if START not in raw or END not in raw or len(sentence) > 20000:
            return answer, None
        data = json.loads(raw.split(START, 1)[1].split(END, 1)[0])
        skeleton = data.get('skeleton')
        if not isinstance(skeleton, str) or not skeleton.strip() or len(skeleton) > 5000 or '\n' in skeleton:
            return answer, None
        # Empty spans explicitly mean the model could not identify the structure.
        if not isinstance(data.get('spans'), list) or not data['spans']:
            return answer, None
        original = re.sub(r'\[[^\[\]]+\]', '', skeleton)
        if '[' in original or ']' in original:
            return answer, None
        pattern = r"[\w]+(?:['’\-][\w]+)*"
        source = list(re.finditer(pattern, sentence))
        target = re.findall(pattern, original)
        if not target or len(target) > 300 or len(source) > 2000:
            return answer, None
        normalize = lambda word: word.casefold().replace('’', "'")
        a = [normalize(token.group()) for token in source]
        b = [normalize(token) for token in target]
        # Count all monotonic subsequence paths, capped at two (ambiguous).
        ways = [[0] * (len(a) + 1) for _ in range(len(b) + 1)]
        ways[-1] = [1] * (len(a) + 1)
        for i in range(len(b)-1, -1, -1):
            for j in range(len(a)-1, -1, -1):
                ways[i][j] = min(2, ways[i][j+1] + (ways[i+1][j+1] if a[j] == b[i] else 0))
        if ways[0][0] != 1:
            return answer, None
        selected = []
        i = j = 0
        while i < len(b):
            if a[j] == b[i] and ways[i+1][j+1]:
                selected.append(source[j].span())
                i += 1
            j += 1
        # Merge adjacent words; preserve original punctuation and UTF-16 offsets.
        merged = []
        for start, end in selected:
            if merged and not re.search(pattern, sentence[merged[-1][1]:start]):
                merged[-1][1] = end
            else:
                merged.append([start, end])
        ranges = [[len(sentence[:start].encode('utf-16-le'))//2,
                   len(sentence[:end].encode('utf-16-le'))//2] for start, end in merged]
        lines = raw.split(START, 1)[0].strip().splitlines()
        answer = skeleton.strip() + ('\n' + '\n'.join(lines[1:]) if len(lines) > 1 else '')
        return answer, {'sentence': sentence, 'ranges': ranges}
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return answer, None
