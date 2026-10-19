import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from services.structure_markup import extract_structure, START, END

def parse(sentence, spans):
    return extract_structure('Explanation\n' + START + json.dumps({'spans': spans}) + END, sentence)

sentence = 'A turbulent environment also has managers cautious.'
spans = [{'text': t, 'occurrence': 1} for t in ['environment', 'has managers cautious']]
answer, core = parse(sentence, spans)
assert answer == 'Explanation'
assert [sentence[a:b] for a, b in core['ranges']] == ['environment', 'has managers cautious']
assert parse('It is what it is.', [{'text':'is', 'occurrence':2}])[1]['ranges'] == [[14,16]]
assert parse('😀 He works.', [{'text':'He works', 'occurrence':1}])[1]['ranges'] == [[3,11]]
for bad in [
    [{'text':'Environment', 'occurrence':1}],
    [{'text':'ment', 'occurrence':1}],
    [{'text':'environment', 'occurrence':True}],
    [{'text':'has', 'occurrence':2}],
    [{'text':'has', 'occurrence':1}, {'text':'environment', 'occurrence':1}],
    [], None, [None], ['invalid']
]:
    assert parse(sentence, bad)[1] is None, bad
for raw in ['Explanation', 'Explanation<<<CORE', 'Explanation' + START + '{', 'Explanation' + START + '{}' + END]:
    assert extract_structure(raw, sentence) == ('Explanation', None)
print('Structure markup: original spans, occurrences, Unicode and malformed metadata passed')
