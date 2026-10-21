import copy
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from services.structure_markup import START, END, extract_structure
from services.structure_reveal import validate_graph, extract_reveal

sentence = 'She uses funds to help people repair homes.'
span = lambda text: {'text':text, 'occurrence':1}
core = extract_structure(START + json.dumps({'spans':[span('She uses funds')]}) + END, sentence)[1]
nodes = [
    dict(id='n1', spans=[span('to help people')], meaning='帮助人们', depends_on=['core'], references=[]),
    dict(id='n2', spans=[span('repair homes')], meaning='修理房屋', depends_on=['n1'], references=[]),
]
graph = validate_graph(sentence, core, nodes)
assert graph['nodes'][1]['depends_on'] == ['n1']
assert graph['nodes'][1]['ranges'] == [[sentence.index('repair'), len(sentence)-1]]
for modify in [
    lambda n: n[0].update(depends_on=['n2']),
    lambda n: n[0].update(depends_on=['unknown']),
    lambda n: n[1].update(spans=[span('homes')]),
    lambda n: n[1].update(spans=[span('people repair homes')]),
    lambda n: n[1].update(references=[dict(source=span('repair'),target=span('homes'),target_node='core',explanation='错误')]),
]:
    bad=copy.deepcopy(nodes); modify(bad)
    raw=START+json.dumps({'nodes':bad})+END
    assert extract_reveal(raw,sentence,core) is None
assert extract_reveal('ordinary answer',sentence,core) is None
assert extract_reveal(START+'[]'+END,sentence,core) is None
assert extract_reveal(START+json.dumps({'nodes':nodes})+END,sentence,None) is None
assert extract_reveal(START+json.dumps({'nodes':nodes})+END,sentence,core)
print('PASS: optional graph, coverage, overlaps, cycles, invalid references and safe fallback')
