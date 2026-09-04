document.addEventListener('DOMContentLoaded', function() {
    var sizes = [12, 14, 15, 16, 18, 20, 22, 24];
    [
        { id: 'articleFontSize', key: 'reading_article_font_size', variable: '--article-font-size', initial: 15 },
        { id: 'chatFontSize', key: 'reading_chat_font_size', variable: '--chat-font-size', initial: 14 }
    ].forEach(function(setting) {
        var select = document.getElementById(setting.id);
        sizes.forEach(function(size) {
            var option = document.createElement('option');
            option.value = String(size);
            option.textContent = size + (size === setting.initial ? '（默认）' : '');
            select.appendChild(option);
        });
        var saved;
        try { saved = Number(localStorage.getItem(setting.key)); } catch (e) {}
        select.value = String(sizes.indexOf(saved) >= 0 ? saved : setting.initial);
        function apply() {
            document.documentElement.style.setProperty(setting.variable, select.value + 'px');
        }
        apply();
        select.addEventListener('change', function() {
            apply();
            try { localStorage.setItem(setting.key, select.value); } catch (e) {}
        });
    });
});
