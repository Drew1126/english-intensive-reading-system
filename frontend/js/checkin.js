var checkinModule = {
    counts: {}, token: '', version: 0,
    badge: function(count) {
        var badge = document.createElement('span'); badge.className = 'checkin-progress';
        badge.textContent = '打卡 ' + count + ' 次';
        var light = Math.round(94 - 68 * (1 - Math.exp(-count / 5)));
        badge.style.backgroundColor = 'hsl(151, 40%, ' + light + '%)';
        badge.style.color = light > 57 ? '#153f32' : '#ffffff';
        badge.title = '每次完成本篇生词回顾后累计打卡，次数越多颜色越深';
        return badge;
    },
    paint: function(el, articleId) {
        el.dataset.checkinArticle = articleId;
        var old = el.querySelector('.checkin-progress'); if (old) old.remove();
        var count = this.counts[articleId] || 0;
        if (count) el.appendChild(this.badge(count));
    },
    refresh: function() {
        var self = this, token = getToken() || '', version = ++this.version;
        if (this.token !== token) { this.token = token; this.counts = {}; this.repaint(); }
        if (!token) return Promise.resolve();
        return fetch(BASE + '/auth/checkin-summary?token=' + encodeURIComponent(token)).then(handleJson).then(function(data) {
            if (token !== getToken() || version !== self.version) return;
            self.counts = data.counts; self.repaint();
        }).catch(function() { /* Reading remains available when counts cannot be refreshed. */ });
    },
    repaint: function() {
        var self = this;
        document.querySelectorAll('[data-checkin-article]').forEach(function(el) { self.paint(el, el.dataset.checkinArticle); });
    }
};
