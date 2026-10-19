// Account-scoped persistent vocabulary; chat navigation remains per article.
var reviewModule = {
    words: new Map(),
    cursor: null,
    accountToken: null,
    loadVersion: 0,
    syncAccount: function() {
        var token = getToken() || '';
        if (token === this.accountToken) return;
        this.accountToken = token;
        this.loadVersion++;
        this.words.clear();
        if (typeof spacedReview !== 'undefined') spacedReview.reset();
        document.getElementById('vocabularyDialog').close();
        document.getElementById('vocabularyStatus').replaceChildren();
        this.updateCount();
        if (token) this.load();
    },
    load: function() {
        var self = this, token = getToken(), version = ++this.loadVersion;
        if (!token) return Promise.resolve();
        return fetch(BASE + '/vocabulary', { headers: { Authorization: 'Bearer ' + token } }).then(handleJson).then(function(data) {
            if (getToken() !== token || version !== self.loadVersion) return;
            self.words.clear();
            data.entries.forEach(function(source) {
                var key = source.word_key || source.word.toLowerCase();
                if (!self.words.has(key)) self.words.set(key, { word: source.word, sources: [] });
                self.words.get(key).sources.push(source);
            });
            if (typeof spacedReview !== 'undefined') spacedReview.accept(data.review);
            self.updateCount(); self.render();
        }).catch(function() {
            if (getToken() === token && version === self.loadVersion) showToast('生词库加载失败，请重新打开回顾重试。', 'error');
        });
    },
    save: function(entries, token) {
        var self = this;
        if (!token || token !== getToken()) return;
        fetch(BASE + '/vocabulary', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token }, body: JSON.stringify({ entries: entries }) }).then(handleJson).then(function() {
            if (getToken() === token) self.load();
        }).catch(function() {
            if (getToken() !== token) return;
            showToast('生词保存失败，可在生词回顾中重试；暂勿刷新页面。', 'error');
            var row = document.createElement('div');
            row.textContent = '未保存：' + entries.map(function(e) { return e.word; }).join('、') + ' ';
            var retry = document.createElement('button'); retry.textContent = '重试保存';
            retry.onclick = function() { row.remove(); self.save(entries, token); };
            row.appendChild(retry); document.getElementById('vocabularyStatus').appendChild(row);
        });
    },
    init: function() {
        var self = this;
        function openReview() {
            self.syncAccount();
            if (typeof spacedReview !== 'undefined') {
                if (spacedReview.busy) return;
                spacedReview.articleSession = null;
                spacedReview.current = null;
                spacedReview.currentGroup = [];
                spacedReview.mode = 'today';
                spacedReview.running = false;
                spacedReview.render();
            }
            self.render();
            document.getElementById('vocabularyDialog').showModal();
            self.load();
        }
        document.getElementById('homeVocabulary').addEventListener('click', openReview);
        document.getElementById('vocabularyClose').addEventListener('click', function() {
            document.getElementById('vocabularyDialog').close();
        });
        // Keep the review open on backdrop clicks; close explicitly with × or Escape.
        document.getElementById('btnPreviousQuestion').addEventListener('click', function() { self.previous(); });
        document.getElementById('btnNextQuestion').addEventListener('click', function() { self.jump(1); });
        var chat = document.getElementById('chatMessages');
        ['wheel', 'touchstart', 'pointerdown', 'keydown'].forEach(function(type) {
            chat.addEventListener(type, function() { self.cursor = null; self.updateNavigation(); }, { passive: true });
        });
        this.reset();
    },
    reset: function() {
        this.syncAccount();
        this.cursor = null;
        document.getElementById('vocabularyDialog').close();
        this.updateCount();
        this.updateNavigation();
    },
    recordAnswer: function(focus, question, answer, source, token) {
        if (!focus || question !== '解释选中内容在句子释义' || !answer.trim()) return;
        if (!source || !source.article_id || !token || token !== getToken()) return;
        // Ellipses describe selection gaps, not vocabulary boundaries.
        // Each model-produced vocabulary card owns its own definition.
        var pattern = /〔([^〕\r\n]+)〕\s*\//g;
        var cards = [], match;
        while ((match = pattern.exec(answer))) {
            cards.push({ word: match[1].trim(), start: match.index });
        }
        if (!cards.length) {
            // A multi-part selection without cards is ambiguous; do not guess a phrase.
            if (/\.{3,}|…/.test(focus)) {
                showToast('回答未给出清晰词条，暂未收录生词，请重新生成。');
                return;
            }
            cards.push({ word: focus, start: 0 });
        }
        var entries = [];
        for (var i = 0; i < cards.length; i++) {
            entries.push(Object.assign({}, source, { word: cards[i].word, meaning: answer.slice(cards[i].start, i + 1 < cards.length ? cards[i + 1].start : answer.length).trim() }));
        }
        this.save(entries, token);
    },
    record: function(focus, question) {
        if (!focus || question !== '解释选中内容在句子释义') return null;
        var word = focus.trim().replace(/\s+/g, ' ');
        if (!word) return null;
        var key = word.toLowerCase();
        var entry = this.words.get(key);
        if (!entry) {
            entry = { word: word, meaning: '' };
            this.words.set(key, entry);
        }
        this.updateCount();
        return entry;
    },
    updateCount: function() {
        document.getElementById('homeVocabulary').textContent = '生词回顾（' + this.words.size + '）';
        if (typeof spacedReview !== 'undefined' && spacedReview.state) {
            document.getElementById('homeVocabulary').textContent = '生词复习 · 待掌握 ' + spacedReview.state.available_words + ' 词';
        }
    },
    render: function() {
        var list = document.getElementById('vocabularyList');
        list.replaceChildren();
        if (!this.words.size) {
            list.textContent = '暂无生词。选中单词或词组，点击“句中释义”即可收录。';
            return;
        }
        var shown = 0;
        this.words.forEach(function(entry, key) {
            if (typeof spacedReview !== 'undefined' && !spacedReview.include(key)) return;
            shown++;
            var item = document.createElement('div');
            item.className = 'vocabulary-item';
            var button = document.createElement('button');
            button.type = 'button';
            button.textContent = entry.word;
            button.setAttribute('aria-expanded', 'false');
            var details = document.createElement('div');
            details.hidden = true;
            (entry.sources || []).forEach(function(source) {
                var block = document.createElement('section'); block.className = 'vocabulary-source';
                var title = document.createElement('p'); title.textContent = source.article_title;
                var sentence = document.createElement('blockquote'); sentence.textContent = source.sentence;
                var meaning = document.createElement('p'); meaning.textContent = source.meaning;
                var locate = document.createElement('button'); locate.textContent = '定位原句'; locate.className = 'vocabulary-locate';
                locate.onclick = function() { reviewModule.locate(source); };
                block.append(title, sentence, locate, meaning); details.appendChild(block);
            });
            button.addEventListener('click', function() {
                details.hidden = !details.hidden;
                button.setAttribute('aria-expanded', String(!details.hidden));
            });
            item.append(button, details);
            if (typeof spacedReview !== 'undefined') spacedReview.decorate(item, entry, key);
            list.appendChild(item);
        });
        if (!shown) list.textContent = '这里暂时没有词条。';
    },
    locate: function(source) {
        var self = this;
        if (articleModule.isLoading || agentModule.isStreaming) { showToast('请先等待当前加载或回答结束。'); return; }
        function selectSentence() {
            if (!articleModule.currentArticle || articleModule.currentArticle.id !== source.article_id) throw new Error('文章无法打开，可能已删除。');
            var sentences = Array.from(document.querySelectorAll('#articleBody .sentence'));
            var target = sentences.find(function(el) { return el.dataset.idx === source.sentence_idx && el.textContent.trim() === source.sentence.trim(); }) || sentences.find(function(el) { return el.textContent.trim() === source.sentence.trim(); });
            if (!target) throw new Error('文章内容已修改，未找到原句；词库中仍保留原句快照。');
            homeModule.showReader();
            agentModule.clearFocus();
            sentences.forEach(function(el) { el.classList.remove('selected'); });
            target.classList.add('selected');
            articleModule.selectedSentenceIdx = target.dataset.idx;
            window.__currentIdx = target.dataset.idx;
            agentModule.showSelectedSentence(target.textContent, target.dataset.idx);
            document.getElementById('vocabularyDialog').close();
            target.scrollIntoView({ block: 'center', behavior: 'smooth' });
        }
        async function navigate() {
            try {
                if (!articleModule.currentArticle || articleModule.currentArticle.id !== source.article_id) {
                    var match = /^zhenti_(\d{4})_([1-5])$/.exec(source.article_id);
                    if (match) await articleModule.loadZhenti(Number(match[1]), Number(match[2]));
                    else {
                        var data = await api.getArticleList(getToken());
                        var article = data.articles.find(function(a) { return a.id === source.article_id; });
                        if (!article) throw new Error('原文章已删除或不可用，仍可在词库查看原句。');
                        await articleModule.loadByIndex(article.index);
                    }
                }
                selectSentence();
            } catch (error) { showToast(error.message, 'error'); }
        }
        if (articleModule.currentArticle && articleModule.currentArticle.id !== source.article_id) {
            document.getElementById('vocabularyDialog').close();
            showConfirm('跳转将切换文章并清空当前问答，已保存的生词不受影响。继续吗？', navigate);
        } else navigate();
    },
    updateNavigation: function() {
        var count = document.querySelectorAll('#chatMessages .question-label').length;
        var button = document.getElementById('btnPreviousQuestion');
        button.disabled = !count || this.cursor === 0;
        document.getElementById('btnNextQuestion').disabled = !count || this.cursor === count - 1;
    },
    previous: function() {
        this.jump(-1);
    },
    jump: function(direction) {
        var chat = document.getElementById('chatMessages');
        var questions = chat.querySelectorAll('.question-label');
        if (!questions.length) return;
        var target;
        if (this.cursor !== null) {
            target = Math.min(questions.length - 1, Math.max(0, this.cursor + direction));
        } else {
            target = direction < 0 ? 0 : questions.length - 1;
            var top = chat.getBoundingClientRect().top + chat.clientTop;
            for (var i = 0; i < questions.length; i++) {
                var questionTop = questions[i].getBoundingClientRect().top;
                if (direction < 0 && questionTop < top - 2) target = i;
                if (direction > 0 && questionTop > top + 2) { target = i; break; }
            }
        }
        this.cursor = target;
        var offset = questions[target].getBoundingClientRect().top - chat.getBoundingClientRect().top - chat.clientTop;
        chat.scrollTo({ top: chat.scrollTop + offset, behavior: 'smooth' });
        this.updateNavigation();
    }
};
