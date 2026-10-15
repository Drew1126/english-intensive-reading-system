/* Selection is deliberately separate from loading: returning home preserves the discussion. */
var homeModule = {
    tab: "exam",
    years: [],
    requestId: 0,
    init: function() {
        var self = this;
        document.getElementById("btnHome").addEventListener("click", function() { self.show(); });
        document.getElementById("homeResume").addEventListener("click", function() { self.showReader(); });
        document.getElementById("homeLibrary").addEventListener("click", function() { articleModule.showHistory(); });
        document.getElementById("homeExamTab").addEventListener("click", function() { self.tab = "exam"; self.refresh(); });
        document.getElementById("homeExternalTab").addEventListener("click", function() { self.tab = "external"; self.refresh(); });
        document.getElementById("homeYear").addEventListener("change", function() { self.renderExams(); });
        self.show();
    },
    show: function() {
        document.body.classList.add("home-active");
        document.body.classList.remove("mobile-agent-open");
        document.getElementById("agentPanel").classList.remove("mobile-open", "mobile-full");
        document.getElementById("mobileAgentBackdrop").classList.remove("visible");
        document.getElementById("btnHome").setAttribute("aria-current", "page");
        var article = articleModule.currentArticle;
        document.getElementById("homeResume").hidden = !article || articleModule.isLoading;
        document.getElementById("homeResumeTitle").textContent = article ? article.title : "";
        this.refresh();
    },
    showReader: function() {
        document.body.classList.remove("home-active");
        document.getElementById("btnHome").removeAttribute("aria-current");
        window.dispatchEvent(new Event("resize"));
    },
    node: function(tag, cls, text) {
        var el = document.createElement(tag);
        el.className = cls;
        el.textContent = text;
        return el;
    },
    message: function(text, retry) {
        var self = this, cards = document.getElementById("homeCards");
        cards.replaceChildren(this.node("p", "home-message", text));
        if (retry) {
            var button = this.node("button", "home-retry", "重新加载");
            button.onclick = function() { self.refresh(); };
            cards.appendChild(button);
        }
    },
    refresh: function() {
        var self = this, exam = this.tab === "exam", request = ++this.requestId;
        document.getElementById("homeExamTab").setAttribute("aria-pressed", String(exam));
        document.getElementById("homeExternalTab").setAttribute("aria-pressed", String(!exam));
        document.getElementById("homeYearLabel").hidden = !exam;
        document.getElementById("homeRecentYears").hidden = !exam;
        document.getElementById("homeRecentYears").replaceChildren();
        document.getElementById("homeSectionTitle").textContent = exam ? "历年阅读，逐篇精读" : "换一个视角，读更大的世界";
        document.getElementById("homeSectionHint").textContent = exam ? "选择年份，再挑选一篇文章。" : "从已收录的外刊中，选择今天感兴趣的话题。";
        this.message("正在整理文章…");
        (exam ? api.getZhentiList() : api.getArticleList(getToken())).then(function(data) {
            if (request !== self.requestId) return;
            if (exam) {
                self.years = (data.years || []).filter(function(y) { return [1,2,3,4,5].some(function(n) { return y["text" + n]; }); }).sort(function(a,b) { return b.year - a.year; });
                var select = document.getElementById("homeYear"), previous = select.value;
                select.replaceChildren();
                self.years.forEach(function(y) { var option = self.node("option", "", y.year + " 年"); option.value = y.year; select.appendChild(option); });
                if (self.years.some(function(y) { return String(y.year) === previous; })) select.value = previous;
                self.renderExams();
            } else {
                var cards = document.getElementById("homeCards");
                cards.replaceChildren();
                if (!(data.articles || []).length) { self.message("还没有外刊文章，可在文章库中由管理员上传 PDF。"); return; }
                data.articles.forEach(function(a) {
                    cards.appendChild(self.card(a.checked_in ? "外刊 · 已打卡" : "外刊阅读", a.title || "未命名文章", [a.source, a.word_count ? a.word_count + " 词" : "", a.date].filter(Boolean).join(" · "), function() { articleModule.loadByIndex(a.index); }));
                });
            }
        }).catch(function() { if (request === self.requestId) self.message("暂时无法获取文章，请确认服务已连接后重试。", true); });
    },
    card: function(label, title, detail, action) {
        var card = this.node("button", "home-article-card", "");
        card.type = "button";
        card.appendChild(this.node("span", "home-card-label", label));
        card.appendChild(this.node("span", "home-card-title", title));
        card.appendChild(this.node("span", "home-card-detail", detail));
        card.appendChild(this.node("span", "home-card-action", "开始精读 ↗"));
        card.addEventListener("click", action);
        return card;
    },
    renderExams: function() {
        var self = this, year = Number(document.getElementById("homeYear").value);
        var recent = document.getElementById("homeRecentYears");
        recent.replaceChildren();
        this.years.slice(0, 5).forEach(function(y) {
            var button = self.node("button", "home-year-chip", String(y.year));
            button.type = "button";
            button.setAttribute("aria-pressed", String(y.year === year));
            button.addEventListener("click", function() {
                document.getElementById("homeYear").value = String(y.year);
                self.renderExams();
                var active = document.querySelector('.home-year-chip[aria-pressed="true"]');
                if (active) active.focus();
            });
            recent.appendChild(button);
        });
        var data = this.years.find(function(y) { return y.year === year; });
        var cards = document.getElementById("homeCards");
        cards.replaceChildren();
        if (!data) { this.message("暂无已收录的真题，请在文章库中添加。"); return; }
        [1,2,3,4,5].forEach(function(n) {
            var card = self.card(year + " · 英语一", n === 5 ? "Part B · 新题型" : "Part A · Text " + n, n === 5 ? "阅读原文与候选内容 · 专注精翻" : "阅读理解 · 句子精读与词汇积累", function() { articleModule.loadZhenti(year, n); });
            if (n === 5) card.classList.add("home-part-b");
            if (!data["text" + n]) { card.disabled = true; card.querySelector(".home-card-action").textContent = "暂未收录"; }
            cards.appendChild(card);
        });
    }
};
