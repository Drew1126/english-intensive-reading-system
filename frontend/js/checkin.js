var checkinModule = {
    counts: {}, token: '', version: 0,
    colors: function(count) {
        var light = Math.round(94 - 68 * (1 - Math.exp(-count / 5)));
        return {background:'hsl(151, 40%, ' + light + '%)', foreground:light > 44 ? '#153f32' : '#ffffff'};
    },
    badge: function(count) {
        var badge = document.createElement('span'); badge.className = 'checkin-progress';
        badge.textContent = '打卡 ' + count + ' 次';
        var colors = this.colors(count);
        badge.style.backgroundColor = colors.background;
        badge.style.color = colors.foreground;
        badge.title = '每次完成本篇生词回顾后累计打卡，次数越多颜色越深';
        return badge;
    },
    paint: function(el, articleId) {
        el.dataset.checkinArticle = articleId;
        var old = el.querySelector('.checkin-progress'); if (old) old.remove();
        var count = this.counts[articleId] || 0;
        if (el.dataset.miniCheckin === 'true') {
            el.style.backgroundColor = count ? this.colors(count).background : '';
            el.title = (el.dataset.readingLabel || '') + ' · ' + (count ? '打卡 '+count+' 次' : '未打卡');
            el.setAttribute('aria-label',el.title);
            return;
        }
        if (el.dataset.heatmapCheckin === 'true') {
            var colors = this.colors(count);
            el.style.backgroundColor = count ? colors.background : '';
            el.style.color = count ? colors.foreground : '';
            var status = count ? '打卡 ' + count + ' 次' : '未打卡';
            el.title = (el.dataset.readingLabel || '') + ' · ' + status;
            el.setAttribute('aria-label', el.title);
            var caption = el.querySelector('.home-cell-count');
            if (!caption) { caption = document.createElement('span'); caption.className = 'home-cell-count'; el.appendChild(caption); }
            caption.textContent = count ? count + ' 次' : '未打卡';
            return;
        }
        if (count) {
            var badge = this.badge(count);
            if (el.dataset.compactCheckin === 'true') {
                badge.textContent = '✓ ' + count;
                badge.title = '已打卡 ' + count + ' 次';
                badge.setAttribute('aria-label', badge.title);
            }
            el.appendChild(badge);
        }
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
        if (typeof homeModule !== 'undefined') homeModule.reorderExams();
    }
};
