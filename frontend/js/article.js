const articleModule = {
    currentArticle: null,
    showTranslation: false,
    selectedSentenceIdx: null,
    isLoading: false,

    async loadCurrent() {
        if (this.isLoading) return;
        this.isLoading = true;
        this._resetView();

        try {
            const data = await api.getCurrentArticle();
            this.currentArticle = data.article;
            this._buildTranslations();
            this.renderArticle(this.currentArticle);
        } catch (err) {
            document.getElementById("articleBody").innerHTML = `<div class="loading">加载失败：${err.message}</div>`;
        } finally {
            this.isLoading = false;
        }
    },

    async loadNext() {
        if (this.isLoading) return;
        document.getElementById("btnNextArticle").disabled = true;
        this.isLoading = true;

        try {
            const data = await api.getNextArticle();
            this.currentArticle = data.article;
            this._buildTranslations();
            this._resetView();
            this.renderArticle(data.article);
        } catch (err) {
            console.error("获取文章失败:", err);
        } finally {
            document.getElementById("btnNextArticle").disabled = false;
            this.isLoading = false;
        }
    },

    _resetView() {
        this.selectedSentenceIdx = null;
        this.showTranslation = false;
        window.__showTrans = false;
        const toggle = document.getElementById("sentenceTranslationToggle");
        if (toggle) toggle.checked = false;
        agentModule.clearFocus();
        document.getElementById("chatMessages").innerHTML = "";
        const bodyEl = document.getElementById("articleBody");
        bodyEl.innerHTML = '<div class="loading">加载中...</div>';
    },

    _buildTranslations() {
        window.__translations = {};
        if (!this.currentArticle?.paragraphs) return;
        this.currentArticle.paragraphs.forEach((para, pIdx) => {
            (para.translations || []).forEach((t, sIdx) => {
                window.__translations[`${pIdx}-${sIdx}`] = t;
            });
        });
    },

    renderArticle(article) {
        document.getElementById("sourceTag").textContent = article.source;
        document.getElementById("wordCountTag").textContent = `${article.word_count} 词`;
        document.getElementById("articleTitle").textContent = article.title;

        const bodyEl = document.getElementById("articleBody");
        bodyEl.innerHTML = "";

        article.paragraphs.forEach((para, pIdx) => {
            const paraEl = document.createElement("div");
            paraEl.className = "paragraph";
            paraEl.dataset.paraIndex = pIdx;

            const textEl = document.createElement("p");

            para.sentences.forEach((sentence, sIdx) => {
                const globalIdx = `${pIdx}-${sIdx}`;
                const span = document.createElement("span");
                span.className = "sentence";
                span.dataset.idx = globalIdx;
                span.textContent = sentence + " ";
                textEl.appendChild(span);
            });
            paraEl.appendChild(textEl);
            bodyEl.appendChild(paraEl);
        });

        this.setupArticleInteractions(bodyEl);
    },

    setupArticleInteractions(bodyEl) {
        this.focusWords = [];

        let clickTimer = null;
        let pendingClickInfo = null;

        bodyEl.addEventListener("click", (e) => {
            if (!e.target.closest(".sentence")) return;

            const wordInfo = this.getWordInfoAtPoint(e.clientX, e.clientY);
            if (!wordInfo) return;

            clearTimeout(clickTimer);
            pendingClickInfo = wordInfo;

            clickTimer = setTimeout(() => {
                if (!pendingClickInfo) return;
                const info = pendingClickInfo;
                pendingClickInfo = null;

                const sentenceEl = info.sentenceEl;
                const idx = sentenceEl?.dataset.idx;
                if (idx) {
                    document.querySelectorAll(".sentence.selected").forEach(s => s.classList.remove("selected"));
                    sentenceEl.classList.add("selected");
                    this.selectedSentenceIdx = idx;
                    window.__currentIdx = idx;
                    agentModule.showSelectedSentence(sentenceEl.textContent.trim(), idx);
                }

                if (this.focusWords.length > 0 && this.focusWords[0].sentenceEl !== info.sentenceEl) {
                    this.focusWords = [];
                }

                const existingIdx = this.focusWords.findIndex(
                    fw => fw.sentenceEl === info.sentenceEl && fw.offset === info.offset
                );
                if (existingIdx !== -1) {
                    this.focusWords.splice(existingIdx, 1);
                } else {
                    this.focusWords.push(info);
                }

                this.updateFocusWordDisplay();
            }, 220);
        });

        bodyEl.addEventListener("dblclick", (e) => {
            clearTimeout(clickTimer);
            pendingClickInfo = null;

            const sentenceSpan = e.target.closest(".sentence");
            if (!sentenceSpan) return;

            this.focusWords = [];
            this.clearWordHighlight();
            agentModule.clearFocus();

            const text = sentenceSpan.textContent.trim();
            const idx = sentenceSpan.dataset.idx;
            document.querySelectorAll(".sentence.selected").forEach(s => s.classList.remove("selected"));
            sentenceSpan.classList.add("selected");
            this.selectedSentenceIdx = idx;
            window.__currentIdx = idx;
            agentModule.showSelectedSentence(text, idx);
        });

        bodyEl.addEventListener("contextmenu", (e) => {
            e.preventDefault();
        });
    },

    getWordInfoAtPoint(x, y) {
        const pos = document.caretPositionFromPoint(x, y);
        if (!pos || !pos.offsetNode) return null;
        const node = pos.offsetNode;
        if (node.nodeType !== Node.TEXT_NODE) return null;

        const sentenceEl = node.parentElement?.closest(".sentence");
        if (!sentenceEl) return null;

        const text = node.textContent;
        const charPos = pos.offset;
        const wordRegex = /[\w'-]/;

        let start = charPos, end = charPos;
        while (start > 0 && wordRegex.test(text[start - 1])) start--;
        while (end < text.length && wordRegex.test(text[end])) end++;
        if (start === end) return null;

        const word = text.slice(start, end);

        const walker = document.createTreeWalker(sentenceEl, NodeFilter.SHOW_TEXT, null);
        let sentenceOffset = 0;
        let n;
        while (n = walker.nextNode()) {
            if (n === node) {
                sentenceOffset += start;
                break;
            }
            sentenceOffset += n.textContent.length;
        }

        return { word, sentenceEl, offset: sentenceOffset };
    },

    updateFocusWordDisplay() {
        this.clearWordHighlight();

        if (this.focusWords.length === 0) {
            agentModule.selectedFocusWord = "";
            return;
        }

        const sorted = [...this.focusWords].sort((a, b) => a.offset - b.offset);
        const sentenceText = sorted[0].sentenceEl.textContent;

        const groups = [[sorted[0]]];
        for (let i = 1; i < sorted.length; i++) {
            const prev = sorted[i - 1];
            const curr = sorted[i];
            const between = sentenceText.slice(prev.offset + prev.word.length, curr.offset);
            if (/^\s*$/.test(between)) {
                groups[groups.length - 1].push(curr);
            } else {
                groups.push([curr]);
            }
        }

        const focusString = groups.map(g => g.map(fw => fw.word).join(" ")).join("...");

        for (const fw of this.focusWords) {
            this.highlightWordAtOffset(fw.sentenceEl, fw.offset, fw.word.length);
        }

        const sentenceEl = sorted[0].sentenceEl;
        document.querySelectorAll(".sentence.selected").forEach(s => s.classList.remove("selected"));
        sentenceEl.classList.add("selected");
        this.selectedSentenceIdx = sentenceEl.dataset.idx;

        agentModule.selectFocusWord(focusString);
    },

    highlightWordAtOffset(sentenceEl, targetOffset, length) {
        const walker = document.createTreeWalker(sentenceEl, NodeFilter.SHOW_TEXT, null);
        let cumOffset = 0;
        let node;
        while (node = walker.nextNode()) {
            const nodeLen = node.textContent.length;
            if (cumOffset + nodeLen > targetOffset) {
                const localOffset = targetOffset - cumOffset;
                if (localOffset >= 0 && localOffset + length <= nodeLen) {
                    try {
                        const range = document.createRange();
                        range.setStart(node, localOffset);
                        range.setEnd(node, localOffset + length);
                        const span = document.createElement("span");
                        span.className = "focus-word-selected";
                        range.surroundContents(span);
                    } catch (err) {
                        console.warn("highlightWordAtOffset error:", err);
                    }
                    return;
                }
            }
            cumOffset += nodeLen;
        }
    },

    clearWordHighlight() {
        document.querySelectorAll(".focus-word-selected").forEach(el => {
            const parent = el.parentNode;
            parent.replaceChild(document.createTextNode(el.textContent), el);
            parent.normalize();
        });
    },

    selectSentenceFromText(text) {
        const sentences = document.querySelectorAll(".sentence");
        for (const span of sentences) {
            if (span.textContent.includes(text)) {
                document.querySelectorAll(".sentence.selected").forEach(s => s.classList.remove("selected"));
                span.classList.add("selected");
                this.selectedSentenceIdx = span.dataset.idx;
                agentModule.showSelectedSentence(span.textContent.trim(), span.dataset.idx);
                return;
            }
        }
    },

    selectSentence(idx, sentence, el) {
        document.querySelectorAll(".sentence.selected").forEach(s => s.classList.remove("selected"));
        el.classList.add("selected");
        this.selectedSentenceIdx = idx;
        window.__currentIdx = idx;
        agentModule.showSelectedSentence(sentence, idx);
    },

};
