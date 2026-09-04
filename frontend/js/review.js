// In-memory state, scoped to the current article conversation.
var reviewModule = {
    words: new Map(),
    cursor: null,
    init: function() {
        var self = this;
        document.getElementById('btnVocabularyReview').addEventListener('click', function() {
            self.render();
            document.getElementById('vocabularyDialog').showModal();
        });
        document.getElementById('vocabularyClose').addEventListener('click', function() {
            document.getElementById('vocabularyDialog').close();
        });
        document.getElementById('vocabularyDialog').addEventListener('click', function(e) {
            if (e.target === this) this.close();
        });
        document.getElementById('btnPreviousQuestion').addEventListener('click', function() { self.previous(); });
        document.getElementById('btnNextQuestion').addEventListener('click', function() { self.jump(1); });
        var chat = document.getElementById('chatMessages');
        ['wheel', 'touchstart', 'pointerdown', 'keydown'].forEach(function(type) {
            chat.addEventListener(type, function() { self.cursor = null; self.updateNavigation(); }, { passive: true });
        });
        this.reset();
    },
    reset: function() {
        this.words.clear();
        this.cursor = null;
        document.getElementById('vocabularyDialog').close();
        this.updateCount();
        this.updateNavigation();
    },
    record: function(focus, question) {
        if (!focus || question !== '解释选中内容在句子释义') return null;
        var word = focus.trim().replace(/\s+/g, ' ');
        if (!word) return null;
        var key = word.toLowerCase();
        var entry = this.words.get(key);
        if (!entry) {
            entry = { word: word, meaning: '' };
            this.words.set(key, entry);
        }
        this.updateCount();
        return entry;
    },
    updateCount: function() {
        document.getElementById('btnVocabularyReview').textContent = '生词回顾（' + this.words.size + '）';
    },
    render: function() {
        var list = document.getElementById('vocabularyList');
        list.replaceChildren();
        if (!this.words.size) {
            list.textContent = '暂无生词。选中单词或词组，点击“句中释义”即可收录。';
            return;
        }
        this.words.forEach(function(entry) {
            var item = document.createElement('div');
            item.className = 'vocabulary-item';
            var button = document.createElement('button');
            button.type = 'button';
            button.textContent = entry.word;
            button.setAttribute('aria-expanded', 'false');
            var meaning = document.createElement('p');
            meaning.hidden = true;
            button.addEventListener('click', function() {
                meaning.hidden = !meaning.hidden;
                meaning.textContent = entry.meaning || '释义尚未生成完成，请完成回答后再试。';
                button.setAttribute('aria-expanded', String(!meaning.hidden));
            });
            item.append(button, meaning);
            list.appendChild(item);
        });
    },
    updateNavigation: function() {
        var count = document.querySelectorAll('#chatMessages .question-label').length;
        var button = document.getElementById('btnPreviousQuestion');
        button.disabled = !count || this.cursor === 0;
        document.getElementById('btnNextQuestion').disabled = !count || this.cursor === count - 1;
    },
    previous: function() {
        this.jump(-1);
    },
    jump: function(direction) {
        var chat = document.getElementById('chatMessages');
        var questions = chat.querySelectorAll('.question-label');
        if (!questions.length) return;
        var target;
        if (this.cursor !== null) {
            target = Math.min(questions.length - 1, Math.max(0, this.cursor + direction));
        } else {
            target = direction < 0 ? 0 : questions.length - 1;
            var top = chat.getBoundingClientRect().top + chat.clientTop;
            for (var i = 0; i < questions.length; i++) {
                var questionTop = questions[i].getBoundingClientRect().top;
                if (direction < 0 && questionTop < top - 2) target = i;
                if (direction > 0 && questionTop > top + 2) { target = i; break; }
            }
        }
        this.cursor = target;
        var offset = questions[target].getBoundingClientRect().top - chat.getBoundingClientRect().top - chat.clientTop;
        chat.scrollTo({ top: chat.scrollTop + offset, behavior: 'smooth' });
        this.updateNavigation();
    }
};
