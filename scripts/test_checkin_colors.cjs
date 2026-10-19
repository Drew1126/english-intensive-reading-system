const fs=require('fs'),vm=require('vm'),assert=require('assert');
const context={document:{createElement:()=>({style:{}})}};
vm.createContext(context);vm.runInContext(fs.readFileSync('frontend/js/checkin.js','utf8'),context);
let previous=101;
for(let count=1;count<=10;count++){
    const badge=context.checkinModule.badge(count);
    const light=Number(badge.style.backgroundColor.match(/, (\d+)%\)$/)[1]);
    assert(light<previous);previous=light;
    assert(badge.textContent.includes(String(count)));
}
console.log('PASS: check-in count labels and progressively darker colors');
const moduleUnderTest=context.checkinModule;
let caption=null;
const cell={dataset:{heatmapCheckin:'true',readingLabel:'2026 阅读 1'},style:{},attrs:{},
    querySelector:s=>s==='.home-cell-count'?caption:null,
    appendChild:n=>{caption=n;},setAttribute(k,v){this.attrs[k]=v;}};
moduleUnderTest.counts={article_1:2};moduleUnderTest.paint(cell,'article_1');
assert.equal(cell.style.backgroundColor,moduleUnderTest.colors(2).background);
assert.equal(caption.textContent,'2 次');assert(cell.attrs['aria-label'].includes('打卡 2 次'));
moduleUnderTest.counts={article_1:10};moduleUnderTest.paint(cell,'article_1');
assert.equal(cell.style.color,'#ffffff');assert.equal(caption.textContent,'10 次');
moduleUnderTest.counts={};moduleUnderTest.paint(cell,'article_1');
assert.equal(cell.style.backgroundColor,'');assert.equal(cell.style.color,'');
assert.equal(caption.textContent,'未打卡');
console.log('PASS: whole-cell fill, dark-cell text, count updates and account reset');
const mini={dataset:{miniCheckin:'true',readingLabel:'2024 阅读 1'},style:{},querySelector:()=>null,setAttribute(){}};
moduleUnderTest.counts={article_1:5};moduleUnderTest.paint(mini,'article_1');
assert.equal(mini.style.backgroundColor,moduleUnderTest.colors(5).background);
assert(mini.title.includes('打卡 5 次'));
moduleUnderTest.counts={};moduleUnderTest.paint(mini,'article_1');
assert.equal(mini.style.backgroundColor,'');assert(mini.title.includes('未打卡'));
