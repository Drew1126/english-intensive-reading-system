window.agentModule = {
    isStreaming: false,
    selectedFocusWord: "",

    showSelectedSentence(sentence, idx) {
        const el = document.getElementById("selectedSentence");
        el.innerHTML = "";

        const translation = window.__translations?.[idx] || "";
        const showTrans = window.__showTrans && translation;
        const text = showTrans ? sentence + "\n" + translation : sentence;

        const p = document.createElement("p");
        p.className = "sentence-text";
        p.textContent = text;
        p.style.cssText = "color:var(--text-primary);font-style:normal;margin:0;white-space:pre-wrap;";
        el.appendChild(p);

        if (this.selectedFocusWord) {
            const focusEl = document.createElement("span");
            focusEl.className = "focus-wrapper";
            focusEl.innerHTML = `<span class="focus-word">${this.escapeHtml(this.selectedFocusWord)}</span> <span class="clear-focus" onclick="agentModule.clearFocus()">×</span>`;
            el.appendChild(focusEl);
        }
    },

    selectFocusWord(word) {
        this.selectedFocusWord = word;
        const p = document.querySelector("#selectedSentence .sentence-text");
        if (p && p.textContent.trim()) {
            this.showSelectedSentence(p.textContent.split("\n")[0], window.__currentIdx);
        } else if (window.__currentIdx) {
            const sentenceEl = document.querySelector(`.sentence[data-idx="${window.__currentIdx}"]`);
            if (sentenceEl) {
                this.showSelectedSentence(sentenceEl.textContent.trim(), window.__currentIdx);
            }
        }
    },

    clearFocus() {
        this.selectedFocusWord = "";
        if (typeof articleModule !== "undefined" && articleModule.focusWords) {
            articleModule.focusWords = [];
            articleModule.clearWordHighlight();
        }
        const p = document.querySelector("#selectedSentence .sentence-text");
        if (p && p.textContent.trim()) {
            this.showSelectedSentence(p.textContent, window.__currentIdx);
        } else {
            document.getElementById("selectedSentence").innerHTML =
                '<p style="color:var(--text-muted);text-align:center;font-style:italic;">点击文章中的句子开始提问</p>';
        }
    },

    highlightFocusInArticle(word) {
        const body = document.getElementById("articleBody");
        if (!body) return;
        const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT, null);
        const textNodes = [];
        let node;
        while (node = walker.nextNode()) {
            if (node.textContent.includes(word)) {
                textNodes.push(node);
            }
        }
        if (textNodes.length === 0) return;

        const firstNode = textNodes[0];
        const parent = firstNode.parentElement;
        if (!parent) return;
        parent.classList.add("focus-highlight");
    },

    clearFocusHighlight() {
        document.querySelectorAll(".focus-highlight").forEach(el => {
            el.classList.remove("focus-highlight");
        });
    },

    sendQuestion(question) {
        const sentence = document.querySelector(".sentence.selected");
        if (!sentence && !this.selectedFocusWord) {
            alert("请先点击文章中的内容");
            return;
        }
        const sentenceText = sentence ? sentence.textContent.trim() : this.selectedFocusWord;
        const articleId = articleModule.currentArticle?.id || "";
        this.streamAnswer(sentenceText, question, articleId, this.selectedFocusWord);
    },

    appendMessage(question, answer) {
        const container = document.getElementById("chatMessages");
        const msgEl = document.createElement("div");
        msgEl.className = "message";
        msgEl.innerHTML = `
            <div class="question-label">Q: ${this.escapeHtml(question)}</div>
            <div class="answer-content">${this.escapeHtml(answer)}</div>
        `;
        container.appendChild(msgEl);
        container.scrollTop = container.scrollHeight;
        return msgEl;
    },

    async streamAnswer(sentence, question, articleId, focus) {
        if (this.isStreaming) {
            this.isStreaming = false;
            document.getElementById("btnSend").disabled = false;
        }
        this.isStreaming = true;
        document.getElementById("btnSend").disabled = true;

        const container = document.getElementById("chatMessages");
        const msgEl = document.createElement("div");
        msgEl.className = "message";
        const focusLabel = focus ? `<span class="focus-tag">${this.escapeHtml(focus)}</span> ` : "";
        msgEl.innerHTML = `
            <div class="question-label">${focusLabel}Q: ${this.escapeHtml(question)}</div>
            <div class="answer-content"></div>
        `;
        container.appendChild(msgEl);
        const answerEl = msgEl.querySelector(".answer-content");
        msgEl.scrollIntoView({ block: "start", behavior: "smooth" });

        let fullAnswer = "";
        const source = api.askAgent(sentence, question, articleId, focus);

        const timeout = setTimeout(() => {
            source.close();
            this.isStreaming = false;
            document.getElementById("btnSend").disabled = false;
            if (!fullAnswer) {
                answerEl.textContent = "请求超时，请重试";
            }
        }, 90000);

        source.onmessage = (e) => {
            if (e.data === "[DONE]") {
                clearTimeout(timeout);
                source.close();
                this.isStreaming = false;
                this.clearFocusHighlight();
                this.selectedFocusWord = "";
                document.getElementById("btnSend").disabled = false;
                return;
            }
            try {
                const { text } = JSON.parse(e.data);
                fullAnswer += text;
                answerEl.textContent = fullAnswer;
            } catch (err) {
                console.error("Parse SSE error:", err);
            }
        };

        source.onerror = (err) => {
            clearTimeout(timeout);
            source.close();
            this.isStreaming = false;
            document.getElementById("btnSend").disabled = false;
            if (!fullAnswer) {
                answerEl.textContent = "请求失败，请重试";
            }
        };
    },

    escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }
};
