const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
class Element {
    constructor(tag = 'div') { this.tag = tag; this.dataset = {}; this.children = []; this.attrs = {}; this.value = ''; this.events = {}; this.classes = new Set(); this.classList = { add: (...names) => names.forEach(n => this.classes.add(n)), remove: (...names) => names.forEach(n => this.classes.delete(n)) }; }
    appendChild(child) { if (child.parent) child.parent.children=child.parent.children.filter(n=>n!==child); child.parent=this; child.isConnected=true; this.children.push(child); if (this.tag === 'select' && !this.value) this.value = String(child.value); return child; }
    replaceChildren(...children) { this.children = children; if (this.tag === 'select') this.value = ''; }
    setAttribute(name, value) { this.attrs[name] = value; }
    removeAttribute(name) { delete this.attrs[name]; }
    addEventListener(name, action) { this.events[name] = action; }
    querySelector(selector) { return this.children.find(e => e.className === selector.slice(1)); }
    scrollIntoView() { this.scrolled = true; }
    focus() { this.focused = true; }
}
const ids = {};
const document = { body: new Element(), querySelector: () => null, createElement: tag => new Element(tag), getElementById: id => ids[id] || (ids[id] = new Element(id === 'homeYear' ? 'select' : 'div')) };
let calls = [], fail = false, admin = false;
const api = { getZhentiList: async () => { if (fail) throw Error('offline'); return { years: [{ year: 2024, text1: true, text5: true }, { year: 2025, text1: true }] }; }, getArticleList: async () => ({ articles: [{ index: 7, title: '<b>plain text</b>', word_count: 400 }] }) };
const articleModule = { loadZhenti: (...args) => calls.push(args), loadByIndex: index => calls.push(index), currentArticle: null, isLoading: false };
const context = { document, api, articleModule, getToken: () => '', isAdmin:()=>admin, window: { dispatchEvent: () => {} }, Event: function() {} };
vm.createContext(context);
vm.runInContext(fs.readFileSync('frontend/js/home.js', 'utf8'), context);
const home = context.homeModule;
const settle = () => new Promise(resolve => setImmediate(resolve));
(async () => {
    home.init(); await settle();
    assert(document.body.classes.has('home-active'));
    assert.equal(home.yearNodes.length, 2);
    const latest=home.yearNodes[0], earlier=home.yearNodes[1];
    assert.equal(latest.id,'homeYear-2025');
    assert.equal(earlier.id,'homeYear-2024');
    assert.equal(latest.tag,'details'); assert.equal(latest.children[0].tag,'summary');
    assert.equal(latest.open,true); assert.equal(earlier.open,true);
    assert.equal(latest.children[1].children[0].dataset.heatmapCheckin,'true');
    assert.equal(latest.children[1].children.length,5);
    assert(latest.children[1].children[4].disabled);
    latest.children[1].children[0].events.click(); assert.deepEqual(calls[0], [2025, 1]);
    earlier.open=true;earlier.events.toggle();
    latest.open=false;latest.events.toggle();
    assert.equal(home.closedYearGrid.children[0],latest);
    assert.equal(latest.children[0].children[2].children.length,5);
    assert.equal(home.closedYearArea.hidden,false);
    earlier.children[1].children[4].events.click(); assert.deepEqual(calls[1], [2024, 5]);
    home.showReader(); assert(!document.body.classes.has('home-active'));
    articleModule.currentArticle = { title: 'Keep discussion' }; home.show(); await settle();
    assert.equal(ids.homeResume.hidden, false); assert.equal(articleModule.currentArticle.title, 'Keep discussion');
    assert.equal(home.yearNodes[0].open,false);
    assert.equal(home.yearNodes[1].open,true);
    const collapsed=home.closedYearGrid.children[0];
    collapsed.open=true;collapsed.events.toggle();
    assert.equal(home.closedYearArea.hidden,true);
    assert.equal(ids.homeCards.children[0],collapsed);
    ids.homeExternalTab.events.click(); await settle();
    assert.equal(ids.homeHeatLegend.hidden,true);
    assert.equal(ids.homeUpload.hidden, true);
    assert.equal(ids.homeCards.children[0].children[0].textContent, '<b>plain text</b>');
    ids.homeCards.children[0].events.click(); assert.equal(calls[2], 7);
    admin=true;home.refresh();await settle();assert.equal(ids.homeUpload.hidden,false);
    fail = true; ids.homeExamTab.events.click(); await settle(); assert.equal(ids.homeCards.children[1].textContent, '重新加载');
    fail = false; ids.homeCards.children[1].onclick(); await settle(); assert.equal(home.yearNodes.length, 2);
    assert.equal(ids.homeUpload.hidden,true);
    home.expandedYears.clear();
    home.years.push({year:2023,text1:true},{year:2022,text1:true});
    home.renderExams();
    assert.deepEqual(home.yearNodes.map(n=>n.open),[true,true,true,false]);
    assert.equal(home.closedYearGrid.children.length,1);
    assert.equal(home.closedYearGrid.children[0].id,'homeYear-2022');
    context.checkinModule={counts:{zhenti_2024_1:2,zhenti_2024_5:5,zhenti_2023_1:7,zhenti_2025_5:999},paint(){}};
    home.reorderExams();
    assert.deepEqual(home.yearNodes.map(n=>n.id),['homeYear-2024','homeYear-2023','homeYear-2025','homeYear-2022']);
    context.checkinModule.counts={zhenti_2022_1:10};
    home.reorderExams();
    assert.equal(home.yearNodes[0].id,'homeYear-2022');
    context.checkinModule.counts={};
    home.reorderExams();
    assert.equal(home.yearNodes[0].id,'homeYear-2025');
    console.log('PASS: default homepage, descending years, Part A/B selection, unavailable articles, resume, external articles, safe text and retry');
})().catch(error => { console.error(error); process.exitCode = 1; });
