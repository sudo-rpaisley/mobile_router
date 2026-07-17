$(document).ready(function () {
  const activeScanJobs = new Map();

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


  function allAccessPoints(networks) {
    const points = [];
    networks.forEach(function (network) {
      const details = Array.isArray(network.access_point_details) && network.access_point_details.length ? network.access_point_details : [network];
      details.forEach(function (ap) {
        points.push({
          ssid: ap.ssid || network.ssid || '<Hidden SSID>',
          bssid: ap.bssid || network.bssid || 'Unknown BSSID',
          security: ap.security || network.security || 'Unknown',
          channel: ap.channel || network.channel || network.freq || 'Unknown',
          band: ap.band || network.band || 'Unknown band',
          signal: ap.signal ?? network.signal,
          channel_width: Number(ap.channel_width || network.channel_width || 20),
          manufacturer: ap.bssid_manufacturer || network.bssid_manufacturer || 'Unknown manufacturer',
          hidden: !(ap.ssid || network.ssid) || (ap.ssid || network.ssid) === '<Hidden SSID>'
        });
      });
    });
    return points;
  }

  function congestionScore(points) {
    if (!points.length) return 0;
    const apLoad = points.length * 18;
    const widthLoad = points.reduce(function (sum, ap) { return sum + Math.max(20, Number(ap.channel_width || 20)); }, 0) / 8;
    const signalLoad = points.reduce(function (sum, ap) {
      const signal = Number(ap.signal);
      if (Number.isNaN(signal)) return sum + 8;
      return sum + (signal >= 0 ? signal / 8 : Math.max(0, 95 + signal) / 3);
    }, 0);
    return Math.min(100, Math.round(apLoad + widthLoad + signalLoad));
  }

  function occupancyByChannel(networks) {
    const channels = {};
    allAccessPoints(networks).forEach(function (ap) {
      const key = ap.channel || 'Unknown';
      channels[key] = channels[key] || { channel: key, band: ap.band, aps: [] };
      channels[key].aps.push(ap);
    });
    Object.values(channels).forEach(function (item) {
      item.score = congestionScore(item.aps);
      item.widths = Array.from(new Set(item.aps.map(function (ap) { return ap.channel_width || 20; }))).sort(function (a, b) { return a - b; });
    });
    return channels;
  }

  function bestChannelSuggestions(networks) {
    const grouped = occupancyByChannel(networks);
    const byBand = {};
    Object.values(grouped).forEach(function (item) {
      const band = item.band || 'Unknown band';
      byBand[band] = byBand[band] || [];
      byBand[band].push(item);
    });
    return Object.keys(byBand).sort().map(function (band) {
      const best = byBand[band].sort(function (left, right) { return left.score - right.score; })[0];
      return `${band}: try channel ${best.channel} (${best.score}/100 congestion)`;
    });
  }

  function heatmapKey(interfaceName) {
    return `mobile-router:wlan-occupancy:${interfaceName}`;
  }

  function saveOccupancyHistory(interfaceName, networks) {
    try {
      const history = JSON.parse(window.sessionStorage.getItem(heatmapKey(interfaceName)) || '[]');
      history.push({ scannedAt: new Date().toISOString(), channels: occupancyByChannel(networks) });
      window.sessionStorage.setItem(heatmapKey(interfaceName), JSON.stringify(history.slice(-12)));
    } catch (error) {
      // Ignore storage failures.
    }
  }

  function loadOccupancyHistory(interfaceName) {
    try {
      const history = JSON.parse(window.sessionStorage.getItem(heatmapKey(interfaceName)) || '[]');
      return Array.isArray(history) ? history : [];
    } catch (error) {
      return [];
    }
  }

  function filteredNetworks(container, networks) {
    const query = String(container.find('[data-wifi-filter="query"]').val() || '').toLowerCase();
    const band = container.find('[data-wifi-filter="band"]').val() || '';
    const security = container.find('[data-wifi-filter="security"]').val() || '';
    const minSignal = Number(container.find('[data-wifi-filter="signal"]').val() || '-999');
    const channelFilter = String(container.data('channelFilter') || '');
    return networks.filter(function (network) {
      const aps = allAccessPoints([network]);
      const text = `${network.ssid || ''} ${network.bssid || ''} ${aps.map(function (ap) { return ap.bssid; }).join(' ')}`.toLowerCase();
      const signal = Number(network.signal ?? -999);
      return (!query || text.includes(query))
        && (!band || network.band === band || aps.some(function (ap) { return ap.band === band; }))
        && (!channelFilter || String(network.channel || network.freq || '') === channelFilter || aps.some(function (ap) { return String(ap.channel || '') === channelFilter; }))
        && (!security || network.security === security)
        && (Number.isNaN(minSignal) || signal >= minSignal);
    });
  }

  function renderWirelessCharts(interfaceName, networks) {
    const channels = occupancyByChannel(networks);
    const channelItems = Object.values(channels).sort(function (left, right) {
      const leftNumber = Number(left.channel);
      const rightNumber = Number(right.channel);
      if (Number.isNaN(leftNumber) || Number.isNaN(rightNumber)) return String(left.channel).localeCompare(String(right.channel));
      return leftNumber - rightNumber;
    });
    const bandCounts = {};
    allAccessPoints(networks).forEach(function (ap) { bandCounts[ap.band] = (bandCounts[ap.band] || 0) + 1; });
    const maxScore = Math.max(1, ...channelItems.map(function (item) { return item.score; }));
    const channelRows = channelItems.map(function (item) {
      const width = Math.max(8, Math.round((item.score / maxScore) * 100));
      const tooltip = item.aps.map(function (ap) {
        return `${ap.ssid} / ${ap.bssid} / ${ap.security} / ${signalLabel(ap.signal)} / ${ap.channel_width || 20} MHz`;
      }).join('\n');
      return `<div class="wireless-chart-row wireless-channel-filter" data-channel="${escapeHtml(item.channel)}" title="${escapeHtml(tooltip)}"><span>Ch ${escapeHtml(item.channel)}</span><div class="wireless-chart-track"><div class="wireless-chart-bar" style="width: ${width}%"></div></div><strong>${item.score}/100</strong><small>${escapeHtml(item.widths.join('/'))} MHz</small></div>`;
    }).join('');

    const maxBand = Math.max(1, ...Object.values(bandCounts));
    const bandRows = Object.keys(bandCounts).sort().map(function (band) {
      const count = bandCounts[band];
      const width = Math.max(8, Math.round((count / maxBand) * 100));
      return `<div class="wireless-band-row ${bandClass(band)} wireless-band-filter" data-band="${escapeHtml(band)}"><span>${escapeHtml(band)}</span><div class="wireless-chart-track"><div class="wireless-chart-bar" style="width: ${width}%"></div></div><strong>${count}</strong></div>`;
    }).join('');

    const suggestions = bestChannelSuggestions(networks).map(function (item) { return `<li>${escapeHtml(item)}</li>`; }).join('');
    const history = loadOccupancyHistory(interfaceName);
    const heatmap = history.map(function (scan, index) {
      const ageMinutes = (Date.now() - new Date(scan.scannedAt).getTime()) / 60000;
      const cells = Object.values(scan.channels || {}).map(function (channel) {
        return `<span class="wireless-heatmap-cell" style="opacity:${Math.max(0.2, (channel.score || 0) / 100)}" title="${escapeHtml(scan.scannedAt)} · Ch ${escapeHtml(channel.channel)} · ${Number(channel.score || 0)}/100">${escapeHtml(channel.channel)}</span>`;
      }).join('');
      return `<div class="wireless-heatmap-row" data-heatmap-index="${index}" data-heatmap-age="${ageMinutes}"><small>${escapeHtml(new Date(scan.scannedAt).toLocaleTimeString())}</small>${cells}</div>`;
    }).join('');

    const apNodes = allAccessPoints(networks).map(function (ap) {
      return `<div class="wireless-map-node" data-map-band="${escapeHtml(ap.band)}" title="${escapeHtml(`${ap.ssid}\n${ap.bssid}\n${ap.security}\nCh ${ap.channel} ${ap.band}\n${ap.channel_width || 20} MHz\n${signalLabel(ap.signal)}`)}"><strong>${escapeHtml(ap.ssid || '<Hidden SSID>')}</strong><span>${escapeHtml(ap.bssid)}</span><span>Ch ${escapeHtml(ap.channel)} · ${escapeHtml(ap.band)} · ${escapeHtml(ap.channel_width || 20)} MHz</span><span>${escapeHtml(ap.security)} · ${escapeHtml(signalLabel(ap.signal))}</span></div>`;
    }).join('');

    return `
      <section class="wireless-results card shadow-sm wireless-chart-panel" data-wireless-map="${escapeHtml(interfaceName)}" role="button" tabindex="0" aria-expanded="false">
        <div class="card-body">
          <div class="wireless-results-header">
            <div>
              <p class="interface-kicker mb-1">Channel & Band Charts</p>
              <h2 class="interface-section-title mb-0">Wireless occupancy</h2>
            </div>
            <div class="btn-group btn-group-sm" role="group" aria-label="Wireless occupancy exports">
              <button class="btn btn-outline-secondary wireless-map-close" type="button">Close</button>
              <button class="btn btn-outline-secondary wireless-export" data-format="json" type="button">JSON</button>
              <button class="btn btn-outline-secondary wireless-export" data-format="csv" type="button">CSV</button>
              <button class="btn btn-outline-secondary wireless-export" data-format="png" type="button">PNG</button>
            </div>
          </div>
          <div class="wireless-chart-grid">
            <article>
              <h3>Channels / congestion</h3>
              ${channelRows || '<p class="text-muted">No channel data.</p>'}
            </article>
            <article>
              <h3>Bands</h3>
              ${bandRows || '<p class="text-muted">No band data.</p>'}
              <h3 class="mt-3">Best channel suggestions</h3>
              <ul class="wireless-suggestion-list">${suggestions || '<li>No suggestions yet.</li>'}</ul>
            </article>
          </div>
          <div class="wireless-chart-expanded" aria-label="Interactive wireless map">
            <h3>Full-screen interactive wireless map</h3>
            <p class="text-muted small">Click this panel to expand. Tooltips include SSID, BSSID, security, signal, channel, and channel width. Channel bars include overlap from 20/40/80/160 MHz widths when provided by the scan source.</p>
            <div class="wireless-map-tabs btn-group btn-group-sm mb-3" role="group" aria-label="Wireless map band filter"><button class="btn btn-outline-info active" data-map-band-tab="" type="button">All</button><button class="btn btn-outline-info" data-map-band-tab="2.4 GHz" type="button">2.4 GHz</button><button class="btn btn-outline-info" data-map-band-tab="5 GHz" type="button">5 GHz</button><button class="btn btn-outline-info" data-map-band-tab="6 GHz" type="button">6 GHz</button></div>
            <div class="wireless-map-grid">${apNodes || '<p class="text-muted">No networks to map.</p>'}</div>
            <h3 class="mt-3">Wireless occupancy heatmap</h3>
            <select class="form-control form-control-sm wireless-heatmap-range mb-2"><option value="5">Last 5 scans</option><option value="30">Last 30 minutes</option><option value="60">Last hour</option></select>
            <div class="wireless-heatmap">${heatmap || '<p class="text-muted">Run repeated scans to build a time-based heatmap.</p>'}</div>
          </div>
        </div>
      </section>
    `;
  }

  function renderNetworks(interfaceName, networks, diagnostics = {}) {
    saveOccupancyHistory(interfaceName, networks);
    const generatedAt = new Date().toISOString();
    const attempts = Array.isArray(diagnostics.attempts) ? diagnostics.attempts : [];
    const fallbackText = Array.isArray(diagnostics.fallbacks) && diagnostics.fallbacks.length ? diagnostics.fallbacks.join(' ') : 'No fallback scan was needed.';
    const warningText = Array.isArray(diagnostics.warnings) ? diagnostics.warnings.join(' ') : '';
    const rawOutputs = diagnostics.raw_outputs || {};
    const rawApCount = allAccessPoints(networks).length;
    const hiddenCount = networks.filter(function (network) { return !network.ssid || network.ssid === '<Hidden SSID>'; }).length;
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
      const channelWidth = network.channel_width || 20;
      const isOpen = security === 'Open';
      const hasWps = network.wps === true;
      const detailUrl = `/wireless/network?interface=${encodeURIComponent(interfaceName)}&ssid=${encodeURIComponent(ssid)}&bssid=${encodeURIComponent(bssid)}`;
      const deauthId = `deauth-${interfaceName}-${bssid}`.replace(/[^A-Za-z0-9_-]/g, '-');
      const canDeauth = /^([0-9a-f]{2}:){5}[0-9a-f]{2}$/i.test(bssid);
      const deauthDisabled = canDeauth ? '' : 'disabled';
      const deauthHelp = canDeauth ? 'Authorized isolated lab only · 1 broadcast frame' : 'Deauth requires a discovered AP BSSID';

      return `
        <article class="wireless-network-card wireless-network-clickable" data-detail-url="${escapeHtml(detailUrl)}" role="link" tabindex="0" aria-label="View details for ${escapeHtml(ssid)}" title="SSID: ${escapeHtml(ssid)}\nBSSID: ${escapeHtml(bssid)}\nSecurity: ${escapeHtml(security)}\nSignal: ${escapeHtml(signalText)}\nChannel: ${escapeHtml(channel)}\nWidth: ${escapeHtml(channelWidth)} MHz">
          <div class="wireless-network-main">
            <div class="wireless-network-identity">
              <h3 class="wireless-network-ssid mb-1">${escapeHtml(ssid)}</h3>
              <div class="wireless-network-meta">
                <span title="BSSID"><i class="fa-solid fa-fingerprint"></i> ${escapeHtml(bssid)}</span>
                <span title="Manufacturer"><i class="fa-solid fa-industry"></i> ${escapeHtml(bssidManufacturer)}</span>
                <span title="Channel"><i class="fa-solid fa-wave-square"></i> Ch ${escapeHtml(channel)}</span>
                <span title="Band"><i class="fa-solid fa-tower-broadcast"></i> ${escapeHtml(band)}</span>
                <span title="Channel width"><i class="fa-solid fa-arrows-left-right"></i> ${escapeHtml(channelWidth)} MHz</span>
              </div>
            </div>
            <div class="wireless-network-badges">
              <span class="badge ${isOpen ? 'badge-success' : 'badge-secondary'}">${escapeHtml(security)}</span>
              ${hasWps ? '<span class="badge badge-warning" title="WPS advertised: review lab router settings and disable WPS where possible">WPS exposed</span>' : ''}
              <span class="badge badge-light border">${escapeHtml(apCount)} ${apCount === 1 ? 'AP' : 'APs'}</span>
              <span class="badge badge-info" title="Open the full network detail page for APs, clients, gateway, and radio information"><i class="fa-solid fa-up-right-from-square"></i> Details</span>
            </div>
          </div>
          <div class="wireless-network-bottom">
            <div class="wireless-network-stats" aria-label="Signal strength">
              <span class="${signalClass(signal)}"><i class="fa-solid fa-signal"></i> ${escapeHtml(signalText)}</span>
            </div>
            ${hasWps && network.wps_note ? `<p class="wireless-network-notes text-warning mb-2"><i class="fa-solid fa-triangle-exclamation"></i> ${escapeHtml(network.wps_note)}</p>` : ''}
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
      ${renderWirelessCharts(interfaceName, networks)}
      <section class="wireless-results card shadow-sm" data-wireless-results="${escapeHtml(interfaceName)}" data-networks="${escapeHtml(JSON.stringify(networks))}" data-diagnostics="${escapeHtml(JSON.stringify(diagnostics))}">
        <div class="card-body">
          <div class="wireless-results-header">
            <div>
              <p class="interface-kicker mb-1">Wireless Scan</p>
              <h2 class="interface-section-title mb-0">Detected Networks</h2>
              <p class="text-muted small mb-0">Fresh at ${escapeHtml(new Date(generatedAt).toLocaleString())} · raw APs ${rawApCount} · grouped SSIDs ${count} · rendered ${count} · hidden ${hiddenCount}</p>
            </div>
            <span class="badge badge-primary">${count} found</span>
          </div>
          <div class="wireless-filter-bar">
            <input class="form-control form-control-sm" data-wifi-filter="query" placeholder="Filter SSID/BSSID">
            <select class="form-control form-control-sm" data-wifi-filter="band"><option value="">All bands</option><option>2.4 GHz</option><option>5 GHz</option><option>6 GHz</option><option>Unknown band</option></select>
            <select class="form-control form-control-sm" data-wifi-filter="security"><option value="">All security</option>${Array.from(new Set(networks.map(function (network) { return network.security || 'Unknown'; }))).sort().map(function (securityOption) { return `<option>${escapeHtml(securityOption)}</option>`; }).join('')}</select>
            <input class="form-control form-control-sm" type="number" data-wifi-filter="signal" placeholder="Min signal">
            <button class="btn btn-outline-secondary btn-sm wireless-show-bssids" type="button">Show all BSSIDs</button>
            <button class="btn btn-outline-primary btn-sm wireless-rescan-all" type="button">Rescan all adapters</button>
          </div>
          ${warningText ? `<div class="alert alert-warning small" role="alert">${escapeHtml(warningText)}</div>` : ''}
          <div class="wireless-source-stats">Scan source stats: backend tools ${escapeHtml(attempts.map(function (attempt) { return `${attempt.tool} (${attempt.scope})`; }).join(', ') || 'unknown')}; freshness ${escapeHtml(diagnostics.freshness || 'unknown')}; fallback ${escapeHtml(fallbackText)} Raw entries ${rawApCount}, parsed entries ${rawApCount}, rendered entries ${count}, grouped SSIDs ${count}.</div>
          <details class="wireless-raw-output"><summary>Raw scan output</summary>${Object.keys(rawOutputs).map(function (tool) { return `<h4>${escapeHtml(tool)}</h4><pre>${escapeHtml(rawOutputs[tool])}</pre>`; }).join('') || '<p class="text-muted">No raw output captured.</p>'}</details>
          <div class="wireless-network-grid">${rows}</div>
        </div>
      </section>
    `;
  }



  function downloadText(filename, mime, content) {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }

  function networksFromSection(section) {
    try {
      return JSON.parse(section.attr('data-networks') || '[]');
    } catch (error) {
      return [];
    }
  }

  function renderBssidRows(interfaceName, networks) {
    return allAccessPoints(networks).map(function (ap) {
      const detailUrl = `/wireless/network?interface=${encodeURIComponent(interfaceName)}&ssid=${encodeURIComponent(ap.ssid)}&bssid=${encodeURIComponent(ap.bssid)}`;
      return `<article class="wireless-network-card wireless-network-clickable" data-detail-url="${escapeHtml(detailUrl)}" role="link" tabindex="0" title="SSID: ${escapeHtml(ap.ssid)}\nBSSID: ${escapeHtml(ap.bssid)}\nSecurity: ${escapeHtml(ap.security)}\nSignal: ${escapeHtml(signalLabel(ap.signal))}\nChannel: ${escapeHtml(ap.channel)}\nWidth: ${escapeHtml(ap.channel_width)} MHz"><div class="wireless-network-main"><div class="wireless-network-identity"><h3 class="wireless-network-ssid mb-1">${escapeHtml(ap.ssid || '<Hidden SSID>')}</h3><div class="wireless-network-meta"><span><i class="fa-solid fa-fingerprint"></i> ${escapeHtml(ap.bssid)}</span><span><i class="fa-solid fa-industry"></i> ${escapeHtml(ap.manufacturer)}</span><span><i class="fa-solid fa-wave-square"></i> Ch ${escapeHtml(ap.channel)}</span><span><i class="fa-solid fa-tower-broadcast"></i> ${escapeHtml(ap.band)}</span><span><i class="fa-solid fa-arrows-left-right"></i> ${escapeHtml(ap.channel_width)} MHz</span></div></div><div class="wireless-network-badges"><span class="badge badge-secondary">${escapeHtml(ap.security)}</span><span class="badge badge-info">BSSID</span></div></div><div class="wireless-network-bottom"><div class="wireless-network-stats"><span class="${signalClass(ap.signal)}"><i class="fa-solid fa-signal"></i> ${escapeHtml(signalLabel(ap.signal))}</span></div></div></article>`;
    }).join('');
  }

  function pollScanJob(jobId, onComplete, onError, retryCount = 0) {
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
          if (retryCount < 3) {
            pollScanJob(jobId, onComplete, onError, retryCount + 1);
            return;
          }
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

  function applyHeatmapRange(panel) {
    const range = panel.find('.wireless-heatmap-range').val() || '5';
    const rows = panel.find('.wireless-heatmap-row');
    rows.show();
    if (range === '5') {
      rows.each(function (index) { $(this).toggle(index >= Math.max(0, rows.length - 5)); });
    } else {
      const minutes = Number(range);
      rows.each(function () { $(this).toggle(Number($(this).data('heatmapAge')) <= minutes); });
    }
  }

  function closeWirelessMap() {
    $('.wireless-chart-panel.is-fullscreen-map').removeClass('is-expanded is-fullscreen-map').attr('aria-expanded', 'false');
  }

  $(document).on('click', '.wireless-channel-filter', function (event) {
    event.stopPropagation();
    const channel = String($(this).data('channel') || '');
    const panel = $(this).closest('.wireless-chart-panel');
    const interfaceName = panel.data('wirelessMap');
    const section = $(`[data-wireless-results="${interfaceName}"]`).first();
    section.data('channelFilter', channel);
    section.find('[data-wifi-filter="query"]').trigger('input');
    section.find('.wireless-source-stats').prepend(`<div class="badge badge-info mr-2">Filtered channel ${escapeHtml(channel)}</div>`);
  });

  $(document).on('click', '.wireless-band-filter', function (event) {
    event.stopPropagation();
    const band = String($(this).data('band') || '');
    const panel = $(this).closest('.wireless-chart-panel');
    const interfaceName = panel.data('wirelessMap');
    const section = $(`[data-wireless-results="${interfaceName}"]`).first();
    section.find('[data-wifi-filter="band"]').val(band).trigger('change');
  });

  $(document).on('click', '.wireless-map-close', function (event) {
    event.stopPropagation();
    closeWirelessMap();
  });

  $(document).on('keydown', function (event) {
    if (event.key === 'Escape') closeWirelessMap();
  });

  $(document).on('change', '.wireless-heatmap-range', function () {
    applyHeatmapRange($(this).closest('.wireless-chart-panel'));
  });

  $(document).on('click', '[data-map-band-tab]', function (event) {
    event.stopPropagation();
    const button = $(this);
    const band = String(button.data('mapBandTab') || '');
    const panel = button.closest('.wireless-chart-panel');
    panel.find('[data-map-band-tab]').removeClass('active');
    button.addClass('active');
    panel.find('.wireless-map-node').each(function () {
      $(this).toggle(!band || String($(this).data('mapBand')) === band);
    });
  });


  $(document).on('click', '.wireless-export', function (event) {
    event.stopPropagation();
    const button = $(this);
    const panel = button.closest('.wireless-chart-panel');
    const interfaceName = panel.data('wirelessMap');
    const resultSection = $(`[data-wireless-results="${interfaceName}"]`).first();
    const networks = networksFromSection(resultSection);
    const report = { interface: interfaceName, exportedAt: new Date().toISOString(), occupancy: occupancyByChannel(networks), networks: networks };
    const format = button.data('format');
    if (format === 'json') {
      downloadText(`wireless-occupancy-${interfaceName}.json`, 'application/json', JSON.stringify(report, null, 2));
    } else if (format === 'csv') {
      const rows = ['ssid,bssid,security,band,channel,width,signal,congestion'];
      allAccessPoints(networks).forEach(function (ap) {
        const channel = occupancyByChannel(networks)[ap.channel] || { score: 0 };
        rows.push([ap.ssid, ap.bssid, ap.security, ap.band, ap.channel, ap.channel_width, signalLabel(ap.signal), channel.score].map(function (value) { return `"${String(value).replace(/"/g, '""')}"`; }).join(','));
      });
      downloadText(`wireless-occupancy-${interfaceName}.csv`, 'text/csv', rows.join('\n'));
    } else if (format === 'png') {
      const canvas = document.createElement('canvas');
      canvas.width = 1200;
      canvas.height = 700;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#e2e8f0';
      ctx.font = '28px sans-serif';
      ctx.fillText(`Wireless Occupancy: ${interfaceName}`, 40, 60);
      Object.values(occupancyByChannel(networks)).forEach(function (item, index) {
        const y = 110 + index * 38;
        ctx.fillStyle = '#cbd5e1';
        ctx.font = '18px sans-serif';
        ctx.fillText(`Ch ${item.channel} · ${item.score}/100 · ${item.aps.length} AP`, 40, y);
        ctx.fillStyle = '#38bdf8';
        ctx.fillRect(330, y - 18, Math.max(8, item.score * 7), 22);
      });
      const link = document.createElement('a');
      link.href = canvas.toDataURL('image/png');
      link.download = `wireless-occupancy-${interfaceName}.png`;
      link.click();
    }
  });

  $(document).on('input change', '[data-wifi-filter]', function () {
    const section = $(this).closest('[data-wireless-results]');
    const interfaceName = section.data('wirelessResults');
    const networks = filteredNetworks(section, networksFromSection(section));
    const diagnostics = JSON.parse(section.attr('data-diagnostics') || '{}');
    section.find('.wireless-network-grid').html($(renderNetworks(interfaceName, networks, diagnostics)).filter('[data-wireless-results]').find('.wireless-network-grid').html());
  });

  $(document).on('click', '.wireless-show-bssids', function () {
    const section = $(this).closest('[data-wireless-results]');
    const interfaceName = section.data('wirelessResults');
    const networks = networksFromSection(section);
    section.find('.wireless-network-grid').html(renderBssidRows(interfaceName, networks));
    section.find('.wireless-source-stats').text(`Showing all BSSIDs: ${allAccessPoints(networks).length} raw AP entries from ${networks.length} grouped SSIDs.`);
  });

  $(document).on('click', '.wireless-rescan-all', function () {
    $('button#wlan-scan').each(function () { $(this).trigger('click'); });
  });


  $(document).on('click keydown', '.wireless-chart-panel', function (event) {
    if (event.type === 'keydown' && !['Enter', ' '].includes(event.key)) return;
    const panel = $(this);
    const expanded = !panel.hasClass('is-expanded');
    panel.toggleClass('is-expanded', expanded);
    panel.toggleClass('is-fullscreen-map', expanded);
    panel.attr('aria-expanded', expanded ? 'true' : 'false');
    if (expanded) applyHeatmapRange(panel);
  });

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
    const scanKey = `wlan:${interfaceName}`;
    if (activeScanJobs.has(scanKey)) {
      resultDiv.prepend(`<div class="alert alert-info mt-3" role="alert">A wireless scan is already running for ${escapeHtml(interfaceName)}.</div>`);
      return;
    }

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
        activeScanJobs.set(scanKey, response.job.id);
        pollScanJob(response.job.id, function (result) {
          activeScanJobs.delete(scanKey);
          const networks = Array.isArray(result.wlans) ? result.wlans : [];
          const diagnostics = result.scan_diagnostics || {};
          button.prop('disabled', false).text('Scan for Networks');
          if (networks.length === 0) {
            resultDiv.html(`<div class="alert alert-info mt-3" role="alert">No wireless networks were found on ${escapeHtml(interfaceName)}. Try moving closer to an access point, scanning again, or checking <a href="/capabilities">capabilities</a>.</div>`);
            return;
          }
          saveCachedNetworks(interfaceName, networks);
          resultDiv.html(renderNetworks(interfaceName, networks, diagnostics));
        }, function (message) {
          activeScanJobs.delete(scanKey);
          button.prop('disabled', false).text('Scan for Networks');
          resultDiv.html(`<div class="alert alert-danger mt-3" role="alert">${escapeHtml(message)} <a href="/capabilities" class="alert-link">Check capabilities</a>.</div>`);
        });
      },
      error: function (xhr) {
        activeScanJobs.delete(scanKey);
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
