$(document).ready(function () {
  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function statusClass(status) {
    if (status === 'failed') return 'danger';
    if (status === 'cancelled') return 'warning';
    if (status === 'complete' || status === 'completed') return 'success';
    return 'info';
  }

  function renderJobs(jobs, runningCount) {
    $('#jobs-running-count').text(`${runningCount} running`);
    if (!jobs.length) {
      $('#jobs-list').html('<p class="text-muted">No background jobs yet.</p>');
      return;
    }

    let html = '<div class="list-group jobs-live-list">';
    jobs.forEach(function (job) {
      const progress = Math.max(0, Math.min(100, Number(job.progress || 0)));
      const title = job.kind === 'port-scan'
        ? `${job.label || 'port scan'} on ${job.host}`
        : `${job.label || job.scan_type || 'scan'} on ${job.selected_interface || 'adapter'}`;
      const detail = job.kind === 'port-scan'
        ? `${job.scanned_ports || 0} of ${job.total_ports || 0} ports checked; ${job.open_ports ? job.open_ports.length : 0} open.`
        : (job.message || job.error || 'Adapter scan job.');
      const details = {};
      (job.open_port_details || []).forEach(function (item) { details[item.port] = item; });
      const openPorts = job.open_ports && job.open_ports.length
        ? `<div class="port-service-grid mt-2">${job.open_ports.map((port) => {
            const info = details[port] || { service: 'Unknown', description: 'No common service mapping found' };
            const portLabel = `${escapeHtml(port)}/tcp`;
            const portHtml = info.web_url ? `<a href="${escapeHtml(info.web_url)}" target="_blank" rel="noopener noreferrer">${portLabel}</a>` : portLabel;
            return `<div class="port-service-card"><div class="port-service-number">${portHtml}</div><div><strong>${escapeHtml(info.service)}</strong><p>${escapeHtml(info.description)}</p></div></div>`;
          }).join('')}</div>`
        : '';
      const cancel = job.cancelable
        ? `<button class="btn btn-outline-danger btn-sm" data-cancel-job="${escapeHtml(job.id)}">Cancel</button>`
        : '';
      html += `<div class="list-group-item">`;
      html += `<div class="d-flex justify-content-between align-items-start"><div><strong>${escapeHtml(title)}</strong> <span class="badge bg-${statusClass(job.status)}">${escapeHtml(job.status)}</span><p class="mb-1 text-muted">${escapeHtml(detail)}</p></div>${cancel}</div>`;
      html += `<div class="progress mt-2"><div class="progress-bar" role="progressbar" style="width: ${progress}%;" aria-valuenow="${progress}" aria-valuemin="0" aria-valuemax="100">${progress}%</div></div>`;
      html += openPorts;
      html += '</div>';
    });
    html += '</div>';
    $('#jobs-list').html(html);
  }

  function loadJobs() {
    $.ajax({
      url: '/jobs/status',
      method: 'GET',
      success: function (resp) {
        renderJobs(resp.jobs || [], resp.running_count || 0);
      },
      error: function () {
        $('#jobs-list').html('<p class="text-danger">Could not load jobs.</p>');
      },
      complete: function () {
        setTimeout(loadJobs, 1500);
      }
    });
  }

  $('#jobs-list').on('click', '[data-cancel-job]', function () {
    const jobId = $(this).data('cancel-job');
    $(this).prop('disabled', true).text('Cancelling...');
    $.ajax({
      url: `/jobs/${encodeURIComponent(jobId)}/cancel`,
      method: 'POST',
      complete: loadJobs
    });
  });

  loadJobs();
});
