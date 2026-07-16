$(document).ready(function () {
  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  const bluetoothActions = [
    { action: 'info', label: 'Info', style: 'outline-secondary', icon: 'circle-info', description: 'Show cached details and controller state for this Bluetooth device.' },
    { action: 'connect', label: 'Connect', style: 'outline-primary', icon: 'link', description: 'Ask this host adapter to connect to the selected device.' },
    { action: 'disconnect', label: 'Disconnect', style: 'outline-warning', icon: 'link-slash', description: 'Disconnect this device from this host adapter only.' },
    { action: 'pair', label: 'Pair', style: 'outline-primary', icon: 'handshake', description: 'Start pairing this device with this host adapter.' },
    { action: 'trust', label: 'Trust', style: 'outline-success', icon: 'shield-halved', description: 'Mark this device as trusted for future local connections.' },
    { action: 'untrust', label: 'Untrust', style: 'outline-secondary', icon: 'shield', description: 'Remove trusted status for this device on this host.' },
    { action: 'block', label: 'Block', style: 'outline-danger', icon: 'ban', description: 'Block local connections from this Bluetooth device.' },
    { action: 'unblock', label: 'Unblock', style: 'outline-success', icon: 'check', description: 'Allow local connections from this Bluetooth device again.' },
    { action: 'remove', label: 'Remove', style: 'outline-danger', icon: 'trash', description: 'Remove the device from this host adapter pairing cache.' }
  ];


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

  function renderDevice(device, actionCapability) {
    const name = device.name || 'Unknown';
    const address = device.address || '';
    const manufacturer = device.manufacturer || 'Unknown manufacturer';
    const detailUrl = address ? `/clients/${encodeURIComponent(address)}` : '';
    const actionsAvailable = Boolean(actionCapability?.available);
    const disabled = actionsAvailable ? '' : 'disabled';
    const actionButtons = bluetoothActions.map(function (item) {
      const tooltip = actionsAvailable ? item.description : `${item.description} ${actionCapability?.message || 'Bluetooth actions are unavailable on this host.'}`;
      return `<span class="bluetooth-action-tooltip" data-toggle="tooltip" data-placement="top" title="${escapeHtml(tooltip)}"><button type="button" class="btn btn-${item.style} btn-sm bluetooth-action" data-action="${escapeHtml(item.action)}" data-address="${escapeHtml(address)}" aria-label="${escapeHtml(item.label + ': ' + tooltip)}" ${disabled}><i class="fa-solid fa-${item.icon}"></i> ${escapeHtml(item.label)}</button></span>`;
    }).join('');

    return `
      <article class="wireless-network-card bluetooth-device-card">
        <div class="wireless-network-main">
          <div>
            <h3 class="wireless-network-ssid mb-1">${detailUrl ? `<a href="${escapeHtml(detailUrl)}">${escapeHtml(name)}</a>` : escapeHtml(name)}</h3>
            <p class="wireless-network-meta mb-0"><i class="fa-brands fa-bluetooth-b"></i> ${escapeHtml(address || 'Unknown address')}</p>
            <p class="wireless-network-meta mb-0"><i class="fa-solid fa-industry"></i> ${escapeHtml(manufacturer)}</p>
          </div>
          <span class="badge badge-info">Bluetooth</span>
        </div>
        <div class="bluetooth-action-grid mt-3">${detailUrl ? `<a class="btn btn-outline-info btn-sm" href="${escapeHtml(detailUrl)}"><i class="fa-solid fa-up-right-from-square"></i> View device</a>` : ''}${actionButtons}</div>
        <pre class="bluetooth-action-output d-none mt-3 mb-0"></pre>
      </article>
    `;
  }

  $(document).on("click", "button#bluetooth-scan", function () {
    const button = $(this);
    const interfaceName = button.val();
    const result = $("#bluetooth-devices");
    button.prop('disabled', true).text('Scanning...');
    result.html(`<div class="wireless-scan-state card shadow-sm"><div class="card-body d-flex align-items-center"><div class="spinner-border text-primary mr-3" role="status" aria-hidden="true"></div><div><strong>Scanning ${escapeHtml(interfaceName)}</strong><p class="text-muted mb-0">Running this Bluetooth scan in the background.</p></div></div></div>`);

    function renderScanResult(response) {
      const devices = Array.isArray(response.devices) ? response.devices : [];
      const actionCapability = response.action_capability || { available: false, message: 'Bluetooth action capability is unknown.' };
      let btDiv = `<section class="wireless-results card shadow-sm"><div class="card-body"><div class="wireless-results-header"><div><p class="interface-kicker mb-1">Bluetooth Scan</p><h2 class="interface-section-title mb-0">Bluetooth Devices</h2></div><span class="badge badge-primary">${devices.length} found</span></div><div class="alert alert-secondary small" role="alert"><strong>Training note:</strong> actions operate through this adapter against devices you own or are authorized to test. Bluetooth does not provide a legitimate generic way to force a third-party device to disconnect from another third-party device.</div>`;
      if (!actionCapability.available) {
        btDiv += `<div class="alert alert-warning small" role="alert"><div><strong>Bluetooth actions unavailable:</strong> ${escapeHtml(actionCapability.message || 'Install bluetoothctl to enable actions.')}</div><a class="btn btn-sm btn-outline-primary mt-2" href="/capabilities#host-dependencies">View install help</a></div>`;
      }
      if (devices.length === 0) {
        btDiv += `<div class="alert alert-info mb-0" role="alert">No Bluetooth devices found. Make sure nearby devices are discoverable; paired classic devices may appear even when not actively advertising.</div>`;
      } else {
        btDiv += `<div class="wireless-network-grid">${devices.map(function (device) { return renderDevice(device, actionCapability); }).join('')}</div>`;
      }
      btDiv += `</div></section>`;
      result.html(btDiv);
      result.find('[data-toggle="tooltip"]').tooltip({ container: 'body' });
    }

    $.ajax({
      url: "/scan-jobs",
      type: "POST",
      data: { scanType: 'bluetooth', selectedInterface: interfaceName },
      success: function (response) {
        pollScanJob(response.job.id, function (scanResult) {
          button.prop('disabled', false).text('Scan for Devices');
          renderScanResult(scanResult);
        }, function (message) {
          button.prop('disabled', false).text('Scan for Devices');
          result.html(`<div class="alert alert-danger mt-3" role="alert">${escapeHtml(message)} <a href="/capabilities#host-dependencies" class="alert-link">Check Bluetooth requirements</a>.</div>`);
        });
      },
      error: function (xhr) {
        button.prop('disabled', false).text('Scan for Devices');
        const message = xhr.responseJSON?.message || 'Unable to start Bluetooth scan';
        result.html(`<div class="alert alert-danger mt-3" role="alert">${escapeHtml(message)} <a href="/capabilities#host-dependencies" class="alert-link">Check Bluetooth requirements</a>.</div>`);
      }
    });
  });

  $(document).on('click', '.bluetooth-action', function () {
    const button = $(this);
    const card = button.closest('.bluetooth-device-card');
    const output = card.find('.bluetooth-action-output');
    $.ajax({
      url: '/bluetooth-action',
      type: 'POST',
      data: { action: button.data('action'), address: button.data('address') },
      beforeSend: function () {
        button.prop('disabled', true);
        output.removeClass('d-none text-danger text-success').addClass('text-muted').text('Running action...');
      },
      success: function (response) {
        output.removeClass('text-muted text-danger').addClass('text-success').text(response.output || response.message || 'Action completed.');
      },
      error: function (xhr) {
        const message = xhr.responseJSON?.message || 'Bluetooth action failed';
        output.removeClass('text-muted text-success').addClass('text-danger').text(message);
      },
      complete: function () {
        button.prop('disabled', false);
      }
    });
  });
});
