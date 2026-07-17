$(document).ready(function () {
  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function badgeClass(item) {
    if (item.is_control_traffic) return 'badge bg-secondary';
    if (item.network_scope === 'Public Internet') return 'badge bg-danger';
    if (item.is_internal) return 'badge bg-info text-dark';
    return 'badge bg-light text-dark';
  }

  function renderSummary(items) {
    const hosts = items.filter((item) => !item.is_control_traffic).length;
    const control = items.length - hosts;
    const internal = items.filter((item) => item.is_internal).length;
    const external = items.filter((item) => item.network_scope === 'Public Internet').length;
    return `<div class="alert alert-info" role="status">${hosts} host-like entries, ${control} broadcast/multicast control entries, ${internal} internal entries, ${external} public entries.</div>`;
  }

  function renderRows(items, mode) {
    let html = '<div class="table-responsive"><table class="table theme-table"><thead><tr><th>IP</th><th>MAC</th><th>Manufacturer</th><th>Role</th><th>Scope</th><th>Methods</th><th>Notes</th><th>Actions</th></tr></thead><tbody>';
    items.forEach(function (item) {
      const ip = escapeHtml(item.ip || '—');
      const mac = escapeHtml(item.mac || '—');
      const manufacturer = escapeHtml(item.manufacturer || 'Unknown');
      const role = escapeHtml(item.network_role || 'Host');
      const scope = escapeHtml(item.network_scope || 'Unknown');
      const methods = escapeHtml((item.discovery_methods || []).join(', ') || mode);
      const note = escapeHtml(item.scan_note || '');
      let ipCell = ip;
      let macCell = mac;
      const portScanAction = item.ip && !item.is_control_traffic
        ? `<a class="btn btn-outline-primary btn-sm" href="/port-scan?host=${encodeURIComponent(item.ip)}">Check ports</a>`
        : '—';
      if (mode === 'active') {
        const display = item.ip || 'Unknown IP';
        const linkTarget = item.mac || item.ip || '';
        ipCell = `<a href="/clients/${encodeURIComponent(linkTarget)}">${escapeHtml(display)}</a>`;
      } else if (item.mac) {
        macCell = `<a href="/clients/${encodeURIComponent(item.mac)}">${mac}</a>`;
      }
      html += `<tr class="${item.is_control_traffic ? 'table-secondary' : ''}"><td>${ipCell}</td><td>${macCell}</td><td>${manufacturer}</td><td><span class="${badgeClass(item)}">${role}</span></td><td>${scope}</td><td>${methods}</td><td>${note}</td><td>${portScanAction}</td></tr>`;
    });
    html += '</tbody></table></div><p><a href="/inventory">View full device inventory</a></p>';
    return html;
  }

  $('#comprehensive-scan-btn').on('click', function (e) {
    e.preventDefault();
    const iface = $('#interface-select-Scan').val();
    $('#scan-results').html('<p>Comprehensive scan running...</p>');
    $.ajax({
      url: '/comprehensive-scan',
      method: 'POST',
      data: {
        selectedInterface: iface,
        includePassive: $('#include-passive').is(':checked') ? 'on' : '',
        includeServices: $('#include-services').is(':checked') ? 'on' : '',
        sweepCidr: $('#sweep-cidr').val()
      },
      success: function (resp) {
        const result = resp.result;
        let html = '<h3>Comprehensive Device Scan Results</h3>';
        html += `<div class="alert alert-info" role="status">${result.summary.total_devices} total devices, ${result.summary.host_like} host-like devices, ${result.summary.with_services} with service metadata. Methods: ${escapeHtml(result.methods.join(', '))}</div>`;
        if (result.errors.length) {
          html += `<div class="alert alert-warning">Some methods reported errors: ${escapeHtml(result.errors.join('; '))}</div>`;
        }
        if (result.devices.length === 0) {
          html += '<p>No devices found</p>';
        } else {
          html += renderRows(result.devices, 'comprehensive');
        }
        $('#scan-results').html(html);
      },
      error: function (xhr) {
        $('#scan-results').html(`<p>${escapeHtml(xhr.responseJSON?.message || 'Comprehensive scan failed')}</p>`);
      }
    });
  });

  $('#active-scan-btn').on('click', function (e) {
    e.preventDefault();
    const iface = $('#interface-select-Scan').val();
    $.ajax({
      url: '/active-scan',
      method: 'POST',
      data: { selectedInterface: iface },
      success: function (resp) {
        let html = '<h3>Active Scan Results</h3>';
        if (resp.hosts.length === 0) {
          html += '<p>No hosts found</p>';
        } else {
          html += renderSummary(resp.hosts) + renderRows(resp.hosts, 'active');
        }
        $('#scan-results').html(html);
      },
      error: function () {
        $('#scan-results').html('<p>Scan failed</p>');
      }
    });
  });

  $('#passive-scan-btn').on('click', function (e) {
    e.preventDefault();
    const iface = $('#interface-select-Scan').val();
    $.ajax({
      url: '/passive-scan',
      method: 'POST',
      data: { selectedInterface: iface },
      success: function (resp) {
        let html = '<h3>Passive Scan Results</h3>';
        if (resp.devices.length === 0) {
          html += '<p>No devices found</p>';
        } else {
          html += renderSummary(resp.devices) + renderRows(resp.devices, 'passive');
        }
        $('#scan-results').html(html);
      },
      error: function () {
        $('#scan-results').html('<p>Scan failed</p>');
      }
    });
  });
});
