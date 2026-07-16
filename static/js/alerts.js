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
      html += `<div class="alert ${alert.read ? 'alert-secondary' : 'alert-warning'} device-alert-row" data-alert-id="${escapeHtml(alert.id)}" ${alert.device_url ? `data-device-url="${escapeHtml(alert.device_url)}" role="link" tabindex="0"` : ''}>`;
      html += `<div><strong>${escapeHtml(alert.display_name)}</strong><p class="mb-1">${escapeHtml(alert.ip || 'No IP')} · ${escapeHtml(alert.mac || 'No MAC')} · ${escapeHtml(alert.manufacturer || 'Unknown')}</p>`;
      html += `<small>Seen via ${escapeHtml(alert.source || 'unknown')}${alert.interface ? ` on ${escapeHtml(alert.interface)}` : ''} at ${escapeHtml(alert.created_at_label || '')}</small>`;
      if (alert.device_url) {
        html += `<div><a href="${escapeHtml(alert.device_url)}" class="alert-device-link">View device</a></div>`;
      }
      html += '</div>';
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

  function markRead(alertId, complete) {
    $.ajax({
      url: `/alerts/${encodeURIComponent(alertId)}/read`,
      method: 'POST',
      complete: complete || loadAlerts
    });
  }

  $('#alerts-list').on('click', '[data-alert-read]', function (event) {
    event.stopPropagation();
    markRead($(this).data('alert-read'));
  });

  $('#alerts-list').on('click keydown', '.device-alert-row[data-device-url]', function (event) {
    if (event.type === 'keydown' && event.key !== 'Enter' && event.key !== ' ') {
      return;
    }
    if ($(event.target).is('button, a')) {
      return;
    }
    event.preventDefault();
    const $row = $(this);
    const alertId = $row.data('alert-id');
    const deviceUrl = $row.data('device-url');
    markRead(alertId, function () {
      window.location.href = deviceUrl;
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
