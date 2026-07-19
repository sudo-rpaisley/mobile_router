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
    return `<div class="network-device-open-ports">${details.slice(0, 6).map((port) => {
      const title = port.http_title ? ` · ${escapeHtml(port.http_title)}` : '';
      const label = `${escapeHtml(port.port)} ${escapeHtml(port.service || 'Unknown')}${title}`;
      const tooltip = escapeHtml(port.http_title || port.http_status || port.description || '');
      return port.web_url ? `<a class="badge badge-info" href="${escapeHtml(port.web_url)}" target="_blank" rel="noopener noreferrer" title="${tooltip}" data-web-service-preview>${label}</a>` : `<span class="badge badge-info">${label}</span>`;
    }).join('')}</div>`;
  }

  function renderTagBadges(tags) {
    if (!Array.isArray(tags) || !tags.length) return '';
    return tags.map((tag) => `<span class="badge badge-light border">${escapeHtml(tag)}</span>`).join('');
  }

  function refreshDeviceCard(host, card) {
    if (!host || !card.length) return;
    $.ajax({
      url: `/clients/${encodeURIComponent(host)}/summary`,
      method: 'GET',
      success: function (resp) {
        const device = resp.device || {};
        const ports = card.find('[data-network-device-ports]');
        ports.html(renderPortBadges(device));
        const tags = card.find('[data-network-device-tags]');
        tags.html(renderTagBadges(device.client_tags || []));
        const notes = card.find('[data-network-device-notes]');
        if (device.client_notes) notes.removeClass('d-none').text(device.client_notes);
        else notes.addClass('d-none').text('');
        card.attr('data-has-open-ports', (device.open_port_details || []).length ? 'true' : 'false');
        if (device.display_name) card.find('[data-network-device-title]').text(device.display_name);
      }
    });
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

  function updateNetworkScanAllHosts(items) {
    const hostList = hostDevices(items).map((item) => item.ip).join(',');
    $('[data-port-scan-all]').attr('data-hosts', hostList);
  }

  function detailsHasPorts(item) {
    return Array.isArray(item.open_port_details) && item.open_port_details.length ? 'true' : 'false';
  }

  function renderDeviceCards(items, mode, includeToolbar) {
    const showToolbar = includeToolbar !== false;
    let html = showToolbar ? renderScanAllToolbar(items) : '';
    html += '<div class="wireless-network-grid network-device-card-grid">';
    items.forEach(function (item) {
      const ip = item.ip || '';
      const mac = item.mac || '';
      const display = item.hostname || item.name || ip || mac || 'Unknown device';
      const manufacturer = item.manufacturer || 'Unknown manufacturer';
      const roleGuess = item.device_role_guess || {};
      const role = roleGuess.role || item.network_role || 'Host';
      const scope = item.network_scope || 'Unknown';
      const methods = (item.discovery_methods || []).join(', ') || mode;
      const note = item.scan_note || '';
      const clientTarget = mac || ip;
      const detailUrl = clientTarget ? `/clients/${encodeURIComponent(clientTarget)}` : '';
      const deviceActions = ip && !item.is_control_traffic
        ? `<div class="network-device-actions">
            <a class="btn btn-outline-info btn-sm" href="/clients/${encodeURIComponent(ip)}">Device profile</a>
            <a class="btn btn-outline-primary btn-sm" href="/port-scan?host=${encodeURIComponent(ip)}">Port scan</a>
            <button class="btn btn-outline-secondary btn-sm" data-port-scan-quick data-host="${escapeHtml(ip)}" data-start="1" data-end="1024" data-label="common port scan">Common ports</button>
            <button class="btn btn-outline-danger btn-sm" data-port-scan-quick data-host="${escapeHtml(ip)}" data-start="1" data-end="65535" data-label="all-port scan">All ports</button>
            <div class="network-device-scan-status small text-muted" data-port-scan-quick-status></div>
            <div class="progress network-device-progress" data-port-scan-quick-progress><div class="progress-bar" role="progressbar" style="width: 0%;" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">0%</div></div>
            <form class="network-device-notes-form" data-network-device-notes-form data-host="${escapeHtml(ip)}">
              <input class="form-control form-control-sm" name="tags" placeholder="Tags, comma separated" value="${escapeHtml((item.client_tags || []).join(', '))}">
              <textarea class="form-control form-control-sm" name="notes" rows="2" placeholder="Device notes">${escapeHtml(item.client_notes || '')}</textarea>
              <button class="btn btn-outline-success btn-sm" type="submit">Save notes/tags</button>
              <div class="network-device-notes-status small text-muted" data-network-device-notes-status></div>
            </form>
          </div>`
        : '<span class="badge badge-secondary">No IP port scan</span>';
      html += `
        <article class="wireless-network-card network-device-card ${item.is_control_traffic ? 'network-device-card-control' : ''}" data-network-device-card data-host="${escapeHtml(ip)}" data-role="${escapeHtml(role)}" data-known-state="${escapeHtml(item.network_known_state || 'Known')}" data-has-open-ports="${detailsHasPorts(item)}" data-unknown="${!ip || manufacturer === 'Unknown manufacturer'}">
          <div class="wireless-network-main">
            <div class="wireless-network-identity">
              <h3 class="wireless-network-ssid mb-1">${detailUrl ? `<a href="${escapeHtml(detailUrl)}">${escapeHtml(display)}</a>` : escapeHtml(display)}</h3>
              <p class="wireless-network-meta mb-0"><i class="fa-solid fa-network-wired"></i> ${escapeHtml(ip || 'Unknown IP')}</p>
              <p class="wireless-network-meta mb-0"><i class="fa-solid fa-fingerprint"></i> ${escapeHtml(mac || 'Unknown MAC')}</p>
              <p class="wireless-network-meta mb-0"><i class="fa-solid fa-industry"></i> ${escapeHtml(manufacturer)}</p>
            </div>
            <div class="wireless-network-badges">
              <span class="badge ${item.network_known_state === 'New' ? 'badge-warning' : 'badge-success'}">${escapeHtml(item.network_known_state || 'Known')}</span>
              <span class="${badgeClass(item)}">${escapeHtml(role)}</span>
              ${item.likely_randomized_mac ? '<span class="badge badge-warning">Randomized MAC likely</span>' : ''}
              <span class="badge badge-light border">${escapeHtml(scope)}</span>
              <span class="badge badge-info">${escapeHtml(methods)}</span>
            </div>
          </div>
          <div class="wireless-network-bottom network-device-bottom">
            <div><div data-network-device-ports>${renderPortBadges(item)}</div><div class="network-device-tags mt-2" data-network-device-tags>${renderTagBadges(item.client_tags || [])}</div>${item.client_notes ? `<p class="text-muted small mb-0 mt-2" data-network-device-notes>${escapeHtml(item.client_notes)}</p>` : `<p class="text-muted small mb-0 mt-2 d-none" data-network-device-notes></p>`}${Array.isArray(item.observed_names) && item.observed_names.length ? `<p class="text-muted small mb-0 mt-2">Names: ${escapeHtml(item.observed_names.slice(0, 3).map((entry) => entry.name).join(', '))}</p>` : ''}${note ? `<p class="text-muted small mb-0 mt-2">${escapeHtml(note)}</p>` : ''}</div>
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

  function startQuickPortScan(button) {
    const host = button.attr('data-host');
    const start = button.attr('data-start');
    const end = button.attr('data-end');
    const label = button.attr('data-label') || 'port scan';
    const actions = button.closest('.network-device-actions');
    const status = actions.find('[data-port-scan-quick-status]');
    actions.find('[data-port-scan-quick]').prop('disabled', true);
    status.text(`Starting ${label} for ${host}...`);
    $.ajax({
      url: '/port-scan-jobs',
      method: 'POST',
      data: { host: host, start: start, end: end, label: label },
      complete: function (xhr) {
        if (xhr.status >= 200 && xhr.status < 300) {
          const job = xhr.responseJSON?.job || {};
          status.text(`Started ${label}. Scanning...`);
          pollQuickPortScan(job.id, actions.closest('[data-network-device-card]'), status);
        } else {
          status.text(xhr.responseJSON?.message || `${label} failed to start.`);
        }
        actions.find('[data-port-scan-quick]').prop('disabled', false);
      }
    });
  }

  function pollQuickPortScan(jobId, card, status) {
    if (!jobId) return;
    $.ajax({
      url: `/port-scan-jobs/${encodeURIComponent(jobId)}`,
      method: 'GET',
      success: function (resp) {
        const job = resp.job || {};
        const progress = job.progress == null ? 0 : job.progress;
        status.text(`${job.label || 'Port scan'} ${job.status}: ${progress}% (${job.open_ports?.length || 0} open)`);
        card.find('[data-port-scan-quick-progress] .progress-bar').css('width', `${progress}%`).attr('aria-valuenow', progress).text(`${progress}%`);
        const host = card.attr('data-host') || job.host;
        refreshDeviceCard(host, card);
        if (['queued', 'running'].includes(job.status)) {
          setTimeout(function () { pollQuickPortScan(jobId, card, status); }, 1500);
        } else {
          status.text(`${job.message || 'Port scan finished.'}`);
          refreshDeviceCard(host, card);
        }
      },
      error: function () {
        status.text('Unable to refresh scan progress.');
      }
    });
  }

  function isNetworkDeviceListMode() {
    return $('[data-network-device-list-scan]').length > 0;
  }

  function showNetworkDeviceListStatus(message, level) {
    const klass = level || 'info';
    $('#scan-results').html(`<div class="alert alert-${klass}" role="status">${escapeHtml(message)}</div>`);
  }

  function networkDeviceListParams() {
    const form = $('[data-network-device-list-scan]');
    return {
      interface: form.attr('data-interface') || $('#interface-select-Scan').val() || $('[data-passive-monitor-toggle]').attr('data-interface') || '',
      ssid: form.attr('data-ssid') || '',
      bssid: form.attr('data-bssid') || ''
    };
  }

  function renderNetworkDeviceListItems(items) {
    const list = $('[data-network-device-list]');
    if (!list.length) return;
    const cards = renderDeviceCards(items || [], 'wireless-network', false);
    const inner = $(cards).filter('.network-device-card-grid').html() || '';
    list.html(inner);
    $('[data-network-device-empty]').toggleClass('d-none', !!(items || []).length);
    updateNetworkScanAllHosts(items || []);
  }

  function refreshNetworkDeviceList(message) {
    const params = networkDeviceListParams();
    showNetworkDeviceListStatus(message || 'Updating device list...', 'success');
    $.ajax({
      url: '/wireless/network/clients.json',
      method: 'GET',
      data: params,
      success: function (resp) {
        renderNetworkDeviceListItems(resp.clients || []);
        showNetworkDeviceListStatus(message || `Device list updated with ${(resp.clients || []).length} device(s).`, 'success');
      },
      error: function (xhr) {
        showNetworkDeviceListStatus(xhr.responseJSON?.message || 'Device list refresh failed. The saved inventory was updated, but this tab could not redraw.', 'warning');
      }
    });
  }

  function activateNetworkDeviceTabFromHash() {
    if (!isNetworkDeviceListMode()) return;
    if (window.location.hash === '#network-device-scan' || window.location.hash === '#network-devices-pane') {
      $('#network-devices-tab').tab('show');
    }
  }

  function applyNetworkDeviceFilter(filter) {
    $('[data-network-device-card]').each(function () {
      const card = $(this);
      const role = String(card.attr('data-role') || '').toLowerCase();
      const show = filter === 'all'
        || (filter === 'gateway' && role.includes('gateway'))
        || (filter === 'open-ports' && card.attr('data-has-open-ports') === 'true')
        || (filter === 'new' && card.attr('data-known-state') === 'New')
        || (filter === 'unknown' && card.attr('data-unknown') === 'true');
      card.toggle(show);
    });
  }


  let passiveMonitorLastUpdate = null;
  let passiveMonitorPollTimer = null;

  function passiveMonitorControls() {
    return $('[data-passive-monitor-toggle]');
  }

  function setPassiveMonitorStatus(message, level) {
    const status = $('[data-passive-monitor-status]');
    status.removeClass('text-muted text-success text-danger text-warning');
    status.addClass(level ? `text-${level}` : 'text-muted');
    status.text(message);
  }

  function pollPassiveMonitorStatus() {
    const toggle = passiveMonitorControls();
    if (!toggle.length) return;
    const iface = toggle.attr('data-interface');
    $.ajax({
      url: '/passive-monitor/status',
      method: 'GET',
      data: { selectedInterface: iface },
      success: function (resp) {
        const status = resp.status || {};
        toggle.prop('checked', !!status.enabled);
        if (status.interval) $('[data-passive-monitor-interval]').val(status.interval);
        if (status.enabled) {
          const count = status.last_count == null ? 'no' : status.last_count;
          setPassiveMonitorStatus(`Passive capture running every ${status.interval || 10}s; last update saw ${count} device(s).`, status.error ? 'warning' : 'success');
          if (status.last_update && passiveMonitorLastUpdate && status.last_update !== passiveMonitorLastUpdate) {
            refreshNetworkDeviceList(`Passive capture added ${count} observed device(s).`);
          }
          passiveMonitorLastUpdate = status.last_update || passiveMonitorLastUpdate;
        } else {
          setPassiveMonitorStatus('Passive monitor is off.', 'muted');
        }
      },
      complete: function () {
        window.clearTimeout(passiveMonitorPollTimer);
        passiveMonitorPollTimer = window.setTimeout(pollPassiveMonitorStatus, 5000);
      }
    });
  }

  function togglePassiveMonitor(toggle) {
    const enabled = toggle.is(':checked');
    const iface = toggle.attr('data-interface');
    const interval = $('[data-passive-monitor-interval]').val() || 10;
    setPassiveMonitorStatus(enabled ? 'Starting continuous passive capture...' : 'Stopping continuous passive capture...', 'muted');
    $.ajax({
      url: '/passive-monitor/toggle',
      method: 'POST',
      data: { selectedInterface: iface, enabled: enabled ? 'on' : '', interval: interval },
      success: function (resp) {
        const status = resp.status || {};
        passiveMonitorLastUpdate = status.last_update || null;
        setPassiveMonitorStatus(resp.message || 'Passive monitor updated.', enabled ? 'success' : 'muted');
        pollPassiveMonitorStatus();
      },
      error: function (xhr) {
        toggle.prop('checked', !enabled);
        setPassiveMonitorStatus(xhr.responseJSON?.message || 'Unable to update passive monitor.', 'danger');
      }
    });
  }

  activateNetworkDeviceTabFromHash();

  pollPassiveMonitorStatus();

  $(document).on('change', '[data-passive-monitor-toggle]', function () {
    togglePassiveMonitor($(this));
  });

  $(document).on('click', 'a[href="#network-device-scan"]', function () {
    if (isNetworkDeviceListMode()) {
      $('#network-devices-tab').tab('show');
    }
  });

  $('#comprehensive-scan-btn').on('click', function (e) {
    e.preventDefault();
    const iface = $('#interface-select-Scan').val();
    if (isNetworkDeviceListMode()) showNetworkDeviceListStatus('Comprehensive scan running. Devices will be saved into this tab...', 'info');
    else $('#scan-results').html('<p>Comprehensive scan running...</p>');
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
        if (isNetworkDeviceListMode()) {
          refreshNetworkDeviceList(`Comprehensive scan saved ${result.summary.total_devices} device(s). Updating the device list...`);
          return;
        }
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
        showNetworkDeviceListStatus(xhr.responseJSON?.message || 'Comprehensive scan failed', 'danger');
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
        if (isNetworkDeviceListMode()) {
          refreshNetworkDeviceList(`Active scan saved ${resp.hosts.length} host(s). Updating the device list...`);
          return;
        }
        let html = '<h3>Active Scan Results</h3>';
        if (resp.hosts.length === 0) {
          html += '<p>No hosts found</p>';
        } else {
          html += renderSummary(resp.hosts) + renderDeviceCards(resp.hosts, 'active');
        }
        $('#scan-results').html(html);
      },
      error: function () {
        showNetworkDeviceListStatus('Scan failed', 'danger');
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
        if (isNetworkDeviceListMode()) {
          refreshNetworkDeviceList(`Passive scan saved ${resp.devices.length} device(s). Updating the device list...`);
          return;
        }
        let html = '<h3>Passive Scan Results</h3>';
        if (resp.devices.length === 0) {
          html += '<p>No devices found</p>';
        } else {
          html += renderSummary(resp.devices) + renderDeviceCards(resp.devices, 'passive');
        }
        $('#scan-results').html(html);
      },
      error: function () {
        showNetworkDeviceListStatus('Scan failed', 'danger');
      }
    });
  });

  $(document).on('click', '[data-port-scan-all]', function (e) {
    e.preventDefault();
    startPortScanAll($(this));
  });

  $(document).on('click', '[data-port-scan-quick]', function (e) {
    e.preventDefault();
    startQuickPortScan($(this));
  });

  $(document).on('click', '[data-network-device-filter]', function (e) {
    e.preventDefault();
    $('[data-network-device-filter]').removeClass('active');
    $(this).addClass('active');
    applyNetworkDeviceFilter($(this).attr('data-network-device-filter'));
  });

  $(document).on('submit', '[data-network-device-label-form]', function (e) {
    e.preventDefault();
    const form = $(this);
    const status = form.find('[data-network-device-label-status]');
    const card = form.closest('[data-network-device-card]');
    status.text('Saving SSID label...');
    $.ajax({
      url: '/wireless/network/label',
      method: 'POST',
      data: {
        interface: form.attr('data-interface'),
        ssid: form.attr('data-ssid'),
        bssid: form.attr('data-bssid'),
        identity: form.attr('data-identity'),
        label: form.find('[name="label"]').val()
      },
      success: function (resp) {
        status.text(resp.message || 'SSID label saved.');
        const label = form.find('[name="label"]').val();
        if (label) card.find('[data-network-device-title]').text(label);
      },
      error: function (xhr) {
        status.text(xhr.responseJSON?.message || 'Failed to save SSID label.');
      }
    });
  });

  $(document).on('submit', '[data-network-device-notes-form]', function (e) {
    e.preventDefault();
    const form = $(this);
    const host = form.attr('data-host');
    const status = form.find('[data-network-device-notes-status]');
    status.text('Saving notes/tags...');
    $.ajax({
      url: `/clients/${encodeURIComponent(host)}/metadata`,
      method: 'POST',
      data: form.serialize(),
      success: function () {
        status.text('Saved notes/tags.');
        refreshDeviceCard(host, form.closest('[data-network-device-card]'));
      },
      error: function (xhr) {
        status.text(xhr.responseJSON?.message || 'Failed to save notes/tags.');
      }
    });
  });
});
