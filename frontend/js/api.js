const api = {
    async getCurrentArticle() {
        const res = await fetch("/api/article/current");
        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || `服务器错误 (${res.status})`);
        }
        return res.json();
    },

    async getNextArticle() {
        const res = await fetch("/api/article/next", { method: "POST" });
        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || `服务器错误 (${res.status})`);
        }
        return res.json();
    },

    async translate(articleId, sentences) {
        const res = await fetch(`/api/translate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ article_id: articleId, sentences })
        });
        if (!res.ok) throw new Error("Failed to translate");
        return res.json();
    },

    askAgent(sentence, question, articleId, focus) {
        const url = `/api/agent/ask?sentence=${encodeURIComponent(sentence)}&question=${encodeURIComponent(question)}&article_id=${encodeURIComponent(articleId)}&focus=${encodeURIComponent(focus || "")}`;
        return new EventSource(url);
    }
};
