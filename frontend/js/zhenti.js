var zhentiModule = {
    years: [],
    currentYear: null,
    currentText: null,
    isUploading: false,
    pendingFiles: [],

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
            self.pendingFiles = [];
            self.renderFileList();
        });

        var pasteZone = document.getElementById("zhentiPasteZone");
        pasteZone.addEventListener("click", function() { document.getElementById("zhentiFileInput").click(); });
        document.getElementById("zhentiFileInput").addEventListener("change", function(e) {
            var files = e.target.files;
            for (var i = 0; i < files.length; i++) { self.pendingFiles.push(files[i]); }
            e.target.value = "";
            self.renderFileList();
        });

        pasteZone.addEventListener("dragover", function(e) {
            e.preventDefault();
            pasteZone.classList.add("dragging");
        });
        pasteZone.addEventListener("dragleave", function() { pasteZone.classList.remove("dragging"); });
        pasteZone.addEventListener("drop", function(e) {
            e.preventDefault();
            pasteZone.classList.remove("dragging");
            var files = e.dataTransfer.files;
            for (var i = 0; i < files.length; i++) {
                if (/image\//.test(files[i].type) || /\.(pdf)$/i.test(files[i].name)) {
                    self.pendingFiles.push(files[i]);
                }
            }
            self.renderFileList();
        });

        document.addEventListener("paste", function(e) {
            if (document.getElementById("zhentiUploadArea").style.display === "none") return;
            var target = e.target;
            if (target && (target.id === "questionInput" || target.tagName === "INPUT")) return;
            var items = e.clipboardData && e.clipboardData.items;
            if (!items) return;
            var added = false;
            var pasteIndex = 0;
            for (var i = 0; i < items.length; i++) {
                var item = items[i];
                if (item.type && item.type.indexOf("image") === 0) {
                    var file = item.getAsFile();
                    if (file) {
                        var fname = "pasted_" + (Date.now()) + "_" + (++pasteIndex) + ".png";
                        file = new File([file], fname, { type: file.type });
                        self.pendingFiles.push(file);
                        added = true;
                    }
                }
            }
            if (added) {
                self.renderFileList();
            }
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
            if (exists) {
                var delBtn = document.createElement("button");
                delBtn.className = "zhenti-text-del";
                delBtn.title = "删除";
                delBtn.textContent = "\u00d7";
                delBtn.addEventListener("click", function(yr, t) {
                    return function(e) {
                        e.stopPropagation();
                        if (!confirm("确定删除 " + yr + "年 Text " + t + " 吗？")) return;
                        api.deleteZhenti(yr, t).then(function() {
                            if (articleModule.currentArticle && articleModule.currentArticle.id === "zhenti_" + yr + "_" + t) {
                                articleModule.currentArticle = null;
                                document.getElementById("articleBody").innerHTML = '<div class="loading">文章已删除</div>';
                                document.getElementById("checkinArea").style.display = "none";
                            }
                            api.getZhentiList().then(function(data) {
                                var years = data.years || [];
                                var updated = null;
                                for (var k = 0; k < years.length; k++) {
                                    if (years[k].year === yr) { updated = years[k]; break; }
                                }
                                if (updated) { self.showTexts(updated); }
                            });
                        }).catch(function(err) { alert("删除失败: " + err.message); });
                    };
                }(this.currentYear, i));
                cell.appendChild(delBtn);
            }
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
        this.pendingFiles = [];
        document.getElementById("zhentiUploadTitle").textContent = this.currentYear + "年 Text " + textNum + " 上传";
        document.getElementById("zhentiUploadArea").style.display = "block";
        this.renderFileList();
    },

    renderFileList: function() {
        var self = this;
        var listEl = document.getElementById("zhentiFileList");
        listEl.innerHTML = "";
        this.pendingFiles.forEach(function(file, idx) {
            var item = document.createElement("div");
            item.className = "zhenti-file-item";
            if (file.type && file.type.indexOf("image") === 0) {
                var img = document.createElement("img");
                img.className = "zhenti-file-thumb";
                img.src = URL.createObjectURL(file);
                img.onload = function() { URL.revokeObjectURL(this.src); };
                item.appendChild(img);
            } else {
                var icon = document.createElement("span");
                icon.className = "zhenti-file-icon";
                icon.textContent = "PDF";
                item.appendChild(icon);
            }
            var name = document.createElement("span");
            name.className = "zhenti-file-name";
            name.textContent = file.name || ("图片 " + (idx + 1));
            item.appendChild(name);
            var del = document.createElement("button");
            del.className = "zhenti-file-del";
            del.textContent = "x";
            del.addEventListener("click", function(fi) {
                return function(e) {
                    e.stopPropagation();
                    self.pendingFiles.splice(fi, 1);
                    self.renderFileList();
                };
            }(idx));
            item.appendChild(del);
            listEl.appendChild(item);
        });
        if (this.pendingFiles.length === 0) {
            listEl.innerHTML = '<div class="zhenti-file-empty">暂未添加文件</div>';
        }
    },

    doUpload: function() {
        var self = this;
        if (this.pendingFiles.length === 0) { alert("请先选择或粘贴文件"); return; }
        if (this.isUploading) return;
        this.isUploading = true;
        document.getElementById("zhentiUploadBtn").disabled = true;
        document.getElementById("zhentiUploadBtn").textContent = "解析中...";
        var files = this.pendingFiles.slice();
        api.uploadZhenti(this.currentYear, this.currentText, files).then(function(data) {
            self.pendingFiles = [];
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
