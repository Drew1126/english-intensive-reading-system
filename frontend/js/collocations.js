/* Custom highlights leave the article DOM, typography and word offsets unchanged. */
var collocationModule = {
    active: null,
    capture: function(articleId, sentence) {
        if ((articleModule.currentArticle || {}).id !== articleId) return null;
        var selected = document.querySelector('#articleBody .sentence.selected');
        var matches = Array.from(document.querySelectorAll('#articleBody .sentence')).filter(function(el) { return el.textContent.trim() === sentence; });
        var el = matches.indexOf(selected) >= 0 ? selected : matches.length === 1 ? matches[0] : null;
        return el ? {articleId:articleId, sentence:sentence, el:el} : null;
    },
    clear: function() {
        if (typeof CSS !== 'undefined' && CSS.highlights) CSS.highlights.delete('sentence-collocation');
        if (this.active) this.active.button.setAttribute('aria-pressed', 'false');
        this.active = null;
    },
    ranges: function(el, pairs) {
        var walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT), nodes = [], node, length = 0;
        while ((node = walker.nextNode())) { nodes.push({node:node,start:length,end:length+node.textContent.length}); length += node.textContent.length; }
        var leading = el.textContent.length - el.textContent.trimStart().length;
        return pairs.map(function(pair) {
            var start = pair[0]+leading, end = pair[1]+leading;
            var first = nodes.find(function(n) { return n.start <= start && start < n.end; });
            var last = nodes.find(function(n) { return n.start < end && end <= n.end; });
            if (!first || !last) throw new Error('搭配位置已变化');
            var range = document.createRange();
            range.setStart(first.node, start-first.start); range.setEnd(last.node, end-last.start);
            return range;
        });
    },
    sync: function() {
        var selected = document.querySelector('#articleBody .sentence.selected');
        var quick = document.getElementById('btnSentenceCollocations');
        if (quick) quick.disabled = !selected || articleModule.editing;
        if (!this.active) return;
        var a = this.active, target = a.target;
        if (!a.button.isConnected || !target.el.isConnected || articleModule.editing || selected !== target.el ||
            (articleModule.currentArticle || {}).id !== target.articleId || target.el.textContent.trim() !== target.sentence) {
            this.clear(); return;
        }
        try {
            CSS.highlights.set('sentence-collocation', new Highlight(...this.ranges(target.el, a.item.ranges)));
        } catch (error) { this.clear(); }
    },
    toggle: function(target, item, button) {
        if (!target || !target.el.isConnected || articleModule.editing ||
            (articleModule.currentArticle || {}).id !== target.articleId || target.el.textContent.trim() !== target.sentence) {
            showToast('原句已切换或修改，请重新选择句子查询。'); return;
        }
        if (this.active && this.active.button === button) { this.clear(); return; }
        if (typeof CSS === 'undefined' || !CSS.highlights || typeof Highlight === 'undefined') {
            showToast('当前浏览器不支持原文联动高亮，请使用新版 Edge 或 Chrome。'); return;
        }
        this.clear();
        if (typeof structureReveal !== 'undefined') structureReveal.clearReferences();
        articleModule.focusWords = [];
        articleModule.clearWordHighlight();
        agentModule.selectedFocusWord = '';
        document.querySelectorAll('#articleBody .sentence.selected').forEach(function(el) { el.classList.remove('selected'); });
        target.el.classList.add('selected');
        articleModule.selectedSentenceIdx = target.el.dataset.idx;
        window.__currentIdx = target.el.dataset.idx;
        agentModule.showSelectedSentence(target.sentence, target.el.dataset.idx);
        this.active = {target:target,item:item,button:button};
        button.setAttribute('aria-pressed','true');
        this.sync();
        target.el.scrollIntoView({block:'nearest',behavior:'smooth'});
    },
    render: function(request) {
        var data = request.collocations, target = request.collocationTarget;
        if (!data || data.sentence !== request.sentence || !Array.isArray(data.items) || !data.items.length || !target) return;
        var self = this, fragment = document.createDocumentFragment();
        var hint = document.createElement('p'); hint.className='collocation-help';
        hint.textContent='点击搭配可在原文中联动高亮，再点一次取消；不会自动收录生词。';
        fragment.appendChild(hint);
        data.items.forEach(function(item) {
            if (typeof item.label !== 'string' || typeof item.meaning !== 'string' ||
                !structureFocus.valid({sentence:data.sentence,ranges:item.ranges},request.sentence)) return;
            var row=document.createElement('div'); row.className='collocation-result';
            var button=document.createElement('button'); button.type='button'; button.className='collocation-link';
            button.textContent=item.label; button.setAttribute('aria-pressed','false'); button.title='在原文中查看这组搭配';
            button.addEventListener('click',function() { self.toggle(target,item,button); });
            var meaning=document.createElement('p'); meaning.textContent=item.meaning;
            row.appendChild(button); row.appendChild(meaning); fragment.appendChild(row);
        });
        if (fragment.childNodes.length > 1) request.answerEl.replaceChildren(fragment);
    }
};
document.addEventListener('DOMContentLoaded', function() { collocationModule.sync(); });
