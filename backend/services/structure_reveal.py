"""Validated optional reveal graph. Invalid metadata never disables core reading."""
import json
import re
from services.structure_markup import START, END, extract_structure

RULES = '''
为右侧解释中的英文片段增加点击解锁数据：在同一个 CORE_SPANS JSON 中，除 skeleton、spans 外增加 nodes 数组；不另输出第二份 JSON。
格式：{"skeleton":"精简主干","spans":[{"text":"原文主干","occurrence":1}],"nodes":[{"id":"n1","spans":[{"text":"可点击原文片段","occurrence":1}],"meaning":"简短中文解释","depends_on":["core"],"references":[]}]}
core 指 spans 中的整句主干，默认显示。nodes 是其余原文的分层片段，最多12个。每个英文词恰好归属 core 或一个节点，不能重叠、漏词；标点可略。节点 text 必须逐字复制原文，非连续分多个 spans。句首 But/And/Yet 应属于 core，而不是背景节点。
正文中尽量将每个节点的原文片段独占一行，便于直接点击；详细解释仍按前面的可读模板输出，不显示节点id。
depends_on 只列直接前置节点：独立时间地点背景依赖 core，不强制其他片段先展开背景。嵌套修饰从句依赖其修饰对象所在节点，目的依赖所属谓语节点，后续动作依赖 help/allow 等动作节点。必须无环、id存在。
例如 to help children read books and write letters 拆为 to help children 和 read books and write letters 两个节点；后者依赖前者。不把同一动作的并列宾语拆成假层级，repair homes and possibly schools 必须在同一节点。
references 是明确的语法指代，不是所有阅读依赖：[{"source":{"text":"which","occurrence":1},"target":{"text":"原文先行词","occurrence":1},"target_node":"n1","explanation":"中文说明"}]。source 位于当前节点，target 只能位于 core 或前置祖先节点。只标先行词名词短语，不标整个父节点。不确定先行词时 references 留空，在 meaning 说明歧义，不猜测。没有指代时 references=[]。
生成定位前检查 core 与 nodes 不重叠、覆盖全部原文词，所有依赖和指代对象能够先解锁。不可靠时 nodes=[]，仍输出正确的主干 spans 和正文。
'''

def _locate(sentence, spans):
    _, core = extract_structure(START + json.dumps({'spans': spans}) + END, sentence)
    if not core:
        raise ValueError('invalid spans')
    return core['ranges']

def _inside(ranges, owner):
    return all(any(a <= x and y <= b for a, b in owner) for x, y in ranges)

def _ancestors(nid, parents):
    seen, stack = set(), list(parents[nid])
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(parents.get(current, []))
    return seen

def validate_graph(sentence, core, nodes):
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= 12:
        raise ValueError('invalid nodes')
    ranges, parents, result = {'core': core['ranges']}, {'core': []}, []
    for node in nodes:
        nid = node['id']
        if not isinstance(nid, str) or not re.fullmatch(r'n[1-9][0-9]*', nid) or nid in ranges:
            raise ValueError('invalid id')
        if not isinstance(node.get('meaning'), str) or not 1 <= len(node['meaning']) <= 600:
            raise ValueError('invalid meaning')
        deps = node['depends_on']
        if not isinstance(deps, list) or not deps or any(not isinstance(d, str) for d in deps) or len(set(deps)) != len(deps):
            raise ValueError('invalid dependencies')
        ranges[nid] = _locate(sentence, node['spans'])
        parents[nid] = deps
        result.append(dict(id=nid, ranges=ranges[nid], text=' … '.join(s['text'] for s in node['spans']),
                           parts=[s['text'] for s in node['spans']], meaning=node['meaning'], depends_on=deps, references=[]))
    for nid, deps in parents.items():
        if any(d not in parents for d in deps) or nid in _ancestors(nid, parents):
            raise ValueError('invalid dependency graph')
    ordered = sorted(pair for group in ranges.values() for pair in group)
    if any(b > c for (a, b), (c, d) in zip(ordered, ordered[1:])):
        raise ValueError('overlap')
    for word in re.finditer(r"\w+(?:['’\-]\w+)*", sentence):
        a = len(sentence[:word.start()].encode('utf-16-le')) // 2
        b = len(sentence[:word.end()].encode('utf-16-le')) // 2
        if not _inside([[a,b]], ordered):
            raise ValueError('incomplete coverage')
    for node, item in zip(nodes, result):
        refs = node.get('references')
        if not isinstance(refs, list) or len(refs) > 6:
            raise ValueError('invalid references')
        for ref in refs:
            target = ref['target_node']
            if target not in _ancestors(node['id'], parents):
                raise ValueError('target not available')
            source_ranges = _locate(sentence, [ref['source']])
            target_ranges = _locate(sentence, [ref['target']])
            if not _inside(source_ranges, ranges[node['id']]) or not _inside(target_ranges, ranges[target]):
                raise ValueError('reference outside owner')
            if not isinstance(ref.get('explanation'), str) or not 1 <= len(ref['explanation']) <= 600:
                raise ValueError('invalid reference explanation')
            item['references'].append(dict(source=ref['source']['text'], target=ref['target']['text'],
                source_ranges=source_ranges, target_ranges=target_ranges, explanation=ref['explanation']))
    return dict(sentence=sentence, nodes=result)

def extract_reveal(raw, sentence, core):
    if not core:
        return None
    try:
        if START not in raw or END not in raw:
            return None
        data = json.loads(raw.split(START, 1)[1].split(END, 1)[0])
        return validate_graph(sentence, core, data.get('nodes'))
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return None
