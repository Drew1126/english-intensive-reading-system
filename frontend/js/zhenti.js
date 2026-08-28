var zhentiModule = {
    years: [],
    currentYear: null,
    currentText: null,
    isUploading: false,

    init: function() {
        var self = this;
        document.getElementById("tabWaikanBtn").addEventListener("click", function() { self.showTab("waikan"); });
        document.getElementById("tabZhentiBtn").addEventListener("click", function() { self.showTab("zhenti"); });
        document.getElementById("zhentiBack").addEventListener("click", function() {
            self.currentYear = null;
            self.currentText = null;
            document.getElementById("zhentiTextView").style.display = "none";
            document.getElementById("zhentiUploadArea").style.display = "none";
            document.getElementById("zhentiYearList").style.display = "block";
        });
        document.getElementById("zhentiUploadBtn").addEventListener("click", function() { self.doUpload(); });
        document.getElementById("zhentiUploadCancel").addEventListener("click", function() {
            document.getElementById("zhentiUploadArea").style.display = "none";
            document.getElementById("zhentiFileInput").value = "";
        });
    },

    showTab: function(tab) {
        var waikan = tab === "waikan";
        document.getElementById("tabWaikanBtn").classList.toggle("active", waikan);
        document.getElementById("tabZhentiBtn").classList.toggle("active", !waikan);
        document.getElementById("tabWaikanContent").style.display = waikan ? "block" : "none";
        document.getElementById("tabZhentiContent").style.display = waikan ? "none" : "block";
        if (!waikan) {
            this.loadYears();
        } else if (typeof articleModule.showHistory === "function") {
            articleModule.renderHistoryList();
        }
    },

    loadYears: function() {
        var self = this;
        var listEl = document.getElementById("zhentiYearList");
        listEl.innerHTML = '<div class="loading">加载中...</div>';
        document.getElementById("zhentiTextView").style.display = "none";
        document.getElementById("zhentiUploadArea").style.display = "none";
        listEl.style.display = "block";
        api.getZhentiList().then(function(data) {
            self.years = data.years || [];
            listEl.innerHTML = "";
            self.years.forEach(function(y) {
                var item = document.createElement("div");
                item.className = "zhenti-year";
                var count = 0;
                for (var i = 1; i <= 4; i++) { if (y["text" + i]) count++; }
                item.innerHTML = '<span class="zhenti-year-num">' + y.year + '</span><span class="zhenti-year-count">' + count + '/4</span>';
                item.addEventListener("click", function(yr) {
                    return function() { self.showTexts(yr); };
                }(y));
                listEl.appendChild(item);
            });
        }).catch(function(err) {
            listEl.innerHTML = '<div class="loading">获取失败：' + err.message + '</div>';
        });
    },

    showTexts: function(yearData) {
        var self = this;
        this.currentYear = yearData.year;
        document.getElementById("zhentiYearList").style.display = "none";
        document.getElementById("zhentiUploadArea").style.display = "none";
        document.getElementById("zhentiTextView").style.display = "block";
        document.getElementById("zhentiYearTitle").textContent = yearData.year + "年考研英语阅读";
        var grid = document.getElementById("zhentiTextGrid");
        grid.innerHTML = "";
        for (var i = 1; i <= 4; i++) {
            var exists = yearData["text" + i];
            var cell = document.createElement("div");
            cell.className = "zhenti-text" + (exists ? " exists" : " empty");
            cell.innerHTML = '<div class="zhenti-text-label">Text ' + i + '</div><div class="zhenti-text-status">' + (exists ? "已收录" : "未收录") + '</div>';
            cell.addEventListener("click", function(t, ex) {
                return function() {
                    if (ex) {
                        zhentiModule.loadArticle(t);
                    } else {
                        zhentiModule.showUpload(t);
                    }
                };
            }(i, exists));
            grid.appendChild(cell);
        }
    },

    showUpload: function(textNum) {
        this.currentText = textNum;
        document.getElementById("zhentiUploadTitle").textContent = this.currentYear + "年 Text " + textNum + " 上传";
        document.getElementById("zhentiUploadArea").style.display = "block";
    },

    doUpload: function() {
        var self = this;
        var input = document.getElementById("zhentiFileInput");
        var files = input.files;
        if (!files || files.length === 0) { alert("请先选择文件"); return; }
        if (this.isUploading) return;
        this.isUploading = true;
        document.getElementById("zhentiUploadBtn").disabled = true;
        document.getElementById("zhentiUploadBtn").textContent = "解析中...";
        api.uploadZhenti(this.currentYear, this.currentText, files).then(function(data) {
            input.value = "";
            document.getElementById("zhentiUploadArea").style.display = "none";
            articleModule.loadZhenti(self.currentYear, self.currentText);
            self.loadYears();
        }).catch(function(err) {
            alert("上传失败：" + err.message);
        }).then(function() {
            document.getElementById("zhentiUploadBtn").disabled = false;
            document.getElementById("zhentiUploadBtn").textContent = "上传";
            self.isUploading = false;
        });
    },

    loadArticle: function(textNum) {
        var overlay = document.getElementById("historyOverlay");
        overlay.style.display = "none";
        articleModule.loadZhenti(this.currentYear, textNum);
    }
};
