/* Selection is deliberately separate from loading: returning home preserves the discussion. */
var homeModule = {
    tab: "exam",
    years: [],
    expandedYears: new Map(),
    yearNodes: [],
    renderedOrder: '',
    requestId: 0,
    init: function() {
        var self = this;
        document.getElementById("btnHome").addEventListener("click", function() { self.show(); });
        document.getElementById("homeResume").addEventListener("click", function() { self.showReader(); });
        document.getElementById("homeUpload").addEventListener("click", function() {
            if (typeof isAdmin === 'function' && isAdmin()) document.getElementById("pdfFileInput").click();
        });
        document.getElementById("homeExamTab").addEventListener("click", function() { self.tab = "exam"; self.refresh(); });
        document.getElementById("homeExternalTab").addEventListener("click", function() { self.tab = "external"; self.refresh(); });
        self.show();
    },
    show: function() {
        if (typeof checkinModule !== 'undefined') checkinModule.refresh();
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
        document.getElementById("homeHeatLegend").hidden = !exam;
        document.getElementById("homeUpload").hidden = exam || !(typeof isAdmin === 'function' && isAdmin());
        this.message("正在整理文章…");
        (exam ? api.getZhentiList() : api.getArticleList(getToken())).then(function(data) {
            if (request !== self.requestId) return;
            if (exam) {
                self.years = (data.years || []).filter(function(y) { return [1,2,3,4,5].some(function(n) { return y["text" + n]; }); }).sort(function(a,b) { return b.year - a.year; });
                self.renderExams();
            } else {
                var cards = document.getElementById("homeCards");
                cards.replaceChildren();
                if (!(data.articles || []).length) { self.message("暂无外刊，管理员可上传 PDF。"); return; }
                data.articles.forEach(function(a) {
                    var card = self.node("button", "home-external-row", "");
                    card.type = "button";
                    card.dataset.compactCheckin = "true";
                    card.appendChild(self.node("span", "home-external-title", a.title || "未命名文章"));
                    card.appendChild(self.node("span", "home-external-meta", [a.source, a.date].filter(Boolean).join(" · ")));
                    card.addEventListener("click", function() { articleModule.loadByIndex(a.index); });
                    if (typeof checkinModule !== 'undefined') checkinModule.paint(card, a.id);
                    cards.appendChild(card);
                });
            }
        }).catch(function() { if (request === self.requestId) self.message("暂时无法获取文章，请确认服务已连接后重试。", true); });
    },
    sortedYears: function() {
        var counts = typeof checkinModule !== 'undefined' ? checkinModule.counts : {};
        function total(data) {
            return [1,2,3,4,5].reduce(function(sum, n) {
                return sum + (data['text'+n] ? Number(counts['zhenti_'+data.year+'_'+n] || 0) : 0);
            }, 0);
        }
        return this.years.slice().sort(function(a,b) { return total(b)-total(a) || b.year-a.year; });
    },
    reorderExams: function() {
        if (this.tab !== 'exam' || !this.years.length) return;
        var cards = document.getElementById('homeCards');
        var expected = this.sortedYears().map(function(y) { return 'homeYear-'+y.year; }).join(',');
        // Do not replace loading/error messages, or rebuild an unchanged layout.
        if (this.yearNodes.some(function(el) { return el.isConnected; }) && this.renderedOrder !== expected) this.renderExams();
    },
    arrangeYears: function() {
        var cards = document.getElementById('homeCards'), count = 0, self = this;
        this.yearNodes.forEach(function(section) {
            if (section.open) cards.appendChild(section);
            else { self.closedYearGrid.appendChild(section); count++; }
        });
        this.closedYearArea.hidden = count === 0;
        cards.appendChild(this.closedYearArea);
    },
    renderExams: function() {
        var self = this, cards = document.getElementById("homeCards");
        cards.replaceChildren();
        this.yearNodes = [];
        if (!this.years.length) { this.message("暂无已收录的真题。"); return; }
        this.closedYearArea = this.node('section', 'home-other-years', '');
        this.closedYearArea.appendChild(this.node('h2', 'home-other-heading', '其他年份'));
        this.closedYearGrid = this.node('div', 'home-other-grid', '');
        this.closedYearArea.appendChild(this.closedYearGrid);
        this.renderedOrder = this.sortedYears().map(function(y) { return 'homeYear-'+y.year; }).join(',');
        this.sortedYears().forEach(function(data, index) {
            var year = data.year, section = self.node("details", "home-year-group", "");
            section.id = "homeYear-" + year;
            section.open = self.expandedYears.has(year) ? self.expandedYears.get(year) : index < 3;
            section.addEventListener("toggle", function(event) {
                if (self.tab !== 'exam' || self.yearNodes.indexOf(section) < 0) return;
                self.expandedYears.set(year, section.open);
                self.arrangeYears();
                if (event && event.isTrusted) heading.focus({preventScroll:true});
            });
            section.setAttribute("aria-label", year + " 年英语一");
            var heading = self.node("summary", "home-year-heading", "");
            heading.appendChild(self.node("span", "home-year-number", String(year)));
            heading.appendChild(self.node("span", "home-year-subtitle", "英语一"));
            var preview = self.node('span', 'home-year-mini', '');
            [1,2,3,4,5].forEach(function(n) {
                var dot = self.node('span', 'home-mini-cell', '');
                dot.dataset.miniCheckin = 'true';
                dot.dataset.readingLabel = year + ' · ' + (n === 5 ? 'Part B' : '阅读 '+n);
                if (data['text'+n]) {
                    if (typeof checkinModule !== 'undefined') checkinModule.paint(dot, 'zhenti_'+year+'_'+n);
                } else { dot.classList.add('is-unavailable'); dot.title = dot.dataset.readingLabel+' · 未收录'; }
                preview.appendChild(dot);
            });
            heading.appendChild(preview);
            section.appendChild(heading);
            var links = self.node("div", "home-exam-links", "");
            [1,2,3,4,5].forEach(function(n) {
                var card = self.node("button", "home-exam-link", n === 5 ? "Part B" : "阅读 " + n);
                card.type = "button";
                card.dataset.heatmapCheckin = "true";
                card.dataset.readingLabel = year + " 年英语一 " + (n === 5 ? "Part B 新题型" : "阅读 " + n);
                card.setAttribute("aria-label", card.dataset.readingLabel + (data["text"+n] ? "" : "，暂未收录"));
                if (!data["text" + n]) {
                    card.disabled = true; card.title = "暂未收录";
                    card.appendChild(self.node("span", "home-cell-count", "未收录"));
                }
                else {
                    card.addEventListener("click", function() { articleModule.loadZhenti(year, n); });
                    if (typeof checkinModule !== 'undefined') checkinModule.paint(card, 'zhenti_' + year + '_' + n);
                }
                links.appendChild(card);
            });
            section.appendChild(links); self.yearNodes.push(section);
        });
        this.arrangeYears();
    }
};
