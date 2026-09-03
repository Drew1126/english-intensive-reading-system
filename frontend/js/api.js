var APP_PREFIX = window.location.pathname.indexOf("/english") === 0 ? "/english" : "";
var BASE = APP_PREFIX + "/data";

var api = {
    getCurrentArticle: function() {
        return fetch(BASE + "/article/current").then(function(res) {
            if (!res.ok) { return res.json().then(function(e) { throw new Error(e.detail || "服务器错误 (" + res.status + ")"); }).catch(function() { throw new Error("服务器错误 (" + res.status + ")"); }); }
            return res.json();
        });
    },
    getArticleList: function(token) {
        var url = BASE + "/article/list";
        if (token) { url += "?token=" + encodeURIComponent(token); }
        return fetch(url).then(function(res) {
            if (!res.ok) { throw new Error("获取历史列表失败 (" + res.status + ")"); }
            return res.json();
        });
    },
    getArticle: function(index) {
        return fetch(BASE + "/article/" + index).then(function(res) {
            if (!res.ok) { return res.json().then(function(e) { throw new Error(e.detail || "获取文章失败 (" + res.status + ")"); }).catch(function() { throw new Error("获取文章失败 (" + res.status + ")"); }); }
            return res.json();
        });
    },
    uploadPdf: function(file) {
        var formData = new FormData();
        formData.append("file", file);
        return fetch(BASE + "/article/upload-pdf", { method: "POST", body: formData }).then(function(res) {
            if (!res.ok) { return res.json().then(function(e) { throw new Error(e.detail || "上传失败 (" + res.status + ")"); }).catch(function() { throw new Error("上传失败 (" + res.status + ")"); }); }
            return res.json();
        });
    },
    translate: function(articleId, sentences) {
        return fetch(BASE + "/translate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ article_id: articleId, sentences: sentences })
        }).then(function(res) { return res.json(); });
    },
    askAgent: function(sentence, question, articleId, focus, user) {
        var url = BASE + "/agent/ask?sentence=" + encodeURIComponent(sentence) + "&question=" + encodeURIComponent(question) + "&article_id=" + encodeURIComponent(articleId) + "&focus=" + encodeURIComponent(focus || "") + "&user=" + encodeURIComponent(user || "");
        return new EventSource(url);
    },
    // Auth
    login: function(username, password) {
        return fetch(BASE + "/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: username, password: password })
        }).then(function(res) {
            if (!res.ok) { return res.json().then(function(e) { throw new Error(e.detail || "登录失败"); }); }
            return res.json();
        });
    },
    getMe: function(token) {
        return fetch(BASE + "/auth/me?token=" + encodeURIComponent(token)).then(function(res) {
            if (!res.ok) { throw new Error("登录已过期"); }
            return res.json();
        });
    },
    checkin: function(articleId, token) {
        return fetch(BASE + "/auth/checkin/" + articleId + "?token=" + encodeURIComponent(token), { method: "POST" }).then(function(res) { return res.json(); });
    },
    getCheckinStatus: function(articleId) {
        return fetch(BASE + "/auth/checkin-status/" + articleId).then(function(res) { return res.json(); });
    },
    updateArticle: function(id, paragraphs, retranslate) {
        return fetch(BASE + "/article/update", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id: id, paragraphs: paragraphs, retranslate: !!retranslate })
        }).then(function(res) {
            if (!res.ok) { return res.json().then(function(e) { throw new Error(e.detail || "保存失败"); }); }
            return res.json();
        });
    },
    uploadAvatar: function(token, file) {
        var formData = new FormData();
        formData.append("file", file);
        return fetch(BASE + "/auth/avatar?token=" + encodeURIComponent(token), { method: "POST", body: formData }).then(function(res) { return res.json(); });
    },
    deleteArticle: function(index, token) {
        return fetch(BASE + "/article/" + index + "?token=" + encodeURIComponent(token), { method: "DELETE" }).then(function(res) {
            if (!res.ok) { return res.json().then(function(e) { throw new Error(e.detail || "删除失败"); }); }
            return res.json();
        });
    },
    // Zhenti
    getZhentiList: function() {
        return fetch(BASE + "/zhenti/list").then(function(res) {
            if (!res.ok) { throw new Error("获取真题列表失败"); }
            return res.json();
        });
    },
    getZhentiArticle: function(year, text) {
        return fetch(BASE + "/zhenti/" + year + "/" + text).then(function(res) {
            if (!res.ok) { return res.json().then(function(e) { throw new Error(e.detail || "获取文章失败"); }); }
            return res.json();
        });
    },
    uploadZhenti: function(year, text, files) {
        var formData = new FormData();
        for (var i = 0; i < files.length; i++) { formData.append("files", files[i]); }
        return fetch(BASE + "/zhenti/" + year + "/" + text + "/upload", { method: "POST", body: formData }).then(function(res) {
            if (!res.ok) { return res.json().then(function(e) { throw new Error(e.detail || "上传失败"); }); }
            return res.json();
        });
    },
    deleteZhenti: function(year, text) {
        return fetch(BASE + "/zhenti/" + year + "/" + text, { method: "DELETE" }).then(function(res) {
            if (!res.ok) { return res.json().then(function(e) { throw new Error(e.detail || "删除失败"); }); }
            return res.json();
        });
    }
};
