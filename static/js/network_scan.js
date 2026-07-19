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

  function hostDevices(items) {
    return (items || []).filter((item) => item.ip && !item.is_control_traffic);
  }

  function renderSummary(items) {
    const hosts = items.filter((item) => !item.is_control_traffic).length;
    const control = items.length - hosts;
    const internal = items.filter((item) => item.is_internal).length;
    const external = items.filter((item) => item.network_scope === 'Public Internet').length;
    return `<div class="alert alert-info" role="status">${hosts} host-like entries, ${control} broadcast/multicast control entries, ${internal} internal entries, ${external} public entries.</div>`;
  }

  function renderPortBadges(item) {
    const details = Array.isArray(item.open_port_details) ? item.open_port_details : [];
    if (!details.length) return '<p class="text-muted mb-0 small">No saved open ports yet.</p>';
    return `<div class="network-device-open-ports">${details.slice(0, 6).map((port) => `<span class="badge badge-info">${escapeHtml(port.port)} ${escapeHtml(port.service || 'Unknown')}</span>`).join('')}</div>`;
  }

  function renderScanAllToolbar(items) {
    const hosts = hostDevices(items);
    if (!hosts.length) return '';
    const hostList = hosts.map((item) => item.ip).join(',');
    return `
      <div class="network-scan-all-toolbar alert alert-secondary" role="region" aria-label="Port scan all discovered devices">
        <div><strong>Port scan discovered IP devices</strong><p class="mb-0 small">Start background scans for all ${hosts.length} host-like IP device${hosts.length === 1 ? '' : 's'} in this result set.</p></div>
        <div class="theme-actions mb-0">
          <button class="btn btn-outline-primary btn-sm" data-port-scan-all data-hosts="${escapeHtml(hostList)}" data-start="1" data-end="1024" data-label="common port scan">Scan all common ports</button>
          <button class="btn btn-outline-danger btn-sm" data-port-scan-all data-hosts="${escapeHtml(hostList)}" data-start="1" data-end="65535" data-label="all-port scan">Scan all ports</button>
        </div>
        <div class="network-scan-all-status small text-muted" data-port-scan-all-status></div>
      </div>`;
  }

  function renderDeviceCards(items, mode) {
    let html = renderScanAllToolbar(items);
    html += '<div class="wireless-network-grid network-device-card-grid">';
    items.forEach(function (item) {
      const ip = item.ip || '';
      const mac = item.mac || '';
      const display = item.hostname || item.name || ip || mac || 'Unknown device';
      const manufacturer = item.manufacturer || 'Unknown manufacturer';
      const role = item.network_role || 'Host';
      const scope = item.network_scope || 'Unknown';
      const methods = (item.discovery_methods || []).join(', ') || mode;
      const note = item.scan_note || '';
      const clientTarget = mac || ip;
      const detailUrl = clientTarget ? `/clients/${encodeURIComponent(clientTarget)}` : '';
      const deviceActions = ip && !item.is_control_traffic
        ? `<div class="network-device-actions">
            <a class="btn btn-outline-info btn-sm" href="/clients/${encodeURIComponent(ip)}">Device profile</a>
            <a class="btn btn-outline-primary btn-sm" href="/port-scan?host=${encodeURIComponent(ip)}">Port scan</a>
            <a class="btn btn-outline-secondary btn-sm" href="/port-scan?host=${encodeURIComponent(ip)}">Common ports</a>
            <a class="btn btn-outline-danger btn-sm" href="/port-scan?host=${encodeURIComponent(ip)}">All ports</a>
          </div>`
        : '<span class="badge badge-secondary">No IP port scan</span>';
      html += `
        <article class="wireless-network-card network-device-card ${item.is_control_traffic ? 'network-device-card-control' : ''}">
          <div class="wireless-network-main">
            <div class="wireless-network-identity">
              <h3 class="wireless-network-ssid mb-1">${detailUrl ? `<a href="${escapeHtml(detailUrl)}">${escapeHtml(display)}</a>` : escapeHtml(display)}</h3>
              <p class="wireless-network-meta mb-0"><i class="fa-solid fa-network-wired"></i> ${escapeHtml(ip || 'Unknown IP')}</p>
              <p class="wireless-network-meta mb-0"><i class="fa-solid fa-fingerprint"></i> ${escapeHtml(mac || 'Unknown MAC')}</p>
              <p class="wireless-network-meta mb-0"><i class="fa-solid fa-industry"></i> ${escapeHtml(manufacturer)}</p>
            </div>
            <div class="wireless-network-badges">
              <span class="${badgeClass(item)}">${escapeHtml(role)}</span>
              <span class="badge badge-light border">${escapeHtml(scope)}</span>
              <span class="badge badge-info">${escapeHtml(methods)}</span>
            </div>
          </div>
          <div class="wireless-network-bottom network-device-bottom">
            <div>${renderPortBadges(item)}${note ? `<p class="text-muted small mb-0 mt-2">${escapeHtml(note)}</p>` : ''}</div>
            ${deviceActions}
          </div>
        </article>`;
    });
    html += '</div><p class="mt-3"><a href="/inventory">View full device inventory</a></p>';
    return html;
  }

  function startPortScanAll(button) {
    const hosts = String(button.attr('data-hosts') || '').split(',').filter(Boolean);
    const start = button.attr('data-start');
    const end = button.attr('data-end');
    const label = button.attr('data-label');
    const status = button.closest('.network-scan-all-toolbar').find('[data-port-scan-all-status]');
    if (!hosts.length) {
      status.text('No host-like IP devices to scan.');
      return;
    }
    button.closest('.network-scan-all-toolbar').find('[data-port-scan-all]').prop('disabled', true);
    status.text(`Starting ${label} jobs for ${hosts.length} host(s)...`);
    let started = 0;
    let failed = 0;
    hosts.forEach(function (host) {
      $.ajax({
        url: '/port-scan-jobs',
        method: 'POST',
        data: { host: host, start: start, end: end, label: label },
        complete: function (xhr) {
          if (xhr.status >= 200 && xhr.status < 300) started += 1;
          else failed += 1;
          status.text(`Started ${started} ${label} job(s); ${failed} failed. Results are saved to device profiles as ports are found.`);
          if (started + failed === hosts.length) {
            button.closest('.network-scan-all-toolbar').find('[data-port-scan-all]').prop('disabled', false);
          }
        }
      });
    });
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
          html += renderDeviceCards(result.devices, 'comprehensive');
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
          html += renderSummary(resp.hosts) + renderDeviceCards(resp.hosts, 'active');
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
          html += renderSummary(resp.devices) + renderDeviceCards(resp.devices, 'passive');
        }
        $('#scan-results').html(html);
      },
      error: function () {
        $('#scan-results').html('<p>Scan failed</p>');
      }
    });
  });

  $(document).on('click', '[data-port-scan-all]', function (e) {
    e.preventDefault();
    startPortScanAll($(this));
  });
});
