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

  function renderNetworks(interfaceName, networks) {
    const count = networks.length;
    const rows = networks.map(function (network) {
      const ssid = network.ssid || '<Hidden SSID>';
      const security = network.security || 'Unknown';
      const bssid = network.bssid || 'Unknown BSSID';
      const channel = network.channel || network.freq || 'Unknown';
      const signal = network.signal;
      const apCount = network.access_points || 1;

      return `
        <div class="wireless-network-card">
          <div class="wireless-network-main">
            <div>
              <h3 class="wireless-network-ssid">${escapeHtml(ssid)}</h3>
              <p class="wireless-network-meta mb-0">${escapeHtml(bssid)} · Channel ${escapeHtml(channel)}</p>
            </div>
            <span class="badge ${security === 'Open' ? 'badge-success' : 'badge-secondary'}">${escapeHtml(security)}</span>
          </div>
          <div class="wireless-network-stats">
            <span class="${signalClass(signal)}"><i class="fa-solid fa-signal"></i> ${escapeHtml(signalLabel(signal))}</span>
            <span><i class="fa-solid fa-tower-broadcast"></i> ${escapeHtml(apCount)} ${apCount === 1 ? 'AP' : 'APs'}</span>
          </div>
          <form class="wireless-connect-form mt-3" data-interface="${escapeHtml(interfaceName)}" data-ssid="${escapeHtml(ssid)}">
            <div class="input-group input-group-sm">
              <input type="password" class="form-control" name="password" placeholder="Password (leave blank for open networks)" aria-label="Password for ${escapeHtml(ssid)}">
              <div class="input-group-append">
                <button class="btn btn-outline-primary" type="submit">Connect</button>
              </div>
            </div>
          </form>
        </div>
      `;
    }).join('');

    return `
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

  $(document).on('click', 'button#wlan-scan', function () {
    const button = $(this);
    const interfaceName = button.val();
    const resultDiv = $(`#wlans-${interfaceName}`);

    $.ajax({
      url: '/wlan-scan',
      type: 'POST',
      data: { selectedInterface: interfaceName },
      beforeSend: function () {
        button.prop('disabled', true).text('Scanning...');
        resultDiv.html(`
          <div class="wireless-scan-state card shadow-sm">
            <div class="card-body d-flex align-items-center">
              <div class="spinner-border text-primary mr-3" role="status" aria-hidden="true"></div>
              <div>
                <strong>Scanning ${escapeHtml(interfaceName)}</strong>
                <p class="text-muted mb-0">Looking for nearby wireless networks.</p>
              </div>
            </div>
          </div>
        `);
      },
      success: function (response) {
        const networks = Array.isArray(response.wlans) ? response.wlans : [];
        if (networks.length === 0) {
          resultDiv.html(`
            <div class="alert alert-info mt-3" role="alert">
              No wireless networks were found on ${escapeHtml(interfaceName)}. Try moving closer to an access point or scanning again.
            </div>
          `);
          return;
        }
        resultDiv.html(renderNetworks(interfaceName, networks));
      },
      error: function (xhr) {
        const message = xhr.responseJSON?.message || 'Error occurred during network scan';
        resultDiv.html(`<div class="alert alert-danger mt-3" role="alert">${escapeHtml(message)}</div>`);
      },
      complete: function () {
        button.prop('disabled', false).text('Scan for Networks');
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
});
