$(document).ready(function () {
  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function renderAlerts(alerts) {
    if (!alerts.length) {
      $('#alerts-list').html('<p class="text-muted">No new device alerts yet.</p>');
      return;
    }
    let html = '';
    alerts.forEach(function (alert) {
      html += `<div class="alert ${alert.read ? 'alert-secondary' : 'alert-warning'} device-alert-row" data-alert-id="${escapeHtml(alert.id)}">`;
      html += `<div><strong>${escapeHtml(alert.display_name)}</strong><p class="mb-1">${escapeHtml(alert.ip || 'No IP')} · ${escapeHtml(alert.mac || 'No MAC')} · ${escapeHtml(alert.manufacturer || 'Unknown')}</p>`;
      html += `<small>Seen via ${escapeHtml(alert.source || 'unknown')}${alert.interface ? ` on ${escapeHtml(alert.interface)}` : ''} at ${escapeHtml(alert.created_at_label || '')}</small></div>`;
      if (!alert.read) {
        html += `<button class="btn btn-sm btn-outline-dark" data-alert-read="${escapeHtml(alert.id)}">Mark read</button>`;
      }
      html += '</div>';
    });
    $('#alerts-list').html(html);
  }

  function loadAlerts() {
    $.ajax({
      url: '/alerts/status',
      method: 'GET',
      success: function (resp) {
        renderAlerts(resp.alerts || []);
      }
    });
  }

  $('#alerts-list').on('click', '[data-alert-read]', function () {
    const alertId = $(this).data('alert-read');
    $.ajax({
      url: `/alerts/${encodeURIComponent(alertId)}/read`,
      method: 'POST',
      complete: loadAlerts
    });
  });

  $('#mark-all-alerts-read').on('click', function () {
    $.ajax({
      url: '/alerts/read-all',
      method: 'POST',
      complete: loadAlerts
    });
  });
});
