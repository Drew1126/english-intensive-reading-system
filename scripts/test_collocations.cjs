const assert=require('assert'),fs=require('fs'),vm=require('vm');
class El {
    constructor(text=''){this.text=text;this.childNodes=[];this.attrs={};this.dataset={idx:'0-0'};this.isConnected=true;this.selected=false;this.classList={add:()=>this.selected=true,remove:()=>this.selected=false};}
    get textContent(){return this.childNodes.length?this.childNodes.map(n=>n.textContent).join(''):this.text;}
    set textContent(t){this.text=t;this.childNodes=[];}
    appendChild(n){this.childNodes.push(n);}
    replaceChildren(f){this.childNodes=f.childNodes.slice();}
    setAttribute(k,v){this.attrs[k]=v;}
    addEventListener(k,fn){this[k]=fn;}
    scrollIntoView(){}
}
const sentence=new El();sentence.childNodes=[new El('They '),new El('took'),new El(' costs '),new El('into '),new El('account.')];sentence.selected=true;
const button=new El(), registry=new Map(), toasts=[];
const document={
    querySelector:()=>sentence.selected?sentence:null,querySelectorAll:s=>s.endsWith('.selected')?(sentence.selected?[sentence]:[]):[sentence],
    getElementById:()=>button,createElement:()=>new El(),createDocumentFragment:()=>new El(),addEventListener(){},
    createTreeWalker(el){let i=0;return {nextNode:()=>el.childNodes[i++]||null};},
    createRange:()=>({setStart(n,i){this.start=[n,i];},setEnd(n,i){this.end=[n,i];}})
};
const articleModule={currentArticle:{id:'a'},editing:false,focusWords:[],clearWordHighlight(){}};
const ctx={document,articleModule,agentModule:{showSelectedSentence(){},selectedFocusWord:''},window:{},NodeFilter:{SHOW_TEXT:4},CSS:{highlights:registry},Highlight:class{constructor(...ranges){this.ranges=ranges;}},showToast:t=>toasts.push(t)};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync('frontend/js/structure-focus.js','utf8'),ctx);
vm.runInContext(fs.readFileSync('frontend/js/collocations.js','utf8'),ctx);
const mod=ctx.collocationModule, text=sentence.textContent, nodes=sentence.childNodes.slice();
const target=mod.capture('a',text),item={label:'take ... into account',meaning:'考虑',ranges:[[5,9],[16,28]]};
assert(target);mod.sync();assert(!button.disabled);
const answer=new El(),request={sentence:text,collocationTarget:target,collocations:{sentence:text,items:[item]},answerEl:answer};
mod.render(request);assert.equal(answer.childNodes.length,2);
const link=answer.childNodes[1].childNodes[0];
link.click();assert.equal(link.attrs['aria-pressed'],'true');
assert.equal(registry.get('sentence-collocation').ranges.length,2);
assert.equal(registry.get('sentence-collocation').ranges[1].end[0],nodes[4]);
assert.equal(registry.get('sentence-collocation').ranges[1].end[1],7);
assert.equal(sentence.textContent,text);assert.deepEqual(sentence.childNodes,nodes);
link.click();assert.equal(registry.size,0);assert.equal(link.attrs['aria-pressed'],'false');
link.click();sentence.selected=false;mod.sync();assert.equal(registry.size,0);assert(button.disabled);
sentence.selected=true;articleModule.currentArticle={id:'other'};link.click();assert(toasts.length);assert.equal(registry.size,0);
articleModule.currentArticle={id:'a'};sentence.isConnected=false;link.click();assert.equal(registry.size,0);
sentence.isConnected=true;articleModule.editing=true;mod.sync();assert(button.disabled);
articleModule.editing=false;sentence.childNodes[1].textContent='changed';link.click();assert.equal(registry.size,0);
console.log('PASS: safe cards, exact ranges across text nodes, toggle, no article mutation, stale article/edit rejection and selection cleanup');
