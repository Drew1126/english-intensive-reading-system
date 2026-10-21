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

def strict(sentence, skeleton, texts):
    raw = 'Old first line\nExplanation retained\n' + START + json.dumps({
        'skeleton': skeleton,
        'spans': [{'text': text, 'occurrence': 1} for text in texts]
    }) + END
    return extract_structure(raw, sentence, require_skeleton=True)

sentence = "It's no surprise that Jennifer Senior’s insightful, provocative magazine cover story is arousing much chatter—nothing gets people talking like the suggestion."
skeleton = "It's no surprise that [the] story is arousing chatter—nothing gets people talking."
texts = ["It's no surprise that", 'story', 'is arousing', 'chatter', 'nothing gets people talking']
answer, core = strict(sentence, skeleton, texts)
assert core is not None and answer == skeleton + '\nExplanation retained'
assert 'story' in [sentence[a:b] for a, b in core['ranges']]
assert strict(sentence, skeleton, [text for text in texts if text != 'story'])[1] is None
assert strict(sentence, skeleton.replace('[the]', 'the'), texts)[1] is None
assert strict('Tom likes tea, and Mary coffee.', 'Tom likes tea, and Mary [likes] coffee.', ['Tom likes tea, and Mary coffee'])[1]
assert strict('Birds fly.', 'Birds Birds fly.', ['Birds fly'])[1] is None
assert strict('Birds fly.', '[Birds fly.]', ['Birds fly'])[1] is None
assert extract_structure('Explanation' + START + json.dumps({'spans': texts}) + END, sentence, require_skeleton=True)[1] is None
print('Structure consistency: added words, omitted subject, repeated words and shared display passed')

# Simplified wording is explanation-only, never a source for original highlights.
from services.structure_markup import extract_structure_aligned
sentence = 'That he survived was a miracle.'
explanation = sentence + '\n◆ 简化表达（辅助改写，非原文）\nHis survival was a miracle.\nThat he survived → His survival：他活下来这件事。'
raw = explanation + '\n' + START + json.dumps({'skeleton': sentence, 'spans': [{'text': sentence, 'occurrence': 1}]}) + END
answer, core = extract_structure_aligned(raw, sentence)
assert answer == explanation
assert core['ranges'] == [[0, len(sentence)]]
raw = explanation + '\n' + START + json.dumps({'skeleton': 'His survival was a miracle.', 'spans': [{'text': 'His survival was a miracle.', 'occurrence': 1}]}) + END
assert extract_structure_aligned(raw, sentence)[1] is None
print('Simplified expression: explanation preserved, paraphrase cannot replace source highlights')
