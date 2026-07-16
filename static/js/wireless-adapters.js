$(document).ready(function () {
  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function signalClass(signal) {
    const value = Number(signal);
    if (Number.isNaN(value)) {
      return 'text-muted';
    }
    if (value >= 0) {
      return value >= 70 ? 'text-success' : value >= 40 ? 'text-warning' : 'text-danger';
    }
    return value >= -55 ? 'text-success' : value >= -70 ? 'text-warning' : 'text-danger';
  }

  function signalLabel(signal) {
    if (signal === undefined || signal === null || signal === '') {
      return 'Unknown signal';
    }
    return `${signal}${Number(signal) > 0 ? '%' : ' dBm'}`;
  }

  function scanCacheKey(interfaceName) {
    return `mobile-router:wlan-scan:${interfaceName}`;
  }

  function scanResultContainer(interfaceName) {
    return $('.wlans').filter(function () {
      return $(this).data('interface') === interfaceName;
    }).first();
  }

  function saveCachedNetworks(interfaceName, networks) {
    try {
      window.sessionStorage.setItem(scanCacheKey(interfaceName), JSON.stringify({
        networks: networks,
        scannedAt: new Date().toISOString()
      }));
    } catch (error) {
      // Some browsers disable storage; scans should still render for this page view.
    }
  }

  function loadCachedNetworks(interfaceName) {
    try {
      const cached = JSON.parse(window.sessionStorage.getItem(scanCacheKey(interfaceName)) || 'null');
      return Array.isArray(cached?.networks) ? cached.networks : [];
    } catch (error) {
      return [];
    }
  }

  function restoreCachedScanResults() {
    $('.wlans[data-interface]').each(function () {
      const container = $(this);
      const interfaceName = container.data('interface');
      const networks = loadCachedNetworks(interfaceName);
      if (networks.length > 0) {
        container.html(renderNetworks(interfaceName, networks));
      }
    });
  }

  function modeInputId(interfaceName, mode) {
    return `mode-${interfaceName}-${mode}`.replace(/[^A-Za-z0-9_-]/g, '-');
  }

  function renderAdapterModes(container, modes, currentMode) {
    if (!Array.isArray(modes) || modes.length === 0) {
      container.html('<p class="adapter-mode-empty mb-2">No switchable modes detected.</p>');
      return;
    }

    const interfaceName = container.data('interface');
    container.data('currentMode', currentMode);
    const switches = modes.map(function (mode) {
      const inputId = modeInputId(interfaceName, mode.value);
      const checked = mode.value === currentMode ? 'checked' : '';
      return `
        <div class="custom-control custom-switch adapter-mode-switch">
          <input type="radio" class="custom-control-input adapter-mode-input" name="mode-${escapeHtml(interfaceName)}" id="${escapeHtml(inputId)}" value="${escapeHtml(mode.value)}" ${checked}>
          <label class="custom-control-label" for="${escapeHtml(inputId)}">${escapeHtml(mode.label)}</label>
        </div>
      `;
    }).join('');

    container.html(`
      <div class="adapter-mode-panel">
        <p class="interface-kicker mb-1">Adapter Mode</p>
        <div class="adapter-mode-list">${switches}</div>
        <p class="adapter-mode-current mb-0">Current: <strong>${escapeHtml(currentMode || 'Unknown')}</strong></p>
      </div>
    `);
  }

  function loadAdapterModes(container) {
    const interfaceName = container.data('interface');
    $.ajax({
      url: '/wlan-modes',
      type: 'GET',
      data: { selectedInterface: interfaceName },
      success: function (response) {
        renderAdapterModes(container, response.supported_modes, response.current_mode);
      },
      error: function (xhr) {
        const message = xhr.responseJSON?.message || 'Unable to load adapter modes';
        container.html(`<div class="adapter-mode-error text-danger small mb-2">${escapeHtml(message)}</div>`);
      }
    });
  }


  function bandClass(band) {
    if (band === '2.4 GHz') return 'wireless-band-24';
    if (band === '5 GHz') return 'wireless-band-5';
    if (band === '6 GHz') return 'wireless-band-6';
    return 'wireless-band-unknown';
  }

  function renderWirelessCharts(networks) {
    const channelCounts = {};
    const bandCounts = {};
    networks.forEach(function (network) {
      const channel = network.channel || network.freq || 'Unknown';
      const band = network.band || 'Unknown band';
      const apCount = Number(network.access_points || 1);
      channelCounts[channel] = (channelCounts[channel] || 0) + apCount;
      bandCounts[band] = (bandCounts[band] || 0) + apCount;
    });

    const maxChannel = Math.max(1, ...Object.values(channelCounts));
    const channelRows = Object.keys(channelCounts).sort(function (left, right) {
      const leftNumber = Number(left);
      const rightNumber = Number(right);
      if (Number.isNaN(leftNumber) || Number.isNaN(rightNumber)) return String(left).localeCompare(String(right));
      return leftNumber - rightNumber;
    }).map(function (channel) {
      const count = channelCounts[channel];
      const width = Math.max(8, Math.round((count / maxChannel) * 100));
      return `<div class="wireless-chart-row"><span>Ch ${escapeHtml(channel)}</span><div class="wireless-chart-track"><div class="wireless-chart-bar" style="width: ${width}%"></div></div><strong>${count}</strong></div>`;
    }).join('');

    const maxBand = Math.max(1, ...Object.values(bandCounts));
    const bandRows = Object.keys(bandCounts).sort().map(function (band) {
      const count = bandCounts[band];
      const width = Math.max(8, Math.round((count / maxBand) * 100));
      return `<div class="wireless-band-row ${bandClass(band)}"><span>${escapeHtml(band)}</span><div class="wireless-chart-track"><div class="wireless-chart-bar" style="width: ${width}%"></div></div><strong>${count}</strong></div>`;
    }).join('');

    return `
      <section class="wireless-results card shadow-sm wireless-chart-panel">
        <div class="card-body">
          <div class="wireless-results-header">
            <div>
              <p class="interface-kicker mb-1">Channel & Band Charts</p>
              <h2 class="interface-section-title mb-0">Wireless occupancy</h2>
            </div>
            <span class="badge badge-info">${networks.length} SSID${networks.length === 1 ? '' : 's'}</span>
          </div>
          <div class="wireless-chart-grid">
            <article>
              <h3>Channels</h3>
              ${channelRows || '<p class="text-muted">No channel data.</p>'}
            </article>
            <article>
              <h3>Bands</h3>
              ${bandRows || '<p class="text-muted">No band data.</p>'}
            </article>
          </div>
        </div>
      </section>
    `;
  }

  function renderNetworks(interfaceName, networks) {
    const count = networks.length;
    const rows = networks.map(function (network) {
      const ssid = network.ssid || '<Hidden SSID>';
      const security = network.security || 'Unknown';
      const bssid = network.bssid || 'Unknown BSSID';
      const channel = network.channel || network.freq || 'Unknown';
      const band = network.band || 'Unknown band';
      const bssidManufacturer = network.bssid_manufacturer || 'Unknown manufacturer';
      const signal = network.signal;
      const signalText = signalLabel(signal);
      const apCount = network.access_points || 1;
      const isOpen = security === 'Open';
      const detailUrl = `/wireless/network?interface=${encodeURIComponent(interfaceName)}&ssid=${encodeURIComponent(ssid)}&bssid=${encodeURIComponent(bssid)}`;
      const deauthId = `deauth-${interfaceName}-${bssid}`.replace(/[^A-Za-z0-9_-]/g, '-');
      const canDeauth = /^([0-9a-f]{2}:){5}[0-9a-f]{2}$/i.test(bssid);
      const deauthDisabled = canDeauth ? '' : 'disabled';
      const deauthHelp = canDeauth ? 'Authorized isolated lab only · 1 broadcast frame' : 'Deauth requires a discovered AP BSSID';

      return `
        <article class="wireless-network-card wireless-network-clickable" data-detail-url="${escapeHtml(detailUrl)}" role="link" tabindex="0" aria-label="View details for ${escapeHtml(ssid)}">
          <div class="wireless-network-main">
            <div class="wireless-network-identity">
              <h3 class="wireless-network-ssid mb-1">${escapeHtml(ssid)}</h3>
              <div class="wireless-network-meta">
                <span title="BSSID"><i class="fa-solid fa-fingerprint"></i> ${escapeHtml(bssid)}</span>
                <span title="Manufacturer"><i class="fa-solid fa-industry"></i> ${escapeHtml(bssidManufacturer)}</span>
                <span title="Channel"><i class="fa-solid fa-wave-square"></i> Ch ${escapeHtml(channel)}</span>
                <span title="Band"><i class="fa-solid fa-tower-broadcast"></i> ${escapeHtml(band)}</span>
              </div>
            </div>
            <div class="wireless-network-badges">
              <span class="badge ${isOpen ? 'badge-success' : 'badge-secondary'}">${escapeHtml(security)}</span>
              <span class="badge badge-light border">${escapeHtml(apCount)} ${apCount === 1 ? 'AP' : 'APs'}</span>
              <span class="badge badge-info" title="Open the full network detail page for APs, clients, gateway, and radio information"><i class="fa-solid fa-up-right-from-square"></i> Details</span>
            </div>
          </div>
          <div class="wireless-network-bottom">
            <div class="wireless-network-stats" aria-label="Signal strength">
              <span class="${signalClass(signal)}"><i class="fa-solid fa-signal"></i> ${escapeHtml(signalText)}</span>
            </div>
            <div class="wireless-network-actions">
              <form class="wireless-connect-form" data-interface="${escapeHtml(interfaceName)}" data-ssid="${escapeHtml(ssid)}">
                <div class="input-group input-group-sm">
                  <input type="password" class="form-control" name="password" placeholder="${isOpen ? 'Open network: no password needed' : 'Password'}" aria-label="Password for ${escapeHtml(ssid)}">
                  <div class="input-group-append">
                    <button class="btn btn-outline-primary" type="submit" title="Connect this host adapter to the selected SSID using the supplied password">Connect</button>
                  </div>
                </div>
              </form>
              <form class="wireless-deauth-form" data-interface="${escapeHtml(interfaceName)}" data-ap="${escapeHtml(bssid)}">
                <div class="custom-control custom-switch wireless-deauth-switch" title="Send one authorized, rate-limited lab deauth frame to broadcast clients on this AP">
                  <input type="checkbox" class="custom-control-input wireless-deauth-toggle" id="${escapeHtml(deauthId)}" aria-label="Run limited deauth lab burst for ${escapeHtml(ssid)}" ${deauthDisabled}>
                  <label class="custom-control-label" for="${escapeHtml(deauthId)}">Limited deauth</label>
                </div>
                <p class="wireless-deauth-help text-muted mb-0">${escapeHtml(deauthHelp)}</p>
              </form>
            </div>
          </div>
        </article>
      `;
    }).join('');

    return `
      ${renderWirelessCharts(networks)}
      <section class="wireless-results card shadow-sm">
        <div class="card-body">
          <div class="wireless-results-header">
            <div>
              <p class="interface-kicker mb-1">Wireless Scan</p>
              <h2 class="interface-section-title mb-0">Detected Networks</h2>
            </div>
            <span class="badge badge-primary">${count} found</span>
          </div>
          <div class="wireless-network-grid">${rows}</div>
        </div>
      </section>
    `;
  }


  function pollScanJob(jobId, onComplete, onError) {
    window.setTimeout(function checkJob() {
      $.ajax({
        url: `/scan-jobs/${encodeURIComponent(jobId)}`,
        type: 'GET',
        success: function (response) {
          const job = response.job || {};
          if (job.status === 'completed') {
            onComplete(job.result || {});
          } else if (job.status === 'failed') {
            onError(job.error || 'Scan job failed');
          } else {
            window.setTimeout(checkJob, 1000);
          }
        },
        error: function (xhr) {
          onError(xhr.responseJSON?.message || 'Unable to check scan job');
        }
      });
    }, 1000);
  }

  function openNetworkDetails(card) {
    const detailUrl = card.data('detailUrl');
    if (detailUrl) {
      window.location.href = detailUrl;
    }
  }

  $(document).on('click', '.wireless-network-clickable', function (event) {
    if ($(event.target).closest('a, button, input, label, select, textarea, form').length) {
      return;
    }
    openNetworkDetails($(this));
  });

  $(document).on('keydown', '.wireless-network-clickable', function (event) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      openNetworkDetails($(this));
    }
  });


  $(document).on('click', 'button#wlan-scan', function () {
    const button = $(this);
    const interfaceName = button.val();
    const resultDiv = scanResultContainer(interfaceName);

    button.prop('disabled', true).text('Scanning...');
    resultDiv.html(`
      <div class="wireless-scan-state card shadow-sm">
        <div class="card-body d-flex align-items-center">
          <div class="spinner-border text-primary mr-3" role="status" aria-hidden="true"></div>
          <div>
            <strong>Scanning ${escapeHtml(interfaceName)}</strong>
            <p class="text-muted mb-0">Running this scan in the background.</p>
          </div>
        </div>
      </div>
    `);

    $.ajax({
      url: '/scan-jobs',
      type: 'POST',
      data: { scanType: 'wlan', selectedInterface: interfaceName },
      success: function (response) {
        pollScanJob(response.job.id, function (result) {
          const networks = Array.isArray(result.wlans) ? result.wlans : [];
          button.prop('disabled', false).text('Scan for Networks');
          if (networks.length === 0) {
            resultDiv.html(`<div class="alert alert-info mt-3" role="alert">No wireless networks were found on ${escapeHtml(interfaceName)}. Try moving closer to an access point, scanning again, or checking <a href="/capabilities">capabilities</a>.</div>`);
            return;
          }
          saveCachedNetworks(interfaceName, networks);
          resultDiv.html(renderNetworks(interfaceName, networks));
        }, function (message) {
          button.prop('disabled', false).text('Scan for Networks');
          resultDiv.html(`<div class="alert alert-danger mt-3" role="alert">${escapeHtml(message)} <a href="/capabilities" class="alert-link">Check capabilities</a>.</div>`);
        });
      },
      error: function (xhr) {
        button.prop('disabled', false).text('Scan for Networks');
        const message = xhr.responseJSON?.message || 'Unable to start wireless scan';
        resultDiv.html(`<div class="alert alert-danger mt-3" role="alert">${escapeHtml(message)} <a href="/capabilities" class="alert-link">Check capabilities</a>.</div>`);
      }
    });
  });

  $(document).on('submit', '.wireless-connect-form', function (event) {
    event.preventDefault();
    const form = $(this);
    const submitButton = form.find('button[type="submit"]');

    $.ajax({
      url: '/wlan-connect',
      type: 'POST',
      data: {
        selectedInterface: form.data('interface'),
        ssid: form.data('ssid'),
        password: form.find('input[name="password"]').val()
      },
      beforeSend: function () {
        submitButton.prop('disabled', true).text('Connecting...');
      },
      success: function (response) {
        form.replaceWith(`<div class="alert alert-success mt-3 mb-0" role="alert">${escapeHtml(response.message || 'Connected successfully')}</div>`);
      },
      error: function (xhr) {
        const message = xhr.responseJSON?.message || 'Failed to connect';
        form.find('.wireless-connect-error').remove();
        form.append(`<div class="wireless-connect-error text-danger small mt-2">${escapeHtml(message)}</div>`);
      },
      complete: function () {
        submitButton.prop('disabled', false).text('Connect');
      }
    });
  });


  $(document).on('change', '.wireless-deauth-toggle', function () {
    const toggle = $(this);
    const form = toggle.closest('.wireless-deauth-form');
    const label = form.find('.custom-control-label');
    const originalLabel = label.data('originalText') || label.text();

    label.data('originalText', originalLabel);
    form.find('.wireless-deauth-status').remove();

    if (!toggle.prop('checked')) {
      return;
    }

    toggle.prop('disabled', true);
    label.text('Sending...');

    $.ajax({
      url: '/deauth',
      type: 'POST',
      data: {
        selectedInterface: form.data('interface'),
        ap: form.data('ap'),
        target: 'ff:ff:ff:ff:ff:ff',
        frames: 1,
        authorized: 'on'
      },
      success: function (response) {
        form.append(`<div class="wireless-deauth-status text-success small mt-1">${escapeHtml(response.message || 'Limited deauth burst sent')}</div>`);
      },
      error: function (xhr) {
        const message = xhr.responseJSON?.message || 'Failed to run limited deauth burst';
        form.append(`<div class="wireless-deauth-status text-danger small mt-1">${escapeHtml(message)}</div>`);
      },
      complete: function () {
        toggle.prop('checked', false).prop('disabled', false);
        label.text(originalLabel);
      }
    });
  });

  restoreCachedScanResults();

  $('.adapter-mode-switches').each(function () {
    loadAdapterModes($(this));
  });

  $(document).on('change', '.adapter-mode-input', function () {
    const input = $(this);
    const container = input.closest('.adapter-mode-switches');
    const interfaceName = container.data('interface');
    const requestedMode = input.val();
    const previousMode = container.data('currentMode');

    container.find('.adapter-mode-input').prop('disabled', true);
    container.find('.adapter-mode-status').remove();
    container.find('.adapter-mode-panel').append('<p class="adapter-mode-status text-muted mb-0">Updating mode...</p>');

    $.ajax({
      url: '/wlan-mode',
      type: 'POST',
      data: { selectedInterface: interfaceName, mode: requestedMode },
      success: function (response) {
        renderAdapterModes(container, response.supported_modes, response.current_mode);
      },
      error: function (xhr) {
        const message = xhr.responseJSON?.message || 'Unable to update adapter mode';
        if (previousMode) {
          container.find(`.adapter-mode-input[value="${previousMode}"]`).prop('checked', true);
        }
        container.find('.adapter-mode-status').remove();
        container.find('.adapter-mode-panel').append(`<p class="adapter-mode-status text-danger mb-0">${escapeHtml(message)}</p>`);
      },
      complete: function () {
        container.find('.adapter-mode-input').prop('disabled', false);
      }
    });
  });

});
