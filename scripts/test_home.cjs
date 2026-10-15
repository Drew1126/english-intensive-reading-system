const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
class Element {
    constructor(tag = 'div') { this.tag = tag; this.children = []; this.attrs = {}; this.value = ''; this.events = {}; this.classes = new Set(); this.classList = { add: (...names) => names.forEach(n => this.classes.add(n)), remove: (...names) => names.forEach(n => this.classes.delete(n)) }; }
    appendChild(child) { this.children.push(child); if (this.tag === 'select' && !this.value) this.value = String(child.value); return child; }
    replaceChildren(...children) { this.children = children; if (this.tag === 'select') this.value = ''; }
    setAttribute(name, value) { this.attrs[name] = value; }
    removeAttribute(name) { delete this.attrs[name]; }
    addEventListener(name, action) { this.events[name] = action; }
    querySelector(selector) { return this.children.find(e => e.className === selector.slice(1)); }
}
const ids = {};
const document = { body: new Element(), querySelector: () => null, createElement: tag => new Element(tag), getElementById: id => ids[id] || (ids[id] = new Element(id === 'homeYear' ? 'select' : 'div')) };
let calls = [], fail = false;
const api = { getZhentiList: async () => { if (fail) throw Error('offline'); return { years: [{ year: 2024, text1: true, text5: true }, { year: 2025, text1: true }] }; }, getArticleList: async () => ({ articles: [{ index: 7, title: '<b>plain text</b>', word_count: 400 }] }) };
const articleModule = { loadZhenti: (...args) => calls.push(args), loadByIndex: index => calls.push(index), currentArticle: null, isLoading: false };
const context = { document, api, articleModule, getToken: () => '', window: { dispatchEvent: () => {} }, Event: function() {} };
vm.createContext(context);
vm.runInContext(fs.readFileSync('frontend/js/home.js', 'utf8'), context);
const home = context.homeModule;
const settle = () => new Promise(resolve => setImmediate(resolve));
(async () => {
    home.init(); await settle();
    assert(document.body.classes.has('home-active'));
    assert.equal(ids.homeYear.value, '2025');
    assert.equal(ids.homeCards.children.length, 5);
    assert.equal(ids.homeRecentYears.children.length, 2);
    assert.equal(ids.homeRecentYears.children[0].attrs['aria-pressed'], 'true');
    assert(ids.homeCards.children[4].disabled);
    ids.homeCards.children[0].events.click(); assert.deepEqual(calls[0], [2025, 1]);
    ids.homeRecentYears.children[1].events.click();
    assert.equal(ids.homeYear.value, '2024');
    assert.equal(ids.homeRecentYears.children[1].attrs['aria-pressed'], 'true');
    ids.homeCards.children[4].events.click(); assert.deepEqual(calls[1], [2024, 5]);
    home.showReader(); assert(!document.body.classes.has('home-active'));
    articleModule.currentArticle = { title: 'Keep discussion' }; home.show(); await settle();
    assert.equal(ids.homeResume.hidden, false); assert.equal(articleModule.currentArticle.title, 'Keep discussion');
    ids.homeExternalTab.events.click(); await settle();
    assert.equal(ids.homeYearLabel.hidden, true);
    assert.equal(ids.homeRecentYears.hidden, true);
    assert.equal(ids.homeCards.children[0].children[1].textContent, '<b>plain text</b>');
    ids.homeCards.children[0].events.click(); assert.equal(calls[2], 7);
    fail = true; ids.homeExamTab.events.click(); await settle(); assert.equal(ids.homeCards.children[1].textContent, '重新加载');
    fail = false; ids.homeCards.children[1].onclick(); await settle(); assert.equal(ids.homeCards.children.length, 5);
    console.log('PASS: default homepage, descending years, Part A/B selection, unavailable articles, resume, external articles, safe text and retry');
})().catch(error => { console.error(error); process.exitCode = 1; });
