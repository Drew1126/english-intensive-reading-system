var AUTH_TOKEN_KEY = "auth_token";
var AUTH_NAME_KEY = "auth_name";
var AUTH_ROLE_KEY = "auth_role";

function getToken() { return localStorage.getItem(AUTH_TOKEN_KEY); }
function getName() { return localStorage.getItem(AUTH_NAME_KEY); }
function getRole() { return localStorage.getItem(AUTH_ROLE_KEY) || "viewer"; }
function isAdmin() { return getRole() === "admin"; }
function setAuth(token, name, role) { localStorage.setItem(AUTH_TOKEN_KEY, token); localStorage.setItem(AUTH_NAME_KEY, name); localStorage.setItem(AUTH_ROLE_KEY, role || "viewer"); }
function clearAuth() { localStorage.removeItem(AUTH_TOKEN_KEY); localStorage.removeItem(AUTH_NAME_KEY); localStorage.removeItem(AUTH_ROLE_KEY); }

function showToast(message, type) {
    var region = document.getElementById("toastRegion");
    if (!region) return;
    var toast = document.createElement("div");
    toast.className = "toast " + (type || "");
    toast.textContent = message;
    region.appendChild(toast);
    setTimeout(function() { toast.remove(); }, 3200);
}

function showConfirm(message, onAccept) {
    var overlay = document.getElementById("confirmOverlay");
    document.getElementById("confirmMessage").textContent = message;
    overlay.style.display = "flex";
    overlay._onAccept = onAccept;
    document.getElementById("confirmAccept").focus();
}

function initFeedbackUI() {
    var overlay = document.getElementById("confirmOverlay");
    function close() { overlay.style.display = "none"; overlay._onAccept = null; }
    document.getElementById("confirmCancel").addEventListener("click", close);
    document.getElementById("confirmAccept").addEventListener("click", function() {
        var callback = overlay._onAccept;
        close();
        if (callback) callback();
    });
    overlay.addEventListener("click", function(event) { if (event.target === overlay) close(); });
}

function initMobileAgentDrawer() {
    var panel = document.getElementById("agentPanel");
    var fab = document.getElementById("mobileAgentFab");
    var backdrop = document.getElementById("mobileAgentBackdrop");
    var toggle = document.getElementById("agentContextToggle");
    var mobile = window.matchMedia("(max-width: 1050px)");
    function open() { if (!mobile.matches) return; panel.classList.add("mobile-open"); backdrop.classList.add("visible"); document.body.classList.add("mobile-agent-open"); }
    function close() { panel.classList.remove("mobile-open", "mobile-full"); backdrop.classList.remove("visible"); document.body.classList.remove("mobile-agent-open"); }
    window.openMobileAgent = open;
    fab.addEventListener("click", open);
    backdrop.addEventListener("click", close);
    var touchStart = null;
    toggle.addEventListener("touchstart", function(event) { touchStart = event.touches[0].clientY; }, { passive: true });
    toggle.addEventListener("touchend", function(event) {
        if (touchStart === null) return;
        var delta = event.changedTouches[0].clientY - touchStart;
        touchStart = null;
        if (delta < -35) panel.classList.add("mobile-full");
        if (delta > 35) close();
    }, { passive: true });
    mobile.addEventListener("change", function(event) { if (!event.matches) close(); });
}

function initResizableLayout() {
    var main = document.querySelector(".main-content");
    var panel = document.getElementById("agentPanel");
    var resizer = document.getElementById("layoutResizer");
    if (!main || !panel || !resizer) return;

    var panelMin = 380;
    var panelMax = 680;
    var articleMin = 520;
    var desktopQuery = window.matchMedia("(min-width: 1051px)");

    function limits() {
        var styles = window.getComputedStyle(main);
        var horizontalPadding = parseFloat(styles.paddingLeft) + parseFloat(styles.paddingRight);
        return {
            min: panelMin,
            max: Math.max(panelMin, Math.min(panelMax, main.clientWidth - horizontalPadding - articleMin - resizer.offsetWidth))
        };
    }

    function setPanelWidth(width, persist) {
        if (!desktopQuery.matches) {
            panel.style.width = "";
            return;
        }
        var range = limits();
        var nextWidth = Math.round(Math.min(range.max, Math.max(range.min, width)));
        panel.style.width = nextWidth + "px";
        resizer.setAttribute("aria-valuenow", String(nextWidth));
        resizer.setAttribute("aria-valuemax", String(Math.round(range.max)));
        if (persist) localStorage.setItem("agent_panel_width", String(nextWidth));
    }

    var savedWidth = Number(localStorage.getItem("agent_panel_width"));
    setPanelWidth(savedWidth || panel.getBoundingClientRect().width || 480, false);

    resizer.addEventListener("pointerdown", function(event) {
        if (!desktopQuery.matches || event.button !== 0) return;
        resizer.setPointerCapture(event.pointerId);
        resizer.classList.add("is-resizing");
        document.body.classList.add("layout-resizing");
    });
    resizer.addEventListener("pointermove", function(event) {
        if (!resizer.hasPointerCapture(event.pointerId)) return;
        var rightPadding = parseFloat(window.getComputedStyle(main).paddingRight);
        setPanelWidth(main.getBoundingClientRect().right - rightPadding - event.clientX, false);
    });
    function finishResize(event) {
        if (!resizer.hasPointerCapture(event.pointerId)) return;
        resizer.releasePointerCapture(event.pointerId);
        resizer.classList.remove("is-resizing");
        document.body.classList.remove("layout-resizing");
        setPanelWidth(panel.getBoundingClientRect().width, true);
    }
    resizer.addEventListener("pointerup", finishResize);
    resizer.addEventListener("pointercancel", finishResize);
    resizer.addEventListener("keydown", function(event) {
        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
        event.preventDefault();
        var direction = event.key === "ArrowLeft" ? 1 : -1;
        setPanelWidth(panel.getBoundingClientRect().width + direction * 24, true);
    });
    resizer.addEventListener("dblclick", function() { setPanelWidth(480, true); });
    window.addEventListener("resize", function() {
        var width = Number(localStorage.getItem("agent_panel_width")) || panel.getBoundingClientRect().width || 480;
        setPanelWidth(width, false);
    });
}

function initAgentContextToggle() {
    var section = document.getElementById("agentContextSection");
    var button = document.getElementById("agentContextToggle");
    var body = document.getElementById("agentContextBody");
    var buttonText = document.getElementById("agentContextToggleText");
    if (!section || !button || !body || !buttonText) return;

    function setCollapsed(collapsed) {
        section.classList.toggle("is-collapsed", collapsed);
        body.hidden = collapsed;
        button.setAttribute("aria-expanded", String(!collapsed));
        buttonText.textContent = collapsed ? "展开" : "收起";
        button.setAttribute("aria-label", collapsed ? "展开选中内容" : "收起选中内容");
        localStorage.setItem("agent_context_collapsed", collapsed ? "1" : "0");
    }
    setCollapsed(localStorage.getItem("agent_context_collapsed") === "1");
    button.addEventListener("click", function() { setCollapsed(!body.hidden); });
}

function getAvatarUrl(name) { return BASE + "/auth/avatar/" + encodeURIComponent(name) + "?t=" + Date.now(); }

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
    var admin = loggedIn && isAdmin();
    document.getElementById("btnAccountManage").style.display = admin ? "inline-block" : "none";
    document.getElementById("btnUploadPdf").style.display = admin ? "inline-block" : "none";
    if (articleModule.currentArticle) document.getElementById("btnEditArticle").style.display = admin ? "inline-block" : "none";
    var roleBadge = document.getElementById("roleBadge");
    roleBadge.textContent = admin ? "管理员" : "只读";
    roleBadge.classList.toggle("admin", admin);
    document.body.classList.toggle("is-admin", admin);
}

function loadAccountList() {
    var list = document.getElementById("accountList");
    list.innerHTML = '<div class="loading">加载中...</div>';
    api.listUsers(getToken()).then(function(data) {
        list.innerHTML = "";
        data.users.forEach(function(user) {
            var item = document.createElement("div");
            item.className = "account-item";
            item.innerHTML = '<div class="account-item-name"></div><span class="account-role"></span><div class="account-actions"><input class="new-password" type="password" placeholder="新密码"><button class="password">修改密码</button><button class="danger">删除</button></div>';
            item.querySelector(".account-item-name").textContent = user.username;
            item.querySelector(".account-role").textContent = user.role === "admin" ? "管理员" : "普通用户";
            if (user.username === "root") item.querySelector(".danger").disabled = true;
            item.querySelector(".password").addEventListener("click", function() {
                var password = item.querySelector(".new-password").value;
                if (!password) { showToast("请输入新密码", "error"); return; }
                api.updateUser(getToken(), user.username, password, user.role).then(function() { item.querySelector(".new-password").value = ""; showToast("密码已更新", "success"); }).catch(function(err) { showToast(err.message, "error"); });
            });
            item.querySelector(".danger").addEventListener("click", function() {
                showConfirm("确定删除账号“" + user.username + "”？", function() {
                    api.deleteUser(getToken(), user.username).then(function() { showToast("账号已删除", "success"); loadAccountList(); }).catch(function(err) { showToast(err.message, "error"); });
                });
            });
            list.appendChild(item);
        });
    }).catch(function(err) { list.innerHTML = '<div class="loading">' + err.message + '</div>'; });
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
    initFeedbackUI();
    initMobileAgentDrawer();
    initResizableLayout();
    initAgentContextToggle();
    var today = new Date();
    document.getElementById("todayDate").textContent = today.toLocaleDateString("zh-CN", { year: "numeric", month: "long", day: "numeric", weekday: "long" });

    updateUserUI();
    if (getToken()) {
        api.getMe(getToken()).then(function(data) { setAuth(getToken(), data.name, data.role); updateUserUI(); }).catch(function() { clearAuth(); updateUserUI(); showLogin(); });
    }

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
            setAuth(data.token, data.name, data.role);
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

    document.getElementById("btnAccountManage").addEventListener("click", function() { document.getElementById("accountOverlay").style.display = "flex"; loadAccountList(); });
    document.getElementById("accountClose").addEventListener("click", function() { document.getElementById("accountOverlay").style.display = "none"; });
    document.getElementById("accountOverlay").addEventListener("click", function(event) { if (event.target === this) this.style.display = "none"; });
    document.getElementById("accountForm").addEventListener("submit", function(event) {
        event.preventDefault();
        api.createUser(getToken(), document.getElementById("accountUsername").value.trim(), document.getElementById("accountPassword").value, "viewer").then(function() {
            showToast("账号已添加", "success");
            document.getElementById("accountForm").reset();
            loadAccountList();
        }).catch(function(err) { showToast(err.message, "error"); });
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
        }).catch(function(err) { showToast("上传失败：" + err.message, "error"); });
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
    if (typeof zhentiModule !== "undefined") { zhentiModule.init(); }
    document.getElementById("avatarOverlay").addEventListener("click", function(e) {
        if (e.target === this) { this.style.display = "none"; }
    });

    // Edit article
    document.getElementById("btnEditArticle").addEventListener("click", function() {
        if (articleModule.editing) {
            articleModule.confirmEdit();
        } else {
            articleModule.enterEditMode();
        }
    });
    document.getElementById("editConfirmYes").addEventListener("click", function() {
        var p = articleModule._pendingEdit;
        document.getElementById("editConfirmOverlay").style.display = "none";
        if (p) { articleModule.saveEdit(p, true); }
    });
    document.getElementById("editConfirmNo").addEventListener("click", function() {
        var p = articleModule._pendingEdit;
        document.getElementById("editConfirmOverlay").style.display = "none";
        if (p) { articleModule.saveEdit(p, false); }
    });
    document.getElementById("editConfirmOverlay").addEventListener("click", function(e) {
        if (e.target === this) { this.style.display = "none"; }
    });

    // Translation toggle
    document.getElementById("sentenceTranslationToggle").addEventListener("change", function(e) {
        window.__showTrans = e.target.checked;
        var p = document.querySelector("#selectedSentence .sentence-text");
        if (p && window.__currentIdx) {
            var en = p.dataset.en || p.textContent;
            var trans = (window.__translations && window.__translations[window.__currentIdx]) || "";
            if (e.target.checked && trans) { p.textContent = trans; } else { p.textContent = en; }
        }
    });

    // Send
    document.getElementById("btnSend").addEventListener("click", function() {
        if (agentModule.isStreaming) { agentModule.stopAnswer(); return; }
        var input = document.getElementById("questionInput");
        var q = input.value.trim();
        if (q) { agentModule.sendQuestion(q); input.value = ""; input.style.height = "auto"; }
    });
    document.getElementById("questionInput").addEventListener("input", function() {
        this.style.height = "auto";
        this.style.height = Math.min(this.scrollHeight, 132) + "px";
    });
    document.getElementById("questionInput").addEventListener("keydown", function(e) {
        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); document.getElementById("btnSend").click(); }
    });

    document.getElementById("clearSelectionBtn").addEventListener("click", function() {
        articleModule.focusWords = [];
        articleModule.clearWordHighlight();
        document.querySelectorAll(".sentence.selected").forEach(function(el) { el.classList.remove("selected"); });
        agentModule.clearFocus();
        articleModule.selectedSentenceIdx = null;
        window.__currentIdx = null;
        document.getElementById("selectedSentence").innerHTML = '<p class="placeholder">点击文章中的句子开始提问</p>';
        showToast("已清除选择");
    });

    document.querySelectorAll(".quick-btn").forEach(function(btn) {
        btn.addEventListener("click", function() {
            if (btn.dataset.nofocus === "1") {
                agentModule.selectedFocusWord = "";
                articleModule.clearWordHighlight();
            }
            agentModule.sendQuestion(btn.dataset.question);
        });
    });

    articleModule.loadCurrent();
});
