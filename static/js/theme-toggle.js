(function () {
  function preferredTheme() {
    var stored = window.localStorage.getItem('theme');
    if (stored === 'dark' || stored === 'light') {
      return stored;
    }
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    var toggle = document.getElementById('theme-toggle');
    if (toggle) {
      var isDark = theme === 'dark';
      toggle.setAttribute('aria-pressed', String(isDark));
      toggle.innerHTML = isDark ? '<i class="fa-solid fa-sun"></i> Light' : '<i class="fa-solid fa-moon"></i> Dark';
      toggle.title = isDark ? 'Switch to light mode' : 'Switch to dark mode';
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    applyTheme(preferredTheme());
    var toggle = document.getElementById('theme-toggle');
    if (!toggle) {
      return;
    }
    toggle.addEventListener('click', function () {
      var nextTheme = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      window.localStorage.setItem('theme', nextTheme);
      applyTheme(nextTheme);
    });
  });
}());
