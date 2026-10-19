const fs=require('fs'),vm=require('vm'),assert=require('assert');
class Node {
    constructor(tag='div',text=''){this.tag=tag;this.textContent=text;this.children=[];this.attrs={};this.open=true;}
    appendChild(n){this.children.push(n);return n;}
    replaceChildren(...nodes){this.children=nodes;}
    setAttribute(k,v){this.attrs[k]=v;}
    addEventListener(){}
}
const ids=new Map(), get=id=>{if(!ids.has(id))ids.set(id,new Node());return ids.get(id);};
const text=n=>n.textContent+n.children.map(text).join(' ');
const source={id:'s1',article_id:'article_1',word:'take...off',sentence:'They take their coats off.',article_title:'Article',meaning:'〔take...off〕/x/ 常见义答案\n◆ 在本句中\n句中专属答案\n◆ 其他常见义\n其他常见义答案'};
const other={...source,id:'s2',article_id:'article_2',sentence:'They take hats off.'};
let calls=[], reply;
const ctx={document:{getElementById:get,createElement:t=>new Node(t),createTextNode:t=>new Node('text',t),addEventListener(){}},window:{addEventListener(){}},setInterval(){},getToken:()=> 'a',BASE:'/data',handleJson:r=>r.json(),showToast(){},reviewModule:{words:new Map([['take...off',{word:'take...off',sources:[source,other]}]]),render(){},updateCount(){},load(){}},fetch:(url,options)=>{calls.push(JSON.parse(options.body));return Promise.resolve({json:()=>Promise.resolve(reply)});}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('frontend/js/spaced-review.js','utf8'),ctx);
const s=ctx.spacedReview;
const tasks=[source,other].map((source,i)=>({id:'context'+i,kind:'context',source_id:source.id,word_key:'take...off',stage:0,due_at:10,version:0}));
const state={tasks,now:20,available_words:1,new_words:1,mastered:[],round:{id:'global1',selected:['take...off'],pending:['take...off'],completed:[]}};
const settle=()=>new Promise(r=>setImmediate(r));
async function main(){
    s.accept(state);s.running=true;s.choose();
    assert.equal(get('reviewTabs').hidden,false);
    assert.equal(get('vocabularyTitle').textContent,'全局生词回顾');
    assert.equal(s.current.kind,'context');
    assert(text(get('reviewSession')).includes('take...off'));
    assert(!text(get('reviewSession')).includes(source.sentence));
    assert(!text(get('reviewSession')).includes('句中专属答案'));
    s.rate('known');assert.equal(calls.length,0);
    s.revealed=true;s.render();
    assert(text(get('reviewSession')).includes('句中专属答案'));
    assert(!text(get('reviewSession')).includes('常见义答案'));
    assert.equal(get('reviewSession').children.filter(n=>n.tag==='blockquote').length,2);
    const marks=s.sentence(source,source.word).children.filter(n=>n.tag==='mark').map(n=>n.textContent);
    assert.deepEqual(marks,['take','off']);
    reply={review:{...state,tasks:tasks.map(t=>({...t,stage:1,due_at:1000,version:1})),round:{...state.round,pending:[],completed:['take...off']}}};
    s.rate('known');s.rate('known');assert.equal(calls.length,1);
    assert.equal(calls[0].targets.length,2);
    assert.equal(calls[0].round_id,'global1');
    await settle();assert.equal(s.current,null);
    // Article practice has the same reveal flow but only local sources and no global advancement.
    s.state=state;s.articleSession={id:'session1',article_id:'article_1',task_ids:['context0'],completed:[]};
    s.choose();assert.equal(s.articleSources(s.current).length,1);
    assert.equal(get('reviewTabs').hidden,true);
    assert.equal(get('vocabularyTitle').textContent,'本篇打卡回顾');
    assert.equal(get('reviewSession').children.filter(n=>n.tag==='blockquote').length,0);
    s.revealed=true;s.render();
    assert.equal(get('reviewSession').children.filter(n=>n.tag==='blockquote').length,1);
    assert(!text(get('reviewSession')).includes('常见义答案'));
    assert(!text(get('reviewSession')).includes('10 分钟后'));
    assert(!text(get('reviewSession')).includes('明天'));
    reply={review:state,session:{...s.articleSession,completed:[]}};
    s.rate('again');await settle();
    assert.equal(calls[1].combined,true);assert.equal(calls[1].session_id,'session1');
    assert.equal(s.current.id,'context0');assert(!s.revealed);
    assert.equal(s.articleSession.completed.length,0);
    s.revealed=true;
    reply={review:state,session:{...s.articleSession,completed:['context0']}};
    s.rate('known');await settle();
    assert.equal(s.current,null);assert(text(get('reviewSummary')).includes('1/1 词'));
    assert(text(get('reviewSession')).includes('确认打卡'));
    // Unknown words move to the tail, not immediately back onto the same card.
    const extra=['second','third'].map((word,i)=>({id:word,kind:'context',source_id:word,word_key:word,stage:0,due_at:0,version:0}));
    extra.forEach(t=>ctx.reviewModule.words.set(t.word_key,{word:t.word_key,sources:[{...source,id:t.source_id,word:t.word_key}]}));
    s.state={...state,tasks:[tasks[0],...extra]};
    s.articleSession={id:'queue2',article_id:'article_1',task_ids:['context0','second','third'],completed:[]};
    s.choose();assert.equal(s.current.word_key,'take...off');
    s.revealed=true;reply={review:s.state,session:s.articleSession};
    s.rate('again');await settle();assert.equal(s.current.word_key,'second');
    s.revealed=true;reply={review:s.state,session:{...s.articleSession,completed:['second']}};
    s.rate('known');await settle();assert.equal(s.current.word_key,'third');
    s.revealed=true;reply={review:s.state,session:{...s.articleSession,completed:['second','third']}};
    s.rate('known');await settle();assert.equal(s.current.word_key,'take...off');
    assert(!s.revealed);
    // Global rounds obey the server's tail order, with no due-time filtering.
    s.articleSession=null;
    s.state={...state,tasks:[tasks[0],...extra],round:{id:'global2',selected:['second','take...off','third'],pending:['second','take...off','third'],completed:[]}};
    s.choose();assert.equal(s.current.word_key,'second');
    s.revealed=true;
    assert(!text(get('reviewSession')).includes('10 分钟后'));
    reply={review:{...s.state,round:{...s.state.round,pending:['take...off','third','second']}}};
    s.rate('again');await settle();assert.equal(s.current.word_key,'take...off');
    assert.equal(calls[calls.length-1].round_id,'global2');
    s.reset();assert.equal(s.state,null);
    s.render();assert.equal(get('reviewTabs').hidden,false);
    console.log('PASS: word-only front, context-only reveal, grouped sources, single submission, article isolation, completion');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
