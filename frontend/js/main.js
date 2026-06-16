var AUTH_TOKEN_KEY = "auth_token";
var AUTH_NAME_KEY = "auth_name";

function getToken() { return localStorage.getItem(AUTH_TOKEN_KEY); }
function getName() { return localStorage.getItem(AUTH_NAME_KEY); }
function setAuth(token, name) { localStorage.setItem(AUTH_TOKEN_KEY, token); localStorage.setItem(AUTH_NAME_KEY, name); }
function clearAuth() { localStorage.removeItem(AUTH_TOKEN_KEY); localStorage.removeItem(AUTH_NAME_KEY); }

function getAvatarUrl(name) { return "/english/data/auth/avatar/" + encodeURIComponent(name) + "?t=" + Date.now(); }

function showLogin() { document.getElementById("loginOverlay").style.display = "flex"; }
function hideLogin() { document.getElementById("loginOverlay").style.display = "none"; }

function updateUserUI() {
    var token = getToken();
    var name = getName();
    var loggedIn = token && name;
    document.getElementById("userInfo").style.display = loggedIn ? "flex" : "none";
    document.getElementById("notLoggedIn").style.display = loggedIn ? "none" : "flex";
    if (loggedIn) {
        document.getElementById("userName").textContent = name;
        document.getElementById("userAvatar").src = getAvatarUrl(name);
    }
}

function updateCheckinArea() {
    var art = articleModule.currentArticle;
    if (!art || !art.id) { document.getElementById("checkinArea").style.display = "none"; return; }
    document.getElementById("checkinArea").style.display = "block";
    var token = getToken();
    var name = getName();
    var list = document.getElementById("checkinUsers");
    var btn = document.getElementById("btnCheckin");
    btn.textContent = "打卡";
    btn.disabled = false;
    api.getCheckinStatus(art.id).then(function(data) {
        list.innerHTML = "";
        var checkins = data.checkins || [];
        checkins.forEach(function(u) {
            var el = document.createElement("div");
            el.className = "checkin-user";
            el.innerHTML = '<img class="checkin-avatar" src="' + getAvatarUrl(u.name) + '" alt=""><span>' + u.name + '</span>';
            list.appendChild(el);
        });
        var checkedByMe = checkins.some(function(u) { return u.name === name; });
        if (checkedByMe) { btn.textContent = "已打卡"; btn.disabled = true; }
    });
}

document.addEventListener("DOMContentLoaded", function() {
    var today = new Date();
    document.getElementById("todayDate").textContent = today.toLocaleDateString("zh-CN", { year: "numeric", month: "long", day: "numeric", weekday: "long" });

    updateUserUI();

    // If no token, show login
    if (!getToken()) { showLogin(); }

    // Login modal
    document.getElementById("loginBtn").addEventListener("click", function() {
        var username = document.getElementById("loginUsername").value.trim();
        var password = document.getElementById("loginPassword").value;
        var errEl = document.getElementById("loginError");
        errEl.textContent = "";
        if (!username || !password) { errEl.textContent = "请输入用户名和密码"; return; }
        document.getElementById("loginBtn").disabled = true;
        document.getElementById("loginBtn").textContent = "登录中...";
        api.login(username, password).then(function(data) {
            setAuth(data.token, data.name);
            updateUserUI();
            hideLogin();
            updateCheckinArea();
        }).catch(function(err) {
            errEl.textContent = err.message;
        }).then(function() {
            document.getElementById("loginBtn").disabled = false;
            document.getElementById("loginBtn").textContent = "登录";
        });
    });
    document.getElementById("loginBtnHeader").addEventListener("click", function() {
        document.getElementById("loginUsername").value = "";
        document.getElementById("loginPassword").value = "";
        document.getElementById("loginError").textContent = "";
        showLogin();
    });
    document.getElementById("loginPassword").addEventListener("keydown", function(e) {
        if (e.key === "Enter") { document.getElementById("loginBtn").click(); }
    });

    // Logout
    document.getElementById("logoutBtn").addEventListener("click", function() {
        clearAuth();
        updateUserUI();
        document.getElementById("checkinArea").style.display = "none";
        showLogin();
    });

    // Checkin
    document.getElementById("btnCheckin").addEventListener("click", function() {
        var art = articleModule.currentArticle;
        if (!art || !art.id) return;
        var token = getToken();
        if (!token) { showLogin(); return; }
        var btn = document.getElementById("btnCheckin");
        btn.disabled = true;
        api.checkin(art.id, token).then(function() { updateCheckinArea(); }).catch(function() { btn.disabled = false; });
    });

    // Avatar change
    document.getElementById("userName").addEventListener("dblclick", function() {
        document.getElementById("avatarOverlay").style.display = "flex";
    });
    document.getElementById("avatarCancelBtn").addEventListener("click", function() {
        document.getElementById("avatarOverlay").style.display = "none";
    });
    document.getElementById("avatarUploadBtn").addEventListener("click", function() {
        var fileInput = document.getElementById("avatarFileInput");
        var file = fileInput && fileInput.files && fileInput.files[0];
        if (!file) return;
        var token = getToken();
        if (!token) return;
        api.uploadAvatar(token, file).then(function() {
            document.getElementById("avatarOverlay").style.display = "none";
            document.getElementById("userAvatar").src = getAvatarUrl(getName());
            fileInput.value = "";
        }).catch(function(err) { alert("上传失败: " + err.message); });
    });

    // Upload PDF
    document.getElementById("btnUploadPdf").addEventListener("click", function() { document.getElementById("pdfFileInput").click(); });
    document.getElementById("pdfFileInput").addEventListener("change", function(e) {
        if (e.target.files && e.target.files.length > 0) {
            articleModule.loadFromPdf(e.target.files[0]);
            e.target.value = "";
        }
    });

    // History
    document.getElementById("btnHistory").addEventListener("click", function() { articleModule.showHistory(); });
    document.getElementById("historyClose").addEventListener("click", function() { document.getElementById("historyOverlay").style.display = "none"; });
    document.getElementById("historyOverlay").addEventListener("click", function(e) {
        if (e.target === this) { this.style.display = "none"; }
    });
    document.getElementById("avatarOverlay").addEventListener("click", function(e) {
        if (e.target === this) { this.style.display = "none"; }
    });

    // Translation toggle
    document.getElementById("sentenceTranslationToggle").addEventListener("change", function(e) {
        window.__showTrans = e.target.checked;
        var p = document.querySelector("#selectedSentence .sentence-text");
        if (p && window.__currentIdx) {
            var trans = (window.__translations && window.__translations[window.__currentIdx]) || "";
            if (e.target.checked && trans) { p.textContent = p.textContent.split("\n")[0] + "\n" + trans; } else { p.textContent = p.textContent.split("\n")[0]; }
        }
    });

    // Send
    document.getElementById("btnSend").addEventListener("click", function() {
        var input = document.getElementById("questionInput");
        var q = input.value.trim();
        if (q) { agentModule.sendQuestion(q); input.value = ""; }
    });
    document.getElementById("questionInput").addEventListener("keydown", function(e) {
        if (e.key === "Enter") { document.getElementById("btnSend").click(); }
    });

    document.querySelectorAll(".quick-btn").forEach(function(btn) {
        btn.addEventListener("click", function() { agentModule.sendQuestion(btn.dataset.question); });
    });

    articleModule.loadCurrent();
});
