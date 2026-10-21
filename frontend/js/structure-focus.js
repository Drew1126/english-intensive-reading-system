/* Cosmetic projection only: original text, font and size are never changed. */
var structureFocus = {
    cache: new Map(), active: null, serial: 0,
    current: function() {
        return document.querySelector('#articleBody .sentence.selected');
    },
    key: function(el) {
        return ((articleModule.currentArticle || {}).id || '') + '\u0000' + el.dataset.idx + '\u0000' + el.textContent.trim();
    },
    init: function() {
        var self = this;
        document.getElementById('structureFocusToggle').onclick = function() {
            var el = self.current(), entry = el && self.cache.get(self.key(el));
            if (!entry || entry.status !== 'ready' || articleModule.editing) return;
            entry.enabled = !entry.enabled; self.sync();
        };
        self.sync();
    },
    rebuild: function(el, ranges) {
        var text = el.textContent, fragment = document.createDocumentFragment(), offset = 0;
        function append(end, muted) {
            if (end <= offset) return;
            var node = muted ? document.createElement('span') : document.createTextNode('');
            if (muted) node.className = 'structure-muted';
            node.textContent = text.slice(offset, end); fragment.appendChild(node); offset = end;
        }
        if (ranges) {
            var leading = text.length - text.trimStart().length;
            ranges.forEach(function(range) { append(range[0] + leading, true); append(range[1] + leading, false); });
            append(text.length, true);
        } else append(text.length, false);
        el.replaceChildren(fragment);
        (articleModule.focusWords || []).forEach(function(word) {
            if (word.sentenceEl === el) articleModule.highlightWordAtOffset(el, word.offset, word.word.length);
        });
    },
    clear: function() {
        if (this.active) this.rebuild(this.active, null);
        this.active = null;
    },
    sync: function() {
        this.clear();
        var button = document.getElementById('structureFocusToggle');
        if (!button) return;
        var el = this.current(), entry = el && this.cache.get(this.key(el));
        var ready = !!(entry && entry.status === 'ready' && !articleModule.editing);
        button.disabled = !ready;
        button.setAttribute('aria-pressed', String(ready && entry.enabled));
        button.title = !entry ? '先点击「句子结构」生成分析' : entry.status === 'pending' ? '正在提取主干…' : !ready ? '未能准确定位，可重新分析' : entry.enabled ? '显示完整句子' : '突出句子主干';
        button.setAttribute('aria-label', button.title);
        if (ready && entry.enabled) {
            var ranges = typeof structureReveal !== 'undefined' && entry.reveal ? structureReveal.project(entry) : entry.ranges;
            this.rebuild(el, ranges); this.active = el;
        }
        if (typeof collocationModule !== 'undefined') collocationModule.sync();
        if (typeof structureReveal !== 'undefined') structureReveal.sync();
    },
    begin: function(articleId, sentence, question) {
        if (!/句子结构|括号标注|逐层划分|划分这个句子/.test(question)) return null;
        if ((articleModule.currentArticle || {}).id !== articleId) return null;
        var matches = Array.from(document.querySelectorAll('#articleBody .sentence')).filter(function(el) { return el.textContent.trim() === sentence; });
        var selected = this.current();
        var target = matches.indexOf(selected) >= 0 ? selected : matches.length === 1 ? matches[0] : null;
        if (!target) return null;
        var key = this.key(target), ticket = ++this.serial;
        this.cache.set(key, {status:'pending', ticket:ticket, enabled:false});
        if (this.cache.size > 200) this.cache.delete(this.cache.keys().next().value);
        this.sync();
        return {key:key, ticket:ticket, sentence:sentence};
    },
    valid: function(core, sentence) {
        if (!core || core.sentence !== sentence || !Array.isArray(core.ranges) || !core.ranges.length) return false;
        var end = 0;
        return core.ranges.every(function(range) {
            if (!Array.isArray(range) || range.length !== 2 || !Number.isInteger(range[0]) || !Number.isInteger(range[1]) || range[0] < end || range[1] <= range[0] || range[1] > sentence.length) return false;
            end = range[1]; return true;
        });
    },
    complete: function(target, core) {
        if (!target) return;
        var entry = this.cache.get(target.key);
        if (!entry || entry.ticket !== target.ticket || entry.status !== 'pending') return;
        var valid = this.valid(core, target.sentence);
        entry.status = valid ? 'ready' : 'failed'; entry.enabled = valid; entry.ranges = valid ? core.ranges : [];
        this.sync();
    },
    fail: function(target) { this.complete(target, null); }
};
document.addEventListener('DOMContentLoaded', function() { structureFocus.init(); });
