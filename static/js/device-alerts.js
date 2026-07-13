(function () {
  function ensureContainer() {
    var container = document.getElementById('device-alert-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'device-alert-container';
      container.className = 'device-alert-container';
      document.body.appendChild(container);
    }
    return container;
  }

  function notify(title, message) {
    var container = ensureContainer();
    var alert = document.createElement('div');
    alert.className = 'device-alert card shadow-sm';
    alert.innerHTML = '<strong>' + title + '</strong><p class="mb-0">' + message + '</p>';
    container.appendChild(alert);
    window.setTimeout(function () { alert.classList.add('show'); }, 10);
    window.setTimeout(function () {
      alert.classList.remove('show');
      window.setTimeout(function () { alert.remove(); }, 250);
    }, 6000);
  }

  window.deviceAlerts = { notify: notify };
}());
