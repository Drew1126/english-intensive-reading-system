/* Context-only review. One card per word, with server-owned scheduling. */
var spacedReview = {
    articleSession: null, articleTitle: '', articleOrder: [], articleOrderId: null,
    state: null, mode: 'today', current: null, running: false, revealed: false, hinted: false, busy: false, epoch: 0,
    reset: function() {
        this.epoch++;
        this.articleSession = null; this.articleTitle = '';
        this.articleOrder = []; this.articleOrderId = null;
        this.state = null; this.current = null; this.currentGroup = []; this.running = false; this.busy = false;
        this.revealed = false; this.hinted = false; this.mode = 'today';
        var session = document.getElementById('reviewSession'); if (session) session.replaceChildren();
        var summary = document.getElementById('reviewSummary'); if (summary) summary.textContent = '';
    },
    init: function() {
        var self = this;
        [['reviewToday', 'today'], ['reviewLibrary', 'library'], ['reviewMastered', 'mastered']].forEach(function(pair) {
            document.getElementById(pair[0]).onclick = function() {
                if (self.busy || self.articleSession) return;
                self.articleSession = null;
                self.mode = pair[1]; self.running = false; self.current = null;
                self.render(); reviewModule.render(); reviewModule.load();
            };
        });
        document.getElementById('vocabularyDialog').addEventListener('close', function() {
            if (!self.busy) { self.running = false; self.current = null; }
        });
        window.addEventListener('focus', function() { if (getToken()) reviewModule.load(); });
        setInterval(function() {
            if (document.getElementById('vocabularyDialog').open && !self.current && !self.busy && getToken()) reviewModule.load();
        }, 30000);
        self.render();
    },
    accept: function(state) {
        this.state = state;
        if (this.current && state) {
            var stale = (this.currentGroup || [this.current]).some(function(old) {
                var fresh = state.tasks.find(function(t) { return t.id === old.id; });
                return !fresh || fresh.version !== old.version;
            });
            if (stale) { this.current = null; this.currentGroup = []; this.running = false; }
        }
        if (!this.current) this.render();
    },
    due: function() {
        if (!this.state) return [];
        if (this.articleSession) {
            var session = this.articleSession;
            var tasks = new Map(this.state.tasks.map(function(t) { return [t.id, t]; }));
            return session.task_ids.filter(function(id) { return session.completed.indexOf(id) < 0 && tasks.has(id); }).map(function(id) { return tasks.get(id); });
        }
        var tasks = this.state.tasks;
        return ((this.state.round && this.state.round.pending) || []).reduce(function(queue, key) {
            return queue.concat(tasks.filter(function(t) { return t.word_key === key && t.stage < 6; }));
        }, []);
    },
    include: function(key) {
        var mastered = this.state && this.state.mastered.indexOf(key) !== -1;
        return this.mode === 'mastered' ? mastered : !mastered;
    },
    el: function(tag, text, cls) {
        var node = document.createElement(tag); node.textContent = text || ''; if (cls) node.className = cls; return node;
    },
    button: function(text, action, cls) {
        var node = this.el('button', text, cls); node.type = 'button'; node.onclick = action; return node;
    },
    date: function(seconds) {
        return new Date(seconds * 1000).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    },
    choose: function(preferredKey) {
        var due = this.due(), key = null;
        if (this.articleSession) {
            if (this.articleOrderId !== this.articleSession.id) {
                this.articleOrderId = this.articleSession.id;
                this.articleOrder = Array.from(new Set(due.map(function(t) { return t.word_key; })));
            }
            key = this.articleOrder.find(function(word) { return due.some(function(t) { return t.word_key === word; }); });
        }
        if (!due.some(function(t) { return t.word_key === key; })) key = due.length ? due[0].word_key : null;
        var group = due.filter(function(t) { return t.word_key === key; }).sort(function(a,b) {
            return (a.kind === 'word' ? -1 : 1) - (b.kind === 'word' ? -1 : 1) || a.stage - b.stage || a.due_at - b.due_at;
        });
        this.current = group[0] || null; this.revealed = false; this.hinted = false;
        this.currentGroup = group;
        this.render();
    },
    source: function(task) {
        var entry = reviewModule.words.get(task.word_key);
        if (!entry) return null;
        if (task.kind === 'context') return entry.sources.find(function(s) { return s.id === task.source_id; });
        if (this.articleSession) return entry.sources.find(function(s) { return s.article_id === spacedReview.articleSession.article_id; });
        return entry.sources[0];
    },
    articleSources: function(task) {
        var entry = reviewModule.words.get(task.word_key), session = this.articleSession;
        var group = this.currentGroup || [task];
        return entry ? entry.sources.filter(function(source) {
            return session ? source.article_id === session.article_id : group.some(function(t) { return t.source_id === source.id; });
        }) : [];
    },
    renderArticleCard: function(task, entry, session) {
        var self = this, sources = this.articleSources(task);
        session.appendChild(this.el('p', this.articleSession ? '打卡前回顾 · 认识一次即通过 · 不计全局' : '句中含义 · 本词评分一次', 'review-step'));
        session.appendChild(this.el('h4', entry.word, 'review-word'));
        session.appendChild(this.el('p', '先看单词回忆，再查看原句，判断是否认识它在句中的含义。', 'review-help'));
        if (this.revealed) sources.forEach(function(source, i) {
            session.appendChild(self.el('p', source.article_title + (sources.length > 1 ? ' · 原句 ' + (i + 1) : ''), 'review-step'));
            session.appendChild(self.sentence(source, entry.word));
            if (self.revealed) session.appendChild(self.el('p', self.definition(source, 'context').text, 'review-definition'));
        });
        if (!this.revealed) session.appendChild(this.button('查看原句与释义', function() { self.revealed = true; self.render(); }, 'review-primary'));
        else {
            var grades = this.el('div', '', 'review-grades');
            [['again','不认识'], ['hard','模糊'], ['known','认识']].forEach(function(pair) {
                var label = pair[1];
                var button = self.button(label, function() { self.rate(pair[0]); });
                button.disabled = self.busy || (!self.articleSession && pair[0] === 'known' && !self.articleReliable(task));
                grades.appendChild(button);
            });
            session.appendChild(grades);
        }
        var pause = this.button('结束本次复习', function() { self.running = false; self.current = null; self.render(); });
        pause.disabled = this.busy; session.appendChild(pause);
    },
    articleReliable: function(task) {
        var self = this, sources = this.articleSources(task);
        return sources.length > 0 && sources.every(function(source) { return self.definition(source, 'context').reliable; });
    },
    definition: function(source, kind) {
        var text = source.meaning, context = text.indexOf('◆ 在本句中');
        if (context < 0) return { text: (this.articleSession ? '旧释义未单列句中义，请结合原句和完整释义自行确认。\n' : '旧释义格式无法准确区分常见义和句中义，请对照完整释义；本次请按“模糊”或“不认识”记录。\n') + text, reliable: false };
        if (kind === 'context') {
            var end = text.indexOf('◆', context + 1);
            return { text: text.slice(context + '◆ 在本句中'.length, end < 0 ? text.length : end).trim(), reliable: true };
        }
        var core = text.slice(0, context).replace(/^〔[^〕]+〕\s*\/[^/]*\//, '').trim();
        var other = text.indexOf('◆ 其他常见义');
        if (other >= 0) {
            var stop = text.indexOf('◆', other + 1);
            core += '\n' + text.slice(other, stop < 0 ? text.length : stop).trim();
        }
        return { text: core || text, reliable: !!core };
    },
    sentence: function(source, word) {
        var block = this.el('blockquote', '', 'review-sentence');
        var parts = word.split(/\.{3,}|…+/).map(function(p) { return p.trim(); }).filter(Boolean);
        var ranges = [];
        parts.forEach(function(part) {
            var escaped = part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            var regex = new RegExp('\\b' + escaped + '\\b', 'gi'), match;
            while ((match = regex.exec(source.sentence))) ranges.push([match.index, match.index + match[0].length]);
        });
        ranges.sort(function(a,b) { return a[0] - b[0]; });
        var cursor = 0;
        ranges.forEach(function(range) {
            if (range[0] < cursor) return;
            block.appendChild(document.createTextNode(source.sentence.slice(cursor, range[0])));
            block.appendChild(spacedReview.el('mark', source.sentence.slice(range[0], range[1]))); cursor = range[1];
        });
        block.appendChild(document.createTextNode(source.sentence.slice(cursor)));
        return block;
    },
    render: function() {
        var self = this, summary = document.getElementById('reviewSummary'), session = document.getElementById('reviewSession');
        if (!session) return;
        document.getElementById('reviewTabs').hidden = !!this.articleSession;
        document.getElementById('vocabularyTitle').textContent = this.articleSession ? '本篇打卡回顾' : '全局生词回顾';
        document.getElementById('vocabularyHint').textContent = this.articleSession
            ? '仅回顾本篇生词，认识一次即通过，无延期，不计入全局复习。'
            : '先看单词回忆，再查看原句与句中释义，评分一次；全部原句掌握后可归档或删除。';
        [['reviewToday','today'], ['reviewLibrary','library'], ['reviewMastered','mastered']].forEach(function(pair) {
            document.getElementById(pair[0]).setAttribute('aria-pressed', String(self.mode === pair[1]));
        });
        document.getElementById('vocabularyList').hidden = this.mode === 'today';
        session.replaceChildren();
        if (!this.state) { summary.textContent = getToken() ? '正在加载复习进度…' : '登录后查看你的复习进度。'; return; }
        var round = this.state.round;
        summary.textContent = '可复习 ' + this.state.available_words + ' 词 · 已掌握 ' + this.state.mastered.length + ' 词'
            + (round ? ' · 本轮通过 ' + round.completed.length + '/' + round.selected.length + ' 词' : '');
        if (this.articleSession) {
            var article = this.articleSession, words = new Set(), remaining = new Set();
            this.state.tasks.forEach(function(t) {
                if (article.task_ids.indexOf(t.id) < 0) return;
                words.add(t.word_key);
                if (article.completed.indexOf(t.id) < 0) remaining.add(t.word_key);
            });
            summary.textContent = '本篇打卡回顾 · ' + this.articleTitle + ' · ' + (words.size - remaining.size) + '/' + words.size + ' 词（不计全局复习）';
        }
        if (this.mode !== 'today') {
            if (this.mode === 'mastered' && this.state.mastered.length) session.appendChild(this.button('删除全部已掌握', function() { self.confirmAction('delete-mastered', null); }, 'review-danger'));
            return;
        }
        if (!this.current) {
            if (this.articleSession) {
                session.appendChild(this.el('p', this.articleSession.task_ids.length ? '每个词点“认识”一次即可通过；不认识或模糊可立即再回顾，无延期，不改变全局复习进度。' : '这篇文章还没有收录生词，无需回顾，可直接确认打卡。', 'review-help'));
                if (this.due().length) session.appendChild(this.button('继续本篇回顾', function() { self.running = true; self.choose(); }, 'review-primary'));
                else {
                    var finish = this.button('完成回顾，确认打卡', function() { self.finishCheckin(); }, 'review-primary');
                    finish.disabled = this.busy; session.appendChild(finish);
                }
                return;
            }
            session.appendChild(this.el('p', '每轮最多 20 词：未复习优先，其余按 0–2、3–5、6–8 天分档，越久越优先，同档随机。不认识或模糊放到本轮队尾，无等待时间。', 'review-help'));
            if (this.due().length) session.appendChild(this.button('继续本轮复习', function() { self.running = true; self.choose(); }, 'review-primary'));
            else if (this.state.available_words) {
                if (round) session.appendChild(this.el('p', '本轮复习已完成。', 'review-complete'));
                var start = this.button(round ? '开始下一轮（最多 20 词）' : '开始复习（最多 20 词）', function() { self.beginGlobal(); }, 'review-primary');
                start.disabled = this.busy; session.appendChild(start);
            } else session.appendChild(this.el('p', '暂无未掌握词汇。', 'review-complete'));
            session.appendChild(this.button('刷新词库', function() { reviewModule.load(); }));
            return;
        }
        var task = this.current, source = this.source(task), entry = reviewModule.words.get(task.word_key);
        if (!source || !entry) { this.current = null; this.running = false; this.render(); return; }
        this.renderArticleCard(task, entry, session);
    },
    rate: function(grade) {
        if (this.busy || !this.current || !this.revealed) return;
        var task = this.current, source = this.source(task);
        if (!this.articleSession && grade === 'known' && !this.articleReliable(task)) return;
        var self = this, token = getToken(), epoch = this.epoch;
        this.busy = true; this.render();
        fetch(BASE + '/vocabulary/rate', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token }, body: JSON.stringify({task_id:task.id,version:task.version,grade:grade,session_id:this.articleSession ? this.articleSession.id : '',round_id:!this.articleSession && this.state.round ? this.state.round.id : '',combined:!!this.articleSession,targets:this.articleSession ? [] : (this.currentGroup || [task]).map(function(t) { return {task_id:t.id,version:t.version}; })}) }).then(handleJson).then(function(data) {
            if (token !== getToken() || epoch !== self.epoch) return;
            self.busy = false; self.state = data.review; self.current = null;
            if (data.session) self.articleSession = data.session;
            if (self.articleSession && grade !== 'known') {
                self.articleOrder = self.articleOrder.filter(function(key) { return key !== task.word_key; });
                self.articleOrder.push(task.word_key);
            }
            reviewModule.updateCount(); reviewModule.render();
            if (document.getElementById('vocabularyDialog').open) self.choose(task.word_key);
            else { self.running = false; self.render(); }
        }).catch(function(error) {
            if (token !== getToken() || epoch !== self.epoch) return;
            self.busy = false; showToast('进度未确认：' + error.message + (self.articleSession ? '。请重新点击文章的打卡按钮开始回顾。' : '。请刷新队列核对。'), 'error');
            // A failed article request must never silently turn into global spaced review.
            self.current = null; self.running = false; self.render(); reviewModule.load();
        });
    },
    beginGlobal: async function() {
        if (this.busy || this.articleSession) return;
        var token = getToken(), epoch = this.epoch;
        this.busy = true; this.render();
        try {
            await reviewModule.load();
            if (token !== getToken() || epoch !== this.epoch) return;
            var response = await fetch(BASE + '/vocabulary/global-review', {method:'POST',headers:{Authorization:'Bearer '+token}});
            var data = await handleJson(response);
            if (token !== getToken() || epoch !== this.epoch) return;
            this.state = data.review; this.mode = 'today'; this.running = true; this.busy = false;
            reviewModule.updateCount(); this.choose();
        } catch (error) {
            if (token === getToken() && epoch === this.epoch) showToast('无法开始复习：'+error.message, 'error');
        } finally {
            if (token === getToken() && epoch === this.epoch) { this.busy = false; this.render(); }
        }
    },
    beginArticle: async function(article) {
        if (this.busy || agentModule.isStreaming || articleModule.isLoading) { showToast('请先完成当前加载或回答。'); return; }
        var token = getToken(), epoch = this.epoch;
        this.busy = true;
        try {
            await reviewModule.load();
            var response = await fetch(BASE + '/vocabulary/article-review', { method: 'POST', headers: {'Content-Type':'application/json', Authorization:'Bearer '+token}, body:JSON.stringify({article_id:article.id}) });
            var data = await handleJson(response);
            if (token !== getToken() || epoch !== this.epoch) return;
            this.articleSession = data.session; this.articleTitle = article.title;
            this.articleOrderId = null;
            this.state = data.review; this.mode = 'today'; this.current = null; this.running = true;
            var self = this;
            if (this.due().some(function(t) { return !self.source(t); })) { this.articleSession=null; throw new Error('词库尚未加载完整，请重试。'); }
            var dialog = document.getElementById('vocabularyDialog'); if (!dialog.open) dialog.showModal();
            this.busy = false; this.choose();
            if (data.resumed) showToast('已继续上次本篇回顾，已通过的词无需重做。', 'success');
        } catch (error) { if (token === getToken() && epoch === this.epoch) showToast(error.message, 'error'); }
        finally { if (token === getToken() && epoch === this.epoch) this.busy = false; }
    },
    finishCheckin: function() {
        if (this.busy || !this.articleSession || this.due().length) return;
        var self=this, token=getToken(), epoch=this.epoch, session=this.articleSession;
        this.busy=true; this.render();
        api.checkin(session.article_id, token, session.id).then(function(data) {
            if (token!==getToken() || epoch!==self.epoch) return;
            self.busy=false; self.articleSession=null; self.current=null; self.running=false;
            document.getElementById('vocabularyDialog').close();
            showToast('打卡成功，本篇累计 '+data.count+' 次。', 'success');
            updateCheckinArea(); checkinModule.refresh(); self.render();
        }).catch(function(error) {
            if (token!==getToken() || epoch!==self.epoch) return;
            self.busy=false; showToast('打卡未确认：'+error.message, 'error'); self.render();
        });
    },
    decorate: function(item, entry, key) {
        if (!this.state) return;
        var self = this, tasks = this.state.tasks.filter(function(t) { return t.word_key === key; });
        var mastered = this.state.mastered.indexOf(key) !== -1;
        var known = tasks.filter(function(t) { return t.stage === 6; }).length;
        item.appendChild(this.el('p', mastered ? '全部原句含义均已掌握' : '已掌握 ' + known + '/' + tasks.length + ' 个原句', 'review-help'));
        tasks.forEach(function(task) {
            var label = task.kind === 'word' ? '常见义' : '原句 ' + (entry.sources.findIndex(function(s) { return s.id === task.source_id; }) + 1);
            var status = task.stage === 6 ? '已掌握' : task.stage + '/6 级 · ' + (task.last_reviewed ? '上次复习 '+new Date(task.last_reviewed*1000).toLocaleDateString('zh-CN',{timeZone:'Asia/Shanghai'}) : '尚未复习');
            item.appendChild(self.el('p', label + '：' + status, 'review-help'));
        });
        var controls = this.el('div', '', 'review-library-actions');
        if (mastered) controls.appendChild(this.button('重新学习', function() { self.confirmAction('restore', entry.word); }));
        controls.appendChild(this.button('删除词条', function() { self.confirmAction('delete', entry.word); }, 'review-danger'));
        item.appendChild(controls);
    },
    confirmAction: function(action, word) {
        var self = this, token = getToken(), epoch = this.epoch;
        var message = action === 'restore' ? '将“' + word + '”的所有原句重新加入学习？' : (word ? '删除“' + word + '”' : '删除全部已掌握词条') + '？这会永久删除来源句子、释义和复习记录，无法撤销。';
        document.getElementById('vocabularyDialog').close();
        showConfirm(message, function() {
            if (token !== getToken() || epoch !== self.epoch) return;
            fetch(BASE + '/vocabulary/' + action, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token }, body: word ? JSON.stringify({word:word}) : undefined }).then(handleJson).then(function() {
                if (token !== getToken() || epoch !== self.epoch) return;
                self.current = null; self.running = false;
                reviewModule.load(); document.getElementById('vocabularyDialog').showModal();
            }).catch(function(error) { if (token === getToken() && epoch === self.epoch) showToast(error.message, 'error'); });
        });
    }
};
document.addEventListener('DOMContentLoaded', function() { spacedReview.init(); });
