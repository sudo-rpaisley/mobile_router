$(document).ready(function () {
  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function detailByPort(job) {
    const details = {};
    (job.open_port_details || []).forEach(function (item) {
      details[item.port] = item;
    });
    return details;
  }

  function renderOpenPorts($panel, job, previousPorts) {
    const ports = job.open_ports || [];
    const details = detailByPort(job);
    const $list = $panel.find('[data-port-scan-open-ports]');
    if (!ports.length) {
      $list.html('<p class="text-muted mb-0">No open ports discovered yet.</p>');
      return;
    }

    let html = '<div class="port-service-grid">';
    ports.forEach(function (port) {
      const info = details[port] || { service: 'Unknown', description: 'No common service mapping found' };
      const isNew = !previousPorts.has(port);
      html += `<div class="port-service-card ${isNew ? 'port-service-card-new' : ''}">`;
      html += `<div class="port-service-number">${escapeHtml(port)}</div>`;
      html += `<div><strong>${escapeHtml(info.service)}</strong><p>${escapeHtml(info.description)}</p></div>`;
      html += '</div>';
    });
    html += '</div>';
    $list.html(html);
  }

  function renderJob($panel, job, previousPorts) {
    const progress = Math.max(0, Math.min(100, Number(job.progress || 0)));
    const scanned = job.scanned_ports || 0;
    const total = job.total_ports || 0;
    const current = job.current_port ? ` Current port: ${escapeHtml(job.current_port)}.` : '';
    const statusClass = job.status === 'failed' ? 'danger' : (job.status === 'complete' ? 'success' : 'info');

    $panel.find('[data-port-scan-status]').html(
      `<div class="alert alert-${statusClass}" role="status"><strong>${escapeHtml(job.status)}</strong>: ${escapeHtml(job.message || '')}${current}</div>`
    );
    $panel.find('[data-port-scan-progress-bar]').css('width', `${progress}%`).attr('aria-valuenow', progress).text(`${progress}%`);
    $panel.find('[data-port-scan-progress-text]').text(`${scanned} of ${total} ports checked`);
    renderOpenPorts($panel, job, previousPorts);
  }

  function pollJob($panel, jobId, previousPorts) {
    $.ajax({
      url: `/port-scan-jobs/${encodeURIComponent(jobId)}`,
      method: 'GET',
      success: function (resp) {
        const job = resp.job;
        const openPorts = new Set(job.open_ports || []);
        renderJob($panel, job, previousPorts);
        if (job.status === 'queued' || job.status === 'running') {
          setTimeout(function () { pollJob($panel, jobId, openPorts); }, 1000);
        } else {
          $panel.find('[data-port-scan-start], [data-port-scan-custom-submit]').prop('disabled', false);
        }
      },
      error: function (xhr) {
        const message = xhr.responseJSON && xhr.responseJSON.message ? xhr.responseJSON.message : 'Port scan status failed';
        $panel.find('[data-port-scan-status]').html(`<div class="alert alert-danger">${escapeHtml(message)}</div>`);
        $panel.find('[data-port-scan-start], [data-port-scan-custom-submit]').prop('disabled', false);
      }
    });
  }

  function startScan($panel, host, start, end, label) {
    if (!host) {
      $panel.find('[data-port-scan-status]').html('<div class="alert alert-danger">Host is required.</div>');
      return;
    }
    $panel.find('[data-port-scan-start], [data-port-scan-custom-submit]').prop('disabled', true);
    $panel.find('[data-port-scan-status]').html(`<div class="alert alert-info">Starting ${escapeHtml(label)} in the background for ${escapeHtml(host)}...</div>`);
    $panel.find('[data-port-scan-progress-bar]').css('width', '0%').attr('aria-valuenow', 0).text('0%');
    $panel.find('[data-port-scan-progress-text]').text('0 ports checked');
    $panel.find('[data-port-scan-open-ports]').html('<p class="text-muted mb-0">Waiting for open ports...</p>');

    $.ajax({
      url: '/port-scan-jobs',
      method: 'POST',
      data: { host: host, start: start, end: end, label: label },
      success: function (resp) {
        renderJob($panel, resp.job, new Set());
        pollJob($panel, resp.job.id, new Set(resp.job.open_ports || []));
      },
      error: function (xhr) {
        const message = xhr.responseJSON && xhr.responseJSON.message ? xhr.responseJSON.message : 'Port scan failed to start';
        $panel.find('[data-port-scan-status]').html(`<div class="alert alert-danger">${escapeHtml(message)}</div>`);
        $panel.find('[data-port-scan-start], [data-port-scan-custom-submit]').prop('disabled', false);
      }
    });
  }

  $('.port-scan-panel').each(function () {
    const $panel = $(this);
    const params = new URLSearchParams(window.location.search);
    const hostParam = params.get('host');
    const $hostInput = $panel.find('[data-port-scan-host]');
    if (hostParam && $hostInput.length) {
      $hostInput.val(hostParam);
    }

    $panel.on('click', '[data-port-scan-start]', function (e) {
      e.preventDefault();
      const $button = $(this);
      const host = ($hostInput.val() || $panel.data('host') || '').trim();
      startScan($panel, host, $button.data('start'), $button.data('end'), $button.data('label') || 'port scan');
    });

    $panel.on('submit', '[data-port-scan-custom-form]', function (e) {
      e.preventDefault();
      const host = ($hostInput.val() || $panel.data('host') || '').trim();
      const start = $panel.find('[data-port-scan-start-input]').val();
      const end = $panel.find('[data-port-scan-end-input]').val();
      startScan($panel, host, start, end, 'custom port scan');
    });
  });
});
