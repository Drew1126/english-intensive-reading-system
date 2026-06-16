var agentModule = {
    isStreaming: false,
    selectedFocusWord: "",

    showSelectedSentence: function(sentence, idx) {
        var el = document.getElementById("selectedSentence");
        el.innerHTML = "";
        var translation = (window.__translations && window.__translations[idx]) || "";
        var showTrans = window.__showTrans && translation;
        var text = showTrans ? sentence + "\n" + translation : sentence;
        var p = document.createElement("p");
        p.className = "sentence-text";
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
        if (p && p.textContent.trim()) {
            this.showSelectedSentence(p.textContent.split("\n")[0], window.__currentIdx);
        } else if (window.__currentIdx) {
            var sentenceEl = document.querySelector('.sentence[data-idx="' + window.__currentIdx + '"]');
            if (sentenceEl) { this.showSelectedSentence(sentenceEl.textContent.trim(), window.__currentIdx); }
        }
    },

    clearFocus: function() {
        this.selectedFocusWord = "";
        if (articleModule.focusWords) { articleModule.focusWords = []; articleModule.clearWordHighlight(); }
        var p = document.querySelector("#selectedSentence .sentence-text");
        if (p && p.textContent.trim()) {
            this.showSelectedSentence(p.textContent, window.__currentIdx);
        } else {
            document.getElementById("selectedSentence").innerHTML = '<p style="color:var(--text-muted);text-align:center;font-style:italic;">点击文章中的句子开始提问</p>';
        }
    },

    clearFocusHighlight: function() {
        document.querySelectorAll(".focus-highlight").forEach(function(el) { el.classList.remove("focus-highlight"); });
    },

    sendQuestion: function(question) {
        var sentence = document.querySelector(".sentence.selected");
        if (!sentence && !this.selectedFocusWord) { alert("请先点击文章中的内容"); return; }
        var sentenceText = sentence ? sentence.textContent.trim() : this.selectedFocusWord;
        var articleId = (articleModule.currentArticle && articleModule.currentArticle.id) || "";
        this.streamAnswer(sentenceText, question, articleId, this.selectedFocusWord);
    },

    streamAnswer: function(sentence, question, articleId, focus) {
        if (this.isStreaming) { this.isStreaming = false; document.getElementById("btnSend").disabled = false; }
        this.isStreaming = true;
        document.getElementById("btnSend").disabled = true;
        var container = document.getElementById("chatMessages");
        var msgEl = document.createElement("div");
        msgEl.className = "message";
        var focusLabel = focus ? '<span class="focus-tag">' + this.escapeHtml(focus) + '</span> ' : "";
        msgEl.innerHTML = '<div class="question-label">' + focusLabel + 'Q: ' + this.escapeHtml(question) + '</div><div class="answer-content"></div>';
        container.appendChild(msgEl);
        var answerEl = msgEl.querySelector(".answer-content");
        msgEl.scrollIntoView({ block: "start", behavior: "smooth" });
        var self = this;
        var fullAnswer = "";
        var streamFinished = false;
        var source = api.askAgent(sentence, question, articleId, focus);
        var timeout = setTimeout(function() {
            if (!streamFinished) {
                streamFinished = true;
                source.close(); self.isStreaming = false; document.getElementById("btnSend").disabled = false;
                if (!fullAnswer) { answerEl.textContent = "请求超时，请重试"; }
            }
        }, 90000);
        source.onmessage = function(e) {
            if (streamFinished) return;
            if (e.data === "[DONE]") {
                streamFinished = true;
                clearTimeout(timeout); source.close(); self.isStreaming = false;
                self.clearFocusHighlight(); self.selectedFocusWord = "";
                document.getElementById("btnSend").disabled = false; return;
            }
            try { var p = JSON.parse(e.data); fullAnswer += p.text; answerEl.textContent = fullAnswer; } catch (err) { console.error("Parse SSE error:", err); }
        };
        source.onerror = function() {
            if (streamFinished) return;
            streamFinished = true;
            clearTimeout(timeout); source.close(); self.isStreaming = false;
            document.getElementById("btnSend").disabled = false;
            if (!fullAnswer) { answerEl.textContent = "请求失败，请重试"; }
        };
    },

    escapeHtml: function(text) {
        var div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }
};
