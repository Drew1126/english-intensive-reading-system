var articleModule = {
    currentArticle: null,
    selectedSentenceIdx: null,
    isLoading: false,
    focusWords: [],

    loadCurrent: function() {
        var self = this;
        if (this.isLoading) return;
        this.isLoading = true;
        document.getElementById("articleBody").innerHTML = '<div class="loading">加载中...</div>';
        api.getCurrentArticle().then(function(data) {
            if (!data.article) {
                document.getElementById("articleBody").innerHTML = '<div class="loading">暂无文章，请上传 PDF</div>';
                return;
            }
            self.currentArticle = data.article;
            self._buildTranslations();
            self.renderArticle(self.currentArticle);
        }).catch(function(err) {
            document.getElementById("articleBody").innerHTML = '<div class="loading">加载失败：' + err.message + '</div>';
        }).then(function() { self.isLoading = false; });
    },

    loadByIndex: function(index) {
        var self = this;
        if (this.isLoading) return;
        this.isLoading = true;
        this._resetView();
        document.getElementById("articleBody").innerHTML = '<div class="loading">加载中...</div>';
        api.getArticle(index).then(function(data) {
            self.currentArticle = data.article;
            self._buildTranslations();
            self.renderArticle(data.article);
        }).catch(function(err) {
            document.getElementById("articleBody").innerHTML = '<div class="loading">加载失败：' + err.message + '</div>';
        }).then(function() { self.isLoading = false; });
    },

    loadFromPdf: function(file) {
        var self = this;
        if (this.isLoading) return;
        this.isLoading = true;
        document.getElementById("btnUploadPdf").disabled = true;
        document.getElementById("articleBody").innerHTML = '<div class="loading">解析 PDF 中...</div>';
        api.uploadPdf(file).then(function(data) {
            self.currentArticle = data.article;
            self._buildTranslations();
            self._resetView();
            self.renderArticle(data.article);
        }).catch(function(err) {
            document.getElementById("articleBody").innerHTML = '<div class="loading">PDF 解析失败：' + err.message + '</div>';
        }).then(function() {
            document.getElementById("btnUploadPdf").disabled = false;
            self.isLoading = false;
        });
    },

    showHistory: function() {
        var self = this;
        var overlay = document.getElementById("historyOverlay");
        var list = document.getElementById("historyList");
        list.innerHTML = '<div class="loading">加载中...</div>';
        overlay.style.display = "flex";
        var token = getToken && getToken();
        api.getArticleList().then(function(data) {
            list.innerHTML = "";
            var articles = data.articles || [];
            if (articles.length === 0) {
                list.innerHTML = '<div class="loading">暂无历史文章</div>';
                return;
            }
            articles.forEach(function(a) {
                var item = document.createElement("div");
                item.className = "history-item";
                if (self.currentArticle && self.currentArticle.id === a.id) {
                    item.classList.add("current");
                }
                var info = document.createElement("div");
                info.className = "history-item-info";
                info.innerHTML = '<div class="history-item-title">' + (a.title || "无标题") + '</div><div class="history-item-meta">' + (a.source || "?") + ' · ' + (a.word_count || "?") + ' 词 · ' + (a.date || "?") + '</div>';
                info.addEventListener("click", function(idx) {
                    return function() {
                        overlay.style.display = "none";
                        self.loadByIndex(idx);
                    };
                }(a.index));
                item.appendChild(info);
                if (token) {
                    var delBtn = document.createElement("button");
                    delBtn.className = "history-del-btn";
                    delBtn.textContent = "删除";
                    delBtn.addEventListener("click", function(idx) {
                        return function(e) {
                            e.stopPropagation();
                            if (!confirm("确定删除《" + (a.title || "无标题") + "》？")) return;
                            api.deleteArticle(idx, token).then(function() {
                                self.showHistory();
                                if (self.currentArticle && self.currentArticle.article_index === idx) {
                                    self.currentArticle = null;
                                    document.getElementById("articleBody").innerHTML = '<div class="loading">文章已删除</div>';
                                }
                            }).catch(function(err) { alert("删除失败: " + err.message); });
                        };
                    }(a.index));
                    item.appendChild(delBtn);
                }
                list.appendChild(item);
            });
        }).catch(function(err) {
            list.innerHTML = '<div class="loading">获取失败：' + err.message + '</div>';
        });
    },

    _resetView: function() {
        this.selectedSentenceIdx = null;
        window.__showTrans = false;
        var toggle = document.getElementById("sentenceTranslationToggle");
        if (toggle) toggle.checked = false;
        agentModule.clearFocus();
        document.getElementById("chatMessages").innerHTML = "";
    },

    _buildTranslations: function() {
        window.__translations = {};
        if (!this.currentArticle || !this.currentArticle.paragraphs) return;
        this.currentArticle.paragraphs.forEach(function(para, pIdx) {
            (para.translations || []).forEach(function(t, sIdx) {
                window.__translations[pIdx + "-" + sIdx] = t;
            });
        });
    },

    renderArticle: function(article) {
        document.getElementById("sourceTag").textContent = article.source;
        document.getElementById("wordCountTag").textContent = article.word_count + " 词";
        document.getElementById("articleTitle").textContent = article.title;
        var bodyEl = document.getElementById("articleBody");
        var container = document.createElement("div");
        article.paragraphs.forEach(function(para, pIdx) {
            var paraEl = document.createElement("div");
            paraEl.className = "paragraph";
            paraEl.dataset.paraIndex = pIdx;
            var textEl = document.createElement("p");
            para.sentences.forEach(function(sentence, sIdx) {
                var span = document.createElement("span");
                span.className = "sentence";
                span.dataset.idx = pIdx + "-" + sIdx;
                span.textContent = sentence + " ";
                textEl.appendChild(span);
            });
            paraEl.appendChild(textEl);
            container.appendChild(paraEl);
        });
        bodyEl.innerHTML = "";
        bodyEl.appendChild(container);
        this.setupArticleInteractions(container);
        if (typeof updateCheckinArea === "function") { updateCheckinArea(); }
    },

    setupArticleInteractions: function(bodyEl) {
        var self = this;
        this.focusWords = [];
        var clickTimer = null;
        var pendingClickInfo = null;

        bodyEl.addEventListener("click", function(e) {
            var sentenceEl = e.target.closest(".sentence");
            if (!sentenceEl) return;
            var wordInfo = self.getWordInfoAtPoint(e.clientX, e.clientY);
            if (!wordInfo) return;
            clearTimeout(clickTimer);
            pendingClickInfo = wordInfo;
            clickTimer = setTimeout(function() {
                if (!pendingClickInfo) return;
                var info = pendingClickInfo;
                pendingClickInfo = null;
                var sentenceEl = info.sentenceEl;
                var idx = sentenceEl ? sentenceEl.dataset.idx : null;
                if (idx) {
                    document.querySelectorAll(".sentence.selected").forEach(function(s) { s.classList.remove("selected"); });
                    sentenceEl.classList.add("selected");
                    self.selectedSentenceIdx = idx;
                    window.__currentIdx = idx;
                    agentModule.showSelectedSentence(sentenceEl.textContent.trim(), idx);
                }
                if (self.focusWords.length > 0 && self.focusWords[0].sentenceEl !== info.sentenceEl) { self.focusWords = []; }
                var existingIdx = self.focusWords.findIndex(function(fw) { return fw.sentenceEl === info.sentenceEl && fw.offset === info.offset; });
                if (existingIdx !== -1) { self.focusWords.splice(existingIdx, 1); } else { self.focusWords.push(info); }
                self.updateFocusWordDisplay();
            }, 220);
        });

        bodyEl.addEventListener("dblclick", function(e) {
            clearTimeout(clickTimer);
            pendingClickInfo = null;
            var sentenceSpan = e.target.closest(".sentence");
            if (!sentenceSpan) return;
            self.focusWords = [];
            self.clearWordHighlight();
            agentModule.clearFocus();
            var text = sentenceSpan.textContent.trim();
            var idx = sentenceSpan.dataset.idx;
            document.querySelectorAll(".sentence.selected").forEach(function(s) { s.classList.remove("selected"); });
            sentenceSpan.classList.add("selected");
            self.selectedSentenceIdx = idx;
            window.__currentIdx = idx;
            agentModule.showSelectedSentence(text, idx);
        });

        bodyEl.addEventListener("contextmenu", function(e) { e.preventDefault(); });
    },

    getWordInfoAtPoint: function(x, y) {
        var node, offset;
        if (document.caretPositionFromPoint) {
            var pos = document.caretPositionFromPoint(x, y);
            if (pos && pos.offsetNode) { node = pos.offsetNode; offset = pos.offset; }
        } else if (document.caretRangeFromPoint) {
            var range = document.caretRangeFromPoint(x, y);
            if (range && range.startContainer) { node = range.startContainer; offset = range.startOffset; }
        } else {
            return null;
        }
        var sentenceEl = node.parentElement ? node.parentElement.closest(".sentence") : null;
        if (!sentenceEl) return null;
        var text = node.textContent;
        var wordRegex = /[\w'-]/;
        var start = offset, end = offset;
        while (start > 0 && wordRegex.test(text[start - 1])) start--;
        while (end < text.length && wordRegex.test(text[end])) end++;
        if (start === end) return null;
        var word = text.slice(start, end);
        var walker = document.createTreeWalker(sentenceEl, NodeFilter.SHOW_TEXT, null);
        var sentenceOffset = 0;
        var n;
        while ((n = walker.nextNode())) {
            if (n === node) { sentenceOffset += start; break; }
            sentenceOffset += n.textContent.length;
        }
        return { word: word, sentenceEl: sentenceEl, offset: sentenceOffset };
    },

    updateFocusWordDisplay: function() {
        this.clearWordHighlight();
        if (this.focusWords.length === 0) { agentModule.selectedFocusWord = ""; return; }
        var sorted = Array.prototype.slice.call(this.focusWords).sort(function(a, b) { return a.offset - b.offset; });
        var sentenceText = sorted[0].sentenceEl.textContent;
        var groups = [[sorted[0]]];
        for (var i = 1; i < sorted.length; i++) {
            var prev = sorted[i - 1], curr = sorted[i];
            var between = sentenceText.slice(prev.offset + prev.word.length, curr.offset);
            if (/^\s*$/.test(between)) { groups[groups.length - 1].push(curr); } else { groups.push([curr]); }
        }
        var focusString = groups.map(function(g) { return g.map(function(fw) { return fw.word; }).join(" "); }).join("...");
        for (var j = 0; j < this.focusWords.length; j++) {
            this.highlightWordAtOffset(this.focusWords[j].sentenceEl, this.focusWords[j].offset, this.focusWords[j].word.length);
        }
        var selEl = sorted[0].sentenceEl;
        document.querySelectorAll(".sentence.selected").forEach(function(s) { s.classList.remove("selected"); });
        selEl.classList.add("selected");
        this.selectedSentenceIdx = selEl.dataset.idx;
        agentModule.selectFocusWord(focusString);
    },

    highlightWordAtOffset: function(sentenceEl, targetOffset, length) {
        var walker = document.createTreeWalker(sentenceEl, NodeFilter.SHOW_TEXT, null);
        var cumOffset = 0;
        var node;
        while ((node = walker.nextNode())) {
            var nodeLen = node.textContent.length;
            if (cumOffset + nodeLen > targetOffset) {
                var localOffset = targetOffset - cumOffset;
                if (localOffset >= 0 && localOffset + length <= nodeLen) {
                    try {
                        var range = document.createRange();
                        range.setStart(node, localOffset);
                        range.setEnd(node, localOffset + length);
                        var span = document.createElement("span");
                        span.className = "focus-word-selected";
                        range.surroundContents(span);
                    } catch (err) { /* skip */ }
                    return;
                }
            }
            cumOffset += nodeLen;
        }
    },

    clearWordHighlight: function() {
        document.querySelectorAll(".focus-word-selected").forEach(function(el) {
            var parent = el.parentNode;
            parent.replaceChild(document.createTextNode(el.textContent), el);
            parent.normalize();
        });
    },

    selectSentence: function(idx, sentence, el) {
        document.querySelectorAll(".sentence.selected").forEach(function(s) { s.classList.remove("selected"); });
        el.classList.add("selected");
        this.selectedSentenceIdx = idx;
        window.__currentIdx = idx;
        agentModule.showSelectedSentence(sentence, idx);
    }
};
