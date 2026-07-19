$(document).ready(function () {
  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  $('.install-package-btn').on('click', function () {
    const button = $(this);
    const packageName = button.data('package');
    const response = $('#package-install-response');

    $.ajax({
      url: '/capabilities/install-package',
      type: 'POST',
      data: { package: packageName },
      beforeSend: function () {
        button.prop('disabled', true).text('Downloading...');
        response.html(`<div class="alert alert-info" role="alert">Downloading ${escapeHtml(packageName)}. This can take a minute.</div>`);
      },
      success: function () {
        response.html(`<div class="alert alert-success" role="alert">${escapeHtml(packageName)} downloaded. Refreshing capabilities...</div>`);
        window.setTimeout(function () { window.location.reload(); }, 1200);
      },
      error: function (xhr) {
        const message = xhr.responseJSON?.message || `Unable to install ${packageName}`;
        response.html(`<div class="alert alert-danger" role="alert">${escapeHtml(message)}</div>`);
      },
      complete: function () {
        button.prop('disabled', false).text(button.hasClass('btn-outline-secondary') ? 'Re-download' : 'Download');
      }
    });
  });

  $('.install-host-dependency-btn').on('click', function () {
    const button = $(this);
    const dependency = button.data('dependency');
    const response = $('#package-install-response');
    const confirmed = window.confirm('Install browser screenshot tooling on this host? This runs the local package manager and can take several minutes.');
    if (!confirmed) return;

    $.ajax({
      url: '/capabilities/install-host-dependency',
      type: 'POST',
      data: { dependency: dependency, confirm: button.data('confirm') },
      beforeSend: function () {
        button.prop('disabled', true).text('Installing...');
        response.html(`<div class="alert alert-info" role="alert">Installing ${escapeHtml(dependency)} host tooling. This can take several minutes.</div>`);
      },
      success: function (resp) {
        response.html(`<div class="alert alert-success" role="alert">${escapeHtml(resp.message || 'Host dependency installed.')} Refreshing capabilities...</div>`);
        window.setTimeout(function () { window.location.reload(); }, 1500);
      },
      error: function (xhr) {
        const message = xhr.responseJSON?.message || `Unable to install ${dependency}`;
        response.html(`<div class="alert alert-danger" role="alert">${escapeHtml(message)}</div>`);
      },
      complete: function () {
        button.prop('disabled', false).text('Install for me');
      }
    });
  });
});
