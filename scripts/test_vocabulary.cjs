const fs = require('fs'), vm = require('vm'), assert = require('assert');
let token = 'a', saved, selected;
const elements = new Map();
function el(id) { if (!elements.has(id)) elements.set(id, {textContent:'', close(){}, replaceChildren(){}, disabled:false}); return elements.get(id); }
const target = {dataset:{idx:'0-0'},textContent:'Original sentence.',classList:{add(){selected=true;},remove(){}},scrollIntoView(){}};
const context = {getToken:()=>token, showToast:()=>{}, document:{getElementById:el,querySelectorAll:()=>[target]}, window:{}, homeModule:{showReader(){}}, articleModule:{currentArticle:{id:'zhenti_2010_5'}}, agentModule:{clearFocus(){},showSelectedSentence(){}}};
vm.createContext(context);vm.runInContext(fs.readFileSync('frontend/js/review.js','utf8'),context);
const r=context.reviewModule;r.save=(entries,t)=>{saved={entries,t};};r.accountToken='a';
const source={article_id:'zhenti_2010_5',article_title:'Part B',sentence:'Original sentence.',sentence_idx:'0-0'};
const question='解释选中内容在句子释义';
r.recordAnswer('turbulent...cloud',question,'〔turbulent〕/a/ meaning1 〔cloud〕/b/ meaning2',source,'a');
assert.equal(saved.entries.length,2);assert(!saved.entries[0].meaning.includes('meaning2'));assert.equal(saved.entries[1].sentence,source.sentence);
r.recordAnswer('take...off',question,'〔take...off〕/a/ phrase',source,'a');assert.equal(saved.entries.length,1);
saved=null;token='b';r.recordAnswer('cloud',question,'〔cloud〕/a/ meaning',source,'a');assert.equal(saved,null);
token='a';r.words.set('cloud',{word:'cloud',sources:[source]});r.reset();assert.equal(r.words.size,1);
r.locate(source);assert(selected);assert.equal(context.window.__currentIdx,'0-0');
token='';r.syncAccount();assert.equal(r.words.size,0);
console.log('PASS: separated cards, discontinuous phrase, source snapshot, stale-account rejection, article reset preservation, sentence selection, logout clearing');
