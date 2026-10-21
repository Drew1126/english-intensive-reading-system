const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
class Node {
  constructor(tag, value = '') { this.tag = tag; this.value = value; this.children = []; this.dataset = {}; this.classes = new Set(); this.classList = { add: x => this.classes.add(x), toggle: (x,on) => on ? this.classes.add(x) : this.classes.delete(x) }; }
  set textContent(t) { this.children = []; this.value = t; }
  get textContent() { return this.value + this.children.map(x => x.textContent).join(''); }
  appendChild(n) { this.children.push(n); return n; }
  replaceChildren() { this.children = []; this.value = ''; }
}
const document = {createElement: t => new Node(t), createTextNode: t => new Node('#text', t)};
const context = vm.createContext({document});
vm.runInContext(fs.readFileSync('frontend/js/agent.js', 'utf8'), context);
const el = new Node('div');
const text = 'Officials use group power.\n官员利用群体力量。\n\n◆ 难点拆解：为了什么？\n↳ **帮助谁？**\nto help individuals\n帮助个人。\n\n↳↳ **做什么？**\nimprove their lives\n改善生活。\n\n◆ 整句翻译\n<img src=x onerror=alert(1)> **重点**';
context.agentModule.renderAnswer(el, text, true);
assert.equal(el.dataset.rawAnswer, text);
assert(el.classes.has('structure-answer'));
assert.equal(el.children[0].textContent, '句子主干');
assert(el.children.some(n => n.classes.has('structure-depth-2') && n.textContent.includes('改善生活')));
assert(el.children.some(n => n.tag === 'h4' && n.textContent === '整句翻译'));
assert(el.children.some(n => n.classes.has('structure-question') && n.textContent.includes('帮助谁')));
assert(el.children.some(n => n.classes.has('structure-english') && n.textContent === 'to help individuals'));
assert(el.children.some(n => n.classes.has('structure-explanation') && n.textContent === '帮助个人。'));
assert(el.children.some(n => n.classes.has('structure-skeleton') && n.textContent === 'Officials use group power.'));
assert(el.children.some(n => n.children.some(c => c.tag === 'strong' && c.textContent === '重点')));
const all = n => [n, ...n.children.flatMap(all)];
assert(!all(el).some(n => ['img','script','a'].includes(n.tag)));
assert(el.textContent.includes('<img src=x onerror=alert(1)>'));
context.agentModule.renderAnswer(el, '普通词汇回答\n第二行', false);
assert.equal(el.textContent, '普通词汇回答\n第二行');
assert(!el.classes.has('structure-answer'));
console.log('PASS: headings, bold, two-level indentation, paragraphs, raw copy, HTML safety and plain-answer fallback');
