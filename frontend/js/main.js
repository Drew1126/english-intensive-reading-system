document.addEventListener("DOMContentLoaded", () => {
    const today = new Date();
    document.getElementById("todayDate").textContent = today.toLocaleDateString("zh-CN", {
        year: "numeric",
        month: "long",
        day: "numeric",
        weekday: "long"
    });

    document.getElementById("btnNextArticle").addEventListener("click", () => {
        articleModule.loadNext();
    });

    document.getElementById("sentenceTranslationToggle").addEventListener("change", (e) => {
        window.__showTrans = e.target.checked;
        const p = document.querySelector("#selectedSentence .sentence-text");
        if (p && window.__currentIdx) {
            const trans = window.__translations?.[window.__currentIdx] || "";
            if (e.target.checked && trans) {
                const sentence = p.textContent.split("\n")[0];
                p.textContent = sentence + "\n" + trans;
            } else {
                p.textContent = p.textContent.split("\n")[0];
            }
        }
    });

    document.getElementById("btnSend").addEventListener("click", () => {
        const input = document.getElementById("questionInput");
        const question = input.value.trim();
        if (question) {
            agentModule.sendQuestion(question);
            input.value = "";
        }
    });

    document.getElementById("questionInput").addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            document.getElementById("btnSend").click();
        }
    });

    document.querySelectorAll(".quick-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            agentModule.sendQuestion(btn.dataset.question);
        });
    });

    initApp();
});

async function initApp() {
    try {
        await articleModule.loadCurrent();
    } catch (err) {
        console.error("App initialization failed:", err);
        document.getElementById("articleBody").innerHTML = `<div class="loading">初始化失败：${err.message}</div>`;
    }
}
