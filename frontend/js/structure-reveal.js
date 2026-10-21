/* Optional reveal projection; never modifies article text or stored learning data. */
var structureReveal = {
    bindings: [],
    available: function(entry, node) {
        return node.depends_on.every(function(id) { return id === 'core' || entry.opened.has(id); });
    },
    project: function(entry) {
        var pairs = entry.ranges.map(function(pair) { return pair.slice(); });
        if (entry.reveal) entry.reveal.nodes.forEach(function(node) {
            if (entry.opened.has(node.id)) pairs.push.apply(pairs, node.ranges.map(function(pair) { return pair.slice(); }));
        });
        pairs.sort(function(a,b) { return a[0]-b[0]; });
        return pairs.reduce(function(result, pair) {
            var last = result[result.length-1];
            if (last && pair[0] <= last[1]) last[1] = Math.max(last[1], pair[1]);
            else result.push(pair);
            return result;
        }, []);
    },
    change: function(entry, id) {
        var node = entry.reveal.nodes.find(function(n) { return n.id === id; });
        if (!node || !this.available(entry, node)) return false;
        if (entry.opened.has(id)) {
            entry.opened.delete(id);
            var removed = true, self = this;
            while (removed) {
                removed = false;
                entry.reveal.nodes.forEach(function(n) {
                    if (entry.opened.has(n.id) && !self.available(entry,n)) { entry.opened.delete(n.id); removed = true; }
                });
            }
            entry.relation = null;
        } else { entry.opened.add(id); entry.relation = id; }
        entry.enabled = true;
        return true;
    },
    validBinding: function(binding) {
        var target = binding.target, entry = structureFocus.cache.get(binding.key);
        return binding.answerEl.isConnected && target.el.isConnected && !articleModule.editing &&
            getToken() === binding.token && (articleModule.currentArticle || {}).id === target.articleId &&
            target.el.textContent.trim() === target.sentence && structureFocus.key(target.el) === binding.key &&
            entry === binding.entry && entry.status === 'ready' && entry.ticket === binding.ticket;
    },
    toggle: function(binding, id) {
        if (!this.validBinding(binding)) { showToast('原句或分析已更新，请重新生成句子结构。'); return; }
        if (!this.change(binding.entry, id)) { showToast('请先展开上一级片段。'); return; }
        if (typeof collocationModule !== 'undefined') collocationModule.clear();
        articleModule.focusWords = [];
        articleModule.clearWordHighlight();
        agentModule.selectedFocusWord = '';
        document.querySelectorAll('#articleBody .sentence.selected').forEach(function(el) { el.classList.remove('selected'); });
        binding.target.el.classList.add('selected');
        articleModule.selectedSentenceIdx = binding.target.el.dataset.idx;
        window.__currentIdx = binding.target.el.dataset.idx;
        agentModule.showSelectedSentence(binding.target.sentence, binding.target.el.dataset.idx);
        structureFocus.sync();
    },
    clearReferences: function() {
        if (typeof CSS !== 'undefined' && CSS.highlights) CSS.highlights.delete('sentence-reference');
    },
    matchLine: function(node, text) {
        var clean = function(value) { return value.trim().replace(/[.。]$/, '').trim(); };
        var line = clean(text), original = clean(node.text);
        if (line === original) return 'exact';
        // The explanation may discuss the relative connector separately. Match
        // only the COMPLETE remaining clause, not an arbitrary substring.
        if (!Array.isArray(node.parts) || node.parts.length !== 1) return null;
        var body = original.replace(/^(?:(?:in|on|at|for|with|by|through|from|to|of|about)\s+)?(?:which|whom|who|whose|that|where|when)\s+/i, '');
        if (body !== original && body.split(/\s+/).length >= 3 && line === body) return 'clause-body';
        return null;
    },
    sync: function() {
        this.clearReferences();
        var self = this, current = structureFocus.current();
        this.bindings = this.bindings.filter(function(binding) { return binding.answerEl.isConnected; });
        this.bindings.forEach(function(binding) {
            var valid = self.validBinding(binding), entry = binding.entry;
            binding.buttons.forEach(function(item) {
                var ready = valid && self.available(entry,item.node), opened = entry.opened.has(item.node.id);
                item.button.disabled = !ready;
                item.button.setAttribute('aria-pressed', String(valid && opened));
                item.button.classList.toggle('reveal-open', valid && opened);
                item.button.classList.toggle('reveal-locked', !ready);
                var missing = item.node.depends_on.filter(function(id) { return id !== 'core' && !entry.opened.has(id); });
                var labels = missing.map(function(id) { return entry.reveal.nodes.find(function(n) { return n.id === id; }).text; });
                item.button.title = !valid ? '请回到原文，或重新生成分析' : !ready ? '先展开：' + labels.join('；') : opened ? '点击收回；依赖它的片段也会收回' : '点击在原文中恢复这部分';
                item.button.setAttribute('aria-label', item.node.text + '。' + item.button.title);
            });
            binding.status.textContent = !valid ? '原句或分析已切换。' : !entry.enabled ? '当前显示完整原句；点击英文片段重新进入分层阅读。' : '已展开 ' + entry.opened.size + ' / ' + entry.reveal.nodes.length + ' 个片段';
            if (!valid || !entry.enabled || current !== binding.target.el || !entry.relation) return;
            var node = entry.reveal.nodes.find(function(n) { return n.id === entry.relation; });
            if (!node || !node.references.length) return;
            binding.status.textContent = node.references.map(function(ref) { return ref.source + ' → ' + ref.target + '：' + ref.explanation; }).join('；');
            if (typeof CSS === 'undefined' || !CSS.highlights || typeof Highlight === 'undefined' || typeof collocationModule === 'undefined') return;
            try {
                var pairs = [];
                node.references.forEach(function(ref) { pairs.push.apply(pairs,ref.source_ranges); pairs.push.apply(pairs,ref.target_ranges); });
                CSS.highlights.set('sentence-reference', new Highlight(...collocationModule.ranges(binding.target.el, pairs)));
            } catch (error) { self.clearReferences(); }
        });
    },
    attach: function(request) {
        var data = request.coreData && request.coreData.reveal, target = request.collocationTarget, ticket = request.coreTarget;
        if (!data || !target || !ticket || data.sentence !== request.sentence || !Array.isArray(data.nodes) || !data.nodes.length || data.nodes.length > 12) return;
        var entry = structureFocus.cache.get(ticket.key), self = this;
        if (!entry || entry.status !== 'ready' || entry.ticket !== ticket.ticket || request.revealAttached) return;
        if (!data.nodes.every(function(n) { return typeof n.text === 'string' && typeof n.meaning === 'string' && Array.isArray(n.depends_on) && Array.isArray(n.references) && structureFocus.valid({sentence:data.sentence,ranges:n.ranges},data.sentence); })) return;
        entry.reveal = data; entry.opened = new Set(); entry.relation = null;
        var binding = {entry:entry, key:ticket.key, ticket:ticket.ticket, target:target, token:request.authToken,
            answerEl:request.answerEl, buttons:[]};
        var hint = document.createElement('p'); hint.className='reveal-help';
        hint.textContent='点击带底纹的英文片段，逐层读回原句；锁定片段需先展开上一级。再次点击可收回。';
        request.answerEl.prepend(hint);
        var status = document.createElement('p'); status.className='reveal-status'; status.setAttribute('role','status');
        request.answerEl.appendChild(status); binding.status=status;
        function buttonFor(node, label) {
            var button=document.createElement('button'); button.type='button'; button.className='reveal-fragment'; button.textContent=label || node.text;
            button.addEventListener('click',function() { self.toggle(binding,node.id); });
            binding.buttons.push({node:node,button:button}); return button;
        }
        var unmatched = [];
        data.nodes.forEach(function(node) {
            var matched = false;
            Array.from(request.answerEl.querySelectorAll('.structure-english')).forEach(function(line) {
                // Use only standalone verbatim English rows; never rewrite a Chinese explanation.
                if (line.querySelector('button')) return;
                var text=line.textContent.trim();
                var match = self.matchLine(node,text);
                var unique = match === 'exact' || data.nodes.filter(function(candidate) { return self.matchLine(candidate,text); }).length === 1;
                if (match && unique) {
                    line.replaceChildren(buttonFor(node,text)); matched=true;
                }
            });
            if (!matched) unmatched.push(node);
        });
        if (unmatched.length) {
            var extra=document.createElement('div'); extra.className='reveal-extra';
            var title=document.createElement('h4'); title.textContent='原文分层片段'; extra.appendChild(title);
            unmatched.forEach(function(node) {
                var row=document.createElement('p'); row.appendChild(buttonFor(node));
                var meaning=document.createElement('span'); meaning.className='reveal-meaning'; meaning.textContent=node.meaning;
                row.appendChild(meaning); extra.appendChild(row);
            });
            request.answerEl.insertBefore(extra,status);
        }
        this.bindings.push(binding); request.revealAttached=true;
        structureFocus.sync();
    }
};
