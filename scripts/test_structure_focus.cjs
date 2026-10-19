const assert = require('assert'), fs = require('fs'), vm = require('vm');
class El {
    constructor(text='') { this.text = text; this.children = []; this.dataset = {idx:'0-0'}; this.attrs = {}; }
    get textContent() { return this.children.length ? this.children.map(x=>x.textContent).join('') : this.text; }
    set textContent(text) { this.text=text; this.children=[]; }
    appendChild(el) { this.children.push(el); }
    replaceChildren(el) { this.text=''; this.children=el.children.slice(); }
    setAttribute(k,v) { this.attrs[k]=v; }
}
const sentence = new El(' A turbulent environment also has managers cautious. ');
const button = new El();
let selected=sentence, highlighted=0;
const document = {
    querySelector:()=>selected, querySelectorAll:()=>[sentence],
    getElementById:()=>button, addEventListener:()=>{},
    createElement:()=>new El(), createTextNode:t=>new El(t), createDocumentFragment:()=>new El()
};
const articleModule = {currentArticle:{id:'test'}, editing:false, focusWords:[],
    highlightWordAtOffset:()=>highlighted++};
const ctx={document,articleModule};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync('frontend/js/structure-focus.js','utf8'),ctx);
const focus=ctx.structureFocus, original=sentence.textContent, text=original.trim();
const core={sentence:text,ranges:[[12,23],[29,50]]};
focus.init(); assert(button.disabled);
assert.equal(focus.begin('test',text,'解释词义'),null);
let task=focus.begin('test',text,'解释句子结构');
assert(button.disabled);
focus.complete(task,core);
assert(!button.disabled); assert.equal(button.attrs['aria-pressed'],'true');
assert.equal(sentence.textContent,original);
assert(sentence.children.some(x=>x.className==='structure-muted'));
button.onclick(); assert.equal(button.attrs['aria-pressed'],'false');
assert(!sentence.children.some(x=>x.className==='structure-muted'));
articleModule.focusWords=[{sentenceEl:sentence,offset:3,word:'turbulent'}];
button.onclick(); assert(highlighted>0);
selected=null; focus.sync();
assert(button.disabled); assert.equal(sentence.textContent,original);
selected=sentence; focus.sync(); assert.equal(button.attrs['aria-pressed'],'true');
task=focus.begin('test',text,'解释句子结构'); focus.fail(task); focus.complete(task,core);
assert(button.disabled); assert.equal(focus.active,null);
const old=focus.begin('test',text,'解释句子结构');
const latest=focus.begin('test',text,'解释句子结构');
focus.complete(old,core); assert(button.disabled);
focus.complete(latest,core); assert(!button.disabled);
articleModule.editing=true; focus.sync(); assert(button.disabled); assert.equal(focus.active,null);
articleModule.editing=false; articleModule.currentArticle={id:'other'}; focus.sync(); assert(button.disabled);
assert(!focus.valid({sentence:text,ranges:[[2,1]]},text));
assert(!focus.valid({sentence:text,ranges:[[0,4],[3,5]]},text));
assert(!focus.valid({sentence:'other',ranges:[[0,4]]},text));
console.log('Structure focus: toggle, exact text, selection, highlighting hook, cancellation and stale response passed');
