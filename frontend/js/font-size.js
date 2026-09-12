document.addEventListener('DOMContentLoaded', function() {
    var settingsOverlay = document.getElementById('settingsOverlay');
    document.getElementById('btnSettings').addEventListener('click', function() {
        settingsOverlay.style.display = 'flex';
        document.getElementById('settingsClose').focus();
    });
    function closeSettings() { settingsOverlay.style.display = 'none'; }
    document.getElementById('settingsClose').addEventListener('click', closeSettings);
    settingsOverlay.addEventListener('click', function(event) { if (event.target === settingsOverlay) closeSettings(); });
    document.addEventListener('keydown', function(event) { if (event.key === 'Escape' && settingsOverlay.style.display !== 'none') closeSettings(); });

    var darkMode = document.getElementById('darkModeToggle');
    darkMode.checked = document.documentElement.dataset.theme === 'dark';
    darkMode.addEventListener('change', function() {
        if (darkMode.checked) document.documentElement.dataset.theme = 'dark';
        else delete document.documentElement.dataset.theme;
        try { localStorage.setItem('reading_theme', darkMode.checked ? 'dark' : 'light'); } catch (e) {}
    });

    var sizes = [12, 14, 15, 16, 18, 20, 22, 24];
    [
        { id: 'articleFontSize', key: 'reading_article_font_size', variable: '--article-font-size', initial: 15 },
        { id: 'chatFontSize', key: 'reading_chat_font_size', variable: '--chat-font-size', initial: 14 },
        { id: 'selectionFontSize', key: 'reading_selection_font_size', variable: '--selection-font-size', initial: 16 }
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
