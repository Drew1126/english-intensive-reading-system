const assert=require('assert'), fs=require('fs'), vm=require('vm');
const ctx={}; vm.createContext(ctx); vm.runInContext(fs.readFileSync('frontend/js/structure-reveal.js','utf8'),ctx);
const mod=ctx.structureReveal;
const relative={text:'in which organizations and officials use the power of group dynamics',parts:['in which organizations and officials use the power of group dynamics']};
assert.equal(mod.matchLine(relative,relative.text),'exact');
assert.equal(mod.matchLine(relative,'organizations and officials use the power of group dynamics.'),'clause-body');
assert.equal(mod.matchLine(relative,'officials use the power of group dynamics'),null);
assert.equal(mod.matchLine(relative,'organizations and officials use power'),null);
assert.equal(mod.matchLine({...relative,parts:['in which','organizations and officials use the power of group dynamics']},'organizations and officials use the power of group dynamics'),null);
assert.equal(mod.matchLine({text:'to help people repair homes',parts:['to help people repair homes']},'people repair homes'),null);
const entry={ranges:[[0,3]],opened:new Set(),enabled:true,reveal:{nodes:[
 {id:'n1',ranges:[[4,8]],depends_on:['core']},
 {id:'n2',ranges:[[9,14]],depends_on:['n1']},
 {id:'n3',ranges:[[15,20]],depends_on:['n2']},
 {id:'background',ranges:[[21,25]],depends_on:['core']}
]}};
assert(!mod.change(entry,'n2'));
assert(mod.change(entry,'background'));
assert(mod.change(entry,'n1')); assert(mod.change(entry,'n2')); assert(mod.change(entry,'n3'));
assert.equal(entry.relation,'n3');
assert.equal(mod.project(entry).length,5);
assert(mod.change(entry,'n1'));
assert.deepEqual([...entry.opened],['background']);
assert.equal(entry.relation,null);
assert(!mod.change(entry,'n3'));
entry.enabled=false; mod.change(entry,'n1'); assert(entry.enabled);
const target={articleId:'a',sentence:'text',el:{isConnected:true,textContent:'text'}};
const binding={target,answerEl:{isConnected:true},token:'one',key:'key',ticket:3,entry};
entry.ticket=3; entry.status='ready';
ctx.getToken=()=> 'one'; ctx.articleModule={currentArticle:{id:'a'},editing:false};
ctx.structureFocus={cache:new Map([['key',entry]]),key:()=> 'key'};
assert(mod.validBinding(binding));
ctx.getToken=()=> 'two'; assert(!mod.validBinding(binding)); ctx.getToken=()=> 'one';
entry.ticket=4; assert(!mod.validBinding(binding)); entry.ticket=3;
target.el.textContent='modified'; assert(!mod.validBinding(binding)); target.el.textContent='text';
ctx.articleModule.editing=true; assert(!mod.validBinding(binding));
console.log('PASS: dependency locks, independent background, projection, cascading collapse, account/ticket/edit guards');
