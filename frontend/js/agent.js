var agentModule = {
    isStreaming: false,
    selectedFocusWord: "",
    activeSource: null,
    activeRequest: null,

    showSelectedSentence: function(sentence, idx) {
        var el = document.getElementById("selectedSentence");
        el.innerHTML = "";
        var translation = (window.__translations && window.__translations[idx]) || "";
        var showTrans = window.__showTrans && translation;
        var text = showTrans ? translation : sentence;
        var p = document.createElement("p");
        p.className = "sentence-text";
        p.dataset.en = sentence;
        p.textContent = text;
        p.style.cssText = "color:var(--text-primary);font-style:normal;margin:0;white-space:pre-wrap;";
        el.appendChild(p);
        if (this.selectedFocusWord) {
            var focusEl = document.createElement("span");
            focusEl.className = "focus-wrapper";
            focusEl.innerHTML = '<span class="focus-word">' + this.escapeHtml(this.selectedFocusWord) + '</span> <span class="clear-focus" onclick="agentModule.clearFocus()">\u00d7</span>';
            el.appendChild(focusEl);
        }
    },

    selectFocusWord: function(word) {
        this.selectedFocusWord = word;
        var p = document.querySelector("#selectedSentence .sentence-text");
        if (p && (p.dataset.en || p.textContent).trim()) {
            this.showSelectedSentence(p.dataset.en || p.textContent, window.__currentIdx);
        } else if (window.__currentIdx) {
            var sentenceEl = document.querySelector('.sentence[data-idx="' + window.__currentIdx + '"]');
            if (sentenceEl) { this.showSelectedSentence(sentenceEl.textContent.trim(), window.__currentIdx); }
        }
    },

    clearFocus: function() {
        this.selectedFocusWord = "";
        if (articleModule.focusWords) { articleModule.focusWords = []; articleModule.clearWordHighlight(); }
        var p = document.querySelector("#selectedSentence .sentence-text");
        if (p && (p.dataset.en || p.textContent).trim()) {
            this.showSelectedSentence(p.dataset.en || p.textContent, window.__currentIdx);
        } else {
            document.getElementById("selectedSentence").innerHTML = '<p style="color:var(--text-muted);text-align:center;font-style:italic;">点击文章中的句子开始提问</p>';
        }
    },

    sendQuestion: function(question) {
        var sentence = document.querySelector(".sentence.selected");
        if (!sentence && !this.selectedFocusWord) { showToast("请先点击文章中的单词或句子", "error"); return; }
        var sentenceText = sentence ? sentence.textContent.trim() : this.selectedFocusWord;
        var articleId = (articleModule.currentArticle && articleModule.currentArticle.id) || "";
        this.streamAnswer(sentenceText, question, articleId, this.selectedFocusWord);
    },

    setStreaming: function(streaming) {
        this.isStreaming = streaming;
        var button = document.getElementById("btnSend");
        button.disabled = false;
        button.textContent = streaming ? "停止" : "发送";
        button.classList.toggle("is-stop", streaming);
    },

    stopAnswer: function() {
        if (!this.isStreaming) return;
        if (this.activeSource) this.activeSource.close();
        this.activeSource = null;
        if (this.activeRequest && this.activeRequest.timeout) clearTimeout(this.activeRequest.timeout);
        this.setStreaming(false);
        if (this.activeRequest && this.activeRequest.statusEl) {
            this.activeRequest.statusEl.innerHTML = "<span>已停止生成</span>";
            this.addMessageActions(this.activeRequest);
        }
    },

    addMessageActions: function(request) {
        if (request.actionsEl.childElementCount) return;
        var self = this;
        var retry = document.createElement("button");
        retry.className = "message-action";
        retry.textContent = "重新生成";
        retry.addEventListener("click", function() {
            if (self.isStreaming) return;
            request.msgEl.remove();
            self.streamAnswer(request.sentence, request.question, request.articleId, request.focus);
        });
        request.actionsEl.appendChild(retry);
        if (request.answerEl.textContent.trim()) {
            var copy = document.createElement("button");
            copy.className = "message-action";
            copy.textContent = "复制回答";
            copy.addEventListener("click", function() {
                navigator.clipboard.writeText(request.answerEl.textContent).then(function() { showToast("回答已复制", "success"); });
            });
            request.actionsEl.appendChild(copy);
        }
    },

    streamAnswer: function(sentence, question, articleId, focus) {
        if (this.isStreaming) return;
        this.setStreaming(true);
        var container = document.getElementById("chatMessages");
        var empty = document.getElementById("chatEmpty");
        if (empty) empty.remove();
        var msgEl = document.createElement("div");
        msgEl.className = "message";
        var focusLabel = focus ? '<span class="focus-tag">' + this.escapeHtml(focus) + '</span> ' : "";
        msgEl.innerHTML = '<div class="question-label">' + focusLabel + 'Q: ' + this.escapeHtml(question) + '</div><div class="answer-status"><span class="thinking-dot"></span><span>正在思考…</span></div><div class="answer-content"></div><div class="message-actions"></div>';
        container.appendChild(msgEl);
        var answerEl = msgEl.querySelector(".answer-content");
        var statusEl = msgEl.querySelector(".answer-status");
        var actionsEl = msgEl.querySelector(".message-actions");
        msgEl.scrollIntoView({ block: "start", behavior: "smooth" });
        var self = this;
        var fullAnswer = "";
        var streamFinished = false;
        var startedAt = performance.now();
        var source = api.askAgent(sentence, question, articleId, focus, (typeof getName === "function") ? getName() : "");
        var request = { sentence: sentence, question: question, articleId: articleId, focus: focus, msgEl: msgEl, answerEl: answerEl, statusEl: statusEl, actionsEl: actionsEl };
        this.activeSource = source;
        this.activeRequest = request;
        var timeout = setTimeout(function() {
            if (!streamFinished) {
                streamFinished = true;
                source.close(); self.activeSource = null; self.setStreaming(false);
                statusEl.innerHTML = '<span class="message-error">请求超时，服务器在 90 秒内没有完成回答。</span>';
                self.addMessageActions(request);
            }
        }, 90000);
        request.timeout = timeout;
        source.onmessage = function(e) {
            if (streamFinished) return;
            if (e.data === "[DONE]") {
                streamFinished = true;
                clearTimeout(timeout); source.close(); self.activeSource = null; self.setStreaming(false);
                self.selectedFocusWord = "";
                statusEl.innerHTML = "<span>回答完成 · " + ((performance.now() - startedAt) / 1000).toFixed(1) + " 秒</span>";
                self.addMessageActions(request);
                return;
            }
            try {
                var p = JSON.parse(e.data);
                fullAnswer = (fullAnswer + p.text).replace(/\n[ \t]*\n+/g, "\n");
                answerEl.textContent = fullAnswer;
            } catch (err) { console.error("Parse SSE error:", err); }
        };
        source.onerror = function() {
            if (streamFinished) return;
            streamFinished = true;
            clearTimeout(timeout); source.close(); self.activeSource = null; self.setStreaming(false);
            statusEl.innerHTML = '<span class="message-error">连接中断，可能是网络异常或服务暂时不可用。</span>';
            self.addMessageActions(request);
        };
    },

    escapeHtml: function(text) {
        var div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }
};
