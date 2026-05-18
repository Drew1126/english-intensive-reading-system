const BASE = "/data";
console.log(">>> api.js loaded, BASE =", BASE);

const api = {
    async getCurrentArticle() {
        const url = `${BASE}/article/current`;
        console.log("[api] fetching:", url);
        const res = await fetch(url);
        console.log("[api] response:", res.status);
        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || `服务器错误 (${res.status})`);
        }
        return res.json();
    },

    async getNextArticle() {
        const url = `${BASE}/article/next`;
        console.log("[api] posting:", url);
        const res = await fetch(url, { method: "POST" });
        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || `服务器错误 (${res.status})`);
        }
        return res.json();
    },

    async translate(articleId, sentences) {
        const url = `${BASE}/translate`;
        console.log("[api] translate:", url);
        const res = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ article_id: articleId, sentences })
        });
        if (!res.ok) throw new Error("Failed to translate");
        return res.json();
    },

    askAgent(sentence, question, articleId, focus) {
        const url = `${BASE}/agent/ask?sentence=${encodeURIComponent(sentence)}&question=${encodeURIComponent(question)}&article_id=${encodeURIComponent(articleId)}&focus=${encodeURIComponent(focus || "")}`;
        console.log("[api] agent:", url);
        return new EventSource(url);
    }
};
